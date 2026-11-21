"""E3.4.5.3: verify/recover the authored AE eyeshadow mask after main Build.

The legacy AE123 stage is still the single owner of the actual overlay nodes,
LOD policy and reversible original-material state. This module does NOT make a
second shader Build or guess masks from mesh appearance. It asks AE123 to retry
only if the *actual LOD0 material graph* was not source-verified after Build.
"""

from . import engine as _engine

REVISION = 'E3453_AE_EYESHADOW_BUILD_1'
_PREFIX = 'SaberShader_AE_EyeBuildE3453_'
_READY = frozenset(('ALREADY_READY', 'REPAIRED'))
_ALLOWED_PREPARED = frozenset(('CONFIGURED', 'ALREADY_CONFIGURED'))


def _store(scene, status, *, actor='', detail='', repaired=0):
    scene[_PREFIX + 'Revision'] = REVISION
    scene[_PREFIX + 'Status'] = status
    scene[_PREFIX + 'Actor'] = actor
    scene[_PREFIX + 'Repaired'] = int(repaired)
    scene[_PREFIX + 'Detail'] = str(detail)[:700]
    return {'status': status, 'actor': actor, 'detail': str(detail),
            'repaired': int(repaired), 'ready': status in _READY}


def _primary_eye(scene, actor):
    matches = []
    for obj in scene.objects:
        if getattr(obj, 'type', None) != 'MESH':
            continue
        if bool(obj.get('XDZR8_AE110_Outline', False)):
            continue
        spec = _engine._xdzr8_ae120_parse_eye(getattr(obj, 'name', ''))
        if spec and spec['actor'] == actor and spec['part'] == 'eyeshadow' and spec['lod'] == 0:
            matches.append(obj)
    return matches


def _valid_mask(obj, source):
    """Inspect actual material, path and UV rather than stale AE119/123 tags."""
    if bool(getattr(obj, 'hide_render', False)) or _engine._xdzr8_ae120_is_hidden(obj):
        return False, 'LOD0_HIDDEN'
    mesh = getattr(obj, 'data', None)
    uv = getattr(mesh, 'uv_layers', None)
    if not uv or not uv.get('UV0'):
        return False, 'MISSING_UV0'
    slots = getattr(obj, 'material_slots', ())
    if len(slots) != 1 or getattr(slots[0], 'material', None) is None:
        return False, 'NON_UNIQUE_MATERIAL_SLOT'
    mat = slots[0].material
    ok, reason = _engine._xdzr8_ae125_overlay_graph(mat, source)
    return bool(ok), reason


def ensure_eye_overlay(context, settings, info, objects, autoae, verified_after):
    """Guarded post-Build recovery; no manual operator or extra material Build.

    When AE123 already succeeded, this does not call it again. On a failed
    mask graph, retry the *same* source-verified AE123 function once; preserve
    its custom-material and prior-state policies. Partial states are surfaced.
    """
    scene = context.scene
    if not verified_after or not _engine._xdzr8_ae129hf455_is_verified(info):
        return _store(scene, 'SKIPPED_UNVERIFIED')
    if not bool(getattr(settings, 'ae_auto_profile_features', False)):
        return _store(scene, 'DISABLED_BY_USER')
    if not isinstance(autoae, dict) or autoae.get('status') not in _ALLOWED_PREPARED:
        return _store(scene, 'SKIPPED_PREFLIGHT')
    if not bool(getattr(settings, 'ae123_eye_full_setup', False)):
        return _store(scene, 'DISABLED_EYE_SETUP')
    try:
        owner = _engine._xdzr8_ae_fullsetup_owner_check(scene, info, objects)
        if owner.get('status') != 'READY':
            return _store(scene, 'BLOCKED_OWNER', detail=str(owner.get('status', 'UNKNOWN')))
        actor, reason = _engine._xdzr8_ae123_actor(context, settings, objects, info)
        if not actor:
            return _store(scene, 'BLOCKED_ACTOR_SOURCE', detail=reason)
        # The source resolver verifies the exact _BaseMap, _UseGrayAsAlpha=1,
        # and material provenance. An arbitrary white diffuse is NEVER a mask.
        source, reason = _engine._xdzr8_ae119_source_files(settings)
        if source is None:
            return _store(scene, 'BLOCKED_MISSING_MASK', actor=actor, detail=reason)
        primaries = _primary_eye(scene, actor)
        if len(primaries) != 1:
            return _store(scene, 'BLOCKED_EYESHADOW_LOD0', actor=actor,
                          detail='Expected exactly one eyeshadow LOD0; found %d' % len(primaries))
        obj = primaries[0]
        ok, reason = _valid_mask(obj, source)
        if ok:
            return _store(scene, 'ALREADY_READY', actor=actor,
                          detail='Verified source red-channel alpha mask and LOD0 material output')
        # Retry only via AE123's existing source/owner guards and reversibility.
        # A deliberate manual assignment is not overridden by that function.
        attempt = _engine._xdzr8_ae123_eye_full_setup(context, settings, objects, info)
        ok_after, reason_after = _valid_mask(obj, source)
        if ok_after:
            return _store(scene, 'REPAIRED', actor=actor,
                          repaired=int(attempt.get('overlays', 0) or 0),
                          detail='AE123 recovered LOD0 mask after Build (%s)' % reason)
        notes = '; '.join(str(x) for x in attempt.get('notes', ()) if x)[:420]
        return _store(scene, 'NEEDS_ATTENTION', actor=actor,
                      detail='Mask %s -> %s; AE123 %s; %s' %
                      (reason, reason_after, attempt.get('status', 'UNKNOWN'), notes))
    except Exception as exc:
        return _store(scene, 'ERROR_SAFE', detail='%s: %s' % (type(exc).__name__, exc))
