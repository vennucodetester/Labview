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
    """Build a clean process diagram matching the test_loop.py reference.

    Layout: Compressor → Condenser → [per module: TXV → SplitterManifold
            → Evaporator → CombinerManifold] → multi-junction → loopback

    Below the refrigerant section: Airflow, Shelving, Doors decorative sections.
    All geometry matches test_loop.py exactly.
    """

    def _circuit_xs(count, width=240, spacing=20):
        """Local x-positions of circuit ports. No snap — exact even spacing."""
        span = (count - 1) * spacing if count > 1 else 0
        return [(width / 2 + (i - 1) * spacing - span / 2)
                for i in range(1, count + 1)]

    topo = request.get('topology', {}) or {}
    mode       = topo.get('mode', 'modular')
    num_doors  = max(1, min(5, int(topo.get('num_doors', 3) or 3)))
    case_type  = topo.get('case_type', 'Doored')
    shelf_rows = max(3, min(8, int(topo.get('shelf_rows', 5) or 5)))
    num_circuits = max(1, int(topo.get('circuits_per_coil', 6) or 6))
    condenser_type = ('Water Cooled'
                      if str(topo.get('condenser_cooling', 'Water')).lower().startswith('w')
                      else 'Air Cooled')

    CENTER_X    = 600
    MOD_SPACING = 300
    COMP_W, COMP_H = 120, 60
    COND_W, COND_H = 120, 60
    TXV_W, TXV_H   = 120, 60
    EVAP_H = 80
    DIST_H = 40   # SplitterManifold (distributor) above evap
    HEAD_H = 40   # CombinerManifold (header) below evap

    Y_COMP   = 100
    Y_COND   = 200
    Y_TXV    = 330
    Y_EVAP   = 445
    BRANCH_Y = Y_COND + COND_H + 30   # 290 — fan-out level below condenser
    DIST_Y   = Y_EVAP - DIST_H - 15   # 390 — distributor top
    HEAD_Y   = Y_EVAP + EVAP_H        # 525 — header/combiner top
    HEAD_OUT_Y = HEAD_Y + HEAD_H       # 565 — combiner outlet y
    MERGE_Y  = Y_EVAP + EVAP_H + 85   # 610 — loopback horizontal level

    # ── Mode: door vs modular ────────────────────────────────────────────
    if mode == 'door':
        EVAP_W     = 240 * num_doors
        num_modules = 1
        mod_xs  = [CENTER_X]
        mod_lbs = ['']
    else:
        EVAP_W     = 240
        num_modules = max(1, min(3, int(topo.get('modules', 1) or 1)))
        if num_modules == 1:
            mod_xs  = [CENTER_X];  mod_lbs = ['']
        elif num_modules == 2:
            mod_xs  = [CENTER_X - MOD_SPACING // 2, CENTER_X + MOD_SPACING // 2]
            mod_lbs = ['Left', 'Right']
        else:
            mod_xs  = [CENTER_X - MOD_SPACING, CENTER_X, CENTER_X + MOD_SPACING]
            mod_lbs = ['Left', 'Center', 'Right']

    LEFTMOST = mod_xs[0] - EVAP_W // 2 - 100

    # Circuit port x-positions (no snap, exact even spacing across EVAP_W)
    ckt_spacing   = (EVAP_W / (num_circuits - 1)) if num_circuits > 1 else EVAP_W
    ckt_local_xs  = _circuit_xs(num_circuits, EVAP_W, spacing=ckt_spacing)

    components: dict = {}
    pipes:      dict = {}

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

    cond_out_y = Y_COND + COND_H

    # ── Multi-module invisible junction (n > 1 only) ──────────────────────
    if num_modules > 1:
        multi_w    = (num_modules - 1) * MOD_SPACING + EVAP_W
        multi_left = CENTER_X - multi_w // 2
        components['multi_suct'] = {
            'type': 'Junction',
            'position': [multi_left, MERGE_Y],
            'size': {'width': multi_w, 'height': 1},
            'properties': {
                'inlet_count':  1, 'outlet_count': 1,
                'port_spacing': 20, 'snapped_mode': 'Yes',
                'circuit_label': 'None',
            },
        }

    # ── Per-module ────────────────────────────────────────────────────────
    for mod_x, lb in zip(mod_xs, mod_lbs):
        cl  = lb if lb else 'None'
        pfx = lb.lower().replace(' ', '_') + '_' if lb else ''
        evap_left = mod_x - EVAP_W // 2

        txv_id  = f'{pfx}txv'
        dist_id = f'{pfx}dist'
        evap_id = f'{pfx}evap'
        head_id = f'{pfx}head'

        # TXV
        components[txv_id] = {
            'type': 'TXV',
            'position': [mod_x - TXV_W // 2, Y_TXV],
            'size': {'width': TXV_W, 'height': TXV_H},
            'properties': {'circuit_label': cl},
        }

        # Distributor — SplitterManifold above evap
        components[dist_id] = {
            'type': 'SplitterManifold',
            'position': [evap_left, DIST_Y],
            'size': {'width': EVAP_W, 'height': DIST_H},
            'properties': {'circuits': num_circuits, 'circuit_label': cl},
        }

        # Evaporator
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

        # Header — CombinerManifold below evap
        components[head_id] = {
            'type': 'CombinerManifold',
            'position': [evap_left, HEAD_Y],
            'size': {'width': EVAP_W, 'height': HEAD_H},
            'properties': {'circuits': num_circuits, 'circuit_label': cl},
        }

        # cond → TXV (branch at BRANCH_Y, drop to mod_x)
        pipes[f'p_cond_{txv_id}'] = {
            'start_component_id': 'cond', 'start_port': 'outlet',
            'end_component_id':   txv_id, 'end_port':   'inlet',
            'route': [[CENTER_X, cond_out_y],
                      [CENTER_X, BRANCH_Y],
                      [mod_x,    BRANCH_Y],
                      [mod_x,    Y_TXV]],
        }

        # TXV → distributor inlet (direct vertical; may be zero-length if coincident)
        txv_out_y = Y_TXV + TXV_H
        if txv_out_y < DIST_Y:
            pipes[f'p_{txv_id}_{dist_id}'] = {
                'start_component_id': txv_id,  'start_port': 'outlet',
                'end_component_id':   dist_id, 'end_port':   'inlet',
                'route': [[mod_x, txv_out_y], [mod_x, DIST_Y]],
            }

        # Header outlet → suction
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
                'start_component_id': head_id,      'start_port': 'outlet',
                'end_component_id':   'multi_suct', 'end_port':   'inlet_1',
                'route': [[mod_x, HEAD_OUT_Y], [mod_x, MERGE_Y], [CENTER_X, MERGE_Y]],
            }

    # ── Multi-module loopback ─────────────────────────────────────────────
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

    # ── Decorative sections ───────────────────────────────────────────────
    left_edge  = mod_xs[0]  - EVAP_W / 2
    right_edge = mod_xs[-1] + EVAP_W / 2
    combined_w = right_edge - left_edge

    # Airflow
    base_y = MERGE_Y + 100
    components['deco_pri_air'] = {
        'type': 'DecorativeRect',
        'position': [left_edge, base_y],
        'size': {'width': combined_w, 'height': 30},
        'properties': {'bg_color': '#B3E5FC', 'label': 'Primary Discharge Air'},
    }
    components['deco_sec_air'] = {
        'type': 'DecorativeRect',
        'position': [left_edge, base_y + 40],
        'size': {'width': combined_w, 'height': 30},
        'properties': {'bg_color': '#FFF9C4', 'label': 'Secondary Discharge Air'},
    }

    fan_y    = base_y + 80
    fan_size = 60
    if mode == 'door':
        slice_w = combined_w / num_doors
        for i in range(num_doors):
            fx = left_edge + (slice_w / 2) + (i * slice_w)
            components[f'deco_fan_{i+1}'] = {
                'type': 'DecorativeRect',
                'position': [fx - fan_size / 2, fan_y],
                'size': {'width': fan_size, 'height': fan_size},
                'properties': {'bg_color': '#E0E0E0', 'label': f'Fan Dr {i+1}'},
            }
    else:
        for mx, lb in zip(mod_xs, mod_lbs):
            fname = f'Fan {lb}'.strip() if lb else 'Fan'
            fkey  = lb.lower().replace(' ', '_') if lb else 'ctr'
            components[f'deco_fan_{fkey}'] = {
                'type': 'DecorativeRect',
                'position': [mx - fan_size / 2, fan_y],
                'size': {'width': fan_size, 'height': fan_size},
                'properties': {'bg_color': '#E0E0E0', 'label': fname},
            }

    ret_air_y = fan_y + fan_size + 10
    components['deco_ret_air'] = {
        'type': 'DecorativeRect',
        'position': [left_edge, ret_air_y],
        'size': {'width': combined_w, 'height': 30},
        'properties': {'bg_color': '#FFCDD2', 'label': 'Return Air'},
    }

    # Shelving
    shelf_base_y  = ret_air_y + 30 + 100
    shelf_height  = 30
    shelf_gap     = 10
    shelf_total_h = shelf_rows * (shelf_height + shelf_gap)

    if mode == 'door':
        col_w  = combined_w / num_doors
        col_xs = [left_edge + i * col_w for i in range(num_doors)]
    else:
        col_w  = EVAP_W
        col_xs = [mx - EVAP_W / 2 for mx in mod_xs]

    for ci, cx in enumerate(col_xs):
        for r in range(shelf_rows):
            sy = shelf_base_y + r * (shelf_height + shelf_gap)
            components[f'deco_shelf_{ci}_{r}'] = {
                'type': 'DecorativeRect',
                'position': [cx + 3, sy],
                'size': {'width': col_w - 6, 'height': shelf_height},
                'properties': {'bg_color': '#F0F0F0', 'label': f'Shelf {r+1}'},
            }

    # Doors
    if case_type == 'Doored':
        door_base_y = shelf_base_y + shelf_total_h + 80
        door_height = 240
        mullion_w   = 16

        if mode != 'door':
            # Modular: end mullions + 2 doors per module + center mullions between modules
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
            # Door mode: end mullions + N doors with mullions between
            N   = num_doors
            gap = 4
            total_mull_w = (N + 1) * mullion_w
            total_gap_w  = (2 * N) * gap
            door_w = (combined_w - total_mull_w - total_gap_w) / N
            cx = left_edge
            components['deco_mull_lh'] = {
                'type': 'DecorativeRect',
                'position': [cx, door_base_y],
                'size': {'width': mullion_w, 'height': door_height},
                'properties': {'bg_color': '#B0BEC5', 'label': ''},
            }
            cx += mullion_w + gap
            for i in range(N):
                components[f'deco_door_{i+1}'] = {
                    'type': 'DecorativeRect',
                    'position': [cx, door_base_y],
                    'size': {'width': door_w, 'height': door_height},
                    'properties': {'bg_color': '#E1F5FE', 'label': f'Door {i+1}'},
                }
                cx += door_w + gap
                if i < N - 1:
                    components[f'deco_mull_ctr_{i}'] = {
                        'type': 'DecorativeRect',
                        'position': [cx, door_base_y],
                        'size': {'width': mullion_w, 'height': door_height},
                        'properties': {'bg_color': '#B0BEC5', 'label': ''},
                    }
                    cx += mullion_w + gap
            components['deco_mull_rh'] = {
                'type': 'DecorativeRect',
                'position': [cx, door_base_y],
                'size': {'width': mullion_w, 'height': door_height},
                'properties': {'bg_color': '#B0BEC5', 'label': ''},
            }
    else:
        door_base_y  = shelf_base_y + shelf_total_h + 80
        door_height  = 0

    # Boundaries
    process_x = LEFTMOST - 40
    process_w = (right_edge + 40) - process_x
    process_y = Y_COMP - 80
    process_h = MERGE_Y + 40 - process_y
    components['bnd_process'] = {
        'type': 'Boundary',
        'position': [process_x, process_y],
        'size': {'width': process_w, 'height': process_h},
        'properties': {'label': 'Refrigeration Process', 'stroke_color': '#AAAAAA'},
    }

    air_y = base_y - 40
    air_h = (ret_air_y + 30 + 40) - air_y
    components['bnd_air'] = {
        'type': 'Boundary',
        'position': [process_x, air_y],
        'size': {'width': process_w, 'height': air_h},
        'properties': {'label': 'Airflow Diagram', 'stroke_color': '#AAAAAA'},
    }

    components['bnd_shelf'] = {
        'type': 'Boundary',
        'position': [process_x, shelf_base_y - 40],
        'size': {'width': process_w, 'height': shelf_total_h + 60},
        'properties': {'label': 'Shelving Diagram', 'stroke_color': '#AAAAAA'},
    }

    if case_type == 'Doored' and door_height > 0:
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
        '_generated_from': (f'bare_minimum ({mode}, {num_modules} module(s), '
                            f'{num_circuits} circuits/module)'),
    }
