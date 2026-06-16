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
        _ensure_canonical_sensor_boxes(model, topo)
        model['_generated_from'] = (f"{meta['file']} "
                                    f"(source {meta.get('source')})")
        print(f"[DIAGRAM GEN] Used template {meta['file']} "
              f"(exact module match, source {meta.get('source')})")
        return model

    # Module-count mismatch on a shared system: surgical reduction of the
    # 3-module reference (only path that needs surgery)
    print(f"[DIAGRAM GEN] No exact template for {want_mod} module(s) — "
          f"reducing the 3-module reference")
    model = build_shared_from_template(topo)
    _ensure_canonical_sensor_boxes(model, topo)
    return model


def _ensure_canonical_sensor_boxes(model: dict, topo: dict) -> None:
    """Auto-add two canonical sensor boxes (Ambient & Walls, Electrical & System)
    so off-diagram instruments have a home on every generated diagram.

    The sensors are added with canonical IDs as their sensor ids — no UUIDs —
    so role_keys are deterministic and the alias DB lights up immediately.

    Safe to call repeatedly: if a box with the same id already exists, leaves
    it alone.
    """
    from sensor_canonical import AMBIENT_WALLS_SLOTS, electrical_system_slots

    boxes = model.setdefault('sensor_boxes', {})

    n_compressors = sum(1 for c in (model.get('components') or {}).values()
                        if c.get('type') == 'Compressor')

    if 'box_ambient_walls' not in boxes:
        boxes['box_ambient_walls'] = {
            'position': [-1200, 100],
            'title': 'Ambient & Walls',
            'sensors': [{'id': cid, 'label': human}
                        for cid, human in AMBIENT_WALLS_SLOTS],
        }
    if 'box_electrical_system' not in boxes:
        boxes['box_electrical_system'] = {
            'position': [200, 100],
            'title': 'Electrical & System',
            'sensors': [{'id': cid, 'label': human}
                        for cid, human in electrical_system_slots(n_compressors)],
        }

def build_bare_minimum_diagram(request: dict) -> dict:
    """Build a clean process diagram matching test_loop.py exactly.

    Supports: modular (1-3 modules), door (1-5 doors),
              cassette_mt (independent loop per cassette),
              cassette_lt (independent loop with HGBV/HGS/LLS per cassette).
    """
    topo = request.get('topology', {}) or {}
    mode       = topo.get('mode', 'modular')
    num_doors  = max(1, min(5, int(topo.get('num_doors', 3) or 3)))
    num_raw    = max(1, min(5, int(topo.get('num_cassettes', 1) or 1)))  # raw 1-5 count
    case_type  = topo.get('case_type', 'Doored')
    shelf_rows = max(3, min(8, int(topo.get('shelf_rows', 5) or 5)))
    num_circuits = max(1, int(topo.get('circuits_per_coil', 6) or 6))
    condenser_type = ('Water Cooled'
                      if str(topo.get('condenser_cooling', 'Water')).lower().startswith('w')
                      else 'Air Cooled')
    is_cassette = mode.startswith('cassette')

    CENTER_X    = 600
    MOD_SPACING = 300
    COMP_W, COMP_H = 120, 60
    COND_W, COND_H = 120, 60
    TXV_W, TXV_H   = 120, 60
    EVAP_W  = 240
    EVAP_H  = 80
    DIST_H  = 40
    HEAD_H  = 40

    Y_COMP     = 100
    Y_COND     = 190
    Y_TXV      = 350
    Y_EVAP     = 495
    BRANCH_Y   = Y_COND + COND_H + 30    # 280
    DIST_Y     = Y_EVAP - DIST_H - 15    # 440
    HEAD_Y     = Y_EVAP + EVAP_H         # 575
    HEAD_OUT_Y = HEAD_Y + HEAD_H          # 615
    MERGE_Y    = Y_EVAP + EVAP_H + 85    # 660

    # ── Module layout (modular mode) ─────────────────────────────────────
    num_modules = max(1, min(3, int(topo.get('modules', 1) or 1)))
    if mode == 'modular':
        if num_modules == 1:
            mod_xs  = [CENTER_X];  mod_lbs = ['']
        elif num_modules == 2:
            mod_xs  = [CENTER_X - MOD_SPACING // 2, CENTER_X + MOD_SPACING // 2]
            mod_lbs = ['Left', 'Right']
        else:
            mod_xs  = [CENTER_X - MOD_SPACING, CENTER_X, CENTER_X + MOD_SPACING]
            mod_lbs = ['Left', 'Center', 'Right']
    else:
        mod_xs = [CENTER_X]; mod_lbs = ['']

    # ── Case-width geometry (matching test_loop.py) ───────────────────────
    if mode == 'modular':
        total_w    = num_modules * EVAP_W + (num_modules - 1) * (MOD_SPACING - EVAP_W)
        left_edge  = mod_xs[0] - EVAP_W / 2
        right_edge = mod_xs[-1] + EVAP_W / 2
        combined_w = total_w
        count = num_modules
    else:  # door or cassette
        count = num_doors if mode == 'door' else num_raw
        total_w    = 240 * count
        left_edge  = CENTER_X - total_w / 2
        right_edge = CENTER_X + total_w / 2
        combined_w = total_w

    process_x = left_edge - 200
    process_w = combined_w + 300
    LEFTMOST  = left_edge - 100

    components: dict = {}
    pipes:      dict = {}

    # ══════════════════════════════════════════════════════════════════════
    #  NON-CASSETTE: Modular / Door — one shared compressor + condenser
    # ══════════════════════════════════════════════════════════════════════
    if not is_cassette:
        ckt_spacing = (EVAP_W / (num_circuits - 1)) if num_circuits > 1 else EVAP_W

        # Shared compressor
        components['comp'] = {
            'type': 'Compressor',
            'position': [CENTER_X - COMP_W // 2, Y_COMP],
            'size': {'width': COMP_W, 'height': COMP_H},
            'properties': {'circuit_label': 'None'},
        }
        # Shared condenser
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
        cond_out_y = Y_COND + COND_H

        # Multi-module suction junction
        if num_modules > 1:
            multi_w    = (num_modules - 1) * MOD_SPACING + EVAP_W
            multi_left = CENTER_X - multi_w // 2
            components['multi_suct'] = {
                'type': 'Junction',
                'position': [multi_left, MERGE_Y],
                'size': {'width': multi_w, 'height': 1},
                'properties': {
                    'inlet_count': 1, 'outlet_count': 1,
                    'port_spacing': 20, 'snapped_mode': 'Yes',
                    'circuit_label': 'None',
                },
            }

        for mod_x, lb in zip(mod_xs, mod_lbs):
            cl    = lb if lb else 'None'
            pfx   = lb.lower().replace(' ', '_') + '_' if lb else ''
            el    = mod_x - EVAP_W // 2
            txv_id  = f'{pfx}txv';  dist_id = f'{pfx}dist'
            evap_id = f'{pfx}evap'; head_id  = f'{pfx}head'

            components[txv_id] = {
                'type': 'TXV',
                'position': [mod_x - TXV_W // 2, Y_TXV],
                'size': {'width': TXV_W, 'height': TXV_H},
                'properties': {'circuit_label': cl},
            }
            components[dist_id] = {
                'type': 'SplitterManifold',
                'position': [el, DIST_Y],
                'size': {'width': EVAP_W, 'height': DIST_H},
                'properties': {'circuits': num_circuits, 'circuit_label': cl},
            }
            components[evap_id] = {
                'type': 'Evaporator',
                'position': [el, Y_EVAP],
                'size': {'width': EVAP_W, 'height': EVAP_H},
                'properties': {
                    'circuits': num_circuits,
                    'port_spacing': ckt_spacing,
                    'circuit_label': cl,
                },
            }
            components[head_id] = {
                'type': 'CombinerManifold',
                'position': [el, HEAD_Y],
                'size': {'width': EVAP_W, 'height': HEAD_H},
                'properties': {'circuits': num_circuits, 'circuit_label': cl},
            }
            # cond → TXV
            pipes[f'p_cond_{txv_id}'] = {
                'start_component_id': 'cond', 'start_port': 'outlet',
                'end_component_id':   txv_id, 'end_port':   'inlet',
                'route': [[CENTER_X, cond_out_y],
                          [CENTER_X, BRANCH_Y], [mod_x, BRANCH_Y], [mod_x, Y_TXV]],
            }
            # TXV → distributor
            txv_out_y = Y_TXV + TXV_H
            if txv_out_y < DIST_Y:
                pipes[f'p_{txv_id}_{dist_id}'] = {
                    'start_component_id': txv_id,  'start_port': 'outlet',
                    'end_component_id':   dist_id, 'end_port':   'inlet',
                    'route': [[mod_x, txv_out_y], [mod_x, DIST_Y]],
                }
            # header → suction collector
            if num_modules == 1:
                pipes['p_loopback'] = {
                    'start_component_id': head_id, 'start_port': 'outlet',
                    'end_component_id':   'comp',  'end_port':   'inlet',
                    'route': [[mod_x,    HEAD_OUT_Y],
                              [mod_x,    MERGE_Y],
                              [LEFTMOST, MERGE_Y],
                              [LEFTMOST, Y_COMP - 30],
                              [CENTER_X, Y_COMP - 30],
                              [CENTER_X, Y_COMP]],
                }
            else:
                pipes[f'p_{head_id}_multi'] = {
                    'start_component_id': head_id,       'start_port': 'outlet',
                    'end_component_id':   'multi_suct',  'end_port':   'inlet_1',
                    'route': [[mod_x, HEAD_OUT_Y], [mod_x, MERGE_Y], [CENTER_X, MERGE_Y]],
                }

        if num_modules > 1:
            pipes['p_loopback'] = {
                'start_component_id': 'multi_suct', 'start_port': 'outlet_1',
                'end_component_id':   'comp',        'end_port':   'inlet',
                'route': [[CENTER_X, MERGE_Y],
                          [CENTER_X, MERGE_Y + 30],
                          [LEFTMOST, MERGE_Y + 30],
                          [LEFTMOST, Y_COMP - 30],
                          [CENTER_X, Y_COMP - 30],
                          [CENTER_X, Y_COMP]],
            }

        # Overall boundary
        proc_y = Y_COMP - 50
        components['bnd_process'] = {
            'type': 'Boundary',
            'position': [process_x, proc_y],
            'size': {'width': process_w, 'height': MERGE_Y - proc_y + 80},
            'properties': {'label': 'Refrigeration Process', 'stroke_color': '#AAAAAA'},
        }

    # ══════════════════════════════════════════════════════════════════════
    #  CASSETTE MODES — independent refrigerant loop per cassette
    # ══════════════════════════════════════════════════════════════════════
    else:
        if num_raw in (1, 2):
            num_cass = 1; cas_lbs = ['']
        elif num_raw in (3, 4):
            num_cass = 2; cas_lbs = ['LH', 'RH']
        else:
            num_cass = 2 if mode == 'cassette_mt' else 3
            cas_lbs  = ['LH', 'RH'] if num_cass == 2 else ['LH', 'CTR', 'RH']

        cas_slice_w = combined_w / num_cass
        cas_evap_w  = cas_slice_w * 0.5
        cas_xs = [left_edge + cas_slice_w / 2 + i * cas_slice_w for i in range(num_cass)]
        global_merge_y = MERGE_Y

        for ci, (cx, lb) in enumerate(zip(cas_xs, cas_lbs)):
            cl  = lb if lb else 'None'
            pfx = f'c{ci}_'
            LEFTMOST_CAS = cx - max(cas_evap_w / 2 + 40,
                                    100 if mode == 'cassette_mt' else 180)

            # Compressor (per cassette)
            components[f'{pfx}comp'] = {
                'type': 'Compressor',
                'position': [cx - COMP_W // 2, Y_COMP],
                'size': {'width': COMP_W, 'height': COMP_H},
                'properties': {'circuit_label': cl},
            }

            if mode == 'cassette_mt':
                # ── Cassette MT: simple independent loop ────────────────
                components[f'{pfx}cond'] = {
                    'type': 'Condenser',
                    'position': [cx - COND_W // 2, Y_COND],
                    'size': {'width': COND_W, 'height': COND_H},
                    'properties': {'circuit_label': cl, 'condenser_type': condenser_type},
                }
                components[f'{pfx}txv'] = {
                    'type': 'TXV',
                    'position': [cx - TXV_W // 2, Y_TXV],
                    'size': {'width': TXV_W, 'height': TXV_H},
                    'properties': {'circuit_label': cl},
                }
                components[f'{pfx}dist'] = {
                    'type': 'SplitterManifold',
                    'position': [cx - cas_evap_w // 2, DIST_Y],
                    'size': {'width': cas_evap_w, 'height': DIST_H},
                    'properties': {'circuits': 1, 'circuit_label': cl},
                }
                components[f'{pfx}evap'] = {
                    'type': 'Evaporator',
                    'position': [cx - cas_evap_w // 2, Y_EVAP],
                    'size': {'width': cas_evap_w, 'height': EVAP_H},
                    'properties': {'circuits': 1, 'circuit_label': cl},
                }
                components[f'{pfx}head'] = {
                    'type': 'CombinerManifold',
                    'position': [cx - cas_evap_w // 2, HEAD_Y],
                    'size': {'width': cas_evap_w, 'height': HEAD_H},
                    'properties': {'circuits': 1, 'circuit_label': cl},
                }
                # comp → cond → txv → dist (all vertical through center cx)
                pipes[f'{pfx}p_comp_cond'] = {
                    'start_component_id': f'{pfx}comp', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}cond', 'end_port':   'inlet',
                    'route': [[cx, Y_COMP + COMP_H], [cx, Y_COND]],
                }
                pipes[f'{pfx}p_cond_txv'] = {
                    'start_component_id': f'{pfx}cond', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}txv',  'end_port':   'inlet',
                    'route': [[cx, Y_COND + COND_H], [cx, Y_TXV]],
                }
                pipes[f'{pfx}p_txv_dist'] = {
                    'start_component_id': f'{pfx}txv',  'start_port': 'outlet',
                    'end_component_id':   f'{pfx}dist', 'end_port':   'inlet',
                    'route': [[cx, Y_TXV + TXV_H], [cx, DIST_Y]],
                }
                # loopback: head → merge_y → LEFTMOST_CAS → comp inlet
                pipes[f'{pfx}p_loopback'] = {
                    'start_component_id': f'{pfx}head', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}comp', 'end_port':   'inlet',
                    'route': [[cx, HEAD_OUT_Y],
                              [cx, global_merge_y],
                              [LEFTMOST_CAS, global_merge_y],
                              [LEFTMOST_CAS, Y_COMP - 20],
                              [cx, Y_COMP - 20],
                              [cx, Y_COMP]],
                }
                bound_left  = cx - cas_evap_w / 2 - 60
                bound_width = (cx + cas_evap_w / 2 + 60) - bound_left

            else:  # cassette_lt
                # ── Cassette LT: hot gas bypass / solenoid / liquid solenoid
                sol_y    = Y_COND + COND_H + 30   # 280
                bypass_x = cx - 140

                # HGBV — Hot Gas Bypass Valve
                components[f'{pfx}hgbv'] = {
                    'type': 'LabeledBox',
                    'position': [bypass_x, Y_COND],
                    'size': {'width': 60, 'height': 50},
                    'properties': {'label': 'Hot Gas\nBypass', 'circuit_label': cl},
                }
                # HGS — Hot Gas Solenoid
                components[f'{pfx}hgs'] = {
                    'type': 'LabeledBox',
                    'position': [bypass_x, sol_y],
                    'size': {'width': 60, 'height': 50},
                    'properties': {'label': 'Hot Gas\nSolenoid', 'circuit_label': cl},
                }
                # Condenser
                components[f'{pfx}cond'] = {
                    'type': 'Condenser',
                    'position': [cx - COND_W // 2, Y_COND],
                    'size': {'width': COND_W, 'height': COND_H},
                    'properties': {'circuit_label': cl, 'condenser_type': condenser_type},
                }
                # LLS — Liquid Line Solenoid
                components[f'{pfx}lls'] = {
                    'type': 'LabeledBox',
                    'position': [cx - COND_W // 2, sol_y],
                    'size': {'width': COND_W, 'height': 40},
                    'properties': {'label': 'Liquid Line\nSolenoid', 'circuit_label': cl},
                }
                # TXV
                components[f'{pfx}txv'] = {
                    'type': 'TXV',
                    'position': [cx - TXV_W // 2, Y_TXV],
                    'size': {'width': TXV_W, 'height': TXV_H},
                    'properties': {'circuit_label': cl},
                }
                # Distributor / evap / header — 2 circuits
                components[f'{pfx}dist'] = {
                    'type': 'SplitterManifold',
                    'position': [cx - cas_evap_w // 2, DIST_Y],
                    'size': {'width': cas_evap_w, 'height': DIST_H},
                    'properties': {'circuits': 2, 'circuit_label': cl},
                }
                components[f'{pfx}evap'] = {
                    'type': 'Evaporator',
                    'position': [cx - cas_evap_w // 2, Y_EVAP],
                    'size': {'width': cas_evap_w, 'height': EVAP_H},
                    'properties': {'circuits': 2, 'circuit_label': cl},
                }
                components[f'{pfx}head'] = {
                    'type': 'CombinerManifold',
                    'position': [cx - cas_evap_w // 2, HEAD_Y],
                    'size': {'width': cas_evap_w, 'height': HEAD_H},
                    'properties': {'circuits': 2, 'circuit_label': cl},
                }

                split_y    = Y_COMP + COMP_H + 15   # 175
                hgbv_in_x  = bypass_x + 30           # HGBV top-center
                hgbv_out_y = Y_COND + 50             # HGBV bottom-center
                hgs_in_y   = sol_y                   # 280
                hgs_out_y  = sol_y + 50              # 330
                asc_y      = DIST_Y - 25             # 415

                # comp → split junction via straight vertical
                # (two branches from same comp outlet)
                pipes[f'{pfx}p_comp_hgbv'] = {
                    'start_component_id': f'{pfx}comp', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}hgbv', 'end_port':   'inlet',
                    'route': [[cx, Y_COMP + COMP_H],
                              [cx, split_y],
                              [hgbv_in_x, split_y],
                              [hgbv_in_x, Y_COND]],
                }
                pipes[f'{pfx}p_comp_cond'] = {
                    'start_component_id': f'{pfx}comp', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}cond', 'end_port':   'inlet',
                    'route': [[cx, Y_COMP + COMP_H],
                              [cx, split_y],
                              [cx, Y_COND]],
                }
                pipes[f'{pfx}p_hgbv_hgs'] = {
                    'start_component_id': f'{pfx}hgbv', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}hgs',  'end_port':   'inlet',
                    'route': [[hgbv_in_x, hgbv_out_y], [hgbv_in_x, hgs_in_y]],
                }
                pipes[f'{pfx}p_cond_lls'] = {
                    'start_component_id': f'{pfx}cond', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}lls',  'end_port':   'inlet',
                    'route': [[cx, Y_COND + COND_H], [cx, sol_y]],
                }
                pipes[f'{pfx}p_lls_txv'] = {
                    'start_component_id': f'{pfx}lls', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}txv', 'end_port':   'inlet',
                    'route': [[cx, sol_y + 40], [cx, Y_TXV]],
                }
                pipes[f'{pfx}p_txv_dist'] = {
                    'start_component_id': f'{pfx}txv',  'start_port': 'outlet',
                    'end_component_id':   f'{pfx}dist', 'end_port':   'inlet',
                    'route': [[cx, Y_TXV + TXV_H], [cx, DIST_Y]],
                }
                # HGS → ASC merge point (into suction/liquid header)
                pipes[f'{pfx}p_hgs_asc'] = {
                    'start_component_id': f'{pfx}hgs',  'start_port': 'outlet',
                    'end_component_id':   f'{pfx}dist', 'end_port':   'inlet',
                    'route': [[hgbv_in_x, hgs_out_y],
                              [hgbv_in_x, asc_y],
                              [cx, asc_y],
                              [cx, DIST_Y]],
                }
                # loopback
                pipes[f'{pfx}p_loopback'] = {
                    'start_component_id': f'{pfx}head', 'start_port': 'outlet',
                    'end_component_id':   f'{pfx}comp', 'end_port':   'inlet',
                    'route': [[cx, HEAD_OUT_Y],
                              [cx, global_merge_y],
                              [LEFTMOST_CAS, global_merge_y],
                              [LEFTMOST_CAS, Y_COMP - 20],
                              [cx, Y_COMP - 20],
                              [cx, Y_COMP]],
                }
                # ASC label as boundary
                components[f'{pfx}bnd_asc'] = {
                    'type': 'Boundary',
                    'position': [cx - 20, asc_y - 14],
                    'size': {'width': 50, 'height': 18},
                    'properties': {'label': 'ASC', 'stroke_color': '#555555'},
                }
                bound_left  = min(cx - cas_evap_w / 2 - 60, cx - 180)
                bound_width = (cx + cas_evap_w / 2 + 60) - bound_left

            # Per-cassette boundary
            components[f'{pfx}bnd_proc'] = {
                'type': 'Boundary',
                'position': [bound_left, Y_COMP - 40],
                'size': {'width': bound_width, 'height': global_merge_y - Y_COMP + 40},
                'properties': {
                    'label': (f'Refrigeration Process [{lb} Cassette]'
                              if lb else 'Refrigeration Process'),
                    'stroke_color': '#AAAAAA',
                },
            }

    # ══════════════════════════════════════════════════════════════════════
    #  AIRFLOW DIAGRAM  (matching test_loop.py ordering)
    # ══════════════════════════════════════════════════════════════════════
    base_y   = MERGE_Y + 100
    fan_size = 60

    if is_cassette:
        # Reversed: Return Air → fans → Primary Discharge Air
        ret_air_y = base_y
        fan_y     = base_y + 40
        pri_air_y = fan_y + fan_size + 10
        air_bottom_y = pri_air_y
        arr_dir_above = 'down'; arr_dir_below = 'down'
        components['deco_ret_air'] = {
            'type': 'DecorativeRect',
            'position': [left_edge, ret_air_y],
            'size': {'width': combined_w, 'height': 30},
            'properties': {'bg_color': '#FFCDD2', 'label': 'Return Air'},
        }
        components['deco_pri_air'] = {
            'type': 'DecorativeRect',
            'position': [left_edge, pri_air_y],
            'size': {'width': combined_w, 'height': 30},
            'properties': {'bg_color': '#B3E5FC', 'label': 'Primary Discharge Air'},
        }
    else:
        # Normal: Primary → (Secondary modular-only) → fans → Return Air
        pri_air_y = base_y
        components['deco_pri_air'] = {
            'type': 'DecorativeRect',
            'position': [left_edge, pri_air_y],
            'size': {'width': combined_w, 'height': 30},
            'properties': {'bg_color': '#B3E5FC', 'label': 'Primary Discharge Air'},
        }
        if mode == 'modular':
            components['deco_sec_air'] = {
                'type': 'DecorativeRect',
                'position': [left_edge, base_y + 40],
                'size': {'width': combined_w, 'height': 30},
                'properties': {'bg_color': '#FFF9C4', 'label': 'Secondary Discharge Air'},
            }
            fan_y = base_y + 80
        else:
            fan_y = base_y + 40

        ret_air_y = fan_y + fan_size + 10
        air_bottom_y = ret_air_y
        arr_dir_above = 'up'; arr_dir_below = 'up'
        components['deco_ret_air'] = {
            'type': 'DecorativeRect',
            'position': [left_edge, ret_air_y],
            'size': {'width': combined_w, 'height': 30},
            'properties': {'bg_color': '#FFCDD2', 'label': 'Return Air'},
        }

    # Fans + AirArrow markers
    if mode == 'modular':
        for mi, (mx, lb) in enumerate(zip(mod_xs, mod_lbs)):
            fname = f'Fan {lb}'.strip() if lb else 'Fan'
            fkey  = lb.lower().replace(' ', '_') if lb else f'm{mi}'
            components[f'deco_fan_{fkey}'] = {
                'type': 'DecorativeRect',
                'position': [mx - fan_size / 2, fan_y],
                'size': {'width': fan_size, 'height': fan_size},
                'properties': {'bg_color': '#E0E0E0', 'label': fname},
            }
            # Arrow below fan (pointing up into fan)
            components[f'deco_arr_{fkey}_bot'] = {
                'type': 'AirArrow',
                'position': [mx - 5, fan_y + fan_size],
                'size': {'width': 10, 'height': 10},
                'properties': {'direction': arr_dir_below},
            }
            # Arrow above fan (pointing up out of fan)
            components[f'deco_arr_{fkey}_top'] = {
                'type': 'AirArrow',
                'position': [mx - 5, fan_y - 10],
                'size': {'width': 10, 'height': 10},
                'properties': {'direction': arr_dir_above},
            }
    else:
        slice_w = combined_w / count
        for i in range(count):
            fx   = left_edge + slice_w / 2 + i * slice_w
            fkey = f'dr{i+1}'
            components[f'deco_fan_{fkey}'] = {
                'type': 'DecorativeRect',
                'position': [fx - fan_size / 2, fan_y],
                'size': {'width': fan_size, 'height': fan_size},
                'properties': {'bg_color': '#E0E0E0', 'label': f'Fan Dr {i+1}'},
            }
            if is_cassette:
                # Cassette arrows point DOWN (reversed airflow)
                components[f'deco_arr_{fkey}_top'] = {
                    'type': 'AirArrow',
                    'position': [fx - 5, fan_y - 10],
                    'size': {'width': 10, 'height': 10},
                    'properties': {'direction': 'down'},
                }
                components[f'deco_arr_{fkey}_bot'] = {
                    'type': 'AirArrow',
                    'position': [fx - 5, fan_y + fan_size],
                    'size': {'width': 10, 'height': 10},
                    'properties': {'direction': 'down'},
                }
            else:
                components[f'deco_arr_{fkey}_bot'] = {
                    'type': 'AirArrow',
                    'position': [fx - 5, fan_y + fan_size],
                    'size': {'width': 10, 'height': 10},
                    'properties': {'direction': 'up'},
                }
                components[f'deco_arr_{fkey}_top'] = {
                    'type': 'AirArrow',
                    'position': [fx - 5, fan_y - 10],
                    'size': {'width': 10, 'height': 10},
                    'properties': {'direction': 'up'},
                }

    # Airflow boundary
    air_bnd_y = base_y - 40
    air_bnd_h = (air_bottom_y + 30 + 40) - air_bnd_y
    components['bnd_air'] = {
        'type': 'Boundary',
        'position': [process_x, air_bnd_y],
        'size': {'width': process_w, 'height': air_bnd_h},
        'properties': {'label': 'Airflow Diagram', 'stroke_color': '#AAAAAA'},
    }

    # ── Shelving Diagram ─────────────────────────────────────────────────
    shelf_base_y  = air_bottom_y + 30 + 100
    shelf_height  = 30
    shelf_gap     = 10
    shelf_total_h = shelf_rows * (shelf_height + shelf_gap)

    if mode == 'modular':
        col_w  = EVAP_W
        col_xs = [mx - EVAP_W / 2 for mx in mod_xs]
    else:
        col_w  = combined_w / count
        col_xs = [left_edge + i * col_w for i in range(count)]

    for ci, csx in enumerate(col_xs):
        for r in range(shelf_rows):
            sy = shelf_base_y + r * (shelf_height + shelf_gap)
            components[f'deco_shelf_{ci}_{r}'] = {
                'type': 'DecorativeRect',
                'position': [csx + 3, sy],
                'size': {'width': col_w - 6, 'height': shelf_height},
                'properties': {'bg_color': '#F0F0F0', 'label': f'Shelf {r+1}'},
            }

    components['bnd_shelf'] = {
        'type': 'Boundary',
        'position': [process_x, shelf_base_y - 40],
        'size': {'width': process_w, 'height': shelf_total_h + 60},
        'properties': {'label': 'Shelving Diagram', 'stroke_color': '#AAAAAA'},
    }

    # ── Doors Diagram ────────────────────────────────────────────────────
    if case_type == 'Doored':
        door_base_y = shelf_base_y + shelf_total_h + 80
        door_height = 240
        mullion_w   = 16

        if mode == 'modular':
            M = len(mod_xs)
            components['deco_mull_lh'] = {
                'type': 'DecorativeRect',
                'position': [left_edge - mullion_w - 10, door_base_y],
                'size': {'width': mullion_w, 'height': door_height},
                'properties': {'bg_color': '#B0BEC5', 'label': ''},
            }
            components['deco_mull_rh'] = {
                'type': 'DecorativeRect',
                'position': [right_edge + 10, door_base_y],
                'size': {'width': mullion_w, 'height': door_height},
                'properties': {'bg_color': '#B0BEC5', 'label': ''},
            }
            door_w = EVAP_W / 2 - 2
            for m, mx in enumerate(mod_xs):
                components[f'deco_door_{2*m+1}'] = {
                    'type': 'DecorativeRect',
                    'position': [mx - EVAP_W / 2, door_base_y],
                    'size': {'width': door_w, 'height': door_height},
                    'properties': {'bg_color': '#E1F5FE', 'label': f'Door {2*m+1}'},
                }
                components[f'deco_door_{2*m+2}'] = {
                    'type': 'DecorativeRect',
                    'position': [mx + 2, door_base_y],
                    'size': {'width': door_w, 'height': door_height},
                    'properties': {'bg_color': '#E1F5FE', 'label': f'Door {2*m+2}'},
                }
                if m < M - 1:
                    ctr_x = (mod_xs[m] + mod_xs[m + 1]) / 2
                    components[f'deco_mull_ctr_{m}'] = {
                        'type': 'DecorativeRect',
                        'position': [ctr_x - mullion_w / 2, door_base_y],
                        'size': {'width': mullion_w, 'height': door_height},
                        'properties': {'bg_color': '#B0BEC5', 'label': ''},
                    }
        else:
            N   = count
            gap = 4
            total_mull_w = (N + 1) * mullion_w
            total_gap_w  = (2 * N) * gap
            door_w = (combined_w - total_mull_w - total_gap_w) / N
            dcx = left_edge
            components['deco_mull_lh'] = {
                'type': 'DecorativeRect',
                'position': [dcx, door_base_y],
                'size': {'width': mullion_w, 'height': door_height},
                'properties': {'bg_color': '#B0BEC5', 'label': ''},
            }
            dcx += mullion_w + gap
            for i in range(N):
                components[f'deco_door_{i+1}'] = {
                    'type': 'DecorativeRect',
                    'position': [dcx, door_base_y],
                    'size': {'width': door_w, 'height': door_height},
                    'properties': {'bg_color': '#E1F5FE', 'label': f'Door {i+1}'},
                }
                dcx += door_w + gap
                if i < N - 1:
                    components[f'deco_mull_ctr_{i}'] = {
                        'type': 'DecorativeRect',
                        'position': [dcx, door_base_y],
                        'size': {'width': mullion_w, 'height': door_height},
                        'properties': {'bg_color': '#B0BEC5', 'label': ''},
                    }
                    dcx += mullion_w + gap
            components['deco_mull_rh'] = {
                'type': 'DecorativeRect',
                'position': [dcx, door_base_y],
                'size': {'width': mullion_w, 'height': door_height},
                'properties': {'bg_color': '#B0BEC5', 'label': ''},
            }
        components['bnd_doors'] = {
            'type': 'Boundary',
            'position': [process_x, door_base_y - 40],
            'size': {'width': process_w, 'height': door_height + 60},
            'properties': {'label': 'Doors Diagram', 'stroke_color': '#AAAAAA'},
        }

    # ── Tag all components and pipes ──────────────────────────────────────
    for p in pipes.values():
        p['_simple_mode'] = True
        p['route_locked'] = True
        p['_raw_route']   = True
    for c in components.values():
        c['_simple_mode'] = True

    return {
        'components': components,
        'pipes':      pipes,
        'sensor_roles':    {},
        'custom_sensors':  {},
        'role_dot_labels': {},
        '_simple_mode': True,
        '_topology': topo,
        '_generated_from': (f'bare_minimum ({mode}, count={count}, '
                            f'{num_circuits} circuits/coil)'),
    }
