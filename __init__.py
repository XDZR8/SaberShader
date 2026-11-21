"""SaberShader Blender add-on registration and lifecycle."""

bl_info = {
    "name": "SaberShader",
    "author": "XDZR8",
    "version": (1, 0, 5),
    "blender": (5, 1, 1),
    "location": "View3D > Sidebar (N) > SaberShader",
    "description": "Profile-based stylized shaders for General/MMD, Uma Musume, FGO Arcade and Endfield.",
    "category": "Material",
}

import bpy

from . import engine as _engine
from . import ui as _ui
from . import lineart_tools as _lineart_tools
from . import lifecycle_controls as _lifecycle_controls
from . import lifecycle_state as _lifecycle_state
from . import handler_dispatch as _handler_dispatch
from . import ae_material_sources as _ae_material_sources
from . import ae_one_click as _ae_one_click
from . import ae_auto_profile as _ae_auto_profile
from . import ae_visual_completion as _ae_visual_completion
from . import ae_eye_overlay_guard as _ae_eye_overlay_guard
from . import ae_eye_mask_recovery as _ae_eye_mask_recovery
from . import ae_fx_ink_sources as _ae_fx_ink_sources
from . import ae_fx_opacity as _ae_fx_opacity
from . import ae_vfx_placeholders as _ae_vfx_placeholders
from . import ae_fx_layered_materials as _ae_fx_layered_materials
from . import ae_fx_validation as _ae_fx_validation
from . import ae_fx_comparison as _ae_fx_comparison
from . import ae_fx_universal as _ae_fx_universal
from . import ae_fx_fidelity as _ae_fx_fidelity
from . import ae_fx_idle_ink as _ae_fx_idle_ink
from . import ae_fx_cross_validation as _ae_fx_cross_validation
from . import ae_fx_auto_appearance as _ae_fx_auto_appearance
from .lifecycle_core import LifecycleLedger, LifecycleConflict
# A build signature catches mixed in-memory modules during upgrades. It is
# independent of the public add-on version and is not stored in .blend files.
_EXPECTED_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
# Blender retains registered RNA classes. Disable the add-on, close Blender,
# replace the package, then start Blender again instead of reloading modules.
if any(getattr(module, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE
       for module in (_engine, _ui, _lineart_tools, _ae_material_sources, _ae_one_click, _ae_fx_ink_sources)):
    raise RuntimeError('SaberShader 1.0.5: mixed or cached modules; restart Blender before enabling')
if getattr(_ae_fx_opacity, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader FX module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_auto_profile, 'REVISION', None) != 'AE_AUTO_PROFILE_E3452_COMPLETE_1':
    raise RuntimeError('SaberShader Endfield profile module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_layered_materials, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader FX appearance module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_layered_materials, 'VFX_B_REVISION', None) != 'E332_DUAL_LAYER_DISTORTION_1':
    raise RuntimeError('SaberShader dual-layer FX module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_vfx_placeholders, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader VFX module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_validation, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader FX validation module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_comparison, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader VFX comparison module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_universal, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader FX inspection module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_fidelity, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader FX fidelity module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_idle_ink, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader Si ink preset module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_cross_validation, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader cross-character validation module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_fx_auto_appearance, 'SABERSHADER_BUILD_SIGNATURE', None) != _EXPECTED_BUILD_SIGNATURE:
    raise RuntimeError('SaberShader Si VFX Build module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_eye_overlay_guard, 'REVISION', None) != 'E3453_AE_EYESHADOW_BUILD_1':
    raise RuntimeError('SaberShader eye shadow module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_one_click, 'SABERSHADER_AE_ONE_CLICK_REVISION', None) != 'E3_4_5_4_EYESHADOW_BUILD_2':
    raise RuntimeError('SaberShader Build integration is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_eye_mask_recovery, 'REVISION', None) != 'E3455_EYE_UV_LAYER_RECOVERY_1':
    raise RuntimeError('SaberShader eye shadow UV recovery module is outdated. Restart Blender after installing the complete add-on.')
if getattr(_ae_visual_completion, 'REVISION', None) != 'E3452_AE_VISUAL_POST_1':
    raise RuntimeError('SaberShader visual Build module is outdated. Restart Blender after installing the complete add-on.')
if (not hasattr(_lifecycle_state, 'registration_active') or
        _lifecycle_state.registration_active()):
    raise RuntimeError('SaberShader 1.0.5: addon already registered or stale state; restart Blender')

from .engine import (
    AEF_SaberShader_V8_Settings,
    AEF_PG_fgo_face_v4574,
    AEF_PG_fgo_opacity_research_v45744,
    AEF_PG_fgo_uv_research_v45745,
    AEF_PG_fgo_uv_repair_v45747,
    AEF_PG_fgo_shading_v45749,
    AEF_PG_fgo_live_v457410,
    AEF_PG_fgo_surface_research_v45746,
    _face_light_on_depsgraph_update,
    _face_light_on_frame_change,
    _face_light_update_dynamic,
    _apply_eyehideall_bindings,
    XDZR8_V112_ROLE_ITEMS,
    log,
)

# Register classes in dependency order. Existing .blend files may refer to
# these operator and RNA identifiers, so keep the legacy names until a
# migration can update every saved scene and material reference.
_CLASS_ORDER = (
    'AEF_SaberShader_V8_Settings',
    'AEF_OT_add_shaders_v11',
    'AEF_OT_ae113_fidelity_uv_audit',
    'AEF_OT_ae110_refresh_outline',
    'AEF_OT_ae110_remove_outline',
    'AEF_OT_ae118polish_create_lights',
    'AEF_OT_ae118polish_remove_lights',
    'AEF_OT_ae120_inspect',
    'AEF_OT_ae120_guard',
    'AEF_OT_ae120_restore_guard',
    'AEF_OT_ae120_apply_overlay',
    'AEF_OT_ae120_restore_overlay',
    'AEF_OT_ae120_limit_iris',
    'AEF_OT_ae120_restore_iris',
    'AEF_OT_ae123_apply_preset',
    'AEF_OT_ae123_restore_preset',
    'AEF_OT_ae126_apply_color_management',
    'AEF_OT_ae126_restore_color_management',
    'AEF_OT_ae126_color_audit',
    'AEF_OT_ae129_apply_preset',
    'AEF_OT_ae129_restore_preset',
    'AEF_OT_ae129hf1_source_audit',
    'AEF_OT_ae129hf42_apply_preset',
    'AEF_OT_ae129hf42_restore_preset',
    'AEF_OT_ae129hf43_source_audit',
    'AEF_OT_ae129hf45_apply_preset',
    'AEF_OT_ae129hf45_restore_preset',
    'AEF_OT_ae129hf451_use_selected_light',
    'AEF_OT_ae129hf451_restore_final_views',
    'AEF_OT_ae129hf452_enable_scene_face',
    'AEF_OT_ae129hf452_setup_scene',
    'AEF_OT_ae129hf453_apply_hybrid',
    'AEF_OT_ae129hf453_outline_audit',
    'AEF_OT_ae129hf454_apply_balanced_face',
    'AEF_OT_ae129hf454_recover_hf2_normals',
    'AEF_OT_ae_fullsetup_review',
    'AEF_OT_ae_fullsetup_last_run',
    'AEF_OT_ae_fullsetup_safe_build',
    'AEF_OT_ae_fullsetup_restore',
    'AEF_OT_ae129hf455_apply_full_setup',
    'AEF_OT_ae129hf455gn_preview',
    'AEF_OT_ae129hf455gn_restore',
    'AEF_OT_ae129hf455gn_audit',
    'AEF_OT_ae129hf456_apply_hair_preset',
    'AEF_OT_ae129hf456_restore_hair',
    'AEF_OT_ae129hf456_preview_existing',
    'AEF_OT_ae129hf456_restore_existing',
    'AEF_OT_ae129hf456_hair_audit',
    'AEF_OT_ae129hf4565_lod_audit',
    'AEF_OT_ae129hf4565_select_lod',
    'AEF_OT_ae129hf4565_restore_lods',
    'AEF_OT_ae129hf4565_compress_preview',
    'AEF_OT_ae129hf45651_calibrate',
    'AEF_OT_ae129hf45651_restore_calibration',
    'AEF_OT_ae127_apply_eye_preset',
    'AEF_OT_ae127_restore_eye_preset',
    'AEF_OT_ae123_apply_eye',
    'AEF_OT_ae123_restore_eye',
    'AEF_OT_ae122_inspect',
    'AEF_OT_ae122_apply',
    'AEF_OT_ae122_restore',
    'AEF_OT_ae119_preview_eyeshadow',
    'AEF_OT_ae119_apply_eyeshadow',
    'AEF_OT_ae119_restore_eyeshadow',
    'AEF_OT_ae111_preview_cleanup',
    'AEF_OT_ae111_hide_cleanup',
    'AEF_OT_ae111_restore_cleanup',
    'AEF_OT_ae111_delete_cleanup',
    'AEF_OT_fgo_arcade_source_audit_v4572',
    'AEF_OT_fgo_arcade_resource_audit_v4573',
    'AEF_OT_fgo_arcade_relink_v4573',
    'AEF_OT_fgo_arcade_restore_images_v4573',
    'AEF_OT_fgo_arcade_store_native_map_v4573',
    'AEF_OT_fgo_arcade_restore_native_map_v4573',
    'AEF_PG_fgo_face_v4574',
    'AEF_OT_fgo_face_audit_v4574',
    'AEF_OT_fgo_face_convert_v4574',
    'AEF_OT_fgo_face_expression_v4574',
    'AEF_OT_fgo_face_reset_v4574',
    'AEF_OT_fgo_face_restore_v4574',
    'AEF_OT_fgo_face_overlay_audit_v45742',
    'AEF_OT_fgo_face_clean_neutral_v45742',
    'AEF_OT_fgo_face_restore_overlay_v45742',
    'AEF_OT_fgo_neutral_face_audit_v45743',
    'AEF_OT_fgo_neutral_face_preview_v45743',
    'AEF_OT_fgo_neutral_face_restore_v45743',
    'AEF_PG_fgo_uv_research_v45745',
    'AEF_PG_fgo_uv_repair_v45747',
    'AEF_OT_fgo_uv_orientation_audit_v45747',
    'AEF_OT_fgo_uv_orientation_preview_v45747',
    'AEF_OT_fgo_uv_orientation_apply_v45747',
    'AEF_OT_fgo_uv_orientation_restore_v45747',
    'AEF_PG_fgo_shading_v45749',
    'AEF_PG_fgo_live_v457410',
    'AEF_OT_fgo410_audit',
    'AEF_OT_fgo410_scale',
    'AEF_OT_fgo410_restore_scale',
    'AEF_OT_fgo410_outline',
    'AEF_OT_fgo410_restore_outline',
    'AEF_OT_fgo410_studio_lights',
    'AEF_OT_fgo410_restore_lights',
    'AEF_OT_fgo410_refresh_lighting',
    'AEF_OT_fgo_shading_audit_v45749',
    'AEF_OT_fgo_shading_preview_v45749',
    'AEF_OT_fgo_shading_restore_v45749',
    'AEF_PG_fgo_surface_research_v45746',
    'AEF_OT_fgo_surface_layer_audit_v45746',
    'AEF_OT_fgo_surface_layer_preview_v45746',
    'AEF_OT_fgo_surface_layer_restore_v45746',
    'AEF_OT_fgo_facial_uv_audit_v45745',
    'AEF_OT_fgo_facial_uv_preview_v45745',
    'AEF_OT_fgo_facial_uv_restore_v45745',
    'AEF_PG_fgo_opacity_research_v45744',
    'AEF_OT_fgo_native_opacity_audit_v45744',
    'AEF_OT_fgo_native_opacity_probe_v45744',
    'AEF_OT_fgo_native_opacity_restore_v45744',
    'AEF_OT_mmd_umd_custom_template',
    'AEF_OT_mmd_umd_scan',
    'AEF_OT_mmd_umd_apply_roles',
    'AEF_OT_mmd_umd_restore_roles',
    'AEF_OT_mmd_umd_apply_preset',
    'AEF_OT_mmd_umd_restore_preset',
    'AEF_OT_sabershader_build_v8',
    'AEF_OT_outline_pipeline_audit_v109b31',
    'AEF_OT_uma_texture_library_audit_v11932',
    'AEF_OT_uma_texture_library_open_report_v11932',
    'AEF_OT_uma_hair_render_match_v1148',
    'AEF_OT_uma_hair_render_match_restore_v1148',
    'AEF_OT_sabershader_save_copy_v8',
    'AEF_PT_saber_shader_v8',
    'AEF_PT_ui121_character',
    'AEF_PT_ui121_general_eyes',
    'AEF_PT_ui121_endfield',
    'AEF_PT_ui121_uma',
    'AEF_PT_ui121_fgo_arcade',
    'AEF_PT_ui121_fgo_arcade_face_v4574',
    'AEF_PT_ui121_fgo_face_overlay_v45742',
    'AEF_PT_ui121_fgo_neutral_face_v45743',
    'AEF_PT_ui121_fgo_native_opacity_v45744',
    'AEF_PT_ui121_fgo_facial_uv_v45745',
    'AEF_PT_ui121_fgo_uv_orientation_v45747',
    'AEF_PT_ui121_fgo_shading_v45749',
    'AEF_PT_ui121_fgo_live_v457410',
    'AEF_PT_ui121_fgo_surface_layers_v45746',
    'AEF_PT_ui121_textures',
    'AEF_PT_ui121_advanced',
    'AEF_PT_ui121_mmd_dictionary',
)


def _resolve_class(name):
    return getattr(_ui, name) if hasattr(_ui, name) else getattr(_engine, name)


classes = (_ui.AEF_AddonPreferences,) + tuple(_resolve_class(name) for name in _CLASS_ORDER) + (
    _ae_one_click.AEF_OT_sabershader_one_click_build,
    _ae_eye_mask_recovery.AEF_OT_ae_eye_diagnose_e3454,
    # Keep these legacy RNA identifiers because saved scenes may refer to them.
    _lineart_tools.AEF_OT_safety_fix1_lineart_audit,
    _lineart_tools.AEF_OT_safety_fix1_lineart_export,
    _lineart_tools.AEF_PT_safety_fix1_lineart,
    _lifecycle_controls.AEF_OT_safety_fix2_enable_live_sync,
    _lifecycle_controls.AEF_OT_safety_fix2_disable_live_sync,
    _lifecycle_controls.AEF_OT_safety_fix3_rescan_eyehideall,
    _lifecycle_controls.AEF_PT_safety_fix2_session,
    _ae_material_sources.AEF_OT_ae_si_source_dictionary_audit,
    _ae_material_sources.AEF_PT_ae_si_source_dictionary,
    _ae_fx_ink_sources.AEF_OT_ae_si_fx_e3_restore,
    _ae_fx_opacity.AEF_OT_ae_si_fx_e31_restore_opacity,
    _ae_vfx_placeholders.AEF_OT_ae_si_vfx_e32_restore,
    _ae_fx_layered_materials.AEF_OT_ae_si_fx_e331_restore,
    _ae_fx_validation.AEF_OT_ae_si_fx_e332_validate,
    _ae_fx_comparison.AEF_OT_si_vfx_ab_prepare,
    _ae_fx_comparison.AEF_OT_si_vfx_ab_show_a,
    _ae_fx_comparison.AEF_OT_si_vfx_ab_show_b,
    _ae_fx_comparison.AEF_OT_si_vfx_ab_restore,
    _ae_fx_comparison.AEF_OT_si_vfx_ab_snapshot,
    _ae_fx_auto_appearance.AEF_OT_si_build_a_restore,
    _ae_fx_auto_appearance.AEF_OT_si_build_a_resume,
    _ae_fx_universal.AEF_OT_ae_universal_fx_e342_audit,
    _ae_fx_universal.AEF_PT_ae_universal_fx_e342,
    _ae_fx_fidelity.AEF_PG_ae_fx_fidelity_e343,
    _ae_fx_fidelity.AEF_OT_ae_fx_e343_prepare,
    _ae_fx_fidelity.AEF_OT_ae_fx_e343_show_a,
    _ae_fx_fidelity.AEF_OT_ae_fx_e343_show_a2,
    _ae_fx_fidelity.AEF_OT_ae_fx_e343_apply,
    _ae_fx_fidelity.AEF_OT_ae_fx_e343_restore,
    _ae_fx_fidelity.AEF_OT_ae_fx_e343_snapshot,
    _ae_fx_fidelity.AEF_PT_ae_fx_e343,
    _ae_fx_idle_ink.AEF_PG_si_idle_ink_e344,
    _ae_fx_idle_ink.AEF_OT_si_idle_ink_e344_prepare,
    _ae_fx_idle_ink.AEF_OT_si_idle_ink_e344_show_a,
    _ae_fx_idle_ink.AEF_OT_si_idle_ink_e344_show_a2,
    _ae_fx_idle_ink.AEF_OT_si_idle_ink_e344_apply,
    _ae_fx_idle_ink.AEF_OT_si_idle_ink_e344_reset,
    _ae_fx_idle_ink.AEF_OT_si_idle_ink_e344_snapshot,
    _ae_fx_idle_ink.AEF_OT_si_idle_ink_e344_restore,
    _ae_fx_idle_ink.AEF_PT_si_idle_ink_e344,
    _ae_fx_cross_validation.AEF_PG_ae_fx_cross_validation_e345,
    _ae_fx_cross_validation.AEF_OT_ae_e345_baseline_aa2,
    _ae_fx_cross_validation.AEF_OT_ae_e345_preview,
    _ae_fx_cross_validation.AEF_OT_ae_e345_restore,
    _ae_fx_cross_validation.AEF_OT_ae_e345_build_baseline,
    _ae_fx_cross_validation.AEF_OT_ae_e345_repeat,
    _ae_fx_cross_validation.AEF_OT_ae_e345_export,
    _ae_fx_cross_validation.AEF_OT_ae_e345_cross,
    _ae_fx_cross_validation.AEF_OT_ae_e345_reset,
    _ae_fx_cross_validation.AEF_PT_ae_fx_cross_validation_e345,
)

# Registration state belongs to this Blender process. Do not replace the addon
# in place while it is registered; disable it and restart Blender first.
_ACTIVE_LIFECYCLE = None


def _live_sync_depsgraph_handler(scene, depsgraph=None):
    if _lifecycle_state.live_sync_enabled():
        _handler_dispatch.dispatch('depsgraph', scene, depsgraph,
                                   _face_light_on_depsgraph_update)


def _live_sync_frame_handler(scene, depsgraph=None):
    if _lifecycle_state.live_sync_enabled():
        _handler_dispatch.dispatch('frame', scene, depsgraph,
                                   _face_light_on_frame_change)


def _register_scene_properties(ledger):
    # Keep the existing RNA identifiers. Record each successful registration
    # so it can be undone if a later step fails. Do not overwrite properties
    # that may still belong to another active installation.
    scene = bpy.types.Scene
    ledger.register_property(scene, 'aef_ae_fx_e345',
        lambda: bpy.props.PointerProperty(type=_ae_fx_cross_validation.AEF_PG_ae_fx_cross_validation_e345))
    ledger.register_property(scene, 'aef_ae_si_idle_ink_e344',
        lambda: bpy.props.PointerProperty(type=_ae_fx_idle_ink.AEF_PG_si_idle_ink_e344))
    ledger.register_property(scene, 'aef_ae_universal_fx_e343',
        lambda: bpy.props.PointerProperty(type=_ae_fx_fidelity.AEF_PG_ae_fx_fidelity_e343))
    ledger.register_property(scene, 'aef_sabershader_v8',
        lambda: bpy.props.PointerProperty(type=AEF_SaberShader_V8_Settings))
    ledger.register_property(scene, 'aef_fgo_face_v4574',
        lambda: bpy.props.PointerProperty(type=AEF_PG_fgo_face_v4574))
    ledger.register_property(scene, 'aef_fgo_opacity_research_v45744',
        lambda: bpy.props.PointerProperty(type=AEF_PG_fgo_opacity_research_v45744))
    ledger.register_property(scene, 'aef_fgo_uv_research_v45745',
        lambda: bpy.props.PointerProperty(type=AEF_PG_fgo_uv_research_v45745))
    ledger.register_property(scene, 'aef_fgo_uv_repair_v45747',
        lambda: bpy.props.PointerProperty(type=AEF_PG_fgo_uv_repair_v45747))
    ledger.register_property(scene, 'aef_fgo_shading_v45749',
        lambda: bpy.props.PointerProperty(type=AEF_PG_fgo_shading_v45749))
    ledger.register_property(scene, 'aef_fgo_live_v457410',
        lambda: bpy.props.PointerProperty(type=AEF_PG_fgo_live_v457410))
    ledger.register_property(scene, 'aef_fgo_surface_research_v45746',
        lambda: bpy.props.PointerProperty(type=AEF_PG_fgo_surface_research_v45746))
    ledger.register_property(scene, 'hf45743_face_original_mix', lambda: bpy.props.FloatProperty(
        name='Original Atlas Detail',
        description='Fraction of the original S01 face atlas to mix with the neutral preview (diagnostic only)',
        min=0.0, max=0.40, default=0.08, precision=3,
    ))
    ledger.register_property(scene, 'hf45743_face_skin_color', lambda: bpy.props.FloatVectorProperty(
        name='Neutral Skin',
        description='Preview skin color; calibrated for the reviewed S02 character, manually adjustable for others',
        size=3, subtype='COLOR', min=0.0, max=1.0, default=(0.95, 0.79, 0.69),
    ))
    ledger.register_property(bpy.types.Material, 'xdzr8_role_override', lambda: bpy.props.EnumProperty(
        name='XDZR8 Material Role Override',
        description='Optional manual role for the active material. Auto Detect keeps the guarded classifier, usage specialization, and audit in control',
        items=XDZR8_V112_ROLE_ITEMS, default='AUTO',
    ))


def register():
    global _ACTIVE_LIFECYCLE
    if _ACTIVE_LIFECYCLE is not None or _lifecycle_state.registration_active():
        raise LifecycleConflict('SaberShader 1.0.5 is already registered in this Python process')
    _lifecycle_state.set_live_sync(False)
    _handler_dispatch.reset()
    if (_face_light_on_depsgraph_update in bpy.app.handlers.depsgraph_update_post or
            _face_light_on_frame_change in bpy.app.handlers.frame_change_post):
        raise LifecycleConflict('Legacy SaberShader handlers are still active; restart Blender')
    ledger = LifecycleLedger()
    try:
        for cls in classes:
            ledger.register_class(bpy.utils, cls)
        _register_scene_properties(ledger)
        ledger.register_handler(bpy.app.handlers.depsgraph_update_post, _live_sync_depsgraph_handler)
        ledger.register_handler(bpy.app.handlers.frame_change_post, _live_sync_frame_handler)
        ledger.step('brand_icon', _ui.register_brand_icon, _ui.unregister_brand_icon)
        # During registration, do not modify scene data, start Live Sync, or remove
        # Line Art modifiers. Always use copies when testing potentially unsafe scenes.
        _ACTIVE_LIFECYCLE = ledger
        _lifecycle_state.set_registration_active(True)
    except Exception as exc:
        failures = ledger.rollback()
        _lifecycle_state.set_live_sync(False)
        if failures:
            _ACTIVE_LIFECYCLE = ledger  # Keep failed cleanup operations so unregister can retry them later.
            _lifecycle_state.set_registration_active(True)
            raise RuntimeError('SaberShader register failed (%s), rollback errors: %s' % (
                exc, '; '.join(failures))) from exc
        _lifecycle_state.set_registration_active(False)
        raise


def unregister():
    global _ACTIVE_LIFECYCLE
    _lifecycle_state.set_live_sync(False)
    ledger = _ACTIVE_LIFECYCLE
    if ledger is None:
        # Unregister only classes this addon can positively identify as its own.
        # Updating the code while the addon is enabled requires a Blender restart.
        return
    failures = ledger.rollback()
    if not failures:
        _ACTIVE_LIFECYCLE = None
        _lifecycle_state.set_registration_active(False)
    if failures:
        raise RuntimeError('SaberShader unregister incomplete: ' + '; '.join(failures))
