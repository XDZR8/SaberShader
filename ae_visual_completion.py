"""Endfield visual Build completion and scene color management.

This post-stage does not recreate shader nodes. It verifies observable output
from the core Build, applies the authorized scene view transform and records
outline, eye shadow and color outcomes separately. Counters represent actual
changes or independently verified pre-existing materials.

Never run audit/JSON tools, experimental previews, lighting setup, manual LOD
selection or a second core Build from this module. Changes to scene-wide color
management require a verified actor and a successful preparation stage.
"""
from . import engine as _engine

REVISION = 'E3452_AE_VISUAL_POST_1'
SCENE_PREFIX = 'SaberShader_AE_CompleteBuild_'
_ALLOWED_PREPARED = frozenset(('CONFIGURED', 'ALREADY_CONFIGURED'))


def summarize(outline_requested, shells, eye_requested, overlays, guarded):
    """Classify observable Build outcomes without pretending zero == success."""
    if not outline_requested:
        outline = 'SKIPPED_PRESET'
    elif shells > 0:
        outline = 'APPLIED_%d_SHELLS' % shells
    else:
        outline = 'NO_ELIGIBLE_SHELLS'
    if not eye_requested:
        eye = 'DISABLED'
    elif overlays > 0:
        eye = 'APPLIED_%d_OVERLAYS' % overlays
    elif guarded > 0:
        eye = 'LOD_GUARD_ONLY_%d' % guarded
    else:
        # Repeat Builds can preserve an existing validated overlay without
        # creating new ones. No claim of success without actual material proof.
        eye = 'CHECK_EYE_REPORT'
    return outline, eye



def _verified_existing_eye(scene, settings, actor):
    """Read-only source/graph proof for an idempotent AE123 second Build.

    AE123 may return overlays=0 when a previously valid mask is preserved;
    the absence of *new* overlays is not a visual failure in that case.
    """
    try:
        source, _reason = _engine._xdzr8_ae119_source_files(settings)
        if not source:
            return False
        ready = []
        for obj in scene.objects:
            if getattr(obj, 'type', None) != 'MESH':
                continue
            spec = _engine._xdzr8_ae120_parse_eye(getattr(obj, 'name', ''))
            if not (spec and spec['actor'] == actor and
                    spec['part'] == 'eyeshadow' and spec['lod'] == 0):
                continue
            if getattr(obj, 'hide_render', False):
                continue
            slots = getattr(obj, 'material_slots', ())
            if len(slots) != 1:
                return False
            mat = slots[0].material
            valid, _ = _engine._xdzr8_ae125_overlay_graph(mat, source)
            ready.append(bool(valid))
        return len(ready) == 1 and ready[0]
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        return False

def complete_post_build(context, settings, info, objects, autoae, verified_after, eye_result=None):
    """Apply scene color only after a successful, source-verified AE Build.

    Scope is rechecked because view settings affect the *whole scene*; actor
    provenance must not be deduced from a filename. Failure does not re-label
    the already-completed material Build as fully rolled back.
    """
    scene = context.scene
    def store(status, outline='NOT_RUN', eye='NOT_RUN', color='NOT_RUN', detail=''):
        scene[SCENE_PREFIX + 'Status'] = status
        scene[SCENE_PREFIX + 'Outline'] = outline
        scene[SCENE_PREFIX + 'Eyeshadow'] = eye
        scene[SCENE_PREFIX + 'Color'] = color
        scene[SCENE_PREFIX + 'Detail'] = detail[:600]
        return {'status': status, 'outline': outline,
                'eyeshadow': eye, 'color': color, 'detail': detail}

    if not verified_after or not _engine._xdzr8_ae129hf455_is_verified(info):
        return store('SKIPPED_UNVERIFIED')
    if not bool(getattr(settings, 'ae_auto_profile_features', False)):
        return store('DISABLED_BY_USER')
    if not isinstance(autoae, dict) or autoae.get('status') not in _ALLOWED_PREPARED:
        return store('SKIPPED_PREFLIGHT', detail='AE auto profile not configured')
    try:
        owner = _engine._xdzr8_ae_fullsetup_owner_check(scene, info, objects)
        if owner.get('status') != 'READY':
            return store('BLOCKED_OWNER', detail=str(owner.get('status', 'UNKNOWN')))
    except Exception as exc:
        return store('BLOCKED_OWNER', detail=type(exc).__name__ + ': ' + str(exc))
    preset = str(getattr(settings, 'ae123_fidelity_preset', 'BALANCED'))
    outline_wanted = bool(getattr(settings, 'ae_outline_enabled', False))
    eye_wanted = bool(getattr(settings, 'ae123_eye_full_setup', False))
    shells = max(0, int(scene.get('SaberShader_AE110_ShellCount', 0) or 0))
    overlays = max(0, int(scene.get('SaberShader_AE123_EyeOverlays', 0) or 0))
    guards = max(0, int(scene.get('SaberShader_AE123_GuardedLODs', 0) or 0))
    outline, eye = summarize(outline_wanted, shells, eye_wanted, overlays, guards)
    if eye_result is not None:
        result_status = str(eye_result.get('status', 'UNKNOWN'))
        if result_status == 'REPAIRED':
            eye = 'REPAIRED_%d_OVERLAYS' % int(eye_result.get('repaired', 0) or 0)
        elif result_status == 'ALREADY_READY':
            eye = 'PRESERVED_VERIFIED_OVERLAY'
        else:
            eye = result_status
    elif eye in {'CHECK_EYE_REPORT', 'LOD_GUARD_ONLY_%d' % guards}:
        if _verified_existing_eye(scene, settings, str(owner.get('actor', ''))):
            eye = 'PRESERVED_VERIFIED_OVERLAY'
    # In SOURCE mode we still show the original view correction and outline,
    # but do not turn on optional source ramp/color-grade nodes.
    try:
        before = _engine._xdzr8_ae126_capture_cm(scene)
        desired = {'display_device': 'sRGB',
                   'view_transform': _engine._AE126_VIEW, 'look': 'None',
                   'exposure': 0.0, 'gamma': 1.0}
        if all(before[k] == desired[k] for k in desired):
            color = 'ALREADY_PBR_NEUTRAL'
        else:
            actual = _engine._xdzr8_ae126_apply_cm(scene)
            color = 'APPLIED_PBR_NEUTRAL' if actual['view_transform'] == desired['view_transform'] else 'ERROR_VIEW_MISMATCH'
    except Exception as exc:
        return store('PARTIAL', outline, eye, 'ERROR_COLOR_VIEW',
                     'AE126 scene color stage failed safely: %s: %s' % (type(exc).__name__, exc))
    cautions = []
    if outline == 'NO_ELIGIBLE_SHELLS':
        cautions.append('Outline enabled, but AE110 produced no eligible shells')
    if eye_wanted and not (eye == 'PRESERVED_VERIFIED_OVERLAY' or
                           eye.startswith('REPAIRED_') or
                           (eye_result is None and eye.startswith('APPLIED_'))):
        reason = eye_result.get('detail', '') if eye_result else 'Inspect AE123 eye report/materials'
        cautions.append('Eyeshadow not source-verified: ' + str(reason)[:280])
    return store('PARTIAL' if cautions else 'COMPLETE', outline, eye, color,
                 '; '.join(cautions))
