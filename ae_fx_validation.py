"""E3.3.2 AE integrated Si FX validation (non-destructive diagnostics).

Scope is deliberately narrow: seven exact Si VFX geometry objects and the
E3.3.2 VFX_B final-look materials. This is NOT a substitute for Blender-native
restore tests, a double-Build run, or a visual comparison with the game.

On a successful, verified AE Si Build, the one-click dispatcher records a
stable material-graph fingerprint and a concise status in scene custom props.
A separate panel operator reads and exports evidence; it never changes any
material, object, image, render setting, or file contents.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import re
import tempfile
import uuid

import bpy
from . import ae_fx_layered_materials as fx
from . import ae_vfx_placeholders as e32
from . import ae_material_sources as source

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = 'AE_SI_VFX_E332_INTEGRATED_VALIDATION_1'
BASELINE_KEY = 'SaberShader_AE_Si_E332QA_Reference'
RESULT_KEY = 'SaberShader_AE_Si_E332QA_LastResult'
STATUS_KEY = 'SaberShader_AE_Si_E332QA_Status'
RUNS_KEY = 'SaberShader_AE_Si_E332QA_BuildObservations'
OBSERVATION_KEY = 'SaberShader_AE_Si_E332QA_LastBuildState'
_SESSION = uuid.uuid4().hex  # Only comparable within this Blender process.
VFX_RE = re.compile(r'^S_actor_jsspsi_vfxpart_0([1-7])_lod0(?:\.\d{3})?$', re.I)
REQUIRED_MAIN = 'T_fx_trail_fj_09_1_v1d4_M'
DETAIL_ALTERNATIVES = ('T_fx_trail_gfx_18', 'T_fx_noise_cyt_003_1')
DISTORT_ALTERNATIVES = ('T_fx_normal_501_N', 'T_fx_flow_527_M')


def _reason(status, detail):
    return {'status': status, 'detail': detail}


def _ptr(obj):
    return obj.as_pointer() if hasattr(obj, 'as_pointer') else id(obj)


def _get(x, name, default=''):
    try:
        return x.get(name, default)
    except (AttributeError, TypeError):
        return default


def _links(mat):
    tree = getattr(mat, 'node_tree', None)
    if tree is None:
        return []
    return sorted((lk.from_node.name, lk.from_socket.name,
                   lk.to_node.name, lk.to_socket.name)
                  for lk in tree.links)


def _as_json_value(val):
    # Serialize node constants deterministically across Blender save/reload.
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return round(float(val), 7) if math.isfinite(float(val)) else str(val)
    if isinstance(val, str):
        return val
    try:
        return [_as_json_value(v) for v in val]
    except (TypeError, ValueError, AttributeError):
        return str(val)


def _material_row(mat):
    if mat is None:
        return None
    tree = getattr(mat, 'node_tree', None)
    nodes = list(tree.nodes) if tree else []
    # E3.3.2 sometimes duplicates an image as `SaberShader AE VFX ... |
    # Data | filename.png` for Non-Color. Use original filepath and the
    # image-node's declared exact filename as alternative identity; the
    # prefixed datablock name alone is not the original texture name.
    images = sorted({source.normalize_basename(value)
        for n in nodes if getattr(n, 'image', None) is not None
        for value in (n.image.name, getattr(n.image, 'filepath', ''),
                      n.name.rsplit(' | ', 1)[-1]) if value})
    graph = {
        'nodes': sorted((n.name, getattr(n, 'bl_idname', getattr(n, 'type', '')))
                        for n in nodes),
        'links': _links(mat),
        'images': images,
        'image_color_spaces': sorted((n.image.name,
            str(getattr(getattr(n.image, 'colorspace_settings', None), 'name', 'UNKNOWN')))
            for n in nodes if getattr(n, 'image', None) is not None),
        'socket_defaults': sorted((n.name, idx, _as_json_value(inp.default_value))
            for n in nodes for idx, inp in enumerate(getattr(n, 'inputs', ()))
            if hasattr(inp, 'default_value')),
        'ramp_elements': sorted((n.name, [(round(float(e.position), 7),
            _as_json_value(e.color)) for e in n.color_ramp.elements])
            for n in nodes if getattr(n, 'color_ramp', None) is not None),
    }
    graph_hash = hashlib.sha256(json.dumps(graph, sort_keys=True).encode('utf-8')).hexdigest()
    pred = str(_get(mat, fx.ORIGINAL_KEY) or '')
    original = bpy.data.materials.get(pred) if pred else None
    return {
        'name': mat.name,
        'material_pointer': _ptr(mat),  # Report only, never persisted in fingerprint.
        'source': str(_get(mat, 'AEF_V11_SourceMaterial') or ''),
        'e331_marker': str(_get(mat, fx.MARKER) or ''),
        'kind': str(_get(mat, fx.KIND_KEY) or ''),
        'vfx_b_marker': str(_get(mat, fx.VFX_B_KEY) or ''),
        'predecessor': pred,
        'predecessor_found': original is not None,
        'predecessor_source': str(_get(original, 'AEF_V11_SourceMaterial') or '') if original else '',
        'predecessor_e32': str(_get(original, e32.MARKER) or '') if original else '',
        'users': int(getattr(mat, 'users', 0)),
        'fake_user': bool(getattr(mat, 'use_fake_user', False)),
        'node_count': len(nodes),
        'link_count': len(graph['links']),
        'images': images,
        'graph_hash': graph_hash,
        'render_method': str(getattr(mat, 'surface_render_method', 'UNKNOWN')),
    }


def _actor_rows(objects):
    rows = []
    for obj in objects or ():
        if getattr(obj, 'type', None) != 'MESH':
            continue
        match = VFX_RE.fullmatch(str(getattr(obj, 'name', '')))
        if not match:
            continue
        mats = list(getattr(getattr(obj, 'data', None), 'materials', ()) or ())
        rows.append({'object': obj.name, 'part': int(match.group(1)),
                     'mesh_users': int(getattr(obj.data, 'users', 0)),
                     'materials': [_material_row(mat) for mat in mats]})
    return sorted(rows, key=lambda r: (r['part'], r['object']))


def _stable_fingerprint(rows):
    # Do not hash session-local pointers, material.users, or fake-user counts.
    data = []
    for row in rows:
        data.append({'object': row['object'], 'part': row['part'], 'materials': [{
            key: val for key, val in (mat or {}).items()
            if key in ('name', 'source', 'e331_marker', 'kind', 'vfx_b_marker',
                       'predecessor', 'predecessor_found', 'predecessor_source',
                       'predecessor_e32', 'node_count', 'link_count', 'images',
                       'graph_hash', 'render_method')
        } if mat else None for mat in row['materials']]})
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _validate_7(rows):
    if not rows:
        return _reason('NOT TESTED', 'No exact Si vfxpart_01..07 meshes in selected AE actor')
    ids = [r['part'] for r in rows]
    if len(rows) != 7 or sorted(ids) != list(range(1, 8)):
        return _reason('FAIL', 'Expected one each of Si vfxpart_01..07; found: %r' % ids)
    failures = []
    main = source.normalize_basename(REQUIRED_MAIN)
    details = {source.normalize_basename(x) for x in DETAIL_ALTERNATIVES}
    distortions = {source.normalize_basename(x) for x in DISTORT_ALTERNATIVES}
    for row in rows:
        mats = row['materials']
        if len(mats) != 1 or not mats[0]:
            failures.append((row['object'], 'SLOT_COUNT_OR_EMPTY'))
            continue
        mat = mats[0]
        if (mat['source'] != 'DefaultHGMaterial'
                or mat['e331_marker'] != fx.REVISION
                or mat['kind'] != 'VFX'
                or mat['vfx_b_marker'] != fx.VFX_B_REVISION):
            failures.append((row['object'], 'STAGE_OR_PROVENANCE_MISMATCH'))
        if not mat['predecessor_found'] or mat['predecessor_source'] != 'DefaultHGMaterial':
            failures.append((row['object'], 'PREDECESSOR_MISSING_OR_MISMATCH'))
        if mat['node_count'] < 15 or mat['link_count'] < 15:
            failures.append((row['object'], 'INCOMPLETE_NODE_GRAPH'))
        attached = set(mat['images'])
        if main not in attached or not (attached & details) or not (attached & distortions):
            failures.append((row['object'], 'SOURCE_IMAGE_NODE_MISSING'))
    if failures:
        return {'status': 'FAIL', 'detail': 'VFX_B assignment/provenance incomplete', 'failures': failures}
    return _reason('PASS', 'Seven correct VFX_B assignments; predecessor IDs and required image nodes exist')


def inspect(objects, *, baseline=None):
    """Pure-ish Blender inspection: reads IDs but does not mutate any data."""
    rows = _actor_rows(objects)
    one = _validate_7(rows)
    signature = _stable_fingerprint(rows)
    check2 = _reason('NOT TESTED', 'A second successful native Build must be observed')
    check7 = _reason('NOT TESTED', 'Save and reopen the built .blend in a new Blender session, then validate')
    if isinstance(baseline, dict) and baseline.get('schema') == 1:
        if baseline.get('session') == _SESSION:
            if baseline.get('fingerprint') == signature and one['status'] == 'PASS':
                # Build observation count is supplied by post_build() below.
                pass
        elif bpy.data.filepath:
            if baseline.get('fingerprint') == signature and one['status'] == 'PASS':
                check7 = _reason('PASS', 'Stored material topology survived reopening in a fresh Blender session')
            else:
                check7 = _reason('FAIL', 'Saved VFX_B topology does not match stored build fingerprint')
    entries = {
        '1': one,
        '2': check2,
        '3': _reason('NOT TESTED', 'Missing mandatory images requires explicit fault-injection test'),
        '4': _reason('NOT TESTED', 'Non-Si object/material comparison requires pre/post stage snapshots'),
        '5': _reason('NOT TESTED', 'Restore operator must be executed explicitly on a copy'),
        '6': _reason('NOT TESTED', 'Chained restore must be executed explicitly on a copy'),
        '7': check7,
        '8': _reason('NOT TESTED', 'Non-Si profile regression requires separate Blender projects'),
    }
    return {
        'revision': REVISION,
        'blender': str(getattr(bpy.app, 'version_string', 'UNKNOWN')),
        'blend_path': str(getattr(bpy.data, 'filepath', '')),
        'session': _SESSION,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'checks': entries,
        'fingerprint': signature,
        'vfx_rows': rows,
        'distinct_vfx_materials': len({m['material_pointer'] for r in rows
                                       for m in r['materials'] if m}),
    }


def _non_si_snapshot(scene):
    """Capture only non-Si mesh/material states, around FX stage (not legacy Build)."""
    state = []
    for obj in getattr(scene, 'objects', ()) or ():
        if getattr(obj, 'type', None) != 'MESH' or 'jsspsi' in obj.name.casefold():
            continue
        # Actor-independent generated meshes are outside this FX-stage scope.
        mats = list(getattr(getattr(obj, 'data', None), 'materials', ()) or ())
        state.append((obj.name, _ptr(obj.data), tuple(
            (m.name, _ptr(m), _material_row(m)['graph_hash']) if m is not None else None
            for m in mats)))
    return sorted(state)


def capture_non_si(scene):
    return _non_si_snapshot(scene)


def _parse_baseline(scene):
    try:
        raw = scene.get(BASELINE_KEY)
        return json.loads(raw) if isinstance(raw, str) else None
    except (TypeError, ValueError, AttributeError):
        return None


def post_build(context, objects, *, non_si_before=None):
    """Read-only validation plus minimal scene metadata, after verified Si Build.

    NEVER calls Build, saves/reopens files, changes visual node parameters or
    invokes restore. Its first observation is NOT a native idempotence PASS.
    """
    scene = context.scene
    saved = _parse_baseline(scene)
    result = inspect(objects, baseline=saved)
    if non_si_before is not None:
        after = capture_non_si(scene)
        result['checks']['4'] = _reason('PASS' if after == non_si_before else 'FAIL',
            'Non-Si material slots, IDs and node graphs unchanged during Si FX stages' if after == non_si_before else
            'Non-Si material assignments or node graphs changed during Si FX stages') if non_si_before else _reason(
                'NOT TESTED', 'No non-Si meshes present to compare')

    count = int(_get(scene, RUNS_KEY, 0) or 0)
    try:
        last_run = json.loads(scene.get(OBSERVATION_KEY, '{}'))
    except (ValueError, TypeError, AttributeError):
        last_run = {}
    if result['checks']['1']['status'] == 'PASS':
        # A single successful observation never proves idempotence.
        # Use a session-scoped previous Build, not a cross-session saved file.
        if last_run.get('session') == _SESSION:
            count_now = len(bpy.data.materials)
            equal = (last_run.get('fingerprint') == result['fingerprint'] and
                     last_run.get('material_count') == count_now)
            result['checks']['2'] = _reason('PASS' if equal else 'FAIL',
                'Second Build kept VFX_B graphs/assignments and global material count' if equal else
                'VFX_B assignments, graph or material count changed on repeated Build')
        if not saved:
            scene[BASELINE_KEY] = json.dumps({'schema': 1, 'session': _SESSION,
                                              'fingerprint': result['fingerprint']}, sort_keys=True)
        scene[OBSERVATION_KEY] = json.dumps({'session': _SESSION,
                                            'fingerprint': result['fingerprint'],
                                            'material_count': len(bpy.data.materials)}, sort_keys=True)
        scene[RUNS_KEY] = count + 1
    else:
        # Do not capture a failed/partial stage as the save/reopen reference.
        scene[RUNS_KEY] = 0
        if OBSERVATION_KEY in scene:
            del scene[OBSERVATION_KEY]
    scene[STATUS_KEY] = result['checks']['1']['status']
    scene[RESULT_KEY] = json.dumps({'checks': result['checks'],
                                    'fingerprint': result['fingerprint'],
                                    'actor_vfx': len(result['vfx_rows'])}, ensure_ascii=False)
    return result


class AEF_OT_ae_si_fx_e332_validate(bpy.types.Operator):
    bl_idname = 'sabershader.ae_si_fx_e332_validate'
    bl_label = 'Inspect Si FX Materials (Read Only)'
    bl_description = 'Inspect seven Si VFX_B materials, saved predecessors and current topology; export JSON without modifying materials'
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            from . import engine
            from . import ae_one_click
            settings = context.scene.aef_sabershader_v8
            selection = engine._aef11_target_objects(context, settings, preview_only=True) or {}
            objects = list(selection.get('objects') or ())
            if not ae_one_click._selected_actor_is_si(objects):
                self.report({'WARNING'}, 'Select the Si actor before validating')
                return {'CANCELLED'}
            mats = list(engine._aef11_materials_from_objects(objects))
            info = engine._xdzr8_v1122_detect_source_intelligence(
                str(getattr(settings, 'universal_texture_folder', '') or ''), objects, mats)
            authorized = (ae_one_click.classify_build(info) == 'AE_VERIFIED' or
                          bool(engine._xdzr8_ae_state(context).get('authorized')))
            if not authorized:
                self.report({'WARNING'}, 'AE source not verified; no Si FX validation run')
                return {'CANCELLED'}
            report = inspect(objects, baseline=_parse_baseline(context.scene))
            result_dir = Path(tempfile.gettempdir())
            path = result_dir / ('SaberShader_AE_Si_E332_Validation_' + uuid.uuid4().hex[:12] + '.json')
            with path.open('x', encoding='utf-8') as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2)
            status = report['checks']['1']['status']
            self.report({'INFO'} if status == 'PASS' else {'WARNING'},
                        'Si VFX_B: %s (%d objects). Report: %s' %
                        (status, len(report['vfx_rows']), str(path)[:150]))
            print('SABERSHADER AE SI VFX VALIDATION:', str(path))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, 'Si FX validation failed: ' + str(exc)[:160])
            return {'CANCELLED'}
