"""Native SaberShader sidebar panels and optional bundled branding."""

import bpy
import bpy.utils.previews
from pathlib import Path

from .ae_ui_visibility import ae_developer_tools_visible

# Keep the engine imports in their established dependency order. Re-exporting
# these names preserves the callbacks and Blender classes used by the panels.
from .engine import *
SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'

_BRAND_PREVIEWS = None


def register_brand_icon():
    """Load the project logo from the installed package without temporary files."""
    global _BRAND_PREVIEWS
    if _BRAND_PREVIEWS is not None:
        return
    collection = None
    try:
        icon_file = Path(__file__).parent / 'assets' / 'SaberShader_icon.png'
        collection = bpy.utils.previews.new()
        collection.load('sabershader_brand', str(icon_file), 'IMAGE')
        _BRAND_PREVIEWS = collection
    except Exception as exc:
        if collection is not None:
            try: bpy.utils.previews.remove(collection)
            except Exception: pass
        print('[SaberShader] Optional brand preview could not be loaded:', exc)


def _sabershader_brand_icon_id():
    if _BRAND_PREVIEWS is None:
        return 0
    try:
        return int(_BRAND_PREVIEWS['sabershader_brand'].icon_id)
    except Exception:
        return 0


def unregister_brand_icon():
    global _BRAND_PREVIEWS
    if _BRAND_PREVIEWS is not None:
        try: bpy.utils.previews.remove(_BRAND_PREVIEWS)
        except Exception: pass
        _BRAND_PREVIEWS = None

class AEF_AddonPreferences(bpy.types.AddonPreferences):
    """Developer-only visibility; does not affect AE Build configuration."""
    bl_idname = __package__

    show_ae_developer_panels: bpy.props.BoolProperty(
        name='Show AE Developer Tools',
        description='Expose AE shader stage controls, A/B research, validation and JSON audits',
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'show_ae_developer_panels')
        layout.label(text='Off: simplified Endfield interface with automatic Build stages hidden.')
        layout.label(text='On: AE diagnostics, manual A/B studies and stage tuning are visible.')
        layout.label(text='This option changes only the interface, never the Build pipeline.')


class AEF_PT_ui121_ae_hair_compression(bpy.types.Panel):
    bl_label='Albedo Highlight Compression'
    bl_idname='AEF_PT_ui121_ae_hair_compression'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_ae_hair_fidelity'
    bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)
    def draw(self,context):
        layout=self.layout; s=context.scene.aef_sabershader_v8
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        layout.label(text='Endfield verified Hair meshes — source images preserved',icon='INFO')
        layout.prop(s,'ae129hf4566_comp_build_enabled')
        layout.label(text='Enabled: next AE Build uses Compressed result on verified Hair')
        layout.label(text='Mask / Split are preview-only; originals stay untouched')
        if int(context.scene.get(_AE129HF4565_LOD_LEVEL,0))!=0:
            warning=layout.row();warning.alert=True
            warning.label(text='Select LOD0 to preview hair compression',icon='ERROR')
        presets=layout.row(align=True)
        presets.operator('sabershader.ae129hf45651_calibrate',text='AE Warm Calibration')
        presets.operator('sabershader.ae129hf45651_restore_calibration',text='Restore Controls')
        layout.prop(s,'ae129hf4565_comp_view')
        if s.ae129hf4565_comp_view!='ORIGINAL':
            layout.prop(s,'ae129hf4565_comp_threshold',slider=True)
            layout.prop(s,'ae129hf4565_comp_softness',slider=True)
            layout.prop(s,'ae129hf45651_white_guard',slider=True)
            if s.ae129hf4565_comp_view in {'CORRECTED','SPLIT'}:
                layout.prop(s,'ae129hf4565_comp_strength',slider=True)
                layout.prop(s,'ae129hf45651_hair01',slider=True)
                layout.prop(s,'ae129hf45651_hair02',slider=True)
                layout.prop(s,'ae129hf4565_comp_tint')
            if s.ae129hf4565_comp_view=='SPLIT':
                layout.prop(s,'ae129hf45651_split',slider=True)
                layout.label(text='LEFT: original    |    RIGHT: compressed')
        action=layout.row(align=True)
        action.operator('sabershader.ae129hf4565_compress_preview',text='Preview Source')
        action.operator('sabershader.ae129hf456_restore_existing',text='Restore Hair')
        layout.label(text='Mask uses brightness and whiteness, not native maps')
        layout.label(text='Refresh Preview Source after editing sliders')
        layout.label(text='Compression audit available in Text Editor')


class AEF_PT_ui121_ae_lod_selector(bpy.types.Panel):
    bl_label='AE Character LOD Selector'
    bl_idname='AEF_PT_ui121_ae_lod_selector'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_endfield'
    bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)
    def draw(self,context):
        layout=self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        s=context.scene.aef_sabershader_v8
        layout.label(text='Choose LOD freely; no meshes are deleted',icon='INFO')
        layout.prop(s,'ae129hf4565_lod_target',text='Display LOD')
        row=layout.row(align=True)
        row.operator('sabershader.ae129hf4565_select_lod',text='Apply Selected LOD',icon='HIDE_OFF')
        row.operator('sabershader.ae129hf4565_lod_audit',text='Audit',icon='TEXT')
        layout.operator('sabershader.ae129hf4565_restore_lods',text='Restore Original Visibility',icon='LOOP_BACK')
        level=context.scene.get(_AE129HF4565_LOD_LEVEL)
        if level is not None:
            layout.label(text='Active LOD: %s | Actor: %s'%(level,context.scene.get(_AE129HF4565_LOD_ACTOR,'?')))
        layout.label(text='Missing parts use nearest available LOD')
        layout.label(text='Eye, iris and shadow helper guards remain untouched')
        layout.label(text='LOD0 outlines hidden while previewing other LODs')
        layout.label(text='Restore visibility before Full Build, then reapply')
        layout.label(text='Avoid other cleanup LOD guards while selector is active')
        layout.label(text='LOD audit available in Text Editor')


class AEF_PT_saber_shader_v8(bpy.types.Panel):
    bl_label = "SaberShader 1.0.5"
    bl_idname = "AEF_PT_saber_shader_v8"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SaberShader"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aef_sabershader_v8

        # -------------------------------------------------------------
        # Native Blender panel layout and presentation.
        # Native widgets follow Blender themes, display scaling and accessibility settings.
        # -------------------------------------------------------------
        hero = layout.box()
        # Show the original icon at a readable size using Blender’s native layout.
        brand_icon_id = _sabershader_brand_icon_id()
        if brand_icon_id:
            brand_image_row = hero.row()
            brand_image_row.alignment = 'CENTER'
            brand_image_row.template_icon(icon_value=brand_icon_id, scale=2.7)
        brand_name_row = hero.row()
        brand_name_row.alignment = 'CENTER'
        brand_name_row.label(text='SABERSHADER', icon='NONE' if brand_icon_id else 'SHADING_RENDERED')
        brand_version_row = hero.row()
        brand_version_row.alignment = 'CENTER'
        brand_version_row.label(text='1.0.5')

        hero.label(text='Source-preserving character shaders')

        # Read the panel state from the active Blender scene.
        target = getattr(context, 'active_object', None)
        if target is not None:
            hero.label(text='Selected: ' + target.name[:38], icon='OBJECT_DATA')
        if _xdzr8_ae_state(context)['authorized']:
            hero.label(text='Endfield profile detected', icon='CHECKMARK')
            hero.label(text='AE Build: complete stable visual pipeline',icon='INFO')
        elif _sabershader_ae_ui_scene_hint(context):
            hero.label(text='Endfield naming found; source unverified', icon='INFO')
        else:
            hero.label(text='Profile: automatic detection', icon='INFO')

        primary = hero.row()
        primary.scale_y = 1.75
        primary.operator(
            'sabershader.one_click_build',
            text='Build SaberShader',
            icon='NODE_MATERIAL',
        )

        utility = hero.row(align=True)
        utility.scale_y = 1.12
        utility.operator(
            AEF_OT_sabershader_save_copy_v8.bl_idname,
            text='Save Copy',
            icon='FILE_TICK',
        )

        build_pct = max(0.0, min(100.0, float(context.scene.get('XDZR8_BuildProgress', 0.0))))
        build_stage = str(context.scene.get('XDZR8_BuildStage', 'Ready'))
        build_running = bool(context.scene.get('XDZR8_BuildRunning', False))
        build_result = str(context.scene.get('XDZR8_BuildLastResult', ''))

        status = hero.box()
        status_row = status.row(align=True)
        if build_running:
            status_row.label(text=f'Building • {build_stage}', icon='TIME')
        elif build_result == 'FINISHED':
            status_row.label(text='Ready • Last build finished', icon='CHECKMARK')
        elif build_result:
            status_row.alert = True
            status_row.label(text='Last build needs attention', icon='ERROR')
        else:
            status_row.label(text='Ready to build', icon='INFO')

        if build_running or build_result:
            if hasattr(status, 'progress'):
                status.progress(
                    factor=build_pct / 100.0,
                    type='BAR',
                    text=f'{build_pct:.0f}% • {build_stage}',
                )
            elif build_running:
                status.label(text=f'Progress: {build_pct:.0f}%')

        # Present quick settings as standard Blender controls.
        quick = layout.box()
        quick.label(text='Quick Features', icon='OPTIONS')
        quick_row = quick.row(align=True)
        quick_row.scale_y = 1.20
        quick_row.prop(
            settings,
            'eye_fx_enabled',
            text='Eye FX',
            icon='HIDE_OFF',
            toggle=True,
        )
        quick_row.prop(
            settings,
            'expression_eyes_enabled',
            text='Expression Eyes',
            icon='SHAPEKEY_DATA',
            toggle=True,
        )

        if bool(context.scene.get('SaberShader_V1148_RenderMatchActive', False)):
            render_status = quick.row()
            render_status.alert = True
            render_status.label(text='UMA Render Match active', icon='RENDER_STILL')


class AEF_PT_ui121_character(bpy.types.Panel):
    bl_label = '01  General / MMD'
    bl_idname = 'AEF_PT_ui121_character'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_saber_shader_v8'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aef_sabershader_v8
        section = layout
        content = section.column(align=True)
        content.prop(settings, 'universal_character_source')
        if settings.universal_character_source in {'AUTO', 'COLLECTION'}:
            content.prop(settings, 'universal_target_collection')
        content.prop(settings, 'universal_texture_folder')

        texture_row = content.row(align=True)
        texture_row.prop(
            settings,
            'universal_auto_load_textures',
            text='Auto-load',
            toggle=True,
        )
        texture_row.prop(
            settings,
            'universal_recover_broken_texture_paths',
            text='Repair Paths',
            toggle=True,
        )

        content.prop(
            settings,
            'universal_label_texture_nodes',
            text='Label Texture Nodes',
        )

        hint = content.box()
        hint.label(text='Auto mode: rig ownership → selection → hierarchy', icon='INFO')
        hint.label(text='Ambiguous texture matches are skipped.')
        if ae_developer_tools_visible(context) and context.scene.get('SaberShader_AE118_Materials', 0):
            hint.label(text='AE texture audit: see Text Editor', icon='TEXT')
            unresolved = int(context.scene.get('SaberShader_AE118_Unresolved', 0))
            if unresolved:
                issue = hint.row()
                issue.alert = True
                issue.label(text=f'AE: {unresolved} unresolved bind(s) in report', icon='ERROR')


class AEF_PT_ui121_general_eyes(bpy.types.Panel):
    bl_label = '02  Eye Tools'
    bl_idname = 'AEF_PT_ui121_general_eyes'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_saber_shader_v8'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aef_sabershader_v8
        eye_section = layout
        eye_fx = eye_section.box()
        eye_fx.label(text='Eye FX', icon='HIDE_OFF')
        eye_fx.prop(settings, 'eye_fx_enabled')
        if settings.eye_fx_enabled:
            eye_fx.prop(settings, 'eye_fx_strength', slider=True)
            row = eye_fx.row(align=True)
            row.prop(settings, 'eye_fx_iris_depth', slider=True)
            row.prop(settings, 'eye_fx_catchlight', slider=True)
            eye_fx.label(text='Authored highlights always take priority.')

        expression_box = eye_section.box()
        expression_box.label(text='Expression Eyes', icon='SHAPEKEY_DATA')
        expression_box.prop(settings, 'expression_eyes_enabled')
        expression_box.label(text='Expression PNGs are user-supplied.', icon='INFO')
        expression_box.label(text='Planes start hidden in the Outliner.', icon='HIDE_ON')
        expression_box.label(text='Enable eye (viewport) and camera (render) icons.')
        expression_box.prop(settings, 'uma_texture_library_folder', text='Expression PNG Folder')
        if settings.expression_eyes_enabled:
            expression_box.prop(settings, 'expression_eyes_style', expand=True)
            expression_box.separator(factor=0.5)
            expression_box.label(text='Sprite Visibility')
            expression_box.prop(settings, 'expression_eye_star_visibility', slider=True)
            expression_box.prop(settings, 'expression_eye_squint_visibility', slider=True)
            expression_box.prop(settings, 'expression_eye_spiral_visibility', slider=True)
            expression_box.prop(settings, 'expression_eye_shock_visibility', slider=True)
        else:
            expression_box.label(text='Native UMA sprites stay prepared but hidden.')



def _sabershader_ae_ui_scene_hint(context):
    """Read-only UI discovery; an actor-style name is NOT AE verification.

 The source detector can lose its scene markers if a later build cannot find
 the original texture/JSON folder. Keep the Endfield section discoverable
 without weakening any source/actor checks in the AE operators.
 """
    scene = getattr(context, 'scene', None)
    if scene is None:
        return False
    for obj in getattr(scene, 'objects', ()):
        if getattr(obj, 'type', '') != 'MESH':
            continue
        if str(getattr(obj, 'name', '')).lower().startswith('sabershader ae outline'):
            continue
        try:
            if bool(obj.get('XDZR8_AE110_Outline', False)):
                continue
        except (AttributeError, TypeError):
            pass
        if re.match(r'^s_actor_[a-z0-9]+_', str(getattr(obj, 'name', '')), re.I):
            return True
    return False


def _sabershader_ae_ui_available(context):
    """Discover AE tools from scene metadata or actor names, without granting verification."""
    return bool(_xdzr8_ui121_is_ae_scene(context) or
                _xdzr8_ui121_is_ae_eye(context) or
                _sabershader_ae_ui_scene_hint(context))


def _sabershader_ae_ui_preview_layout(layout, context):
    """Expose AE panel descriptions, but prevent mutations until source-verified."""
    if _xdzr8_ui121_is_ae_scene(context):
        return layout
    warning = layout.row()
    warning.alert = True
    warning.label(text='Source unverified: tools disabled', icon='LOCKED')
    locked = layout.column()
    locked.enabled = False
    return locked


def _sabershader_ae_draw_sections_inline(root_layout, context):
    """Draw Endfield sections inside the visible parent, bypassing hidden nested Panels.

 A read-only preview appears for AE-named scenes that fail source verification.
 Underlying operator guards remain unchanged.
 """
    from types import SimpleNamespace
    section_defs = (
        ('shading', 'Shading & Lighting', AEF_PT_ui121_ae_core),
        ('face_hair', 'Face SDF & Hair', AEF_PT_ui121_ae_face_hair),
        ('hair_fidelity', 'AE Hair Fidelity', AEF_PT_ui121_ae_hair_fidelity),
        ('hair_compression', 'Albedo Highlight Compression', AEF_PT_ui121_ae_hair_compression),
        ('cloth_iris', 'Cloth & Iris', AEF_PT_ui121_ae_cloth_eye),
        ('eye_repair', 'Eye Repair & LOD Guard', AEF_PT_ui121_ae_eye_repair),
        ('outline', 'Outline & Cleanup', AEF_PT_ui121_ae_outline_cleanup),
        ('ink', 'AE Ink — Camera & Material', AEF_PT_ui121_ae_gn_outline),
        ('lod', 'AE Character LOD Selector', AEF_PT_ui121_ae_lod_selector),
        ('audit', 'Material & UV Audit', AEF_PT_ui121_ae_audit),
    )
    root_layout.separator()
    root_layout.label(text='Endfield tools', icon='TOOL_SETTINGS')
    for token, label, panel_class in section_defs:
        header, body = root_layout.panel('sabershader_ae_' + token, default_closed=True)
        header.label(text=label)
        if body is not None:
            panel_class.draw(SimpleNamespace(layout=body), context)


class AEF_PT_ui121_endfield(bpy.types.Panel):
    bl_label = 'Arknights: Endfield'
    bl_idname = 'AEF_PT_ui121_endfield'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_saber_shader_v8'

    @classmethod
    def poll(cls, context):
        # An Endfield profile can remain available even if its source files are missing.
        # Keep its panel visible so the user can diagnose or repair that state.
        return (_xdzr8_ui121_is_ae_scene(context) or
                _xdzr8_ui121_is_ae_eye(context) or
                _sabershader_ae_ui_scene_hint(context))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.aef_sabershader_v8
        verified = _xdzr8_ui121_is_ae_scene(context)
        developer = ae_developer_tools_visible(context)

        if not verified:
            warning = layout.box()
            warning.label(text='AE character detected; sources not verified', icon='ERROR')
            warning.label(text=_xdzr8_ae_state(context)['reason'][:65], icon='INFO')
            warning.prop(settings, 'universal_texture_folder', text='Source Folder')
            warning.label(text='Run Build after verifying source assets', icon='INFO')
        else:
            layout.label(text='AE character verified', icon='CHECKMARK')

        # Keep the public interface focused on results and optional artist actions.
        # Shader stages run from Build, irrespective of panel visibility.
        # Diagnostic buttons and experiments remain behind Developer Tools;
        # versioned RNA names are never presented as public labels.
        count = int(scene.get('SaberShader_AE118_Materials', 0))
        if count:
            layout.label(text=f'{count} materials in last Build', icon='MATERIAL')
        visual_status = str(scene.get('SaberShader_AE_CompleteBuild_Status', ''))
        if visual_status:
            report = layout.box()
            row = report.row()
            if visual_status == 'COMPLETE':
                row.label(text='Last AE Build: Complete', icon='CHECKMARK')
            else:
                row.alert = True
                row.label(text='Last AE Build: Needs attention', icon='ERROR')
            eye_status = str(scene.get('SaberShader_AE_EyeBuildE3454_Status', ''))
            if eye_status and eye_status not in {'ALREADY_READY', 'REPAIRED'}:
                detail = str(scene.get('SaberShader_AE_EyeBuildE3454_Detail', ''))
                row = report.row()
                row.alert = True
                row.label(text='EyeShadow: ' + (detail[:55] if detail else eye_status[:55]), icon='ERROR')
            if developer:
                report.label(text='Outline: ' + str(scene.get('SaberShader_AE_CompleteBuild_Outline', ''))[:60])
                report.label(text='Eyeshadow: ' + str(scene.get('SaberShader_AE_CompleteBuild_Eyeshadow', ''))[:60])
                report.label(text='Color: ' + str(scene.get('SaberShader_AE_CompleteBuild_Color', ''))[:60])

        # Display LOD is deliberately manual, and is not part of AE Build.
        display_header, display_body = layout.panel('sabershader_ae_public_display_lod', default_closed=True)
        display_header.label(text='Display LOD (Optional)', icon='MOD_DECIM')
        if display_body is not None:
            display = display_body.column(align=True)
            display.enabled = bool(verified)
            display.prop(settings, 'ae129hf4565_lod_target', text='Display LOD')
            display.operator('sabershader.ae129hf4565_select_lod', text='Apply Display LOD', icon='HIDE_OFF')
            display.operator('sabershader.ae129hf4565_restore_lods', text='Restore Original Visibility', icon='LOOP_BACK')
            level = scene.get(_AE129HF4565_LOD_LEVEL)
            if level is not None:
                display.label(text='Current LOD: %s' % level, icon='INFO')
            display.label(text='Restore visibility before Build', icon='INFO')

        # Optional three-point scene lighting changes objects, not Build stages.
        lights_header, lights_body = layout.panel('sabershader_ae_public_lights', default_closed=True)
        lights_header.label(text='Preview Lighting (Optional)', icon='LIGHT_AREA')
        if lights_body is not None:
            lights = lights_body.column(align=True)
            lights.enabled = bool(verified)
            row = lights.row(align=True)
            row.operator('sabershader.ae118polish_create_lights', text='Create / Update', icon='LIGHT_AREA')
            row.operator('sabershader.ae118polish_remove_lights', text='Remove', icon='X')
            lights.label(text='Manual preview; does not alter original lights')

        # Older .blend files may contain an unfinished Si A/B study. Do not
        # strand ordinary users behind a developer-only Restore button when
        # that session prevents Build. Expose recovery, not experimentation.
        if verified:
            ab_rows = [obj for obj in scene.objects
                       if obj.name.startswith('S_actor_jsspsi_vfxpart_')
                       and obj.get('SaberShader_AE_Si_E341_AB_Token', '')]
            if ab_rows:
                ab_warning = layout.box()
                ab_row = ab_warning.row()
                ab_row.alert = True
                ab_row.label(text='Unfinished Si A/B session blocks Build', icon='ERROR')
                ab_warning.operator('sabershader.si_vfx_ab_restore',
                                    text='Restore Original Si VFX', icon='LOOP_BACK')
            else:
                from . import ae_fx_auto_appearance
                if ae_fx_auto_appearance.status(context) == 'SUSPENDED':
                    suspended = layout.box()
                    suspended.label(text='Si VFX restoration needs attention', icon='ERROR')
                    suspended.operator('sabershader.si_build_a_resume',
                                       text='Recover Suspended Si VFX', icon='FILE_REFRESH')

        # Settings rollback should remain accessible after an unsuccessful
        # Build, even with Developer Tools disabled.
        backup_id = str(scene.get('SaberShader_AEFullSetup_LastBackup', '') or '')
        if backup_id:
            recovery = layout.box()
            recovery.label(text='Previous AE Settings', icon='FILE_BACKUP')
            recovery.operator('sabershader.ae_fullsetup_restore',
                              text='Restore Previous AE Settings', icon='LOOP_BACK')
            recovery.label(text='Restores settings only, not materials')

        if developer:
            dev_header, dev_body = layout.panel('sabershader_ae_internal_tools', default_closed=True)
            dev_header.label(text='AE Developer Tools', icon='CONSOLE')
            if dev_body is not None:
                _sabershader_ae_draw_sections_inline(dev_body, context)
                # Keep the original setup, validation and recovery controls for
                # development without exposing them to default users.
                self._draw_ae_developer_setup(context, dev_body, settings, verified)

    @staticmethod
    def _draw_ae_developer_setup(context, parent_layout, settings, verified):
        # The controls below are the original Full Setup & Build Options UI.
        layout = parent_layout
        # Keep Full Setup controls available without overwhelming the main panel.
        setup_header, setup_body = layout.panel('sabershader_ae_setup_options', default_closed=True)
        setup_header.label(text='AE Full Setup & Build Options')
        if setup_body is not None:
            build_box = setup_body.box()
            build_box.label(text='AE Full Setup • Single verified Build', icon='SHADING_RENDERED')
            build_box.label(text='Included in main Build SaberShader', icon='CHECKMARK')
            build_box.prop(settings, 'ae_auto_profile_features',
                           text='Complete AE Visual Build (automatic)')
            build_box.label(text='Includes ramps, hair, cloth, eyes, rim, grading, outline')
            build_box.label(text='Previously OFF stage toggles enabled; numeric tuning preserved')
            build_box.label(text='Includes color view; no second Build or test previews')
            auto_status = str(context.scene.get('SaberShader_AE_AutoProfile_Status', '') or '')
            if auto_status:
                build_box.label(text='Auto AE: ' + auto_status[:26])
                build_box.label(text='Enabled %d | Preserved %d' % (
                    int(context.scene.get('SaberShader_AE_AutoProfile_Changed', 0)),
                    int(context.scene.get('SaberShader_AE_AutoProfile_Preserved', 0))))
                build_box.label(text='Prior OFF toggles updated: %d' % int(
                    context.scene.get('SaberShader_AE_AutoProfile_Overrides', 0)))
            preview = setup_body.box()
            preview.label(text='AE Full Setup • Read-only plan', icon='INFO')
            preview.operator('sabershader.ae_fullsetup_review',
                             text='Review planned steps', icon='VIEWZOOM')
            last_row = preview.row()
            last_row.enabled = bool(context.scene.get('SaberShader_AEFullSetup_LastRunReport', ''))
            last_row.operator('sabershader.ae_fullsetup_last_run',
                              text='Review last execution', icon='TEXT')
            preview.label(text='Forecast is separate from recorded task outcomes')
            # Keep recovery available after a failed build, even when source verification
            # is unknown and the usual source-dependent controls are disabled.
            recovery = setup_body.box()
            recovery.label(text='AE Full Setup • Settings Recovery', icon='FILE_BACKUP')
            backup_id = str(context.scene.get('SaberShader_AEFullSetup_LastBackup', '') or '')
            restore_row = recovery.row()
            restore_row.enabled = bool(backup_id)
            restore_row.operator('sabershader.ae_fullsetup_restore',
                                 text='Restore Previous AE Settings', icon='LOOP_BACK')
            if backup_id:
                recovery.label(text='Backup: ' + backup_id[-28:], icon='TEXT')
            recovery.label(text='Available after failed Build; settings only, no shader changes')
            setup_controls = setup_body.column()
            setup_controls.enabled = bool(verified)
            block=setup_controls.box()
            block.label(text='Endfield Full Setup • Stable Core', icon='SHADING_RENDERED')
            block.prop(settings,'ae129hf455_auto_full_setup', text='First AE Build defaults')
            block.label(text='Initial settings only on first AE Build')
            block.label(text='Complete Build enables stable final stages in existing scenes',icon='INFO')
            block.operator('sabershader.ae129hf455_apply_full_setup',
                           text='Reapply AE Settings (automatic JSON backup)',icon='FILE_BACKUP')
            block.label(text='Manual reapply requires Build again')
            prior=str(context.scene.get('SaberShader_AE129HF455_Profile',''))
            if prior:
                block.label(text='Last setup: '+prior[:38],icon='TEXT')
            block.label(text='Full setup report in Text Editor',icon='TEXT')
            hair_build=setup_controls.box()
            hair_build.label(text='AE Hair in Build',icon='SHADING_RENDERED')
            hair_build.prop(settings,'ae129hf4566_comp_build_enabled')
            hair_build.label(text='Final-only compression on verified Endfield hair')
            hair_build.label(text='Uses Hair01/02 calibration; no source images modified')
            hair_build.label(text='Set hair controls below; then Build SaberShader')
            hair_build.label(text='Mask/Split and GN preview stay manual')


class AEF_PT_ui121_ae_core(bpy.types.Panel):
    bl_label = 'Shading & Lighting'
    bl_idname = 'AEF_PT_ui121_ae_core'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)

    def draw(self, context):
        layout = self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        settings = context.scene.aef_sabershader_v8
        # Put the main Endfield calibration settings above the advanced controls.
        if _xdzr8_ui121_is_ae_scene(context):
            tune=layout.box()
            tune.label(text='Fidelity Calibration',icon='COLOR')
            tune.prop(settings,'ae123_fidelity_preset',text='Preset')
            row=tune.row(align=True)
            row.operator(AEF_OT_ae123_apply_preset.bl_idname,text='Apply Preset',icon='CHECKMARK')
            row.operator(AEF_OT_ae123_restore_preset.bl_idname,text='Restore Settings',icon='LOOP_BACK')
            tune.prop(settings,'ae123_calibration_enabled')
            if settings.ae123_calibration_enabled and settings.ae123_fidelity_preset!='SOURCE':
                tune.prop(settings,'ae123_calibration_strength',slider=True)
                cal = tune.box()
                cal.label(text='Render Fidelity', icon='RESTRICT_RENDER_OFF')
                cal.prop(settings,'ae126_grade_enabled')
                if settings.ae126_grade_enabled:
                    cal.prop(settings,'ae126_grade_strength',slider=True)
                else:
                    cal.label(text='Enable to make these controls affect Build')
                cal.prop(settings,'ae124_shadow_contrast',slider=True)
                cal.prop(settings,'ae124_fill_compression',slider=True)
                cal.prop(settings,'ae124_highlight_rolloff',slider=True)
                cal.prop(settings,'ae124_skin_lift',slider=True)
                cal.prop(settings,'ae124_cloth_white_protection',slider=True)
                cal.prop(settings,'ae124_hair_spec_balance',slider=True)
                cal.prop(settings,'ae124_iris_pop',slider=True)
            tune.label(text='Build to apply material changes',icon='INFO')
            tune.label(text='Artistic preview; not a game-exact LUT')
        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # Arknights Endfield — isolated native diffuse ramp preview
        # -------------------------------------------------------------
        if _sabershader_ae_ui_available(context):
            shade = layout.box()
            shade.label(text='Source Ramps', icon='SHADING_RENDERED')
            shade.prop(settings, 'ae_shading_enabled')
            if settings.ae_shading_enabled:
                shade.prop(settings, 'ae_shading_strength', slider=True)
                shade.prop(settings, 'ae_shading_ramp_floor', slider=True)
                shade.prop(settings, 'ae_shading_json_tint')
                shade.label(text=f'Ramp materials: {int(context.scene.get("SaberShader_AE112_ShadingCount",0))}')
                shade.label(text='Apply changes with Build SaberShader', icon='INFO')
            shade.label(text='Eevee + 1D _DiffRampMap required')
            shade.label(text='Shading report in Text Editor', icon='TEXT')
            shade.label(text='Packed / 2D decoding not yet verified.')

        # Keep scene-lighting adjustments manual and separate from shader builds.
        if _sabershader_ae_ui_available(context):
            polish=layout.box()
            polish.label(text='Lighting & Render Calibration',icon='LIGHT_AREA')
            polish.prop(settings,'ae_lighting_polish_enabled')
            if settings.ae_lighting_polish_enabled:
                polish.prop(settings,'ae_lighting_shadow_lift',slider=True)
                polish.prop(settings,'ae_lighting_rolloff',slider=True)
                polish.prop(settings,'ae_lighting_saturation',slider=True)
                polish.prop(settings,'ae_lighting_polish_eyes')
                if not settings.ae_shading_enabled:
                    w=polish.row();w.alert=True
                    w.label(text='AE Source Ramps required',icon='ERROR')
                polish.label(text='Rebuild shaders to apply tone settings',icon='INFO')
            polish.separator()
            polish.label(text='Optional calibrated 3-point Eevee preview rig')
            row=polish.row(align=True)
            row.prop(settings,'ae_lighting_key')
            row.prop(settings,'ae_lighting_fill')
            row.prop(settings,'ae_lighting_rim')
            row=polish.row(align=True)
            row.operator(AEF_OT_ae118polish_create_lights.bl_idname,text='Create / Update',icon='LIGHT_AREA')
            row.operator(AEF_OT_ae118polish_remove_lights.bl_idname,text='Remove',icon='X')
            polish.label(text='Keeps existing scene lighting intact; tune Fill first.')
            polish.label(text='Lighting and outline report in Text Editor',icon='TEXT')
        if _xdzr8_ui121_is_ae_scene(context):
            cm=layout.box()
            cm.label(text='AE Color Management', icon='COLOR')
            current=context.scene.view_settings
            cm.label(text='View: '+str(current.view_transform)[:28])
            cm.label(text='Recommended: Khronos PBR Neutral')
            row=cm.row(align=True)
            row.operator(AEF_OT_ae126_apply_color_management.bl_idname,
                         text='Apply AE View',icon='CHECKMARK')
            row.operator(AEF_OT_ae126_restore_color_management.bl_idname,
                         text='Restore View',icon='LOOP_BACK')
            cm.operator(AEF_OT_ae126_color_audit.bl_idname,
                        text='Audit Colors & Binds',icon='TEXT')
            cm.label(text='Complete AE Build applies View automatically.')
            cm.label(text='Color audit available in Text Editor')


class AEF_PT_ui121_ae_face_hair(bpy.types.Panel):
    bl_label = 'Face SDF & Hair'
    bl_idname = 'AEF_PT_ui121_ae_face_hair'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)

    def draw(self, context):
        layout = self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        settings = context.scene.aef_sabershader_v8
        # Show face-SDF controls only for a detected Endfield character.
        if _sabershader_ae_ui_available(context):
            face_sdf = layout.box()
            face_sdf.label(text='Face SDF', icon='LIGHT_SUN')
            face_sdf.prop(settings, 'ae_face_sdf_enabled')
            if settings.ae_face_sdf_enabled:
                face_sdf.prop(settings, 'ae_face_sdf_light_target', text='Light Direction Target')
                face_sdf.prop(settings, 'ae_face_sdf_uv_layer')
                face_sdf.prop(settings, 'ae_face_sdf_channel')
                face_sdf.prop(settings, 'ae_face_sdf_forward_axis')
                face_sdf.prop(settings, 'ae_face_sdf_mirror_side')
                face_sdf.prop(settings, 'ae_face_sdf_strength', slider=True)
                # Compare face-SDF shading against EEVEE’s diffuse-light response.
                facefix=face_sdf.box();facefix.label(text='Face Light Recovery',icon='LIGHT_AREA')
                facefix.prop(settings,'ae129hf451_face_enabled')
                if settings.ae129hf451_face_enabled:
                    facefix.prop(settings,'ae129hf451_face_mode')
                    if settings.ae129hf451_face_mode=='BALANCED':
                        facefix.prop(settings,'ae129hf451_face_recovery',slider=True)
                    facefix.label(text='Eevee diffuse probe + AE-authored ramp',icon='INFO')
                facefix.operator('sabershader.ae129hf451_use_selected_light',text='Use Selected Light for Face + Rim',icon='LIGHT_AREA')
                face_sdf.prop(settings, 'ae_face_sdf_softness', slider=True)
                face_sdf.prop(settings, 'ae_face_sdf_bias', slider=True)
                face_sdf.prop(settings, 'ae_face_sdf_invert')
                face_sdf.prop(settings, 'ae_face_sdf_preview')
                if not settings.ae_shading_enabled:
                    row = face_sdf.row(); row.alert=True
                    row.label(text='Enable AE Source Ramps first', icon='ERROR')
                if settings.ae_face_sdf_light_target is None:
                    row = face_sdf.row(); row.alert=True
                    row.label(text='Select light or Empty target', icon='ERROR')
                if (getattr(settings.ae_face_sdf_light_target,'type',None)=='LIGHT' and
                    getattr(getattr(settings.ae_face_sdf_light_target,'data',None),'type','')=='SUN'):
                    row = face_sdf.row(); row.alert=True
                    row.label(text='Sun: use Empty as direction locator', icon='ERROR')
                face_sdf.label(text='Experimental, not the original shader.')
                face_sdf.label(text='Rebuild with Build SaberShader', icon='INFO')
            face_live = layout.box()
            face_live.label(text='Live Eevee Face', icon='LIGHT_AREA')
            face_live.prop(settings,'ae129hf452_face_probe')
            if settings.ae129hf452_face_probe:
                face_live.prop(settings,'ae129hf452_face_gain',slider=True)
                face_live.prop(settings,'ae129hf452_face_range',slider=True)
                face_live.label(text='Uses all Eevee scene lights (not just SDF target)',icon='INFO')
            row=face_live.row(align=True)
            row.operator('sabershader.ae129hf452_enable_scene_face',
                               text='Enable Scene-Lit Face',icon='LIGHT_AREA')
            row.operator('sabershader.ae129hf454_apply_balanced_face',
                               text='Apply Balanced Face',icon='LIGHT')
            face_live.label(text='Preserves face SDF data; Build to apply')
            face_sdf.label(text='Face shading report in Text Editor', icon='TEXT')
            face_sdf.label(text='JSON report available in Text Editor', icon='INFO')
            count=int(context.scene.get('SaberShader_AE114_FaceActive',0))
            face_sdf.label(text='Face SDF active groups: %d' % count)

        # Hair-specular previews affect Endfield only; other profiles are unchanged.
        if _sabershader_ae_ui_available(context):
            hair = layout.box()
            hair.label(text='Hair Shading', icon='SHADING_TEXTURE')
            fidelity=hair.box()
            fidelity.label(text='Hair & Cloth Fidelity',icon='MODIFIER')
            fidelity.prop(settings,'ae129_preset',text='Preset')
            row=fidelity.row(align=True)
            row.operator(AEF_OT_ae129_apply_preset.bl_idname,text='Apply',icon='CHECKMARK')
            row.operator(AEF_OT_ae129_restore_preset.bl_idname,text='Restore',icon='LOOP_BACK')
            fidelity.prop(settings,'ae129_enabled')
            if settings.ae129_enabled:
                fidelity.prop(settings,'ae129_hair_pass')
            if settings.ae129_enabled and settings.ae129_hair_pass:
                fidelity.prop(settings,'ae129_hair_shadow',slider=True)
                fidelity.prop(settings,'ae129_hair_highlight_width',slider=True)
                fidelity.prop(settings,'ae129_hair_line_influence',slider=True)
                fidelity.label(text='Build to update • line map is experimental')
            fidelity.label(text='Hair/cloth fidelity report in Text Editor',icon='TEXT')
            source_check=hair.box()
            source_check.label(text='Source Texture Integrity',icon='VIEWZOOM')
            source_check.operator(AEF_OT_ae129hf1_source_audit.bl_idname,text='Audit Sources / Connections',icon='TEXT')
            source_check.prop(settings,'ae129hf1_debug_enabled')
            if settings.ae129hf1_debug_enabled:
                source_check.prop(settings,'ae129hf1_hair_mode')
                source_check.label(text='Debug view requires Build',icon='INFO')
            hf2=hair.box()
            hf2.label(text='Normal & Specular Reconstruction',icon='MODIFIER')
            hf2.prop(settings,'ae129hf2_enabled')
            if settings.ae129hf2_enabled:
                hf2.prop(settings,'ae129hf2_cloth_enabled')
                hf2.prop(settings,'ae129hf2_hair02_enabled')
                hf2.prop(settings,'ae129hf454_hf2_auto_recovery')
                hf2.operator('sabershader.ae129hf454_recover_hf2_normals',text='Check Existing HF2 Normals',icon='FILE_REFRESH')
                hf2.prop(settings,'ae129hf2_normal_strength',slider=True)
                hf2.prop(settings,'ae129hf2_flip_green')
                hf2.prop(settings,'ae129hf2_uv')
                hf2.prop(settings,'ae129hf2_debug')
                hf2.label(text='Only Wulfa _N RG; Hair01 _HN excluded')
                hf2.label(text='Build to compare • unchanged eyes',icon='INFO')
            hf2.label(text='Normal/specular report in Text Editor',icon='TEXT')
            hf3=hair.box()
            hf3.label(text='Hair Normal & Specular Source',icon='SHADING_TEXTURE')
            hf3.prop(settings,'ae129hf3_enabled')
            if settings.ae129hf3_enabled:
                hf3.prop(settings,'ae129hf3_hn_enabled')
                if settings.ae129hf3_hn_enabled:
                    hf3.prop(settings,'ae129hf3_hn_decode')
                    hf3.prop(settings,'ae129hf3_hn_strength',slider=True)
                    hf3.prop(settings,'ae129hf3_hn_uv')
                hf3.prop(settings,'ae129hf3_rs_mode')
                hf3.prop(settings,'ae129hf3_rs_y',slider=True)
                hf3.prop(settings,'ae129hf3_rs_flip_x')
                if settings.ae129hf3_rs_mode=='TINT_PROBE':
                    hf3.prop(settings,'ae129hf3_rs_weight',slider=True)
                hf3.prop(settings,'ae129hf3_preview')
                hf3.label(text='Experimental hypotheses • Build to compare',icon='INFO')
                hf3.label(text='Native HN / RS formulas NOT verified')
            hf3.label(text='Hair source report in Text Editor',icon='TEXT')
            hf4=hair.box()
            hf4.label(text='Hair Specular Ramp Calibration',icon='SHADING_RENDERED')
            hf4.prop(settings,'ae129hf4_enabled')
            if not settings.ae129hf4_enabled:
                hf4.label(text='Enable calibration and Build to generate an audit',icon='INFO')
            elif not settings.ae_shading_enabled or not settings.ae_hair_enabled:
                warning=hf4.row();warning.alert=True
                warning.label(text='Requires Source Ramps + Hair Shading',icon='ERROR')
            if settings.ae129hf4_enabled:
                hf4.prop(settings,'ae129hf4_mode')
                if settings.ae129hf4_mode!='GGX_ONLY':
                    hf4.prop(settings,'ae129hf4_y_axis')
                    if settings.ae129hf4_y_axis=='FIXED':
                        hf4.prop(settings,'ae129hf4_fixed_y',slider=True)
                    hf4.prop(settings,'ae129hf4_weight',slider=True)
                    row=hf4.row(align=True)
                    row.prop(settings,'ae129hf4_flip_x')
                    row.prop(settings,'ae129hf4_flip_y')
                hf4.prop(settings,'ae129hf4_preview')
                hf4.label(text='Requires AE Source Ramps + Hair Shading',icon='INFO')
                hf4.label(text='GGX vs _RS • build after each change')
                hf4.label(text='Source 2D axes remain experimental')
            hf4.label(text='Specular ramp report in Text Editor',icon='TEXT')
            hf42=hair.box()
            hf42.label(text='Hair Specular Window',icon='SHADING_RENDERED')
            hf42.prop(settings,'ae129hf42_enabled')
            hf42.prop(settings,'ae129hf42_preset')
            actions=hf42.row(align=True)
            actions.operator('sabershader.ae129hf42_apply_preset',text='Apply Preset',icon='CHECKMARK')
            actions.operator('sabershader.ae129hf42_restore_preset',text='Restore',icon='LOOP_BACK')
            if settings.ae129hf42_enabled:
                if not settings.ae129hf4_enabled or settings.ae129hf4_mode=='GGX_ONLY':
                    warning=hf42.row();warning.alert=True
                    warning.label(text='Select RS Tint / Gate',icon='INFO')
                hf42.prop(settings,'ae129hf42_separate')
                for family,label in [('hair01','Hair 01'),('hair02','Hair 02')]:
                    if family=='hair02' and not settings.ae129hf42_separate:
                        continue
                    section=hf42.column(align=True)
                    section.label(text=label)
                    for key in ('weight','glint','roughness','anisotropy','window'):
                        section.prop(settings,'ae129hf42_'+family+'_'+key,slider=True)
                hf42.label(text='GGX reference bypasses experimental overrides')
            hf42.label(text='Build after changing values',icon='INFO')
            hf42.label(text='Hair specular report in Text Editor',icon='TEXT')
            hf43=hair.box()
            hf43.label(text='Hair Source Research',icon='SHADING_TEXTURE')
            hf43.prop(settings,'ae129hf43_enabled')
            hf43.operator('sabershader.ae129hf43_source_audit',text='Inspect _HN / _RS Channels',icon='TEXT')
            if settings.ae129hf43_enabled:
                hf43.prop(settings,'ae129hf43_axis')
                if settings.ae129hf43_axis=='T_HALF':
                    hf43.label(text='Manual Light Direction (World XYZ):')
                    xyz = hf43.row(align=True)
                    xyz.prop(settings,'ae129hf43_light_dir',index=0,text='X')
                    xyz.prop(settings,'ae129hf43_light_dir',index=1,text='Y')
                    xyz.prop(settings,'ae129hf43_light_dir',index=2,text='Z')
                    hf43.label(text='Manual light proxy • does not track lights',icon='INFO')
                hf43.prop(settings,'ae129hf43_channel')
                if settings.ae129hf43_channel=='A':
                    hf43.label(text='Wulfa _RS alpha is constant: diagnostic only',icon='INFO')
                hf43.prop(settings,'ae129hf43_preview')
                if not settings.ae129hf4_enabled or settings.ae129hf4_mode=='GGX_ONLY':
                    notice=hf43.row();notice.alert=True
                    notice.label(text='Select RS Tint / Gate for this comparison',icon='INFO')
                hf43.label(text='Build after settings; source PNGs untouched')
            hf43.label(text='Hair source diagnostics in Text Editor',icon='TEXT')
            hf45=hair.box()
            hf45.label(text='Hair Rim Light',icon='LIGHT_SUN')
            hf45.prop(settings,'ae129hf45_enabled')
            hf45.prop(settings,'ae129hf45_preset')
            actions=hf45.row(align=True)
            actions.operator('sabershader.ae129hf45_apply_preset',text='Apply Preset',icon='CHECKMARK')
            actions.operator('sabershader.ae129hf45_restore_preset',text='Restore',icon='LOOP_BACK')
            if settings.ae129hf45_enabled:
                if not settings.ae_shading_enabled or not settings.ae_hair_enabled:
                    warning=hf45.row();warning.alert=True
                    warning.label(text='Requires AE Source Ramps + Hair Shading',icon='ERROR')
                hf45.prop(settings,'ae129hf45_intensity',slider=True)
                hf45.prop(settings,'ae129hf451_smooth_mask')
                hf45.prop(settings,'ae129hf45_width',slider=True)
                hf45.prop(settings,'ae129hf45_softness',slider=True)
                if settings.ae129hf451_smooth_mask:
                    hf45.label(text='Smoothstep rim: width + softness, no extreme power')
                else:
                    hf45.label(text='Legacy narrow power rim',icon='INFO')
                hf45.prop(settings,'ae129hf45_tint')
                rim_family=hf45.column(align=True)
                rim_family.label(text='Material Strength')
                rim_family.prop(settings,'ae129hf45_hair01',slider=True)
                rim_family.prop(settings,'ae129hf45_hair02',slider=True)
                hf45.prop(settings,'ae129hf45_directional',slider=True)
                hf45.prop(settings,'ae129hf451_rim_light_source')
                if settings.ae129hf451_rim_light_source=='SCENE':
                    hf45.prop(settings,'ae129hf451_rim_light',text='Blender Rim Light')
                    hf45.prop(settings,'ae129hf451_rim_backlight')
                    hf45.prop(settings,'ae129hf452_rim_live_gate')
                    if settings.ae129hf452_rim_live_gate:
                        hf45.prop(settings,'ae129hf452_rim_softness',slider=True)
                        hf45.prop(settings,'ae129hf452_rim_floor',slider=True)
                    if not _xdzr8_ae129hf451_target_ok(settings.ae129hf451_rim_light):
                        warn=hf45.row();warn.alert=True
                        warn.label(text='Choose Point / Area / Spot light',icon='ERROR')
                    elif settings.ae129hf45_directional<=0.00001:
                        hf45.label(text='Increase Directional Gate to follow light',icon='INFO')
                    else:
                        hf45.label(text='Rim follows light position (not its wattage)',icon='INFO')
                else:
                    hf45.label(text='Manual Rim Light (World XYZ):')
                    rimxyz=hf45.row(align=True)
                    for i,axis in enumerate('XYZ'):
                        rimxyz.prop(settings,'ae129hf45_light_dir',index=i,text=axis)
                    hf45.label(text='Manual proxy • does not track lights',icon='INFO')
                hybrid=hf45.box()
                hybrid.label(text='Hybrid Highlight',icon='LIGHT')
                hybrid.prop(settings,'ae129hf453_hybrid_enabled')
                if settings.ae129hf453_hybrid_enabled:
                    hybrid.prop(settings,'ae129hf453_hybrid_strength',slider=True)
                    hybrid.prop(settings,'ae129hf454_hybrid_mode')
                    if settings.ae129hf454_hybrid_mode=='CAMERA_BAND':
                        hybrid.prop(settings,'ae129hf453_axis')
                    else:
                        hybrid.label(text='Uses UV tangent flow + light/view half vector',icon='INFO')
                    hybrid.prop(settings,'ae129hf453_band_center',slider=True)
                    hybrid.prop(settings,'ae129hf453_band_width',slider=True)
                    hybrid.prop(settings,'ae129hf453_rim_mix',slider=True)
                    hybrid.prop(settings,'ae129hf453_tint')
                    hybrid.label(text='Camera-space band added to hair rim',icon='INFO')
                hf45.prop(settings,'ae129hf45_preview')
                hf45.label(text='Warm rim is separate from source reflections')
                hf45.label(text='Build after changing controls',icon='INFO')
            hf45.label(text='Hair rim report in Text Editor',icon='TEXT')
            repair=hair.box();repair.label(text='Live Face & Hair Rim Repair',icon='TOOL_SETTINGS')
            repair.operator('sabershader.ae129hf452_setup_scene',
                text='Use Selected Light for Live Face + Rim',icon='LIGHT_AREA')
            repair.operator('sabershader.ae129hf451_restore_final_views',text='Reset Hair Debug Views to Final',icon='LOOP_BACK')
            repair.operator('sabershader.ae129hf453_apply_hybrid',text='Apply Hybrid Hair Starter',icon='SHADING_RENDERED')
            tools=repair.row(align=True)
            tools.operator('sabershader.ae129hf454_apply_balanced_face',text='Apply Balanced Face',icon='LIGHT')
            tools.operator('sabershader.ae129hf454_recover_hf2_normals',text='Load HF2 Recovery Normals',icon='FILE_REFRESH')
            dupes=_xdzr8_ae129hf451_duplicate_preview_rims(context.scene)
            if dupes:
                warning=repair.row();warning.alert=True
                warning.label(text=f'{len(dupes)} duplicate AE Preview Rim set(s)',icon='ERROR')
            repair.label(text='Live lighting report in Text Editor',icon='TEXT')
            repair.label(text='Hair highlight report in Text Editor',icon='TEXT')
            repair.label(text='Hair recovery report in Text Editor',icon='TEXT')
            repair.label(text='Original source audit remains available')
            repair.label(text='Changes require Build; lights are not moved')
            hair.prop(settings,'ae_hair_enabled')
            if settings.ae_hair_enabled:
                hair.prop(settings,'ae_hair_spec_strength',slider=True)
                hair.prop(settings,'ae_hair_spec_roughness',slider=True)
                hair.prop(settings,'ae_hair_anisotropy',slider=True)
                hair.prop(settings,'ae_hair_rotation',slider=True)
                hair.prop(settings,'ae_hair_spec_threshold',slider=True)
                hair.prop(settings,'ae_hair_tangent_uv')
                hair.prop(settings,'ae_hair_preview')
                if not settings.ae_shading_enabled:
                    warning=hair.row();warning.alert=True
                    warning.label(text='Enable AE Source Ramps first',icon='ERROR')
                hair.label(text='Eevee • JSON hair anisotropy • UV tangents')
                hair.label(text='Rebuild with Build SaberShader',icon='INFO')
            hair.label(text='Native Unity BRDF / _RS decode not inferred')
            hair.label(text='Hair audit available in Text Editor',icon='TEXT')
            hair.label(text='Active groups: %d' % int(context.scene.get('SaberShader_AE115_HairActive',0)))


class AEF_PT_ui121_ae_cloth_eye(bpy.types.Panel):
    bl_label = 'Cloth & Iris'
    bl_idname = 'AEF_PT_ui121_ae_cloth_eye'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)

    def draw(self, context):
        layout = self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        settings = context.scene.aef_sabershader_v8
        # Endfield apparel/specular, independently opt-in.
        if _sabershader_ae_ui_available(context):
            cloth=layout.box()
            cloth.label(text='Cloth & Specular',icon='SHADING_RENDERED')
            if settings.ae129_enabled:
                fidelity=cloth.box()
                fidelity.label(text='AE Cloth Fidelity',icon='SHADING_RENDERED')
                fidelity.prop(settings,'ae129_cloth_pass')
                column=fidelity.column()
                column.enabled=settings.ae129_cloth_pass
                column.prop(settings,'ae129_cloth_ramp_multiplier')
                column.prop(settings,'ae129_cloth_dark_floor',slider=True)
                column.prop(settings,'ae129_cloth_material_separation',slider=True)
                column.prop(settings,'ae129_cloth_spec_scale')
                fidelity.label(text='Exact JSON; packed channels not decoded')
            if settings.ae129hf1_debug_enabled:
                source_check=cloth.box()
                source_check.label(text='Cloth Source View',icon='VIEWZOOM')
                source_check.prop(settings,'ae129hf1_cloth_mode')
                if settings.ae129hf1_cloth_mode=='SPEC_RAMP':
                    source_check.prop(settings,'ae_cloth_ramp_v',slider=True)
                source_check.label(text='Debug only • Build to apply')
            cloth.prop(settings,'ae_cloth_spec_enabled')
            if settings.ae_cloth_spec_enabled:
                cloth.prop(settings,'ae_cloth_spec_strength',slider=True)
                cloth.prop(settings,'ae_cloth_roughness_bias',slider=True)
                cloth.prop(settings,'ae_cloth_spec_threshold',slider=True)
                cloth.prop(settings,'ae_cloth_metal_emphasis',slider=True)
                cloth.prop(settings,'ae_cloth_authored_tint',slider=True)
                cloth.prop(settings,'ae_cloth_spec_mode')
                if settings.ae_cloth_spec_mode=='SOURCE_2D':
                    cloth.prop(settings,'ae_cloth_ramp_v',slider=True)
                cloth.prop(settings,'ae_cloth_preview')
                if str(settings.ae_cloth_preview).startswith('PACKED_'):
                    cloth.prop(settings,'ae_cloth_probe_uv')
                if (settings.ae_cloth_preview=='SPEC_RAMP' and
                    settings.ae_cloth_spec_mode!='SOURCE_2D'):
                    cloth.prop(settings,'ae_cloth_ramp_v',slider=True)
                if not settings.ae_shading_enabled:
                    warning=cloth.row();warning.alert=True
                    warning.label(text='Enable AE Source Ramps first',icon='ERROR')
                cloth.label(text='Eevee only • Apply via Build SaberShader',icon='INFO')
            cloth.label(text='2D _RS axes and _P channels not decoded')
            cloth.label(text='Cloth shading report in Text Editor',icon='TEXT')
            cloth.label(text='Active groups: %d' % int(context.scene.get('SaberShader_AE116_SpecularActive',0)))

        # Use the verified iris source for Endfield MatCap, independently of face and Uma eye effects.
        if _sabershader_ae_ui_available(context):
            eyes=layout.box()
            eyes.label(text='Iris & MatCap',icon='HIDE_OFF')
            eyes.prop(settings,'ae_eyes_enabled')
            if settings.ae_eyes_enabled:
                eyes.prop(settings,'ae_eyes_matcap_strength',slider=True)
                eyes.prop(settings,'ae_eyes_json_tint',slider=True)
                eyes.prop(settings,'ae_eyes_depth_strength',slider=True)
                eyes.prop(settings,'ae_eyes_glaze_strength',slider=True)
                row=eyes.row(align=True)
                row.prop(settings,'ae_eyes_flip_x')
                row.prop(settings,'ae_eyes_flip_y')
                eyes.prop(settings,'ae_eyes_preview')
                eyes.label(text='Source JSON iris + MatCap RGB; no alpha changes')
                eyes.label(text='Rebuild with Build SaberShader',icon='INFO')
            source=eyes.box()
            source.label(text='Iris Source Reconstruction',icon='IMAGE_DATA')
            source.prop(settings,'ae128hf1_iris_mode',text='Output')
            source.label(text='Source RGB: no MatCap, grades or alpha transparency')
            source.label(text='Build to update; original textures stay unchanged')
            source.label(text='Iris source report in Text Editor',icon='TEXT')
            # Use the verified source iris rather than an incidental numeric suffix
            # on a generated material such as SaberShader - Eyes.002.
            polish=eyes.box()
            polish.label(text='AE Eye Material Polish',icon='COLOR')
            polish.prop(settings,'ae127_eye_preset',text='Preset')
            actions=polish.row(align=True)
            actions.operator(AEF_OT_ae127_apply_eye_preset.bl_idname,text='Apply Preset',icon='CHECKMARK')
            actions.operator(AEF_OT_ae127_restore_eye_preset.bl_idname,text='Restore',icon='LOOP_BACK')
            polish.prop(settings,'ae127_enabled')
            if settings.ae127_enabled:
                polish.prop(settings,'ae127_iris_saturation',slider=True)
                polish.prop(settings,'ae127_iris_contrast',slider=True)
                polish.prop(settings,'ae127_dark_definition',slider=True)
                polish.prop(settings,'ae127_highlight_taming',slider=True)
                polish.prop(settings,'ae_eyeshadow_strength',slider=True,text='Upper Lid Overlay Opacity')
                polish.label(text='Only verified source iris; shadow is separate')
                polish.label(text='Rebuild to update iris nodes',icon='INFO')
            polish.label(text='Active iris materials: %d'%int(context.scene.get('SaberShader_AE127_ActiveEyes',0)))
            polish.label(text='Iris audit: see Text Editor',icon='TEXT')
            eyes.label(text='MatCap camera-normal mapping is an approximation')
            eyes.label(text='Eye highlights report in Text Editor',icon='TEXT')
            eyes.label(text='Active eyes: %d'%int(context.scene.get('SaberShader_AE117_EyesActive',0)))


class AEF_PT_ui121_ae_eye_repair(bpy.types.Panel):
    bl_label = 'Eye Repair & LOD Guard'
    bl_idname = 'AEF_PT_ui121_ae_eye_repair'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)

    def draw(self, context):
        layout = self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        settings = context.scene.aef_sabershader_v8
        # Full Build uses the verified LOD0 eye mask by default.
        full=layout.box()
        full.label(text='Integrated Eye Full Setup',icon='HIDE_OFF')
        full.prop(settings,'ae123_eye_full_setup')
        if settings.ae123_eye_full_setup:
            full.prop(settings,'ae123_eye_guard_lods')
            full.prop(settings,'ae_eyeshadow_strength',slider=True)
            full.prop(settings,'ae_eyeshadow_invert')
            full.label(text='Auto-applied during verified AE Build')
        last_action=str(context.scene.get('SaberShader_AE123_LastAction',''))
        if last_action in {'FULL_BUILD','FULL_BUILD_SAFE_SKIP'}:
            n=int(context.scene.get('SaberShader_AE124_EyeReady',0))
            total=int(context.scene.get('SaberShader_AE124_EyeTotal',0))
            warning=int(context.scene.get('SaberShader_AE124_EyeWarnings',0))
            status=full.row()
            status.alert=bool(warning or not n)
            status.label(text=f'Built eye overlay: {n}/{total} ready',
                         icon='CHECKMARK' if n and not warning else 'ERROR')
        if context.scene.get('SaberShader_AE125_Status',''):
            status=full.row()
            status.alert=context.scene.get('SaberShader_AE125_Status')!='READY'
            status.label(text='AE Face/Eye: '+str(context.scene['SaberShader_AE125_Status']),
                         icon='CHECKMARK' if not status.alert else 'ERROR')
            full.label(text='Face and eye report in Text Editor',icon='TEXT')
        row=full.row(align=True)
        row.operator(AEF_OT_ae123_apply_eye.bl_idname,text='Apply Now',icon='CHECKMARK')
        row.operator(AEF_OT_ae123_restore_eye.bl_idname,text='Restore',icon='LOOP_BACK')
        full.operator('sabershader.ae_eye_diagnose_e3454', text='Inspect EyeShadow UV & Mask', icon='VIEWZOOM')
        status = str(context.scene.get('SaberShader_AE_EyeBuildE3454_Status', ''))
        if status:
            full.label(text='Eye Shadow Build: ' + status[:38], icon='CHECKMARK' if status in {'ALREADY_READY','REPAIRED'} else 'ERROR')
            if status not in {'ALREADY_READY', 'REPAIRED'}:
                full.label(text=str(context.scene.get('SaberShader_AE_EyeBuildE3454_Detail',''))[:90])
        full.label(text='Iris & sclera are never painted white')
        full.label(text='Eye build report in Text Editor',icon='TEXT')

        # Keep eye whites separate from the source-authored eye-shadow overlay.
        eye122 = layout.box()
        eye122.label(text='Eye White & Lid Detail', icon='HIDE_OFF')
        eye122.prop(settings, 'ae_eye122_material')
        eye122.operator(AEF_OT_ae122_inspect.bl_idname, text='Inspect Eye Material', icon='VIEWZOOM')
        eye122.prop(settings, 'ae_eye122_mode')
        if settings.ae_eye122_mode == 'SCLERA':
            eye122.prop(settings, 'ae_eye122_ivory')
            eye122.prop(settings, 'ae_eye122_shadow_softness', slider=True)
            eye122.prop(settings, 'ae_eye122_opacity', slider=True)
            eye122.label(text='Artist sclera only; not an original JSON shader')
        elif settings.ae_eye122_mode == 'LID_MASK':
            eye122.prop(settings, 'ae_eyeshadow_strength', slider=True)
            eye122.prop(settings, 'ae_eyeshadow_invert')
        row = eye122.row(align=True)
        row.operator(AEF_OT_ae122_apply.bl_idname, text='Apply to Eye', icon='MATERIAL')
        row.operator(AEF_OT_ae122_restore.bl_idname, text='Restore', icon='LOOP_BACK')
        eye122.label(text='Eyes.003 name alone does not prove its role')
        eye122.label(text='Eye white/lid report in Text Editor', icon='TEXT')

        # Eye LOD and compositing safeguards require explicit user action.
        # Do not apply them automatically during Build or affect other profiles.
        if _sabershader_ae_ui_available(context):
            eye120 = layout.box()
            eye120.label(text='Eye Compositing / LOD Guard', icon='HIDE_OFF')
            eye120.label(text='Inspect before editing AE eye meshes.')
            eye120.operator(AEF_OT_ae120_inspect.bl_idname, text='Inspect Eye LODs / Materials', icon='VIEWZOOM')
            eye120.prop(settings, 'ae_eye120_guard_iris')
            eye120.prop(settings, 'ae_eye120_guard_shadow')
            row = eye120.row(align=True)
            row.operator(AEF_OT_ae120_guard.bl_idname, text='Guard Eye LODs', icon='HIDE_ON')
            row.operator(AEF_OT_ae120_restore_guard.bl_idname, text='Restore', icon='LOOP_BACK')
            eye120.label(text='Overlay uses original mask; LOD0 only.')
            eye120.prop(settings, 'ae_eyeshadow_strength', slider=True)
            eye120.prop(settings, 'ae_eyeshadow_invert')
            row = eye120.row(align=True)
            row.operator(AEF_OT_ae120_apply_overlay.bl_idname, text='Apply Eye Overlay', icon='MATERIAL')
            row.operator(AEF_OT_ae120_restore_overlay.bl_idname, text='Restore Overlay', icon='LOOP_BACK')
            eye120.separator()
            eye120.label(text='Optional: tame iris highlights (no Build).')
            eye120.prop(settings, 'ae_eye120_matcap_cap', slider=True)
            eye120.prop(settings, 'ae_eye120_glaze_cap', slider=True)
            row = eye120.row(align=True)
            row.operator(AEF_OT_ae120_limit_iris.bl_idname, text='Limit Iris Glare', icon='LIGHT_SUN')
            row.operator(AEF_OT_ae120_restore_iris.bl_idname, text='Restore Glare', icon='LOOP_BACK')
            eye120.label(text='Eye LOD audit available in Text Editor', icon='TEXT')

        # Preserve the original Endfield mask in a separate transparent eye-shadow material.
        # Leave imported FBX materials untouched during Build.
        if _sabershader_ae_ui_available(context):
            eye_shadow=layout.box()
            eye_shadow.label(text='Eye Shadow Overlay',icon='HIDE_OFF')
            eye_shadow.label(text='Separate transparent material; never auto-applied')
            eye_shadow.prop(settings,'ae_eyeshadow_prefer_lod0')
            eye_shadow.prop(settings,'ae_eyeshadow_hide_other_lods')
            eye_shadow.prop(settings,'ae_eyeshadow_strength',slider=True)
            eye_shadow.prop(settings,'ae_eyeshadow_invert')
            eye_shadow.prop(settings,'ae_eyeshadow_color_source')
            if settings.ae_eyeshadow_color_source=='CUSTOM':
                eye_shadow.prop(settings,'ae_eyeshadow_custom_color')
            row=eye_shadow.row(align=True)
            row.operator(AEF_OT_ae119_preview_eyeshadow.bl_idname,text='Inspect',icon='VIEWZOOM')
            row.operator(AEF_OT_ae119_apply_eyeshadow.bl_idname,text='Apply Material',icon='MATERIAL')
            eye_shadow.operator(AEF_OT_ae119_restore_eyeshadow.bl_idname,text='Restore Original Materials',icon='LOOP_BACK')
            eye_shadow.label(text='Select S_actor_*_eyeshadow_*_lodN')
            eye_shadow.label(text='Eye shadow report in Text Editor',icon='TEXT')


class AEF_PT_ui121_ae_outline_cleanup(bpy.types.Panel):
    bl_label = 'Outline & Cleanup'
    bl_idname = 'AEF_PT_ui121_ae_outline_cleanup'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)

    def draw(self, context):
        layout = self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        settings = context.scene.aef_sabershader_v8
        # Arknights Endfield — isolated silhouette preview
        # -------------------------------------------------------------
        if _sabershader_ae_ui_available(context):
            ae = layout.box()
            ae.label(text='AE Silhouette', icon='MOD_OUTLINE')
            ae.prop(settings, 'ae_outline_enabled')
            ae.label(text='Legacy outline is disabled for AE.')
            if settings.ae_outline_enabled:
                ae.prop(settings, 'ae_outline_width', slider=True)
                ae.prop(settings, 'ae_outline_width_mode')
                if settings.ae_outline_width_mode == 'CAMERA':
                    ae.prop(settings,'ae_outline_target_px')
                    if context.scene.camera is None:
                        w=ae.row(); w.alert=True
                        w.label(text='No active camera: uses world width',icon='ERROR')
                widths=ae.column(align=True)
                widths.prop(settings,'ae_outline_hair_multiplier')
                widths.prop(settings,'ae_outline_cloth_multiplier')
                ae.prop(settings, 'ae_outline_color_mode')
                if settings.ae_outline_color_mode == 'FIXED':
                    ae.prop(settings, 'ae_outline_fixed_color')
                else:
                    ae.prop(settings,'ae_outline_ink_brightness',slider=True)
                ae.prop(settings, 'ae_outline_body')
                if settings.ae_outline_body:
                    ae.prop(settings,'ae_outline_body_multiplier')
                ae.prop(settings, 'ae_outline_face')
                if settings.ae_outline_face:
                    ae.prop(settings,'ae_outline_face_multiplier')
            actions = ae.row(align=True)
            actions.operator(AEF_OT_ae110_refresh_outline.bl_idname, text='Refresh Silhouette', icon='FILE_REFRESH')
            actions.operator(AEF_OT_ae110_remove_outline.bl_idname, text='Remove', icon='X')
            ae.label(text=f'Generated shells: {int(context.scene.get("SaberShader_AE110_ShellCount",0))}')
            ae.label(text='Outline report in Text Editor', icon='TEXT')
            ae.label(text='Camera adaptation recalculated on Refresh only.')
            ae.label(text='ST/detail strokes await validation.')
            research=layout.box()
            research.label(text='Hybrid Outline Research',icon='MOD_OUTLINE')
            research.prop(settings,'ae129hf453_outline_research_enabled')
            research.prop(settings,'ae129hf453_outline_mode')
            row=research.row(align=True)
            row.operator('sabershader.ae129hf453_outline_audit',text='Audit Research',icon='TEXT')
            row.operator('sabershader.ae129hf453_apply_hybrid',text='Apply Hair Starter',icon='CHECKMARK')
            research.label(text='Read-only comparison is available',icon='INFO')
            research.label(text='Outline comparison report in Text Editor',icon='TEXT')
            research.label(text='Geometry Nodes is in the dedicated panel below.', icon='INFO')


        # -------------------------------------------------------------
        # Arknights Endfield — non-destructive scene cleanup
        # -------------------------------------------------------------
        if _sabershader_ae_ui_available(context):
            clean = layout.box()
            clean.label(text='Scene Cleanup', icon='OUTLINER_OB_EMPTY')
            clean.prop(settings, 'ae_cleanup_auto_build')
            clean.prop(settings, 'ae_cleanup_shadow')
            clean.prop(settings, 'ae_eyeshadow_keep_helpers')
            clean.prop(settings, 'ae_cleanup_axes')
            clean.prop(settings, 'ae_cleanup_lods')
            clean.label(text='Use AE Character LOD Selector below; do not delete source LODs')
            actions = clean.row(align=True)
            actions.operator(AEF_OT_ae111_preview_cleanup.bl_idname, text='Preview', icon='VIEWZOOM')
            actions.operator(AEF_OT_ae111_hide_cleanup.bl_idname, text='Hide', icon='HIDE_ON')
            actions = clean.row(align=True)
            actions.operator(AEF_OT_ae111_restore_cleanup.bl_idname, text='Restore', icon='LOOP_BACK')
            actions.operator(AEF_OT_ae111_delete_cleanup.bl_idname, text='Delete (Manual)', icon='TRASH')
            clean.label(text='Rig parent axes are never auto-deleted.')
            clean.label(text='Cleanup report in Text Editor', icon='TEXT')


class AEF_PT_ui121_ae_hair_fidelity(bpy.types.Panel):
    bl_label='AE Hair Fidelity'
    bl_idname='AEF_PT_ui121_ae_hair_fidelity'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_ae_face_hair'
    bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)
    def draw(self,context):
        layout=self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        s=getattr(context.scene,'aef_sabershader_v8',None)
        if s is None:
            layout.label(text='SaberShader settings unavailable',icon='ERROR');return
        layout.prop(s,'ae129hf456_enabled')
        layout.prop(s,'ae129hf456_preset')
        row=layout.row(align=True)
        row.operator('sabershader.ae129hf456_apply_hair_preset',text='Apply Preset')
        row.operator('sabershader.ae129hf456_restore_hair',text='Restore Previous')
        if s.ae129hf456_enabled:
            if not (s.ae_shading_enabled and s.ae_hair_enabled and s.ae129hf45_enabled):
                warning=layout.row();warning.alert=True
                warning.label(text='Enable source ramps, hair and rim',icon='ERROR')
            layout.prop(s,'ae129hf456_mode')
            if s.ae129hf456_mode!='LEGACY':
                layout.prop(s,'ae129hf456_strength',slider=True)
                layout.prop(s,'ae129hf456_width',slider=True)
                layout.prop(s,'ae129hf456_rim_balance',slider=True)
                layout.prop(s,'ae129hf456_color_preserve',slider=True)
                layout.prop(s,'ae129hf456_strand_contrast',slider=True)
                layout.prop(s,'ae129hf456_facing_bias',slider=True)
                layout.prop(s,'ae129hf456_hair01',slider=True)
                layout.prop(s,'ae129hf456_hair02',slider=True)
                layout.prop(s,'ae129hf456_tint')
                layout.prop(s,'ae129hf456_preview')
                layout.prop(s,'ae129hf456_isolate_rim')
                if s.ae129hf456_mode in {'TANGENT_HALF','ROSSI_GROUNDED'}:
                    layout.label(text='UV tangent uses existing AE Hair UV control')
                if s.ae129hf453_hybrid_enabled:
                    w=layout.row();w.alert=True
                    w.label(text='Hybrid also enabled: stacked highlights',icon='ERROR')
        layout.separator()
        diagnosis=layout.box()
        diagnosis.label(text='AE Hair • Albedo, Diffuse & Source Mask',icon='SHADING_RENDERED')
        diagnosis.prop(s,'ae129hf4563_source_view')
        if s.ae129hf4563_source_view == 'DIFFUSE_RECON':
            diagnosis.prop(s,'ae129hf4564_recon_mix',slider=True)
        diagnosis.label(text='Delta views = absolute RGB difference, not native masks')
        diagnosis.label(text='Each Preview replaces prior preview; Restore returns original')
        layout.label(text='A/B compatible Endfield hair (no external JSON):')
        preview=layout.row(align=True)
        preview.operator('sabershader.ae129hf456_preview_existing',text='Preview Existing')
        preview.operator('sabershader.ae129hf456_restore_existing',text='Restore Existing')
        layout.label(text='Preview groups: %d'%int(context.scene.get('SaberShader_AE129HF456_PreviewGroups',0)))
        layout.operator('sabershader.ae129hf456_hair_audit',text='Audit Hair Source Graph',icon='TEXT')
        layout.label(text='Trace hair from Raw Albedo to Source Diffuse before specular and rim')
        layout.label(text='Use Raw Albedo / Source Diffuse / Diffuse Reconstruction first, then Preview Existing')
        layout.label(text='Hair fidelity report in Text Editor')


class AEF_PT_ui121_ae_gn_outline(bpy.types.Panel):
    bl_label = 'AE Ink — Camera & Material'
    bl_idname = 'AEF_PT_ui121_ae_gn_outline'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_ae_outline_cleanup'

    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)

    def draw(self,context):
        layout=self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        settings=getattr(context.scene,'aef_sabershader_v8',None)
        if settings is None:
            layout.label(text='SaberShader settings not registered',icon='ERROR')
            return
        layout.label(text='GN preview is optional; Full Setup retains AE Ink',icon='INFO')
        mode=layout.box();mode.label(text='Projected Width')
        mode.prop(settings,'ae129hf4552_width_mode')
        if settings.ae129hf4552_width_mode=='PIXELS':
            for key in ('ae129hf4552_px_cloth','ae129hf4552_px_hair',
                        'ae129hf4552_px_body','ae129hf4552_px_face'):
                mode.prop(settings,key)
            if context.scene.camera is None:
                warning=mode.row();warning.alert=True
                warning.label(text='No active camera: world-width fallback',icon='ERROR')
            mode.label(text='Camera movement tracked; lens change requires Preview GN')
        else:
            mode.label(text='Uses original AE world/character scale')
        inks=layout.box();inks.label(text='Material-Specific Ink')
        inks.prop(settings,'ae129hf4552_split_materials')
        if settings.ae129hf4552_split_materials:
            inks.prop(settings,'ae129hf4552_max_shells')
        inks.prop(settings,'ae129hf455gn_desaturate',text='Ink Desaturation',slider=True)
        inks.prop(settings,'ae129hf4552_color_depth',slider=True)
        inks.prop(settings,'ae129hf455gn_width_scale',text='GN Global Width',slider=True)
        inks.prop(settings,'ae129hf4552_clamp_factor')
        actions=layout.row(align=True)
        actions.operator('sabershader.ae129hf455gn_preview',text='Preview GN')
        actions.operator('sabershader.ae129hf455gn_restore',text='Restore AE Ink')
        layout.operator('sabershader.ae129hf455gn_audit',text='Audit AE Ink / GN / ST')
        layout.label(text='Preview shells: %d' % int(context.scene.get('SaberShader_AE129HF455GN_PreviewCount',0)))
        layout.label(text='Build clears GN preview; only changes generated shells')
        layout.label(text='Internal _ST strokes: research only, NOT applied')
        layout.label(text='Outline preview report in Text Editor',icon='TEXT')


class AEF_PT_ui121_ae_audit(bpy.types.Panel):
    bl_label = 'Material & UV Audit'
    bl_idname = 'AEF_PT_ui121_ae_audit'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _sabershader_ae_ui_available(context)

    def draw(self, context):
        layout = self.layout
        layout = _sabershader_ae_ui_preview_layout(layout, context)
        settings = context.scene.aef_sabershader_v8
        # This audit reports findings without running Build or editing shaders.
        if _sabershader_ae_ui_available(context):
            audit_box = layout.box()
            audit_box.label(text='Material & UV Audit', icon='IMAGE_DATA')
            audit_box.operator(AEF_OT_ae113_fidelity_uv_audit.bl_idname,
                               text='Audit Materials / UV (Read-Only)', icon='VIEWZOOM')
            audit_box.label(text='Automatic after verified AE Build; manual rerun available')
            audit_box.label(text='JSON • PNG • UV • image bindings')
            audit_box.label(text='Material/UV report in Text Editor', icon='TEXT')
            if int(context.scene.get('SaberShader_AE113_LastAuditSlots',0)):
                audit_box.label(text='Slots: %d  |  JSON matched: %d' % (
                    int(context.scene.get('SaberShader_AE113_LastAuditSlots',0)),
                    int(context.scene.get('SaberShader_AE113_LastAuditMatched',0))))
                missing_uv=int(context.scene.get('SaberShader_AE113_LastAuditMissingUV',0))
                if missing_uv:
                    warning=audit_box.row();warning.alert=True
                    warning.label(text='%d slots reference absent UV maps' % missing_uv, icon='ERROR')


class AEF_PT_ui121_uma(bpy.types.Panel):
    bl_label = 'UMA Hair Lab'
    bl_idname = 'AEF_PT_ui121_uma'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_saber_shader_v8'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aef_sabershader_v8
        uma_section = layout
        hair_native = uma_section.box()
        hair_native.label(text='Current Hair Flow', icon='MATERIAL')
        hair_native.label(text='Independent recreation; not copied nodes.')
        hair_native.label(text='N·V • Base.G gloss • Ctrl.G metal • Ctrl.B rim')

        hair_diag = uma_section.box()
        hair_diag.label(text='Line Flow Audit', icon='VIEWZOOM')
        hair_diag.prop(settings, 'uma_hair_texture_sampling')
        hair_diag.prop(settings, 'uma_hair_diagnostic_mode')

        _flow_notes = {
            'FULL_NATIVE': '00 • Complete Hair stack',
            'RAW_DIFF': '01 • MainTex only',
            'RAW_SHAD': '02 • ToonMap only',
            'DIFF_SHAD_DELTA': '03 • |Diff - Shad-C| ×8',
            'TRIPLE_R': '04 • Base.R toon control',
            'TRIPLE_G': '05 • Base.G highlight mask',
            'TRIPLE_B': '06 • Base.B cutout',
            'CTRL_G': '07 • Ctrl.G metallic mask',
            'CTRL_B': '08 • Ctrl.B rim mask',
            'TOON_FACTOR': '09 • Toon factor',
            'TOON_ONLY': '10 • Toon base',
            'POST_HIGHLIGHT': '11 • After highlight',
            'POST_RIM': '12 • After rim',
        }
        hair_diag.label(text=_flow_notes.get(settings.uma_hair_diagnostic_mode, 'Hair audit mode'))

        render_match = uma_section.box()
        render_match.label(text='EEVEE Render Match', icon='RENDER_STILL')
        row = render_match.row(align=True)
        row.scale_y = 1.15
        row.operator(
            AEF_OT_uma_hair_render_match_v1148.bl_idname,
            text='Apply Match',
            icon='CHECKMARK',
            depress=bool(context.scene.get('SaberShader_V1148_RenderMatchActive', False)),
        )
        row.operator(
            AEF_OT_uma_hair_render_match_restore_v1148.bl_idname,
            text='Restore',
            icon='LOOP_BACK',
        )
        render_match.label(text='1920×1080 • Standard • Viewport 16 • Render 64')


class AEF_PT_ui121_fgo_arcade(bpy.types.Panel):
    """Dedicated profile UI over the existing auto-detected FGO Arcade backend."""
    bl_label = 'FGO Arcade'
    bl_idname = 'AEF_PT_ui121_fgo_arcade'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_saber_shader_v8'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aef_sabershader_v8
        source = layout.box()
        source.label(text='Servant / Ascension Source', icon='FILE_FOLDER')
        source.prop(settings,'universal_texture_folder',text='Source Folder')
        source.label(text='Use one svt_####_s## folder per audit.')
        source.operator(AEF_OT_fgo_arcade_source_audit_v4572.bl_idname,
                        text='Audit Source & Stage',icon='VIEWZOOM')
        if context.scene.get('SaberShader_HF4572_FGOAuditStage'):
            source.label(text='Servant: '+str(context.scene.get('SaberShader_HF4572_FGOAuditServant','?')) +
                         '  /  '+str(context.scene.get('SaberShader_HF4572_FGOAuditStage','?')))
            row=source.row()
            ready=bool(context.scene.get('SaberShader_HF4572_FGOAuditReady',False))
            row.label(text=('Source verified' if ready else 'Source needs review')+
                      ' - '+str(context.scene.get('SaberShader_HF4572_FGOAuditCount',0))+' DDS',
                      icon='CHECKMARK' if ready else 'ERROR')
            warnings=int(context.scene.get('SaberShader_HF4572_FGOAuditWarnings',0))
            if warnings:
                source.label(text=f'{warnings} note(s); see Text Editor',icon='INFO')
        source.label(text='S01 face maps in S02 may be shared.')
        resource_box = layout.box()
        resource_box.label(text='Resource Resolution', icon='IMAGE_DATA')
        resource_box.operator(AEF_OT_fgo_arcade_resource_audit_v4573.bl_idname,
                              text='Audit 2D Paths & Native Materials', icon='VIEWZOOM')
        if 'SaberShader_HF4573_ReadyRelinks' in context.scene:
            resource_box.label(text=f'Exact 2D: {int(context.scene.get("SaberShader_HF4573_ReadyRelinks", 0))}  |  Native: {int(context.scene.get("SaberShader_HF4573_MappedMaterials", 0))}')
            resource_box.label(text=f'Cubemaps skipped: {int(context.scene.get("SaberShader_HF4573_CubemapsSkipped", 0))}', icon='INFO')
        path_row = resource_box.row(align=True)
        path_row.operator(AEF_OT_fgo_arcade_relink_v4573.bl_idname,
                          text='Relink Verified 2D', icon='FILE_REFRESH')
        path_row.operator(AEF_OT_fgo_arcade_restore_images_v4573.bl_idname,
                          text='Restore Paths', icon='LOOP_BACK')
        native_row = resource_box.row(align=True)
        native_row.operator(AEF_OT_fgo_arcade_store_native_map_v4573.bl_idname,
                            text='Store Native Map', icon='BOOKMARKS')
        native_row.operator(AEF_OT_fgo_arcade_restore_native_map_v4573.bl_idname,
                            text='Restore Map', icon='LOOP_BACK')
        resource_box.label(text='Only exact, native-backed, non-cubemap DDS relinked.')
        resource_box.label(text='Report: Text Editor / FGO Resource Mapping Audit')
        settings_box = layout.box()
        settings_box.label(text='FGO Arcade Native Controls',icon='MATERIAL')
        settings_box.prop(settings,'fgo_ramp_stage_isolation')
        settings_box.prop(settings,'fgo_isolate_base_facial_layers')
        settings_box.prop(settings,'fgo_cheek_overlay_strength')
        settings_box.label(text='Ramp slots are diagnostic, not stage selectors.')
        settings_box.label(text='Keep source-authored images unchanged.')
        build = layout.box()
        build.label(text='Automatic FGO detection on Build',icon='INFO')
        build.label(text='Only verified native source activates routing.')
        build.prop(context.scene.aef_fgo_uv_repair_v45747, 'auto_on_build',
                   text='Auto-correct UV V (FGO only)')
        build.prop(context.scene.aef_fgo_shading_v45749,'mode', text='Shading after Build')
        build.prop(context.scene.aef_fgo_live_v457410,'auto_scale',text='Normalize FGO scale on Build')
        build.prop(context.scene.aef_fgo_live_v457410,'auto_outline',text='Add FGO outline on Build')
        build.operator(AEF_OT_add_shaders_v11.bl_idname,text='Build SaberShader',icon='NODE_MATERIAL')
        uv_status = str(context.scene.get('SaberShader_HF45748_BuildUVStatus', ''))
        if uv_status:
            build.label(text='UV: ' + uv_status.replace('_', ' ').title(),
                        icon='CHECKMARK' if uv_status in {'APPLIED', 'ALREADY_REPAIRED'} else 'INFO')
        build.label(text='V flip reversible via UV Orientation panel.')
        build.label(text='No official affiliation; user supplies assets.')


class AEF_PT_ui121_textures(bpy.types.Panel):
    bl_label = '05  Texture Intelligence'
    bl_idname = 'AEF_PT_ui121_textures'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_saber_shader_v8'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aef_sabershader_v8
        audit_section = layout
        uma_audit = audit_section.column(align=True)
        uma_audit.prop(settings, 'uma_texture_library_folder')
        uma_audit.prop(settings, 'uma_texture_audit_report_folder')
        uma_audit.prop(settings, 'uma_texture_audit_write_disk_reports')

        audit_row = uma_audit.row(align=True)
        op = audit_row.operator(
            AEF_OT_uma_texture_library_audit_v11932.bl_idname,
            text='Current .blend',
            icon='BLENDER',
        )
        op.audit_source = 'CURRENT_BLEND'
        op = audit_row.operator(
            AEF_OT_uma_texture_library_audit_v11932.bl_idname,
            text='Texture Folder',
            icon='FILE_FOLDER',
        )
        op.audit_source = 'EXTERNAL_FOLDER'

        audit_row2 = uma_audit.row(align=True)
        op = audit_row2.operator(
            AEF_OT_uma_texture_library_audit_v11932.bl_idname,
            text='Blend + Folder',
            icon='LINKED',
        )
        op.audit_source = 'BLEND_AND_FOLDER'
        audit_row2.operator(
            AEF_OT_uma_texture_library_open_report_v11932.bl_idname,
            text='Report',
            icon='TEXT',
        )

        if context.scene.get('SaberShader_V11932_UMAAuditFingerprint'):
            summary = uma_audit.box()
            audit_source = str(context.scene.get('SaberShader_V11932_UMAAuditSource', ''))
            audit_textures = int(context.scene.get('SaberShader_V11932_UMAAuditTextures', 0))
            audit_known = int(context.scene.get('SaberShader_V11932_UMAAuditKnown', 0))
            summary.label(text=f'{audit_textures} textures • {audit_known} recognized', icon='CHECKMARK')
            if audit_source:
                summary.label(text=f'Source: {audit_source}')

        uma_audit.label(text='Read-only; original images untouched.', icon='INFO')


class AEF_PT_ui121_advanced(bpy.types.Panel):
    bl_label = '06  Advanced & General'
    bl_idname = 'AEF_PT_ui121_advanced'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_saber_shader_v8'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aef_sabershader_v8
        advanced = layout.box()
        advanced.label(text='Universal Shader Controls', icon='PREFERENCES')
        advanced.prop(settings, 'universal_assign_materials')
        advanced.prop(settings, 'universal_build_compositor')
        advanced.label(text='Original materials and legacy IDs kept.')
        advanced.prop(settings, 'universal_target_npr_core')
        advanced.prop(settings, 'fgo_ramp_stage_isolation')
        advanced.prop(settings, 'fgo_isolate_base_facial_layers')
        advanced.prop(settings, 'fgo_cheek_overlay_strength')
        advanced.label(text='FGO: base face kept; expressions hidden.')
        advanced.label(text='FGO cheek strength: mt_cheek slot 16.')
        advanced.label(text='FGO ramp 1/2/5/6: diagnostic only.')
        advanced.prop(settings, 'universal_toon_strength')
        advanced.prop(settings, 'universal_shadow_depth')
        advanced.prop(settings, 'universal_texture_match_strictness')
        advanced.prop(settings, 'universal_use_reference_backend')
        advanced.separator()
        advanced.label(text='Material Role Classifier', icon='MATERIAL')
        active_obj = context.view_layer.objects.active if context.view_layer else None
        active_mat = getattr(active_obj, 'active_material', None) if active_obj else None
        if active_mat and hasattr(active_mat, 'xdzr8_role_override'):
            advanced.label(text=f'Active material: {active_mat.name}')
            advanced.prop(active_mat, 'xdzr8_role_override', text='Active Material Role Override')
            try:
                role_conf = str(active_mat.get('XDZR8_RoleConfidence', 'not classified yet'))
                role_reason = str(active_mat.get('XDZR8_RoleReason', ''))
            except Exception:
                role_conf, role_reason = 'not classified yet', ''
            advanced.label(text=f'Last classifier confidence: {role_conf}')
            if role_reason:
                advanced.label(text=role_reason[:95])
        else:
            advanced.label(text='Select a mesh to override material role.')
        advanced.label(text='Auto role uses combined visual evidence.')
        advanced.separator()
        advanced.label(text='Context-aware texture semantics')
        advanced.label(text="Resolve source texture anchors to their texture family.")
        advanced.label(text='FOUND applies; AMBIGUOUS is skipped.')
        advanced.label(text='General / MMD; AE requires verified binding.')
        advanced.label(text='Names alone do not define material role.')
        advanced.label(text='Aliases are hints, not model identities.')
        advanced.label(text='MMD: _C Base; _H Toon; _S Shadow.')
        advanced.label(text='General: base, light, face and packed maps.')
        advanced.prop(settings, 'universal_decode_packed_maps')
        advanced.label(text='Known pack channels labeled; unknown skipped.')
        advanced.label(text='Known ORM/ARM/MRA decoded cautiously.')
        advanced.label(text='Explicit normal, roughness, metal, alpha.')
        advanced.separator()
        advanced.label(text='Universal Adaptive Outline (non-AE)', icon='MOD_OUTLINE')
        advanced.label(text='AE silhouette uses independent controls.')
        advanced.prop(settings, 'universal_build_adaptive_outline')
        if settings.universal_build_adaptive_outline:
            advanced.prop(settings, 'universal_outline_strength')
            advanced.prop(settings, 'universal_outline_camera_adapt')
            advanced.prop(settings, 'universal_outline_static_envelope_clamp')
            advanced.prop(settings, 'universal_face_hair_intelligence')
            advanced.prop(settings, 'universal_head_outline_guard')
            advanced.label(text='Outline width scales with character.')
            advanced.label(text='Source slots and helpers are preserved.')
            advanced.label(text='Low-Poly face has dedicated outline.')
            advanced.label(text='Pose shells track rigs; static clamp safe.')
        advanced.label(text='Native Blender Line Art remains quarantined.')
        advanced.label(text='Legacy P/ST/HN/RS labels preserved.')
        advanced.separator()
        advanced.label(text='No dedicated collection is required.')
        advanced.label(text='Auto: rig → selection → hierarchy → mesh.')
        advanced.label(text='Low confidence: select full character.')
        advanced.label(text='Unknown models: no auto shape/Line Art.')


class AEF_PT_ui121_mmd_dictionary(bpy.types.Panel):
    """An opt-in General/MMD utility; intentionally not a new profile."""
    bl_label = 'Material & Texture Dictionary'
    bl_idname = 'AEF_PT_ui121_mmd_dictionary'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_character'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.aef_sabershader_v8
        box = layout.box()
        box.label(text='General / MMD Recognition', icon='MATERIAL')
        box.prop(settings, 'mmd_umd_scope')
        box.prop(settings, 'mmd_umd_match_mode')
        box.prop(settings, 'mmd_umd_include_compatibility')
        box.prop(settings, 'mmd_umd_read_pmx_names')
        box.label(text=f'Catalog: {sum(len(x) for x in XDZR8_HF4569_GENERIC_ALIASES.values())} aliases / {len(XDZR8_HF4569_GENERIC_ALIASES)} groups')
        box.label(text='Texture name hints: HN / P / ST / RS and MMD C / H / S')
        box.operator('sabershader.mmd_dictionary_custom_template', text='Custom Alias JSON (optional)', icon='TEXT')
        row = box.row(align=True)
        row.operator('sabershader.mmd_dictionary_scan', text='Scan & Report', icon='VIEWZOOM')
        box.label(text='Read-only scan. Report in Blender Text Editor.', icon='INFO')
        count = context.scene.get('XDZR8_HF4569_LastAuditMaterials', None)
        if count is not None:
            high = context.scene.get('XDZR8_HF4569_LastAuditHigh', 0)
            amb = context.scene.get('XDZR8_HF4569_LastAuditAmbiguous', 0)
            ready = context.scene.get('XDZR8_HF4569_LastAuditEligible', 0)
            box.label(text=f'{count} materials | {high} exact | {amb} ambiguous')
            box.label(text=f'{ready} safe candidates for optional roles')
        row = box.row(align=True)
        row.operator('sabershader.mmd_dictionary_apply_safe_roles', text='Apply Safe Roles', icon='CHECKMARK')
        row.operator('sabershader.mmd_dictionary_restore_roles', text='Restore Roles', icon='LOOP_BACK')
        box.label(text='Only exact, unambiguous and AUTO materials.')
        box.label(text='Manual overrides and source nodes are protected.')
        selected = getattr(context, 'active_object', None)
        active_mat = getattr(selected, 'active_material', None) if selected and selected.type == 'MESH' else None
        if active_mat:
            rec = _xdzr8_hf4569_lookup(active_mat.name, settings.mmd_umd_match_mode,
                                        settings.mmd_umd_include_compatibility,
                                        extra_names=(_xdzr8_hf4570_mmd_names(active_mat) if settings.mmd_umd_read_pmx_names else ()),
                                        custom_json=_xdzr8_hf4570_custom_alias_json())
            box.label(text=('Active: ' + active_mat.name)[:80])
            box.label(text=f'Suggested: {rec["category"] or "unknown"} / {rec["confidence"]}')
            if hasattr(active_mat, 'xdzr8_role_override'):
                box.prop(active_mat, 'xdzr8_role_override', text='Manual Role')
        style = layout.box()
        style.label(text='General NPR Style Library', icon='SHADING_RENDERED')
        style.prop(settings, 'mmd_umd_style')
        row = style.row(align=True)
        row.operator('sabershader.mmd_dictionary_apply_style', text='Stage Style', icon='PRESET')
        row.operator('sabershader.mmd_dictionary_restore_style', text='Restore Previous', icon='LOOP_BACK')
        style.label(text='Stages 3 universal values; Build remains manual.')
        style.label(text='UMA, Endfield and legacy profile paths unchanged.')


class AEF_PT_ui121_fgo_arcade_face_v4574(bpy.types.Panel):
    """Facial family audit / conversion / expression controls."""
    bl_label = 'Facial Families & Expressions'
    bl_idname = 'AEF_PT_ui121_fgo_arcade_face_v4574'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_fgo_arcade'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        opts = getattr(scene, 'aef_fgo_face_v4574', None)
        if opts is None:
            layout.label(text='Settings unavailable (re-enable the addon).', icon='ERROR')
            return
        box = layout.box()
        box.label(text='Facial Space & Hybrid Repair', icon='SHAPEKEY_DATA')
        box.operator('sabershader.fgo_face_audit_v4574', text='Audit Facial Families', icon='VIEWZOOM')
        box.prop(opts, 'hide_converted_sources')
        box.prop(opts, 'visual_proxy_preview')
        box.operator('sabershader.fgo_face_convert_v4574', text='Convert Safe Variants', icon='SHAPEKEY_DATA')
        row = box.row(align=True)
        row.operator('sabershader.fgo_face_reset_v4574', text='Reset Expressions', icon='X')
        row.operator('sabershader.fgo_face_restore_v4574', text='Restore Original Setup', icon='LOOP_BACK')
        box.label(text='Report: Text Editor / ' + _FGO4574_REPORT_NAME)
        index = _fgo4574_load_index(scene)
        if not index:
            layout.label(text='Run Audit Facial Families to list expressions.', icon='INFO')
            return
        ctrl = layout.box()
        ctrl.label(text='Expression Controls', icon='MOD_MESHDEFORM')
        ctrl.prop(opts, 'exclusive_per_family')
        ctrl.row().prop(opts, 'family_tab', expand=True)
        fam = str(opts.family_tab).casefold()
        fam_index = index.get('families', {}).get(fam, {})
        if fam_index.get('status') != 'OK':
            ctrl.label(text='%s: %s' % (fam, fam_index.get('status', 'NOT_AUDITED')), icon='ERROR')
            return
        ctrl.label(text='Base: %s  |  %d variants' % (fam_index['base'], len(fam_index['variants'])))
        active = _fgo4574_load_active(scene).get(fam)
        grid = ctrl.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for entry in fam_index['variants']:
            if entry['class'] == 'EXCLUDED':
                continue
            icon = 'SHAPEKEY_DATA' if entry['mode'] == 'KEY' else ('HIDE_OFF' if entry['mode'] == 'PREVIEW_OPTIONAL' else 'ERROR')
            op = grid.operator('sabershader.fgo_face_expression_v4574', text=entry['label'], icon=icon,
                               depress=(active == entry['label']))
            op.family = fam
            op.variant = entry['label']
            op.action = 'TOGGLE'
        ctrl.label(text='Keys with UV/material differences reproduce geometry only.')
        ctrl.label(text='Eye icon = guarded source proxy, optional.')


class AEF_PT_ui121_fgo_face_overlay_v45742(bpy.types.Panel):
    bl_label='Face Texture / Overlay Diagnosis'
    bl_idname='AEF_PT_ui121_fgo_face_overlay_v45742'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_fgo_arcade'
    bl_options={'DEFAULT_CLOSED'}

    def draw(self,context):
        layout=self.layout
        box=layout.box()
        box.label(text='Native Face Overlay',icon='MATERIAL')
        box.operator('sabershader.fgo_face_overlay_audit_v45742',text='Audit Face Overlay',icon='VIEWZOOM')
        active=bool(context.scene.get(_XDZR8_FGO45742_GUARD_KEY))
        if active:
            box.label(text='Neutral preview active',icon='HIDE_ON')
            box.operator('sabershader.fgo_face_restore_overlay_v45742',text='Restore Face Overlay',icon='LOOP_BACK')
            box.label(text='FACE shape keys are temporarily invisible',icon='ERROR')
        else:
            box.operator('sabershader.fgo_face_clean_neutral_v45742',text='Preview Clean Neutral Face',icon='HIDE_OFF')
            box.label(text='Only a reversible neutral preview; not a shader fix',icon='INFO')
        box.label(text='Report: Text Editor / ' + _XDZR8_FGO45742_REPORT)


class AEF_PT_ui121_fgo_neutral_face_v45743(bpy.types.Panel):
    bl_label = 'Neutral Face Base Resolution (Experimental)'
    bl_idname = 'AEF_PT_ui121_fgo_neutral_face_v45743'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_fgo_arcade'
    bl_options = {'DEFAULT_CLOSED'}
    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text='Skin-Matched Preview', icon='MATERIAL')
        box.operator('sabershader.fgo_neutral_face_audit_v45743', text='Audit Neutral Face Base', icon='VIEWZOOM')
        box.prop(context.scene, 'hf45743_face_skin_color', text='Neutral Skin')
        box.prop(context.scene, 'hf45743_face_original_mix', text='Original Atlas Detail')
        active = _xdzr8_fgo45743_state(context.scene) is not None
        box.operator('sabershader.fgo_neutral_face_preview_v45743',
                     text='Update Neutral Preview' if active else 'Preview Skin-Matched Face',
                     icon='SHADING_RENDERED')
        if active:
            box.operator('sabershader.fgo_neutral_face_restore_v45743',
                         text='Restore Native Face Material', icon='LOOP_BACK')
        box.label(text='Face shape keys remain visible.', icon='SHAPEKEY_DATA')
        box.label(text='Approximation, NOT native shader fidelity.', icon='ERROR')
        box.label(text='Report: Text Editor / ' + _XDZR8_FGO45743_REPORT)


class AEF_PT_ui121_fgo_native_opacity_v45744(bpy.types.Panel):
    bl_label='Native Face Material & Opacity Research'
    bl_idname='AEF_PT_ui121_fgo_native_opacity_v45744'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_fgo_arcade'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        layout=self.layout
        opts=context.scene.aef_fgo_opacity_research_v45744
        box=layout.box()
        box.label(text='Native Slot Research',icon='MATERIAL')
        box.prop(opts,'source_folder')
        box.operator('sabershader.fgo_native_opacity_audit_v45744',text='Audit Native Face Slots / Masks',icon='VIEWZOOM')
        box.label(text='Face: slot 14 (role unverified)',icon='INFO')
        box.label(text='Cheek: slot 16 (native opacity)',icon='INFO')
        box.separator()
        box.prop(opts,'mask_channel')
        box.prop(opts,'threshold')
        box.prop(opts,'feather')
        box.prop(opts,'invert')
        enabled=bool(_xdzr8_fgo45744_state(context.scene))
        box.operator('sabershader.fgo_native_opacity_probe_v45744',
                     text='Update Research Probe' if enabled else 'Preview Experimental Opacity',
                     icon='SHADING_RENDERED')
        if enabled:
            box.operator('sabershader.fgo_native_opacity_restore_v45744',
                         text='Restore Original Face Material',icon='LOOP_BACK')
        box.label(text='Diagnostic only: not native shader fidelity.',icon='ERROR')
        box.label(text='Read Text Editor report for mask channel stats.')


class AEF_PT_ui121_fgo_facial_uv_v45745(bpy.types.Panel):
    bl_label='Facial UV & Material Reconstruction Research'
    bl_idname='AEF_PT_ui121_fgo_facial_uv_v45745'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_fgo_arcade';bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        lay=self.layout
        opts=context.scene.aef_fgo_uv_research_v45745
        active=bool(_xdzr8_fgo45745_state(context.scene))
        lay.operator('sabershader.fgo_facial_uv_audit_v45745',text='Audit Native Facial UV / Materials',icon='VIEWZOOM')
        lay.label(text='Report: FGO Facial UV Material Audit',icon='TEXT')
        fit=float(context.scene.get('SaberShader_HF45745_LastUVFit',-1.0))
        if fit>=0:lay.label(text='Face neutral max affine residual: %.8f' % fit)
        box=lay.box();box.label(text='UV Sampling Experiment (Manual Opt-in)',icon='UV')
        box.prop(opts,'mode')
        box.prop(opts,'scope')
        if opts.mode=='MANUAL':
            row=box.row(align=True);row.prop(opts,'scale_u');row.prop(opts,'scale_v')
            row=box.row(align=True);row.prop(opts,'offset_u');row.prop(opts,'offset_v')
        box.prop(opts,'verify_native_pair')
        box.operator('sabershader.fgo_facial_uv_preview_v45745',
                     text='Update Preview' if active else 'Preview UV Candidate',icon='SHADING_TEXTURE')
        if active:
            box.operator('sabershader.fgo_facial_uv_restore_v45745',
                         text='Restore Original UV Material',icon='LOOP_BACK')
        box.label(text='Clones material + shader group; leaves mesh UVs intact.')
        box.label(text='Do not combine with previous FGO face previews.',icon='ERROR')
        box.label(text='No claim of native FGO shader fidelity.')


class AEF_PT_ui121_fgo_surface_layers_v45746(bpy.types.Panel):
    bl_label='Native Surface & Face Layer Composition'
    bl_idname='AEF_PT_ui121_fgo_surface_layers_v45746'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_fgo_arcade';bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        lay=self.layout; scene=context.scene
        opts=scene.aef_fgo_surface_research_v45746
        lay.operator('sabershader.fgo_surface_layer_audit_v45746',
                     text='Audit Native Surface & Face Layers',icon='VIEWZOOM')
        lay.label(text='Audit saved to Text Editor',icon='TEXT')
        try:
            last=json.loads(str(scene.get('SaberShader_HF45746_AuditSummary','{}')))
            lay.label(text='%d materials | %d native slots' % (
                last.get('native_generated_materials',0),last.get('native_slot_references',0)))
            lay.label(text='%d direct native slot nodes connected' %
                      last.get('direct_native_slot_nodes_connected',0))
        except Exception:pass
        box=lay.box();box.label(text='Surface lighting comparison (opt-in)',icon='SHADING_RENDERED')
        active=bool(_xdzr8_fgo45746_state(scene))
        box.prop(opts,'scope');box.prop(opts,'mode')
        if opts.mode=='LIT':
            box.prop(opts,'roughness');box.prop(opts,'use_normal')
        else:
            box.prop(opts,'ramp_strength')
            box.label(text='Ramp mode: choose Active object scope.',icon='INFO')
        box.prop(opts,'use_alpha')
        box.prop(opts,'preview_light')
        if active:
            box.label(text='Preview active: restore before edits',icon='INFO')
            box.operator('sabershader.fgo_surface_layer_restore_v45746',
                         text='Restore Original Surface Materials',icon='LOOP_BACK')
        else:
            box.operator('sabershader.fgo_surface_layer_preview_v45746',
                         text='Preview Surface Candidate',icon='SHADING_RENDERED')
        lay.label(text='Face/eyes excluded from surface preview.')
        lay.label(text='Face BS slot 14 remains unverified.',icon='ERROR')
        lay.label(text='This is NOT native FGO shader fidelity.')


class AEF_PT_ui121_fgo_shading_v45749(bpy.types.Panel):
    bl_label='FGO Arcade Shading Fidelity'
    bl_idname='AEF_PT_ui121_fgo_shading_v45749'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_fgo_arcade'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self, context):
        layout=self.layout
        opts=context.scene.aef_fgo_shading_v45749
        scene=context.scene
        layout.prop(opts,'mode')
        col=layout.column(align=True)
        col.prop(opts,'face_strength')
        col.prop(opts,'diffuse_strength')
        row=layout.row(align=True)
        row.prop(opts,'shadow_threshold')
        row.prop(opts,'light_threshold')
        layout.operator(AEF_OT_fgo_shading_audit_v45749.bl_idname,text='Audit Shading Candidates',icon='VIEWZOOM')
        state=_xdzr8_fgo45749_state(scene)
        if state:
            layout.label(text='Preview active: source materials backed up',icon='CHECKMARK')
            layout.operator(AEF_OT_fgo_shading_restore_v45749.bl_idname,text='Restore Source Baseline',icon='LOOP_BACK')
        else:
            layout.operator(AEF_OT_fgo_shading_preview_v45749.bl_idname,text='Preview Arcade Shading',icon='HIDE_OFF')
        layout.label(text='Eevee: diffuse light on face / body / hair / metal.')
        layout.label(text='Eyes, cheeks and expressions remain protected.')
        if scene.get('SaberShader_HF45749_LastStatus'):
            layout.label(text='Status: '+str(scene.get('SaberShader_HF45749_LastStatus',''))[:48],icon='INFO')
        layout.label(text='Compare to reference capture under equal lighting.')


class AEF_PT_ui121_fgo_uv_orientation_v45747(bpy.types.Panel):
    bl_label = 'UV Orientation Audit & Repair'
    bl_idname = 'AEF_PT_ui121_fgo_uv_orientation_v45747'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_fgo_arcade'
    bl_options = {'DEFAULT_CLOSED'}
    def draw(self, context):
        scene = context.scene
        opt = scene.aef_fgo_uv_repair_v45747
        state = _xdzr8_fgo45747_state(scene)
        layout = self.layout
        box = layout.box()
        box.label(text='V correction: U = U, V = 1 - V', icon='UV')
        box.prop(opt, 'auto_on_build', text='Auto-correct when building FGO')
        box.label(text='Disable if original UVs are already correct.')
        box.prop(opt, 'scope')
        box.prop(opt, 'uv_layers')
        box.prop(opt, 'reference_collection')
        box.operator('sabershader.fgo_uv_orientation_audit_v45747',
                     text='Analyze UV Orientation', icon='VIEWZOOM')
        try:
            last = json.loads(str(scene.get(_XDZR8_FGO45747_SUMMARY, '{}')))
            box.label(text='%d meshes | %d with UV' % (
                last.get('target_objects', 0), last.get('uv_targets', 0)))
            pair_count = last.get('pair_counts', {})
            if last.get('reference_count'):
                box.label(text='Ref: %d flip | %d aligned | %d unresolved' % (
                    pair_count.get('FLIP_V_VERIFIED', 0),
                    pair_count.get('ALREADY_ALIGNED', 0),
                    sum(pair_count.get(k, 0) for k in ('UNRESOLVED', 'AMBIGUOUS', 'UNMATCHED', 'NO_UV'))))
        except (ValueError, TypeError, AttributeError):
            pass
        if state:
            box.label(text=('Committed' if state.get('phase') == 'APPLIED' else 'Preview active') +
                      ': %d mesh objects' % state.get('objects', 0), icon='INFO')
            if state.get('phase') != 'APPLIED':
                box.operator('sabershader.fgo_uv_orientation_apply_v45747',
                             text='Apply Preview V Flip', icon='CHECKMARK')
            box.operator('sabershader.fgo_uv_orientation_restore_v45747',
                         text='Restore Original UV', icon='LOOP_BACK')
        else:
            box.operator('sabershader.fgo_uv_orientation_preview_v45747',
                         text='Preview V Flip (reversible)', icon='SHADING_TEXTURE')
            box.operator('sabershader.fgo_uv_orientation_apply_v45747',
                         text='Apply V Flip (reversible)', icon='CHECKMARK')
        box.label(text='Backups retained in .blend until Restore.', icon='INFO')
        box.label(text='Without reference, orientation is unverified.', icon='ERROR')
        box.label(text='Cheek / expressions need visual checking.')


class AEF_PT_ui121_fgo_live_v457410(bpy.types.Panel):
    bl_label='FGO Live Light, Outline & Scale'
    bl_idname='AEF_PT_ui121_fgo_live_v457410'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_fgo_arcade'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        layout=self.layout
        opts=context.scene.aef_fgo_live_v457410
        layout.operator(AEF_OT_fgo410_audit.bl_idname,text='Audit Size / Materials / Outline',icon='VIEWZOOM')
        box=layout.box();box.label(text='Live Lighting | EEVEE Rendered',icon='LIGHT')
        box.prop(context.scene.aef_fgo_shading_v45749,'mode',text='Build Lighting')
        box.prop(context.scene.aef_fgo_shading_v45749,'face_strength')
        box.prop(context.scene.aef_fgo_shading_v45749,'diffuse_strength')
        box.operator(AEF_OT_fgo410_refresh_lighting.bl_idname,text='Refresh Live Lighting',icon='FILE_REFRESH')
        if _xdz_fgo410_state(context.scene,_XDZ_FGO410_LIGHT_STATE):
            box.operator(AEF_OT_fgo410_restore_lights.bl_idname,text='Remove Test Lights',icon='X')
        else:
            box.operator(AEF_OT_fgo410_studio_lights.bl_idname,text='Create Test Lights',icon='LIGHT_AREA')
        box=layout.box();box.label(text='Arcade Silhouette (reversible)',icon='MOD_SOLIDIFY')
        box.prop(opts,'auto_outline')
        box.prop(opts,'outline_width')
        box.prop(opts,'outline_color')
        if _xdz_fgo410_state(context.scene,_XDZ_FGO410_OUTLINE_STATE):
            box.operator(AEF_OT_fgo410_restore_outline.bl_idname,text='Restore Outline',icon='LOOP_BACK')
        else:
            box.operator(AEF_OT_fgo410_outline.bl_idname,text='Preview Outline',icon='HIDE_OFF')
        box=layout.box();box.label(text='Character Scale (reversible)',icon='ARROW_LEFTRIGHT')
        box.prop(opts,'auto_scale')
        box.prop(opts,'target_height')
        if _xdz_fgo410_state(context.scene,_XDZ_FGO410_SCALE_STATE):
            box.operator(AEF_OT_fgo410_restore_scale.bl_idname,text='Restore Original Scale',icon='LOOP_BACK')
        else:
            box.operator(AEF_OT_fgo410_scale.bl_idname,text='Normalize to Target Height',icon='FULLSCREEN_ENTER')
        layout.label(text='UV and shape keys are not modified.')
        layout.label(text='Outline: main meshes only, not face variants.')
