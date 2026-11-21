"""E3.4.5: explicit, native Blender actor QA evidence (NO shader writes).

Creates only Blender Text datablocks, scene evidence pointers and external JSON
reports. FX source materials/images/meshes and all existing Build entry points
remain untouched. This is repeatable QA tooling, not auto-build FX enablement.
"""
from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bpy

from .ae_ui_visibility import ae_developer_tools_visible

from . import ae_fx_universal_core as fxcore
from . import ae_fx_universal as inventory
from . import ae_fx_fidelity_core as fidelity_policy
from . import ae_fx_fidelity as e343
from . import ae_fx_idle_ink as e344
from . import ae_fx_comparison as e341
from . import ae_fx_cross_validation_core as pure

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
PREFIX = 'SaberShader_AE_FX_E345_'
AA2_TEXT = PREFIX + 'AA2BaselineText'
BUILD_TEXT = PREFIX + 'BuildBaselineText'
ACTOR = PREFIX + 'Actor'
PHASES = {m: PREFIX + 'ResultText_' + m for m in pure.MODES}
MAX_BYTES = 8_000_000


def _now():
    return datetime.now(timezone.utc).isoformat()


def _value(value):
    """Stable and bounded Blender socket serialization; no RNA mutation."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 7)
    try:
        return [_value(v) for v in list(value)[:32]]
    except (ValueError, TypeError, AttributeError):
        return str(value)[:128]


def _image_record(img):
    return {'filepath': str(getattr(img, 'filepath', '')),
            'source': str(getattr(img, 'source', '')),
            'colorspace': str(getattr(getattr(img, 'colorspace_settings', None), 'name', '')),
            'alpha_mode': str(getattr(img, 'alpha_mode', '')),
            'size': list(getattr(img, 'size', (0, 0)) or (0, 0)),
            'packed': bool(getattr(img, 'packed_file', None))}


def _tree_record(tree, visited=None):
    if tree is None:
        return {}
    visited = visited if visited is not None else set()
    key = tree.as_pointer()
    if key in visited:
        return {'cycle': True, 'name': tree.name}
    visited.add(key)
    try:
        nodes = []
        for n in sorted(tree.nodes, key=lambda n: n.name):
            image = getattr(n, 'image', None)
            nested = getattr(n, 'node_tree', None)
            nodes.append({
                'name': n.name, 'type': n.bl_idname,
                'attributes': {p: _value(getattr(n, p)) for p in (
                    'operation', 'blend_type', 'data_type', 'interpolation', 'extension',
                    'projection', 'distribution', 'attribute_name', 'use_clamp') if hasattr(n, p)},
                'inputs': [(s.name, _value(s.default_value)) for s in n.inputs
                           if hasattr(s, 'default_value')],
                'image': _image_record(image) if image else None,
                'group': _tree_record(nested, visited) if nested else None,
            })
        links = sorted((l.from_node.name, l.from_socket.identifier, l.to_node.name,
                        l.to_socket.identifier) for l in tree.links)
        return {'nodes': nodes, 'links': links}
    finally:
        visited.remove(key)


def _material_record(mat):
    if mat is None:
        return None
    return {
        'source': str(mat.get('AEF_V11_SourceMaterial', '')),
        'shader': pure.digest(_tree_record(mat.node_tree if mat.use_nodes else None)),
        'use_nodes': bool(mat.use_nodes),
        'blend_method': str(getattr(mat, 'surface_render_method',
                                    getattr(mat, 'blend_method', ''))),
        'diffuse_color': _value(mat.diffuse_color),
        'fake_user': bool(mat.use_fake_user),
        'e343_revision': str(mat.get(e343.M_VARIANT, '')),
        'e344_revision': str(mat.get(e344.M_REV, '')),
    }


def _object_record(obj):
    data = getattr(obj, 'data', None)
    slots = []
    for index, slot in enumerate(getattr(obj, 'material_slots', ())):
        mats = getattr(data, 'materials', ()) or ()
        data_mat = mats[index] if index < len(mats) else None
        active_mat = slot.material
        slots.append({'data': data_mat.name if data_mat else '',
                      'effective': active_mat.name if active_mat else '',
                      'link': str(slot.link)})
    return {
        'actor': fxcore.actor_id(obj.name), 'mesh_data': data.name if data else '',
        'data_users': int(data.users) if data else 0,
        'vertices': len(data.vertices) if data and hasattr(data, 'vertices') else 0,
        'polygons': len(data.polygons) if data and hasattr(data, 'polygons') else 0,
        'parent': obj.parent.name if obj.parent else '',
        'hide_render': bool(obj.hide_render), 'hide_viewport': bool(obj.hide_viewport),
        'hide_set': bool(obj.hide_get()),
        'location': _value(obj.location), 'rotation': _value(obj.rotation_euler),
        'scale': _value(obj.scale), 'slots': slots,
    }


def _session(context, actor):
    """Read-only provenance check with original E343/E344 session guards."""
    scene = context.scene
    objects = [o for o in scene.objects if o.type == 'MESH']
    foreign = [o.name for o in objects if fxcore.actor_id(o.name) != actor and
               (o.get(e343.O_TOKEN, '') or o.get(e344.O_TOKEN, ''))]
    if foreign:
        raise RuntimeError('Another actor has active A/A2 tags: ' + ', '.join(foreign[:3]))
    local = [o for o in objects if fxcore.actor_id(o.name) == actor]
    has_u, has_s = e343.has_active_comparison(local), e344.has_active_comparison(local)
    if has_u and has_s:
        raise RuntimeError('Mixed E343 / E344 A/A2 sessions')
    if has_u:
        a_actor, a, a2, pairs, token = e343._get_active_session(context)
        if a_actor != actor:
            raise RuntimeError('E343 actor mismatch')
        targets = []
        for obj, slot in pairs:
            state = str(obj.get(e343.O_CURRENT, ''))
            if state != 'A2' or obj.material_slots[slot].material != a2:
                raise RuntimeError('E343 A2 is not shown on every tagged mesh')
            targets.append({'object': obj.name, 'slot': slot, 'original': a.name,
                            'staged': a2.name, 'current': state})
        return {'kind': 'E343_UNIVERSAL', 'targets': sorted(targets, key=lambda t: (t['object'], t['slot']))}
    if has_s:
        if actor != pure.SI_ACTOR:
            raise RuntimeError('E344 Si preset tags detected on a non-Si actor')
        si_objs, a, a2, tree = e344._session(context)
        targets = []
        for obj in si_objs:
            state = str(obj.get(e344.O_CURRENT, ''))
            if state != 'A2' or obj.material_slots[0].material != a2:
                raise RuntimeError('E344 A2 is not shown on every Si mesh')
            targets.append({'object': obj.name, 'slot': 0, 'original': a.name,
                            'staged': a2.name, 'current': state})
        return {'kind': 'E344_SI', 'targets': sorted(targets, key=lambda t: t['object'])}
    return {'kind': '', 'targets': []}


def _fx_audit(context, actor, actor_objects):
    rows = inventory.inspect_actor(context, actor_objects, actor=actor, require_verified=True)
    summary = []
    eligibility = 0
    verified = 0
    for row in rows['rows']:
        name, source = row['object'], row['source_material']
        owner = fxcore.source_owner(source)
        entry = dict(row, source_owner=owner)
        supported = fidelity_policy.authoritative_textured_row(entry, actor)
        eligible, why = False, ''
        if supported:
            verified += 1
            obj = context.scene.objects.get(name)
            mat = obj.material_slots[row['slot']].material if obj else None
            try:
                if not mat or mat.library or mat.override_library or not mat.use_nodes:
                    raise RuntimeError('Material unavailable/linked/non-node')
                main = row['texture_slots']['_MainTex']['path']
                main_node = e343._source_node(mat.node_tree, Path(main))
                e343._transparency_mix(mat.node_tree)
                if not e343._color_targets(mat.node_tree, main_node):
                    raise RuntimeError('No separate output-connected _MainTex color path')
                if (obj.library or obj.override_library or obj.data.library or
                        obj.data.override_library or obj.data.users != 1):
                    raise RuntimeError('Shared/linked mesh')
                eligible = True
                eligibility += 1
            except Exception as exc:
                why = str(exc)[:170]
        else:
            why = 'Source JSON/texture provenance not sufficient for E343'
        summary.append({'object': name, 'slot': row['slot'],
                        'source_material': source, 'family': row['family'],
                        'source_proof': row['source_proof'], 'source_json_status': row['source_json_status'],
                        'maintex_status': row.get('texture_slots', {}).get('_MainTex', {}).get('status', ''),
                        'supported_E343': eligible, 'reason_if_unsupported': why})
    si_leak = any(o.get(e344.O_TOKEN, '') for o in context.scene.objects if o.type == 'MESH') or any(
        m.get(e344.M_REV, '') == e344.REVISION for m in bpy.data.materials)
    return {'fx_material_slot_count': len(summary),
            'source_verified_slots': verified, 'eligible_preview_slots': eligibility,
            'families': rows['family_counts'],
            'rows': sorted(summary, key=lambda d: (d['object'], d['slot'])),
            'skipped': rows['skipped'], 'si_preset_leak': si_leak}


def capture(context):
    actor, objs = inventory._manual_scope(context)
    inventory._ae_authorized(context, actor)
    scene = context.scene
    current_session = _session(context, actor)
    from . import engine
    latest = engine._xdzr8_ae_fullsetup_latest_run(scene) or {}
    render = scene.render
    view = scene.view_settings
    # Snapshot all mesh objects and all existing materials/images, including
    # unrelated profiles. This deliberately catches non-actor spillover.
    return {
        'schema': pure.SNAP_SCHEMA, 'revision': pure.REVISION, 'actor': actor,
        'timestamp_utc': _now(), 'blender': '.'.join(str(x) for x in bpy.app.version[:3]),
        'blend_path': str(bpy.data.filepath),
        'source_root': str(Path(inventory._source_folder(context)).resolve()),
        'scene_render': {'engine': str(render.engine), 'frame': int(scene.frame_current),
                         'camera': scene.camera.name if scene.camera else '',
                         'view_transform': str(view.view_transform), 'look': str(view.look),
                         'exposure': round(float(view.exposure), 7),
                         'gamma': round(float(view.gamma), 7)},
        'objects': {o.name: _object_record(o) for o in sorted(scene.objects, key=lambda x: x.name)
                    if o.type == 'MESH'},
        'materials': {m.name: _material_record(m) for m in sorted(bpy.data.materials, key=lambda x: x.name)},
        'images': {i.name: _image_record(i) for i in sorted(bpy.data.images, key=lambda x: x.name)
                   if str(getattr(i, 'source', '')) not in ('VIEWER', 'RENDER_RESULT')},
        'session': current_session,
        'audit': _fx_audit(context, actor, objs),
        'build': {'run_id': str(latest.get('text_name', '')),
                  'run_actor': str(latest.get('actor', '')),
                  'run_event': str(latest.get('event', '')),
                  'run_status': str(latest.get('status', '')),
                  'last_result': str(scene.get('XDZR8_BuildLastResult', ''))},
    }


def _store(scene, key, data):
    if scene.get(key, ''):
        raise RuntimeError('E345 evidence already exists; use Reset E345 Evidence for a new run')
    txt = bpy.data.texts.new(PREFIX + uuid.uuid4().hex[:12])
    txt.use_fake_user = True
    try:
        txt.write(json.dumps(data, sort_keys=True, ensure_ascii=False))
        scene[key] = txt.name
    except Exception:
        txt.use_fake_user = False
        bpy.data.texts.remove(txt)
        raise


def _load(scene, key):
    name = str(scene.get(key, ''))
    txt = bpy.data.texts.get(name) if name else None
    if not txt:
        raise RuntimeError('Missing E345 evidence: ' + key.removeprefix(PREFIX))
    payload = txt.as_string()
    if len(payload.encode('utf-8')) > MAX_BYTES:
        raise RuntimeError('E345 stored evidence is too large')
    return json.loads(payload)


def _export(data, label):
    out = Path(tempfile.gettempdir()) / (PREFIX + label + '_' +
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8] + '.json')
    with out.open('x', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    return str(out)


def _require_no_preview(context, allow_parent):
    actor, objs = inventory._manual_scope(context)
    if _session(context, actor)['kind']:
        raise RuntimeError('Restore E343/E344 A/A2 before this snapshot')
    if not allow_parent and e341.has_active_comparison(objs):
        raise RuntimeError('Restore parent Si E3.4.1 A/B before Repeat Build baseline')
    if allow_parent and e341.has_active_comparison(objs):
        if any(o.get(e341.PROP_CURRENT, '') != 'A' for o in objs if o.get(e341.PROP_TOKEN, '')):
            raise RuntimeError('E3.4.1 must display Original A for the A2 baseline')
    return actor


def baseline_aa2(context):
    actor = _require_no_preview(context, allow_parent=True)
    if context.scene.get(ACTOR, '') and context.scene.get(ACTOR, '') != actor:
        raise RuntimeError('E345 evidence belongs to another actor; reset first')
    snap = capture(context)
    _store(context.scene, AA2_TEXT, snap)
    context.scene[ACTOR] = actor
    return {'status': 'BASELINE_A_A2_SAVED', 'actor': actor}


def validate_phase(context, mode):
    scene = context.scene
    if scene.get(PHASES[mode], ''):
        raise RuntimeError('Phase already recorded; reset E345 for a new run')
    baseline = _load(scene, BUILD_TEXT if mode == 'REPEAT_BUILD' else AA2_TEXT)
    current = capture(context)
    if current['actor'] != scene.get(ACTOR, ''):
        raise RuntimeError('Current actor differs from baseline')
    if mode == 'RESTORED':
        first = _load(scene, PHASES['PREVIEW_A2'])
        if first.get('status') != 'PASS_STATIC':
            raise RuntimeError('Preview A2 must pass before restoring')
    if mode == 'REPEAT_BUILD':
        restored = _load(scene, PHASES['RESTORED'])
        if restored.get('status') != 'PASS_STATIC':
            raise RuntimeError('A2 restore must pass before Repeat Build')
    result = pure.compare(baseline, current, mode)
    result['timestamp_utc'] = _now()
    result['blender'] = '.'.join(str(v) for v in bpy.app.version[:3])
    path = _export(result, mode)
    # Store result even when it fails, so tests cannot be reported as passed later.
    _store(scene, PHASES[mode], result)
    return {'status': result['status'], 'actor': current['actor'],
            'issues': len(result['failures']), 'path': path, 'result': result}


def baseline_build(context):
    actor = _require_no_preview(context, allow_parent=False)
    scene = context.scene
    previous = _load(scene, PHASES['RESTORED'])
    if previous.get('status') != 'PASS_STATIC' or previous.get('actor') != actor:
        raise RuntimeError('Complete A/A2 + Restore tests before Build baseline')
    if scene.get(ACTOR, '') != actor:
        raise RuntimeError('Actor switched since A2 baseline')
    snap = capture(context)
    if snap['audit']['si_preset_leak']:
        raise RuntimeError('E344 staged material/tag still exists; restore before Build')
    if (snap['build']['run_status'] != 'FINISHED' or snap['build']['run_actor'] != actor
            or snap['build']['run_event'] != 'BUILD'):
        raise RuntimeError('Native AE Full Setup completed run for this actor required')
    _store(scene, BUILD_TEXT, snap)
    return {'status': 'BASELINE_FOR_REPEAT_BUILD_SAVED', 'actor': actor,
            'run_id': snap['build']['run_id']}


def export_evidence(context):
    scene = context.scene
    baseline = _load(scene, BUILD_TEXT)
    actor = str(scene.get(ACTOR, ''))
    results = {}
    for mode, key in PHASES.items():
        try:
            results[mode] = _load(scene, key)
        except RuntimeError:
            pass
    data = pure.evidence(actor, results, baseline)
    data['timestamp_utc'] = _now()
    data['blender'] = '.'.join(str(x) for x in bpy.app.version[:3])
    return {'status': data['status'], 'actor': actor,
            'issues': len(data['reasons']), 'path': _export(data, 'ActorEvidence'), 'result': data}


def _read_evidence_file(raw_path):
    if not raw_path:
        raise RuntimeError('Select both actor evidence JSON files')
    path = Path(bpy.path.abspath(raw_path))
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise RuntimeError('Missing/oversized actor evidence file: ' + str(path)[:110])
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or data.get('schema') != pure.EVIDENCE_SCHEMA:
        raise RuntimeError('Expected E345 actor evidence JSON, not a raw snapshot')
    return data


def cross_check(context):
    p = context.scene.aef_ae_fx_e345
    first, second = _read_evidence_file(p.first_evidence), _read_evidence_file(p.second_evidence)
    result = pure.compare_characters(first, second)
    result['timestamp_utc'] = _now()
    result['blender'] = '.'.join(str(x) for x in bpy.app.version[:3])
    return {'status': result['status'], 'issues': len(result['problems']),
            'path': _export(result, 'CrossCharacter'), 'result': result}


def reset(context):
    scene = context.scene
    names = [str(scene.get(k, '')) for k in (AA2_TEXT, BUILD_TEXT, *PHASES.values())]
    # Only remove E345-created Text blocks that are not used by other scenes.
    for key in (AA2_TEXT, BUILD_TEXT, ACTOR, *PHASES.values()):
        if key in scene:
            del scene[key]
    for name in set(names):
        txt = bpy.data.texts.get(name) if name and name.startswith(PREFIX) else None
        if txt is not None and not any(
            s.get(k, '') == name for s in bpy.data.scenes
            for k in (AA2_TEXT, BUILD_TEXT, *PHASES.values())):
            txt.use_fake_user = False
            bpy.data.texts.remove(txt)
    return {'status': 'E345_EVIDENCE_RESET'}


class AEF_PG_ae_fx_cross_validation_e345(bpy.types.PropertyGroup):
    first_evidence: bpy.props.StringProperty(name='Si Actor Evidence', subtype='FILE_PATH', default='')
    second_evidence: bpy.props.StringProperty(name='Second Actor Evidence', subtype='FILE_PATH', default='')


class _Base(bpy.types.Operator):
    bl_options = {'REGISTER'}
    action = None
    def execute(self, context):
        try:
            result = self.action(context)
            path = result.get('path', '')
            if path:
                print('SABERSHADER E3.4.5 JSON:', path)
            self.report({'INFO'} if result['status'] not in ('FAIL', 'INCOMPLETE_OR_FAIL')
                        else {'WARNING'}, 'E345 %s | issues=%d | %s' % (
                result['status'], result.get('issues', 0), path[:112]))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, 'E345: ' + str(exc)[:175])
            return {'CANCELLED'}


class AEF_OT_ae_e345_baseline_aa2(_Base):
    bl_idname='sabershader.ae_e345_baseline_aa2'; bl_label='1. Capture A / A2 Baseline'
    bl_description='Capture shader/texture/mesh safety fingerprint in Blender Text (no shader edits)'
    action=staticmethod(baseline_aa2)


class AEF_OT_ae_e345_preview(_Base):
    bl_idname='sabershader.ae_e345_preview'; bl_label='2. Validate Visible A2'
    bl_description='Compare only guarded E343/E344 A2 slots against captured original material state'
    action=staticmethod(lambda context: validate_phase(context, 'PREVIEW_A2'))


class AEF_OT_ae_e345_restore(_Base):
    bl_idname='sabershader.ae_e345_restore'; bl_label='3. Validate Restored A'
    bl_description='Prove A2 materials removed and all scene mesh/image/material fingerprints restored'
    action=staticmethod(lambda context: validate_phase(context, 'RESTORED'))


class AEF_OT_ae_e345_build_baseline(_Base):
    bl_idname='sabershader.ae_e345_build_baseline'; bl_label='4. Capture Build Baseline'
    bl_description='After restoring all A/B experiments, capture first completed AE Build state'
    action=staticmethod(baseline_build)


class AEF_OT_ae_e345_repeat(_Base):
    bl_idname='sabershader.ae_e345_repeat'; bl_label='5. Validate Repeat Build'
    bl_description='Require a different completed AE Full Setup execution plus identical shader/mesh/texture signatures'
    action=staticmethod(lambda context: validate_phase(context, 'REPEAT_BUILD'))


class AEF_OT_ae_e345_export(_Base):
    bl_idname='sabershader.ae_e345_export'; bl_label='6. Export Actor Evidence'
    bl_description='Write evidence with explicit PASS/INCOMPLETE markers; does not claim in-game visual parity'
    action=staticmethod(export_evidence)


class AEF_OT_ae_e345_cross(_Base):
    bl_idname='sabershader.ae_e345_cross'; bl_label='Compare Si + Second AE Actor'
    bl_description='Compare two independently completed E345 actor evidence JSON files'
    action=staticmethod(cross_check)


class AEF_OT_ae_e345_reset(_Base):
    bl_idname='sabershader.ae_e345_reset'; bl_label='Reset E345 Evidence'
    bl_description='Delete only locally recorded E345 QA snapshots/results, never shaders or source files'
    bl_options={'REGISTER', 'UNDO'}
    action=staticmethod(reset)


class AEF_PT_ae_fx_cross_validation_e345(bpy.types.Panel):
    bl_label='Cross-Character FX Validation'
    bl_idname='AEF_PT_ae_fx_cross_validation_e345'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_endfield';bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls, context):
        return ae_developer_tools_visible(context)

    def draw(self, context):
        layout=self.layout
        layout.label(text='Read-only FX QA; evidence stored in .blend Text', icon='CHECKMARK')
        layout.label(text='Use a saved copy / one verified AE actor')
        layout.operator('sabershader.ae_e345_baseline_aa2', icon='DUPLICATE')
        layout.operator('sabershader.ae_e345_preview', icon='SHADING_TEXTURE')
        layout.operator('sabershader.ae_e345_restore', icon='LOOP_BACK')
        layout.separator()
        layout.label(text='Restore Si E341 parent before Build baseline')
        layout.operator('sabershader.ae_e345_build_baseline', icon='DOCUMENTS')
        layout.label(text='Run standard Build again before step 5')
        layout.operator('sabershader.ae_e345_repeat', icon='FILE_REFRESH')
        layout.operator('sabershader.ae_e345_export', icon='TEXT')
        layout.separator()
        props = getattr(context.scene, 'aef_ae_fx_e345', None)
        if props is not None:
            layout.prop(props, 'first_evidence')
            layout.prop(props, 'second_evidence')
        layout.operator('sabershader.ae_e345_cross', icon='CHECKMARK')
        layout.operator('sabershader.ae_e345_reset', icon='TRASH')
        layout.label(text='PASS_STATIC is not a visual/game fidelity pass')
