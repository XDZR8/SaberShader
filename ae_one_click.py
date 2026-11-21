"""Build orchestration for every SaberShader profile.

The main Build operator runs once. Only source-verified Arknights: Endfield
actors enter the Endfield-specific visual pipeline (outline, shading, eyes,
scene color and verified FX). In particular, Si receives its established
single-trail VFX appearance after the material build.

Safety contract:
- Source names alone never authorize Endfield-specific changes.
- A/B research previews and JSON export are not part of normal Build.
- Rebuilds temporarily suspend and restore Si's automatic VFX material.
- Failure in an optional stage must be reported, not silently presented as
  completion or used to affect another profile.

Historical revision tokens in imported module names and scene keys are
compatibility identifiers, not names intended for the Blender interface.
"""

import json

import bpy

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
from . import engine as _engine
from . import ae_material_sources as _source
from . import ae_fx_ink_sources as _fx
from . import ae_fx_opacity as _e31
from . import ae_vfx_placeholders as _e32
from . import ae_fx_layered_materials as _e331
from . import ae_fx_validation as _fxqa
from . import ae_auto_profile as _autoae
from . import ae_visual_completion as _visual
from . import ae_eye_mask_recovery as _eyebuild
from . import ae_fx_comparison as _ab341
from . import ae_fx_universal as _universalfx
from . import ae_fx_fidelity as _e343
from . import ae_fx_idle_ink as _e344
from . import ae_fx_auto_appearance as _auto_a

SABERSHADER_AE_ONE_CLICK_REVISION = 'E3_4_5_4_EYESHADOW_BUILD_2'


def classify_build(info):
    """Choose a *verified* AE route. Naming evidence never grants AE permission."""
    return 'AE_VERIFIED' if _engine._xdzr8_ae129hf455_is_verified(info) else 'OTHER_OR_UNVERIFIED'


def _selected_actor_is_si(objects):
    """Avoid auditing an unrelated Si asset while building another AE actor."""
    for obj in objects or ():
        if 'jsspsi' in str(getattr(obj, 'name', '')).casefold():
            return True
        for mat in getattr(getattr(obj, 'data', None), 'materials', ()) or ():
            if mat is None:
                continue
            try:
                name = str(mat.get('AEF_V11_SourceMaterial', '') or '')
            except Exception:
                name = ''
            if 'jsspsi' in name.casefold():
                return True
    return False


def source_audit_after_build(context, info, *, target_objects=None, write_report=True):
    """Inspect only exact Si actor meshes after a verified Endfield Build.

    Retains the original dictionary's read-only matching policy. A distinct
    report path prevents accidental replacement of the user's E1 diagnostics.
    """
    if classify_build(info) != 'AE_VERIFIED':
        return {'status': 'SKIPPED_UNVERIFIED'}
    if not _selected_actor_is_si(target_objects):
        return {'status': 'SKIPPED_NOT_SI'}
    catalog = _source._source_catalog()
    result = _source.inspect_scene(context, catalog=catalog)
    if not result['mesh_count']:
        return {'status': 'SKIPPED_NOT_SI'}
    path = None
    if write_report:
        path = _source._unique_report_path()
        with path.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
    counts = result.get('status_counts', {})
    scene = context.scene
    scene['SaberShader_AE_SourceAudit_LastActor'] = 'Si'
    scene['SaberShader_AE_SourceAudit_LastStatus'] = 'COMPLETE'
    scene['SaberShader_AE_SourceAudit_LastPath'] = str(path or '')
    scene['SaberShader_AE_SourceAudit_LastMeshes'] = int(result['mesh_count'])
    scene['SaberShader_AE_SourceAudit_LastFXUnbound'] = int(counts.get('FX_SOURCE_TEXTURES_UNBOUND', 0))
    scene['SaberShader_AE_SourceAudit_LastGeneratedHelpers'] = int(counts.get('GENERATED_SABERSHADER_HELPER', 0))
    return {'status': 'AUDITED_SI', 'path': str(path or ''),
            'meshes': result['mesh_count'], 'counts': counts}


class AEF_OT_sabershader_one_click_build(bpy.types.Operator):
    bl_idname = 'sabershader.one_click_build'
    bl_label = 'Build SaberShader'
    bl_description = ('One main Build for all profiles: verified Endfield uses the guarded AE Full Setup '
                      'and full visual stages (including color management); other profiles retain their existing pipeline')
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        if bool(scene.get('XDZR8_BuildRunning', False)):
            self.report({'WARNING'}, 'SaberShader Build is already running')
            return {'CANCELLED'}
        autoae = None
        settings = None
        a_suspended = False
        objects = []
        try:
            settings = scene.aef_sabershader_v8
            selection = _engine._aef11_target_objects(context, settings, preview_only=True) or {}
            objects = list(selection.get('objects') or ())
            if not objects:
                self.report({'WARNING'}, 'No character meshes detected. Select the armature or character')
                return {'CANCELLED'}
            materials = list(_engine._aef11_materials_from_objects(objects))
            info = _engine._xdzr8_v1122_detect_source_intelligence(
                str(getattr(settings, 'universal_texture_folder', '') or ''), objects, materials)
            ae_verified = classify_build(info) == 'AE_VERIFIED'
            # E3.4.1 research materials are deliberately excluded from normal
            # Build: no stage may overwrite a live visual comparison.
            if _e344.has_active_comparison(objects):
                self.report({'ERROR'}, 'Si ink comparison is active. Restore the original ink appearance before Build.')
                return {'CANCELLED'}
            if _e343.has_active_comparison(objects):
                self.report({'ERROR'}, 'Universal FX comparison is active. Restore original FX before Build.')
                return {'CANCELLED'}
            if ae_verified and _selected_actor_is_si(objects) and _ab341.has_active_comparison(objects):
                self.report({'ERROR'}, 'Si VFX comparison is active. Restore original Si VFX before Build.')
                return {'CANCELLED'}
            if _selected_actor_is_si(objects) and _auto_a.status(context) in {'SUSPENDED', 'INCOMPLETE'}:
                self.report({'ERROR'}, 'Si Build A is suspended/incomplete; recover the scene before rebuilding')
                return {'CANCELLED'}
            if _selected_actor_is_si(objects) and _auto_a.has_active_build_a(objects) and not ae_verified:
                self.report({'ERROR'}, 'Si Build A is active but AE is no longer source-verified')
                return {'CANCELLED'}
            if ae_verified:
                # One-click AE final-stage configuration: use precisely the
                # same current source/owner gate as the guarded AE Full Setup.
                # Complete visual mode promotes stable stage flags even in
                # previously calibrated files. No manual preview ops.
                autoae = _autoae.prepare(scene, settings, info, objects)
                if autoae['status'] in {'ERROR_ROLLED_BACK', 'ROLLBACK_INCOMPLETE'}:
                    self.report({'ERROR'}, 'AE profile configuration failed: ' + str(autoae.get('error', ''))[:130])
                    return {'CANCELLED'}
                if autoae['status'] not in {'CONFIGURED', 'ALREADY_CONFIGURED'}:
                    self.report({'WARNING'}, 'AE auto profile: ' + autoae['status'])
                if _selected_actor_is_si(objects) and _auto_a.has_active_build_a(objects):
                    # Prevent unrelated or unverified scenes from altering A.
                    guard = _engine._xdzr8_ae_fullsetup_owner_check(scene, info, objects)
                    if guard['status'] != 'READY':
                        _autoae.rollback(settings, autoae)
                        self.report({'ERROR'}, 'Si Build A preflight blocked: ' + str(guard['status']))
                        return {'CANCELLED'}
                    _auto_a.suspend_for_build(context, objects)
                    a_suspended = True
                # The existing AE safe operator does current-source and
                # single-actor preflight before its one and only legacy Build.
                result = bpy.ops.sabershader.ae_fullsetup_safe_build('EXEC_DEFAULT')
            else:
                # Keep the legacy detection and texture-path recovery for
                # General/MMD, FGO and Uma; names alone are not authorization.
                result = bpy.ops.aef.add_shaders_v11('EXEC_DEFAULT')
        except Exception as exc:
            if autoae is not None and settings is not None:
                _autoae.rollback(settings, autoae)
            if a_suspended:
                try:
                    _auto_a.resume_after_build(context, objects)
                    a_suspended = False
                except Exception as recovery_exc:
                    scene['SaberShader_AE_SiBuildA_Status'] = 'RECOVERY_REQUIRED'
                    self.report({'ERROR'}, 'Si A recovery required after Build error: ' + str(recovery_exc)[:110])
            self.report({'ERROR'}, 'Build dispatch failed: %s: %s' %
                        (type(exc).__name__, str(exc)[:155]))
            return {'CANCELLED'}
        if not result or 'FINISHED' not in result:
            if autoae is not None and settings is not None:
                rollback_errors = _autoae.rollback(settings, autoae)
                if rollback_errors:
                    self.report({'ERROR'}, 'AE settings rollback incomplete: ' + str(rollback_errors)[:135])
            if a_suspended:
                try:
                    _auto_a.resume_after_build(context, objects)
                    a_suspended = False
                except Exception as exc:
                    scene['SaberShader_AE_SiBuildA_Status'] = 'RECOVERY_REQUIRED'
                    self.report({'ERROR'}, 'Si Build A resume failed after cancelled Build: ' + str(exc)[:110])
            return {'CANCELLED'}
        if autoae is not None:
            try:
                _autoae.commit(scene, autoae)
                if autoae.get('changed'):
                    self.report({'INFO'}, 'AE visual Build: %d stage flags enabled (%d older OFF overrides)' %
                                (len(autoae['changed']), len(autoae.get('overridden', ()))) )
            except Exception as exc:
                self.report({'WARNING'}, 'AE auto profile telemetry failed: ' + str(exc)[:120])

        # Re-check authoritative committed AE scene state, not stale pre-Build
        # IDs. Never run the Si catalog on a non-Endfield profile.
        try:
            verified_after = bool(_engine._xdzr8_ae_state(context)['authorized'])
        except Exception:
            verified_after = False
        if ae_verified and not verified_after:
            _eyebuild.ensure_eye_overlay(context, settings, info, objects,
                                         autoae, verified_after)
            self.report({'WARNING'}, 'AE eye Build not run: completed source authorization failed')
        if verified_after and ae_verified:
            # Validate the actual eye shadow material after the core build.
            # The legacy eye step may be skipped in a previously
            # built .blend (e.g. stale overlay tags/material slots). Check the
            # actual eyeshadow LOD0 graph; retry the same guarded AE123 setup
            # at most once, only if the source alpha mask is not connected.
            # The retry is NOT a second shader Build or manual A/B action.
            eye_result = _eyebuild.ensure_eye_overlay(context, settings, info,
                                                       objects, autoae, verified_after)
            if not eye_result['ready'] and eye_result['status'] not in {
                    'DISABLED_BY_USER', 'DISABLED_EYE_SETUP'}:
                self.report({'WARNING'}, 'AE eye mask: ' +
                            (eye_result.get('detail') or eye_result['status'])[:135])
            # Complete visual status includes verified eyeshadow result and
            # real scene color; never claim complete on a white/opaque LOD0.
            visual = _visual.complete_post_build(context, settings, info, objects,
                                                 autoae, verified_after,
                                                 eye_result=eye_result)
            visual_status = visual.get('status', 'UNKNOWN')
            if visual_status in {'PARTIAL', 'FAILED'}:
                self.report({'WARNING'}, 'AE visual Build: ' +
                            str(visual.get('detail', visual_status))[:135])
            elif visual_status == 'COMPLETE':
                self.report({'INFO'}, 'AE visual Build: outline=%s, eyeshadow=%s, color=%s' %
                            (visual.get('outline'), visual.get('eyeshadow'),
                             visual.get('color')))
        if verified_after:
            # E3: add only the five identified Si stroke effects. Preflight is
            # scoped to the ACTUAL selection, and makes no changes if a required
            # source texture is missing. A shader-stage error does not claim
            # that the already successful legacy Build was rolled back.
            if ae_verified and _selected_actor_is_si(objects):
                # Validation: capture non-Si material pointers and topology
                # AFTER the legacy AE Build, BEFORE optional Si FX stages.
                # Only those FX stages are in scope for this safety check.
                non_si_before = None
                try:
                    non_si_before = _fxqa.capture_non_si(scene)
                except Exception as exc:
                    self.report({'WARNING'}, 'Si FX non-Si baseline unavailable: ' + str(exc)[:105])
                try:
                    texture_dir = str(getattr(settings, 'universal_texture_folder', '') or '')
                    fx = _fx.apply_fx(objects, texture_dir=texture_dir)
                    scene['SaberShader_AE_SiFX_E3_Status'] = fx['status']
                    scene['SaberShader_AE_SiFX_E3_Materials'] = int(fx.get('applied', 0))
                    scene['SaberShader_AE_SiFX_E3_Skipped'] = int(len(fx.get('skipped', ())))
                    # E3.1: tune only exact, unmodified E3 FX materials. A
                    # manually edited opacity or active E3 A/B test is never
                    # overwritten; the five legacy original materials remain.
                    if fx['status'] != 'ERROR_ROLLED_BACK':
                        try:
                            tune = _e31.calibrate_e3_opacity(objects)
                            scene['SaberShader_AE_SiFX_E31_Status'] = tune['status']
                            scene['SaberShader_AE_SiFX_E31_Calibrated'] = int(tune.get('calibrated', 0))
                            scene['SaberShader_AE_SiFX_E31_Already'] = int(tune.get('already', 0))
                            scene['SaberShader_AE_SiFX_E31_Skipped'] = int(len(tune.get('skipped', ())))
                            if tune['status'] in {'ERROR_ROLLED_BACK', 'ROLLBACK_INCOMPLETE'}:
                                self.report({'WARNING'}, 'FX opacity adjustment failed: ' + str(tune.get('error',''))[:120])
                            elif tune.get('skipped'):
                                self.report({'WARNING'}, 'Preserved %d custom or unverified FX opacities' % len(tune['skipped']))
                        except Exception as exc:
                            scene['SaberShader_AE_SiFX_E31_Status'] = 'ERROR'
                            self.report({'WARNING'}, 'FX opacity diagnostic: ' + str(exc)[:125])
                    # Read-only classification is retained separately from the
                    # reversible E3.2 preview (no native shader equivalence).
                    try:
                        vfx = _e31.classify_vfxparts(objects)
                        scene['SaberShader_AE_SiVFX_E31_Status'] = vfx['status']
                        scene['SaberShader_AE_SiVFX_E31_Recognized'] = int(vfx['recognized'])
                        scene['SaberShader_AE_SiVFX_E31_Unverified'] = int(vfx['unverified'])
                        if vfx['found']:
                            self.report({'INFO'}, '%d Si vfxpart meshes classified (visual shader unverified)' % vfx['recognized'])
                    except Exception as exc:
                        scene['SaberShader_AE_SiVFX_E31_Status'] = 'ERROR'
                        self.report({'WARNING'}, 'Si vfxpart classification failed: ' + str(exc)[:125])
                    # E3.2: preview only the seven verified DefaultHGMaterial
                    # Si vfxpart meshes. Never modify the shared Hair shader.
                    try:
                        vfx_preview = _e32.apply(objects)
                        scene['SaberShader_AE_SiVFX_E32_Status'] = vfx_preview['status']
                        scene['SaberShader_AE_SiVFX_E32_Applied'] = int(vfx_preview.get('applied', 0))
                        scene['SaberShader_AE_SiVFX_E32_Skipped'] = int(len(vfx_preview.get('skipped', ())))
                        if vfx_preview['status'] in {'ERROR_ROLLED_BACK', 'ROLLBACK_INCOMPLETE'}:
                            self.report({'WARNING'}, 'Si VFX preview failed; core Build is still complete')
                        elif vfx_preview.get('applied'):
                            self.report({'INFO'}, 'Si VFX preview: %d translucent effects' % vfx_preview['applied'])
                    except Exception as exc:
                        scene['SaberShader_AE_SiVFX_E32_Status'] = 'ERROR'
                        self.report({'WARNING'}, 'Si VFX preview diagnostic: ' + str(exc)[:125])
                    # E3.3.1: transactional static look refinement for E3 ink FX and
                    # E3.2 Si VFX preview materials. No new source scan, no
                    # rig changes, and no claim of Unity-equivalent shading.
                    try:
                        look = _e331.apply(objects)
                        scene['SaberShader_AE_SiFX_E331_Status'] = look['status']
                        scene['SaberShader_AE_SiFX_E331_FX'] = int(look.get('ink', 0))
                        scene['SaberShader_AE_SiFX_E331_VFX'] = int(look.get('vfx', 0))
                        scene['SaberShader_AE_SiFX_E331_Skipped'] = int(len(look.get('skipped', ())))
                        scene['SaberShader_AE_SiFX_E332_VFXB_Upgraded'] = int(look.get('vfx_upgraded', 0))
                        if look['status'] == 'APPLIED' and look.get('new'):
                            self.report({'INFO'}, 'Si FX: %d ink materials, %d dual-layer VFX previews' % (look.get('ink', 0), look.get('vfx', 0)))
                        elif look['status'] in {'ERROR_ROLLED_BACK', 'ROLLBACK_INCOMPLETE'}:
                            self.report({'WARNING'}, 'Si FX appearance stage failed (' + look['status'] + '): ' + str(look.get('error', ''))[:100])
                        if look.get('skipped'):
                            self.report({'WARNING'}, 'Preserved %d shared, edited or unverified FX materials' % len(look['skipped']))
                    except Exception as exc:
                        scene['SaberShader_AE_SiFX_E331_Status'] = 'ERROR'
                        self.report({'WARNING'}, 'FX appearance diagnostic: ' + str(exc)[:125])
                    if fx['status'] == 'ERROR_ROLLED_BACK':
                        self.report({'WARNING'}, 'Build finished; experimental Si FX reverted: '+fx.get('error','')[:120])
                    elif fx['status'] == 'APPLIED':
                        self.report({'WARNING'} if fx['skipped'] else {'INFO'}, 'AE Si FX E3: %d ink materials approximated; %d skipped' %
                                    (fx['applied'], len(fx['skipped'])))
                    elif fx.get('skipped'):
                        self.report({'WARNING'}, 'Build finished; Si FX E3 skipped (source textures/materials need review)')
                except Exception as exc:
                    scene['SaberShader_AE_SiFX_E3_Status']='DIAGNOSTIC_ERROR'
                    self.report({'WARNING'},'Build finished; Si FX E3 could not run: '+str(exc)[:120])
                # Read-only native topology checks are part of the verified
                # AE-Si Build; destructive/restoration and save/load QA never
                # run implicitly. Failures cannot change a completed Build.
                try:
                    fxqa = _fxqa.post_build(context, objects, non_si_before=non_si_before)
                    state = fxqa['checks']['1']['status']
                    if state != 'PASS':
                        self.report({'WARNING'}, 'Si VFX validation: ' + state + ' (see AE panel)')
                    if fxqa['checks']['4']['status'] == 'FAIL':
                        self.report({'WARNING'}, 'Non-Si mesh changed during optional Si FX stage')
                except Exception as exc:
                    scene[_fxqa.STATUS_KEY] = 'ERROR'
                    self.report({'WARNING'}, 'Si VFX validation diagnostic failed: ' + str(exc)[:120])
                # Apply the verified Si single-trail appearance last. A uses
                # the same gfx18 graph as E341 Show A, but no manual A/B tags.
                # A pre-existing Build A reuses its exact material datablock.
                # Failure is explicit: never label a successful legacy Build
                # as rolled back when the optional ink step failed.
                try:
                    if a_suspended:
                        ink_a = _auto_a.resume_after_build(context, objects)
                        a_suspended = False
                    else:
                        ink_a = _auto_a.apply_after_build(context, objects)
                    scene['SaberShader_AE_SiBuildA_Status'] = ink_a['status']
                    scene['SaberShader_AE_SiBuildA_Meshes'] = int(ink_a.get('meshes', 0))
                    if ink_a['status'] in {'ACTIVE_A', 'ACTIVE_A_REUSED', 'ALREADY_EXACT_A'}:
                        self.report({'INFO'}, 'Si idle ink A active in main Build: ' + ink_a['status'])
                    else:
                        self.report({'WARNING'}, 'Si idle ink A was not applied: ' + ink_a['status'])
                except Exception as exc:
                    scene['SaberShader_AE_SiBuildA_Status'] = 'RECOVERY_REQUIRED' if a_suspended else 'ERROR'
                    self.report({'ERROR'}, 'AE Build finished, but Si ink A failed: ' + str(exc)[:125])
            # Read-only source/UV/FX inventories are NOT visual
            # stages; use their existing buttons when diagnostic data is needed.
        if a_suspended:
            try:
                _auto_a.resume_after_build(context, objects)
                scene['SaberShader_AE_SiBuildA_Status'] = 'ACTIVE_A_REUSED'
            except Exception as exc:
                scene['SaberShader_AE_SiBuildA_Status'] = 'RECOVERY_REQUIRED'
                self.report({'ERROR'}, 'Si A recovery required after Build: ' + str(exc)[:130])
        return {'FINISHED'}
