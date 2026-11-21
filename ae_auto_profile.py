"""Verified Endfield complete visual Build flags (E3.4.5.2).

The AE Full Setup in engine.py is already part of the main Build, but its
initial defaults intentionally skip previously built .blend files. 
This module enables the supported final-stage shader flags on every verified
AE Build, including previously built projects whose False values are explicit
RNA properties. It does not overwrite numeric tuning or source-derived data. It never invokes preview/restore/delete,
changes render engine, creates scene lights, selects LODs, or edits shader
nodes directly. Execution is gated by the SAME current AE source and single-
actor ownership checks as the main guarded AE Build.
"""
from __future__ import annotations

from . import engine as _engine

REVISION = 'AE_AUTO_PROFILE_E3452_COMPLETE_1'

# Only supported final stages consumed by the existing legacy Build.
# These toggles are guaranteed ON for verified AE when the complete-Build switch
# is enabled, even in older .blend scenes. Numeric calibration and shader source
# proof remain under the engine's original guards. The SOURCE preset still
# excludes any additional stylization.
DEFAULT_FINAL_FLAGS = (
    'ae_shading_enabled',                 # verified _DiffRampMap only
    'ae_hair_enabled',                    # source-verified AE hair
    'ae_cloth_spec_enabled',              # verified AE cloth only
    'ae_eyes_enabled',                    # exact AE iris / MatCap source
    'ae_lighting_polish_enabled',         # color-only material shading polish
    'ae126_grade_enabled',               # bounded AE material grade nodes
    'ae129hf451_face_enabled',           # face light recovery
    'ae129hf452_face_probe',             # scene-lit face response
    'ae129hf45_enabled',                 # hair rim, final view
    'ae129hf4566_comp_build_enabled',    # final hair highlight compression
    'ae_outline_enabled',                # guarded AE silhouette only
    'ae123_eye_full_setup',              # eye/lid LOD0 guard (already default)
    'ae123_eye_guard_lods',              # preserve iris/eye LOD integrity
    'ae_cleanup_auto_build',             # reversible helper hiding only
)

# SOURCE is the source/no-calibration preset: do not silently activate any
# extra shader grading, stylized hair/cloth/eye layers or the source ramp.
# HF2 normal recovery was source-verified specifically for Wulfa. Do not
# enable these on Si or an arbitrary character with _HN/_RS textures.
WULFA_FINAL_FLAGS = (
    'ae129hf2_enabled', 'ae129hf2_cloth_enabled',
    'ae129hf2_hair02_enabled', 'ae129hf454_hf2_auto_recovery',
)

# Debug outputs and face lighting comparisons are not final material output.
# Complete Build selects the already-validated SCENE face probe and final
# preview modes; these are still user-selectable with complete mode disabled.
FINAL_VIEW_ENUMS = (
    ('ae129hf451_face_mode', 'SCENE'),
    ('ae129hf45_preview', 'FINAL'),
    ('ae_hair_preview', 'FINAL'),
    ('ae129hf2_debug', 'FINAL'),
    ('ae129hf3_preview', 'FINAL'),
    ('ae129hf4_preview', 'FINAL'),
    ('ae129hf43_preview', 'FINAL'),
)

SOURCE_EXCLUDE = {
    'ae_shading_enabled', 'ae_hair_enabled', 'ae_cloth_spec_enabled',
    'ae_eyes_enabled', 'ae_lighting_polish_enabled', 'ae126_grade_enabled',
    'ae129hf451_face_enabled', 'ae129hf452_face_probe',
    'ae129hf45_enabled', 'ae129hf4566_comp_build_enabled',
}


def _explicit(settings, key):
    """Fail closed where Blender cannot tell default RNA from a user value."""
    fn = getattr(settings, 'is_property_set', None)
    if not callable(fn):
        return True
    try:
        return bool(fn(key))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return True


def _enabled(settings):
    return bool(getattr(settings, 'ae_auto_profile_features', False))


def _guard(scene, info, objects):
    if not _engine._xdzr8_ae129hf455_is_verified(info):
        return 'SKIP_UNVERIFIED'
    try:
        checked = _engine._xdzr8_ae_fullsetup_owner_check(scene, info, objects)
    except Exception:
        return 'BLOCKED_PREFLIGHT_ERROR'
    return 'READY' if checked.get('status') == 'READY' else checked.get('status', 'BLOCKED')


def prepare(scene, settings, info, objects):
    """Enable the final visual AE stages on every verified Build.

    This intentionally promotes explicitly disabled stage toggles to True
    under the user-enabled Complete AE Build mode. Numeric settings, SOURCE
    preset, and unsupported preview operators remain untouched.
    """
    result = {'status':'SKIPPED', 'changed': [], 'preserved': [],
              'overridden': [], 'skipped': [], 'revision':REVISION, 'snapshots': []}
    if not _enabled(settings):
        result['status'] = 'DISABLED'
        return result
    gate = _guard(scene, info, objects)
    if gate != 'READY':
        result['status'] = gate
        return result
    source_preset = str(getattr(settings,'ae123_fidelity_preset','BALANCED')) == 'SOURCE'
    is_wulfa = bool(_engine._xdzr8_ae129hf455_is_wulfa(info)) if not source_preset else False
    try:
        final_flags = DEFAULT_FINAL_FLAGS + (WULFA_FINAL_FLAGS if is_wulfa else ())
        for key in final_flags:
            if source_preset and key in SOURCE_EXCLUDE:
                result['skipped'].append((key,'SOURCE_PRESET_PRESERVED'))
                continue
            if not hasattr(settings, key):
                result['skipped'].append((key, 'UNKNOWN_RNA_PROPERTY'))
                continue
            before = getattr(settings, key)
            if bool(before):
                result['preserved'].append(key)
                continue
            # Track RNA explicitness exactly for cancellation rollback. An
            # explicit False is intentionally overridden in Complete Build.
            was_explicit = _explicit(settings, key)
            result['snapshots'].append((key, before, was_explicit))
            setattr(settings, key, True)
            result['changed'].append(key)
            if was_explicit:
                result['overridden'].append(key)
        if not source_preset:
            for key, desired in FINAL_VIEW_ENUMS:
                if not hasattr(settings, key):
                    result['skipped'].append((key, 'UNKNOWN_RNA_PROPERTY'))
                    continue
                before = getattr(settings, key)
                if before == desired:
                    result['preserved'].append(key)
                    continue
                was_explicit = _explicit(settings, key)
                result['snapshots'].append((key, before, was_explicit))
                setattr(settings, key, desired)
                result['changed'].append(key)
                if was_explicit:
                    result['overridden'].append(key)
    except Exception as exc:
        failures = rollback(settings, result)
        result['status'] = 'ROLLBACK_INCOMPLETE' if failures else 'ERROR_ROLLED_BACK'
        result['error'] = repr(exc)
        result['rollback_errors'] = failures
        return result
    result['status'] = 'CONFIGURED' if result['changed'] else 'ALREADY_CONFIGURED'
    # Intentional exclusions: the stable AE Build clears GN preview; a LOD
    # switch changes source-object visibility; scene-light creation changes
    # user lights, and visual hair labs can stack speculative highlights.
    result['manual'] = (
        'GN Ink preview', 'LOD selector', 'Hair Fidelity experimental A/B',
        'scene light rig', 'restore/delete', 'diagnostic previews',
    )
    return result


def rollback(settings, result):
    errors = []
    for key, before, was_explicit in reversed(result.get('snapshots', ())):
        try:
            if not was_explicit and hasattr(settings, 'property_unset'):
                settings.property_unset(key)
            else:
                setattr(settings, key, before)
        except Exception as exc:
            errors.append(key+': '+str(exc))
    result['snapshots'] = []
    return errors


def commit(scene, result):
    scene['SaberShader_AE_AutoProfile_Revision'] = REVISION
    scene['SaberShader_AE_AutoProfile_Status'] = result.get('status', 'UNKNOWN')
    scene['SaberShader_AE_AutoProfile_Changed'] = len(result.get('changed', ()))
    scene['SaberShader_AE_AutoProfile_Preserved'] = len(result.get('preserved', ()))
    scene['SaberShader_AE_AutoProfile_Overrides'] = len(result.get('overridden', ()))
    scene['SaberShader_AE_AutoProfile_Skipped'] = len(result.get('skipped', ()))
