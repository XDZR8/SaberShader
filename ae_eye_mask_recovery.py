"""Source-aware eye shadow recovery after the Endfield material Build.

Reuse the verified source-mask constructor and its ownership snapshot. This
module locates source files through the configured or Build-effective folder,
checks the eye shadow LOD0 material graph and repairs only when necessary.

An existing valid material is retained. A missing or ambiguous UV layer is
not guessed, and a failed repair must produce a diagnostic rather than a
false success status. Debug JSON/text output is generated on request only.
"""

import json
from pathlib import Path

import bpy
from . import engine as _engine

REVISION = 'E3455_EYE_UV_LAYER_RECOVERY_1'
_PREFIX = 'SaberShader_AE_EyeBuildE3454_'
_READY = frozenset(('ALREADY_READY', 'REPAIRED'))
_ALLOWED = frozenset(('CONFIGURED', 'ALREADY_CONFIGURED'))
_REPORT = 'SaberShader_E3455_Eye_Build_Diagnostic'


class _SourceSettings:
    """Read-only settings view for source-dependent engine functions.

    Does not mutate the artist's configured path or any numeric tuning.
    """
    def __init__(self, original, folder):
        self._original = original
        self.universal_texture_folder = folder

    def __getattr__(self, key):
        return getattr(self._original, key)


def _candidate_roots(settings, scene):
    folders = (
        ('CONFIGURED', str(getattr(settings, 'universal_texture_folder', '') or '').strip()),
        ('BUILD_EFFECTIVE', str(scene.get('SaberShader_AEStateV1_EffectiveSourceFolder', '') or '').strip()),
    )
    seen = set()
    for label, folder in folders:
        if not folder:
            continue
        normalized = folder.casefold().rstrip('\\/')
        if normalized in seen:
            continue
        seen.add(normalized)
        yield label, folder


def _source_for_actor(settings, scene, actor):
    problems = []
    for label, folder in _candidate_roots(settings, scene):
        proxy = _SourceSettings(settings, folder)
        try:
            iris = _engine._xdzr8_ae120_source_proof(proxy, actor)
            if not iris:
                problems.append(label + ': matching actor iris JSON unavailable')
                continue
            source, reason = _engine._xdzr8_ae119_source_files(proxy)
            if source:
                return proxy, source, label, '', problems
            problems.append(label + ': ' + str(reason))
        except (ValueError, TypeError, OSError, AttributeError, RuntimeError) as exc:
            problems.append(label + ': ' + type(exc).__name__ + ': ' + str(exc))
    return None, None, '', '; '.join(problems) or 'No source folder configured or recovered', problems


def _store(scene, status, *, actor='', detail='', repaired=0, source_mode='', material='', graph=''):
    scene[_PREFIX + 'Revision'] = REVISION
    scene[_PREFIX + 'Status'] = str(status)
    scene[_PREFIX + 'Actor'] = str(actor)
    scene[_PREFIX + 'Repaired'] = int(repaired)
    scene[_PREFIX + 'Detail'] = str(detail)[:1400]
    scene[_PREFIX + 'SourceMode'] = str(source_mode)
    scene[_PREFIX + 'Material'] = str(material)[:200]
    scene[_PREFIX + 'Graph'] = str(graph)[:200]
    return {'status': status, 'actor': actor, 'detail': str(detail),
            'repaired': int(repaired), 'ready': status in _READY,
            'source_mode': source_mode, 'material': material, 'graph': graph}


def _primary_eyes(scene, actor):
    result = []
    for obj in scene.objects:
        if getattr(obj, 'type', None) != 'MESH' or bool(obj.get('XDZR8_AE110_Outline', False)):
            continue
        spec = _engine._xdzr8_ae120_parse_eye(getattr(obj, 'name', ''))
        if spec and spec['actor'] == actor and spec['part'] == 'eyeshadow' and spec['lod'] == 0:
            result.append(obj)
    return result


def _mask_state(obj, source):
    slots = getattr(obj, 'material_slots', ())
    mat = slots[0].material if len(slots) == 1 else None
    name = str(getattr(mat, 'name', '') or '')
    if bool(getattr(obj, 'hide_render', False)) or _engine._xdzr8_ae120_is_hidden(obj):
        return False, 'LOD0_HIDDEN', name
    uv_name, uv_reason = _engine._xdzr8_ae123_eye_uv_layer(obj)
    if not uv_name:
        return False, uv_reason, name
    if len(slots) != 1 or mat is None:
        return False, 'MISSING_OR_MULTIPLE_MATERIAL_SLOTS', name
    ok, reason = _engine._xdzr8_ae125_overlay_graph(mat, source)
    if ok and not _engine._xdzr8_ae125_overlay_uv_correct(mat, uv_name):
        return False, 'MASK_UV_LAYER_MISMATCH: ' + uv_name, name
    return bool(ok), str(reason), name


def ensure_eye_overlay(context, settings, info, objects, autoae, verified_after):
    scene = context.scene
    if not bool(verified_after) or not _engine._xdzr8_ae129hf455_is_verified(info):
        return _store(scene, 'SKIPPED_UNVERIFIED',
                      detail='Current AE Build source verification did not commit')
    if not bool(getattr(settings, 'ae_auto_profile_features', False)):
        return _store(scene, 'DISABLED_BY_USER', detail='Complete AE Visual Build unchecked')
    if not isinstance(autoae, dict) or autoae.get('status') not in _ALLOWED:
        return _store(scene, 'BLOCKED_PREFLIGHT',
                      detail='AE full visual settings: ' + str((autoae or {}).get('status', 'none')))
    if not bool(getattr(settings, 'ae123_eye_full_setup', False)):
        return _store(scene, 'DISABLED_EYE_SETUP', detail='AE123 eye setup switch OFF')
    try:
        owner = _engine._xdzr8_ae_fullsetup_owner_check(scene, info, objects)
        if owner.get('status') != 'READY' or not owner.get('actor'):
            return _store(scene, 'BLOCKED_OWNER', detail='Actor owner: ' + str(owner.get('status')))
        actor = str(owner['actor']).casefold()
        proxy, source, mode, error, _issues = _source_for_actor(settings, scene, actor)
        if not source:
            return _store(scene, 'BLOCKED_SOURCE_FILES', actor=actor, detail=error)
        # Reuse the EXACT source/actor gate in AE123, not filename plausibility.
        verified_actor, reason = _engine._xdzr8_ae123_actor(context, proxy, objects, info)
        if verified_actor != actor:
            return _store(scene, 'BLOCKED_ACTOR_PROOF', actor=actor, detail=str(reason))
        eyes = _primary_eyes(scene, actor)
        if len(eyes) != 1:
            return _store(scene, 'BLOCKED_EYESHADOW_LOD0', actor=actor, source_mode=mode,
                          detail='Expected 1 exact LOD0 eyeshadow, found %d' % len(eyes))
        obj = eyes[0]
        ok, graph, material = _mask_state(obj, source)
        if ok:
            return _store(scene, 'ALREADY_READY', actor=actor, source_mode=mode,
                          graph=graph, material=material, detail='Exact source mask reaches surface')
        old_material = material
        attempt = _engine._xdzr8_ae123_eye_full_setup(context, proxy, objects, info)
        ok_after, after, material_after = _mask_state(obj, source)
        notes = '; '.join(str(x) for x in (attempt.get('notes') or []) if x)[:900]
        if ok_after:
            return _store(scene, 'REPAIRED', actor=actor, source_mode=mode,
                          material=material_after, graph=after,
                          repaired=int(attempt.get('overlays', 0) or 0),
                          detail='AE123 %s; before=%s [%s]; after=%s [%s]; %s' %
                          (attempt.get('status'), old_material, graph, material_after, after, notes))
        return _store(scene, 'NEEDS_ATTENTION', actor=actor, source_mode=mode,
                      material=material_after, graph=after,
                      detail='Before=%s [%s]; after=%s [%s]; AE123=%s; %s' %
                      (old_material, graph, material_after, after, attempt.get('status'), notes))
    except Exception as exc:
        return _store(scene, 'ERROR_SAFE', detail='%s: %s' % (type(exc).__name__, exc))


def inspect(context):
    """Read-only report independent of previous stored AE123 counters."""
    scene = context.scene
    settings = scene.aef_sabershader_v8
    actor = str(scene.get('SaberShader_AEStateV1_ActorId', '') or '').casefold()
    if not actor:
        active = getattr(context, 'active_object', None)
        spec = _engine._xdzr8_ae120_parse_eye(getattr(active, 'name', ''))
        actor = spec['actor'] if spec else ''
    row = {'revision': REVISION, 'actor': actor,
           'ae_state': str(scene.get('SaberShader_AEStateV1_Status', '')),
           'previous_stage': str(scene.get(_PREFIX + 'Status', '')),
           'previous_detail': str(scene.get(_PREFIX + 'Detail', '')),
           'complete_build': bool(getattr(settings, 'ae_auto_profile_features', False)),
           'eye_build': bool(getattr(settings, 'ae123_eye_full_setup', False)),
           'objects': []}
    if not actor:
        row['issue'] = 'No AE actor in last Build; select exact S_actor_*_eyeshadow_*_lod0'
        return row
    _proxy, source, mode, error, attempts = _source_for_actor(settings, scene, actor)
    row['source_mode'] = mode
    row['source_attempts'] = attempts
    row['source_ready'] = bool(source)
    if not source:
        row['source_issue'] = error
    for obj in _primary_eyes(scene, actor):
        mat = (obj.material_slots[0].material if len(obj.material_slots) == 1 else None)
        valid, reason, mat_name = _mask_state(obj, source) if source else (False,'SOURCE_UNAVAILABLE',getattr(mat,'name',''))
        uv_name, uv_reason = _engine._xdzr8_ae123_eye_uv_layer(obj)
        uv_names = [str(getattr(layer, 'name', layer)) for layer in getattr(obj.data, 'uv_layers', ())]
        row['objects'].append({
            'object': obj.name, 'material': mat_name, 'graph_valid': valid,
            'uv_layers': uv_names, 'selected_uv': uv_name, 'uv_decision': uv_reason,
            'graph_reason': reason, 'mesh_users': int(getattr(obj.data, 'users', 0)),
            'slot_count': len(obj.material_slots),
            'slot_link': str(obj.material_slots[0].link) if len(obj.material_slots) else '',
            'uv0': bool(obj.data.uv_layers.get('UV0')),
            'uv_layer_count': len(uv_names),
            'hidden_render': bool(obj.hide_render),
            'hidden_viewport': bool(_engine._xdzr8_ae120_is_hidden(obj)),
            'manual_eye_tag': bool(obj.get(_engine._AE119_ORIGINAL, '') or obj.get(_engine._AE122_STATE, '')),
            'auto_eye_tag': bool(obj.get(_engine._AE123_EYE_STATE, '')),
        })
    if not row['objects']:
        row['issue'] = 'No exact eyeshadow LOD0 for actor in this scene'
    return row


class AEF_OT_ae_eye_diagnose_e3454(bpy.types.Operator):
    bl_idname = 'sabershader.ae_eye_diagnose_e3454'
    bl_label = 'Inspect Eye Shadow Build'
    bl_description = 'Read-only: inspect source mask, material assignment, and available UV maps after AE Build'
    bl_options = {'REGISTER'}

    def execute(self, context):
        data = inspect(context)
        block = bpy.data.texts.get(_REPORT) or bpy.data.texts.new(_REPORT)
        block.clear()
        block.write(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        self.report({'INFO'}, 'Eye diagnostic: open Text Editor > ' + _REPORT)
        return {'FINISHED'}
