"""
diagram_from_request.py

Phase 3 of TEST_REQUEST_PLAN.md: generate the process diagram from a test
request's topology — one click, nothing re-typed.

Strategy (per the user's verdict that algorithmic layout "doesn't understand
refrigeration positioning"): the templates ARE the user's own hand-built
diagrams, ingested from Lab viewer/2.0/Config into templates/tmpl_*.json
(see templates/index.json).  Generation = nearest-match template → patch
circuits / condenser type → hand back.  The output is their layout by
construction.  Module-count surgery on the 3-module reference happens only
when no template with the right module count exists; the procedural builders
are a last-resort fallback for system types with no template at all.

The returned model carries a transient '_generated_from' key naming the
template file actually used — callers pop it for display/logging before
loading the model into the session.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Dict, List

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

# Which circuit labels survive for a given module count (house convention:
# 2-module = Left + Right, per CLAUDE.md column configs)
_LABELS_FOR_COUNT = {1: ['Left'], 2: ['Left', 'Right'],
                     3: ['Left', 'Center', 'Right']}


def _load_template(name: str) -> dict:
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


_LABEL_NORMALIZE = {'lh': 'Left', 'left': 'Left',
                    'ctr': 'Center', 'center': 'Center',
                    'rh': 'Right', 'right': 'Right'}


def _comp_label(comp: dict):
    """Normalized circuit label — the hand-built diagrams mix conventions
    ('LH' on some components, 'Left' on others)."""
    lbl = (comp.get('properties') or {}).get('circuit_label')
    if lbl in (None, '', 'None'):
        return None
    return _LABEL_NORMALIZE.get(str(lbl).strip().lower(), lbl)


def _assign_unlabeled_to_modules(model: dict) -> Dict[str, str]:
    """Per-module items without a circuit_label (e.g. AirSensorArray) are
    assigned to the nearest evaporator by x distance.  Only types that occur
    once per module are assigned; shared items (Compressor, main Junction,
    shared Sensors) are left alone."""
    evap_x = {}
    for cid, c in model['components'].items():
        if c.get('type') == 'Evaporator' and _comp_label(c):
            evap_x[_comp_label(c)] = (c.get('position') or [0, 0])[0]
    if not evap_x:
        return {}

    # Count occurrences per type among unlabeled components
    by_type: Dict[str, List[str]] = {}
    for cid, c in model['components'].items():
        if _comp_label(c) is None:
            by_type.setdefault(c.get('type'), []).append(cid)

    n_modules = len(evap_x)
    assigned = {}
    for ctype, ids in by_type.items():
        if len(ids) != n_modules or ctype in ('Compressor', 'Condenser',
                                              'Junction', 'Sensor'):
            continue  # not a per-module pattern
        for cid in ids:
            cx = (model['components'][cid].get('position') or [0, 0])[0]
            label = min(evap_x, key=lambda lb: abs(evap_x[lb] - cx))
            assigned[cid] = label
    return assigned


def _best_shared_3module_file() -> str:
    """The richest 3-module shared template in the library — the reduction
    source.  (User verdict: the 2.0/Config diagrams are the good ones.)"""
    best, best_n = None, -1
    for meta in _template_index().values():
        if meta.get('system_type') == 'shared' and meta.get('modules') == 3 \
                and meta.get('components', 0) > best_n:
            best, best_n = meta['file'], meta.get('components', 0)
    return best or 'tmpl_ID5SL12.json'


def build_shared_from_template(topology: dict) -> dict:
    """Generate a shared-compressor diagram from the user's reference layout."""
    src_file = _best_shared_3module_file()
    model = copy.deepcopy(_load_template(src_file))
    modules = max(1, min(3, int(topology.get('modules', 3) or 3)))
    keep = set(_LABELS_FOR_COUNT[modules])

    extra_labels = _assign_unlabeled_to_modules(model)

    # ── 1. Remove components of dropped modules ─────────────────────────────
    drop_ids = set()
    for cid, c in model['components'].items():
        lbl = _comp_label(c) or extra_labels.get(cid)
        if lbl and lbl not in keep:
            drop_ids.add(cid)
    for cid in drop_ids:
        model['components'].pop(cid, None)

    # ── 2. Remove pipes touching dropped components ─────────────────────────
    model['pipes'] = {pid: p for pid, p in model['pipes'].items()
                      if p.get('start_component_id') not in drop_ids
                      and p.get('end_component_id') not in drop_ids}

    # ── 3. Close the layout gap left by removed modules ────────────────────
    # Shift everything right of the removed band leftward so the diagram
    # stays compact (only needed when 'Center' was removed but 'Right' kept).
    if modules == 2:
        tmpl = _load_template(src_file)
        ev = {_comp_label(c): c['position'][0]
              for c in tmpl['components'].values()
              if c.get('type') == 'Evaporator' and _comp_label(c)}
        if 'Center' in ev and 'Right' in ev and 'Left' in ev:
            dx = ev['Right'] - ev['Center']
            boundary = (ev['Center'] + ev['Left']) / 2 + (ev['Center'] - ev['Left']) / 2
            shifted = set()
            for cid, c in model['components'].items():
                pos = c.get('position') or [0, 0]
                if pos[0] > boundary:
                    c['position'] = [pos[0] - dx, pos[1]]
                    shifted.add(cid)
            for pid, p in model['pipes'].items():
                s_in = p.get('start_component_id') in shifted
                e_in = p.get('end_component_id') in shifted
                route = p.get('route') or []
                if s_in and e_in:
                    p['route'] = [[v[0] - dx, v[1]] for v in route]
                elif s_in or e_in:
                    p.pop('route', None)      # re-auto-route across the seam
                    p.pop('waypoints', None)

    # ── 4. Patch per-request parameters ─────────────────────────────────────
    circuits = int(topology.get('circuits_per_coil', 6) or 6)
    for c in model['components'].values():
        props = c.setdefault('properties', {})
        if c.get('type') == 'Evaporator':
            props['circuits'] = circuits
            props['fan_sensor_count'] = max(1, min(circuits,
                                                   props.get('fan_sensor_count', circuits)))
        if c.get('type') == 'Condenser':
            props['condenser_type'] = ('Water Cooled'
                                       if str(topology.get('condenser_cooling',
                                                           'Water')).lower().startswith('w')
                                       else 'Air Cooled')

    # ── 5. Fresh start for mappings ─────────────────────────────────────────
    model['sensor_roles'] = {}
    model['custom_sensors'] = {}
    model['role_dot_labels'] = {}
    model['_generated_from'] = f"{src_file} (reduced to {modules} module(s))"
    return model


def _template_index() -> dict:
    path = os.path.join(TEMPLATES_DIR, 'index.json')
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _pick_template(topo: dict):
    """Nearest-match over the library of the user's hand-built diagrams.
    Scoring: same system type is mandatory; then closest module count;
    then closest circuits-per-coil; then richer template wins."""
    system = (topo.get('system_type') or 'shared').lower()
    want_mod = int(topo.get('modules', 1) or 1)
    want_circ = int(topo.get('circuits_per_coil', 6) or 6)
    best, best_key = None, None
    for name, meta in _template_index().items():
        if meta.get('system_type') != system:
            continue
        key = (abs(meta.get('modules', 0) - want_mod),
               abs(meta.get('circuits_per_coil', 6) - want_circ),
               -meta.get('components', 0))
        if best_key is None or key < best_key:
            best, best_key = meta, key
    return best


def _patch_params(model: dict, topo: dict) -> None:
    """Apply the request's per-coil circuits and condenser cooling type."""
    circuits = int(topo.get('circuits_per_coil', 6) or 6)
    for c in model['components'].values():
        props = c.setdefault('properties', {})
        if c.get('type') == 'Evaporator':
            props['circuits'] = circuits
        if c.get('type') == 'Condenser':
            props['condenser_type'] = ('Water Cooled'
                                       if str(topo.get('condenser_cooling', 'Water'))
                                       .lower().startswith('w')
                                       else 'Air Cooled')
    model['sensor_roles'] = {}
    model['custom_sensors'] = {}
    model['role_dot_labels'] = {}
    


def build_diagram_for_request(request: dict) -> dict:
    """Entry point: nearest hand-built template, patched to the request.

    The layouts are the user's own finished diagrams (ingested from
    Lab viewer/2.0/Config + the ID6SU12WE session), so generated output is
    'their layout' by construction.  Module-count surgery is used only when
    no template with the right module count exists.
    """
    topo = request.get('topology', {}) or {}
    want_mod = max(1, int(topo.get('modules', 1) or 1))

    meta = _pick_template(topo)
    if meta is None:
        # No template for this system type at all — old procedural fallback
        from diagram_templates import build_diagram_from_config
        print("[DIAGRAM GEN] No template for system type "
              f"{topo.get('system_type')!r} — procedural fallback")
        model = build_diagram_from_config({
            'case_type': 'modular_self_contained', 'case_size': '12 ft',
            'circuits_per_module': int(topo.get('circuits_per_coil', 6) or 6),
            'condenser_type': 'Water Cooled', 'expansion_type': 'TXV',
            'include_filter_dryer': False, 'include_hot_gas_bypass': False,
            'air_curtain_type': 'single', 'shelf_rows': 4,
        })
        model['_generated_from'] = 'procedural fallback (no template)'
        return model

    if meta.get('modules') == want_mod or meta.get('system_type') == 'cassette':
        model = copy.deepcopy(_load_template(meta['file']))
        _patch_params(model, topo)
        model['_generated_from'] = (f"{meta['file']} "
                                    f"(source {meta.get('source')})")
        print(f"[DIAGRAM GEN] Used template {meta['file']} "
              f"(exact module match, source {meta.get('source')})")
        return model

    # Module-count mismatch on a shared system: surgical reduction of the
    # 3-module reference (only path that needs surgery)
    print(f"[DIAGRAM GEN] No exact template for {want_mod} module(s) — "
          f"reducing the 3-module reference")
    return build_shared_from_template(topo)

def build_bare_minimum_diagram(request: dict) -> dict:
    """Build a clean bare-minimum process diagram.

    Layout: Compressor → Condenser → [per module: TXV → Evaporator (N circuits)]
            → per-module suction-header Junction → [multi-module Junction] → loopback

    No Distributor, Header, SplitterManifold, or CombinerManifold components.
    Circuit fan-out (TXV → evap inlets) uses N pre-routed pipes from the single
    TXV.outlet.  Circuit fan-in (evap outlets → suction line) uses a thin Junction
    (snapped_mode=Yes: inlets top, outlet bottom-center) whose port spacing matches
    the Evaporator's dynamic_ports formula so all pipes are straight-vertical.
    """
    import math

    def _snap(val):
        return math.floor(val / 20 + 0.5) * 20

    def _circuit_xs(count, width=240, spacing=20):
        """Local x-positions of circuit ports. No snap — exact even spacing."""
        span = (count - 1) * spacing if count > 1 else 0
        return [(width / 2 + (i - 1) * spacing - span / 2)
                for i in range(1, count + 1)]

    topo = request.get('topology', {}) or {}
    num_modules = max(1, min(3, int(topo.get('modules', 1) or 1)))
    num_circuits = max(1, int(topo.get('circuits_per_coil', 6) or 6))
    condenser_type = ('Water Cooled'
                      if str(topo.get('condenser_cooling', 'Water')).lower().startswith('w')
                      else 'Air Cooled')

    CENTER_X   = 600
    MOD_SPACING = 300
    COMP_W, COMP_H = 120, 60
    COND_W, COND_H = 120, 60
    TXV_W,  TXV_H  = 120, 60
    EVAP_W, EVAP_H = 240, 80
    SUCT_H = 15     # suction-header Junction height

    Y_COMP  = 100
    Y_COND  = 200
    Y_TXV   = 330
    Y_EVAP  = 430
    CKT_OUT_Y = Y_EVAP + EVAP_H + 20     # 530
    Y_MULTI   = Y_EVAP + EVAP_H + 85     # 595 — multi-module collector (n>1)

    BRANCH_Y  = Y_COND + COND_H + 30     # 290 — fan-out level below condenser
    CKT_IN_Y  = Y_TXV  + TXV_H  + 20    # 410 — fan-out level below TXV

    if num_modules == 1:
        mod_xs  = [CENTER_X]
        mod_lbs = ['']
    elif num_modules == 2:
        mod_xs  = [CENTER_X - MOD_SPACING // 2, CENTER_X + MOD_SPACING // 2]
        mod_lbs = ['Left', 'Right']
    else:
        mod_xs  = [CENTER_X - MOD_SPACING, CENTER_X, CENTER_X + MOD_SPACING]
        mod_lbs = ['Left', 'Center', 'Right']

    LEFTMOST = mod_xs[0] - 200

    components: dict = {}
    pipes: dict = {}

    # ── Compressor ────────────────────────────────────────────────────────
    components['comp'] = {
        'type': 'Compressor',
        'position': [CENTER_X - COMP_W // 2, Y_COMP],
        'size': {'width': COMP_W, 'height': COMP_H},
        'properties': {'circuit_label': 'None'},
    }

    # ── Condenser ─────────────────────────────────────────────────────────
    components['cond'] = {
        'type': 'Condenser',
        'position': [CENTER_X - COND_W // 2, Y_COND],
        'size': {'width': COND_W, 'height': COND_H},
        'properties': {'circuit_label': 'None', 'condenser_type': condenser_type},
    }

    pipes['p_comp_cond'] = {
        'start_component_id': 'comp', 'start_port': 'outlet',
        'end_component_id':   'cond', 'end_port':   'inlet',
        'route': [[CENTER_X, Y_COMP + COMP_H], [CENTER_X, Y_COND]],
    }

    cond_out = [CENTER_X, Y_COND + COND_H]

    # Port spacing that makes circuits span the full evaporator width (edge to edge).
    # For 1 circuit: centered (spacing irrelevant). For N>1: EVAP_W/(N-1).
    ckt_spacing = (EVAP_W / (num_circuits - 1)) if num_circuits > 1 else EVAP_W
    ckt_local_xs = _circuit_xs(num_circuits, EVAP_W, spacing=ckt_spacing)

    # ── Multi-module collector — created before module loop so circuit pipes can reference it ──
    if num_modules > 1:
        multi_w      = (num_modules - 1) * MOD_SPACING + EVAP_W
        multi_left   = CENTER_X - multi_w // 2
        Y_MULTI      = CKT_OUT_Y + 35          # matches test_loop MERGE_Y spacing
        multi_out_lx = _snap(multi_w / 2)
        multi_out_sx = multi_left + multi_out_lx
        lb_y         = Y_MULTI                  # height=1 so inlet==outlet y-pos

        # Single inlet at CENTER_X — all module pipes share it and include horizontal leg.
        components['multi_suct'] = {
            'type': 'Junction',
            'position': [multi_left, Y_MULTI],
            'size': {'width': multi_w, 'height': 1},
            'properties': {
                'inlet_count':  1,
                'outlet_count': 1,
                'port_spacing': 20,
                'snapped_mode': 'Yes',
                'circuit_label': 'None',
            },
        }

    # ── Per-module components ──────────────────────────────────────────────
    for mi, (mod_x, lb) in enumerate(zip(mod_xs, mod_lbs), 1):
        cl  = lb if lb else 'None'
        pfx = lb.lower() + '_' if lb else ''

        txv_id  = f'{pfx}txv'
        evap_id = f'{pfx}evap'
        evap_left = mod_x - EVAP_W // 2

        # TXV
        components[txv_id] = {
            'type': 'TXV',
            'position': [mod_x - TXV_W // 2, Y_TXV],
            'size': {'width': TXV_W, 'height': TXV_H},
            'properties': {'circuit_label': cl},
        }

        # Evaporator (N inlets top / N outlets bottom via dynamic_ports)
        components[evap_id] = {
            'type': 'Evaporator',
            'position': [evap_left, Y_EVAP],
            'size': {'width': EVAP_W, 'height': EVAP_H},
            'properties': {
                'circuits':     num_circuits,
                'port_spacing': ckt_spacing,
                'circuit_label': cl,
            },
        }

        # Single-module only: invisible suction junction that feeds the loopback pipe.
        if num_modules == 1:
            suct_id = 'suct'
            components[suct_id] = {
                'type': 'Junction',
                'position': [mod_x - 20, CKT_OUT_Y],
                'size': {'width': 40, 'height': 1},
                'properties': {
                    'inlet_count':  1,
                    'outlet_count': 1,
                    'port_spacing': 20,
                    'snapped_mode': 'Yes',
                    'circuit_label': cl,
                },
            }

        # cond → TXV: branch at BRANCH_Y then drop to module x
        pipes[f'p_cond_{txv_id}'] = {
            'start_component_id': 'cond',   'start_port': 'outlet',
            'end_component_id':   txv_id,   'end_port':   'inlet',
            'route': [cond_out,
                      [CENTER_X, BRANCH_Y],
                      [mod_x,    BRANCH_Y],
                      [mod_x,    Y_TXV]],
        }

        txv_out = [mod_x, Y_TXV + TXV_H]

        # TXV → each evap circuit inlet: fan-out at CKT_IN_Y
        for i, lx in enumerate(ckt_local_xs, 1):
            cx = int(evap_left + lx)
            pipes[f'p_{txv_id}_ckt{i}'] = {
                'start_component_id': txv_id,  'start_port': 'outlet',
                'end_component_id':   evap_id, 'end_port':   f'inlet_circuit_{i}',
                'route': [txv_out,
                          [mod_x, CKT_IN_Y],
                          [cx,    CKT_IN_Y],
                          [cx,    Y_EVAP]],
            }

        # Evap circuit outlet → collection point (test_loop fan-in pattern):
        #   down to CKT_OUT_Y → horizontal to mod_x → [down to multi junction for n>1]
        if num_modules == 1:
            # All circuits share the single suction junction inlet_1
            for i, lx in enumerate(ckt_local_xs, 1):
                cx = int(evap_left + lx)
                pipes[f'p_ckt{i}_{evap_id}_suct'] = {
                    'start_component_id': evap_id, 'start_port': f'outlet_circuit_{i}',
                    'end_component_id':   suct_id, 'end_port':   'inlet_1',
                    'route': [[cx, Y_EVAP + EVAP_H], [cx, CKT_OUT_Y], [mod_x, CKT_OUT_Y]],
                }
        else:
            # Per-module collector: 1-inlet/1-outlet (same pattern as single-module
            # suct which works). All circuits share inlet_1 → horizontal bar renders
            # from the explicit route waypoints. Then one pipe to multi_suct.
            mod_suct_id = f'{pfx}mod_suct'
            components[mod_suct_id] = {
                'type': 'Junction',
                'position': [mod_x - 20, CKT_OUT_Y],
                'size': {'width': 40, 'height': 1},
                'properties': {
                    'inlet_count':  1,
                    'outlet_count': 1,
                    'port_spacing': 20,
                    'snapped_mode': 'Yes',
                    'circuit_label': cl,
                },
            }
            for i, lx in enumerate(ckt_local_xs, 1):
                cx = int(evap_left + lx)
                pipes[f'p_ckt{i}_{evap_id}_modsct'] = {
                    'start_component_id': evap_id,     'start_port': f'outlet_circuit_{i}',
                    'end_component_id':   mod_suct_id, 'end_port':   'inlet_1',
                    'route': [[cx, Y_EVAP + EVAP_H], [cx, CKT_OUT_Y], [mod_x, CKT_OUT_Y]],
                }
            # All modules share multi_suct.inlet_1 at (CENTER_X, Y_MULTI).
            # Route: down to Y_MULTI then horizontal to CENTER_X (matches test_loop branch).
            pipes[f'p_{mod_suct_id}_multi'] = {
                'start_component_id': mod_suct_id,  'start_port': 'outlet_1',
                'end_component_id':   'multi_suct', 'end_port':   'inlet_1',
                'route': [[mod_x, CKT_OUT_Y], [mod_x, Y_MULTI], [CENTER_X, Y_MULTI]],
            }

    # ── Loopback ──────────────────────────────────────────────────────────
    if num_modules == 1:
        sy = CKT_OUT_Y
        pipes['p_loopback'] = {
            'start_component_id': 'suct', 'start_port': 'outlet_1',
            'end_component_id':   'comp', 'end_port':   'inlet',
            'route': [[CENTER_X, sy],
                      [CENTER_X, sy + 30],
                      [LEFTMOST, sy + 30],
                      [LEFTMOST, Y_COMP - 30],
                      [CENTER_X, Y_COMP - 30],
                      [CENTER_X, Y_COMP]],
        }
    else:
        pipes['p_loopback'] = {
            'start_component_id': 'multi_suct', 'start_port': 'outlet_1',
            'end_component_id':   'comp',        'end_port':   'inlet',
            'route': [[multi_out_sx, lb_y],
                      [multi_out_sx, lb_y + 30],
                      [LEFTMOST,     lb_y + 30],
                      [LEFTMOST,     Y_COMP - 30],
                      [CENTER_X,     Y_COMP - 30],
                      [CENTER_X,     Y_COMP]],
        }

    for p in pipes.values():
        p['_simple_mode'] = True
        p['route_locked'] = True
        p['_raw_route']   = True   # bypass _pin_end, _sanitize, port_inset trim

    for c in components.values():
        c['_simple_mode'] = True

    return {
        'components': components,
        'pipes':      pipes,
        'sensor_roles':    {},
        'custom_sensors':  {},
        'role_dot_labels': {},
        '_simple_mode': True,
        '_generated_from': (f'bare_minimum ({num_modules} module(s), '
                            f'{num_circuits} circuits/module)'),
    }
