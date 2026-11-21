"""Session controls for explicit Live Sync and EyeHideAll rescanning."""
import bpy
import json
from . import lifecycle_state
from . import handler_dispatch


class AEF_OT_safety_fix2_enable_live_sync(bpy.types.Operator):
    bl_idname = 'sabershader.safety_fix2_enable_live_sync'
    bl_label = 'Enable Live Sync (This Session)'
    bl_description = 'Allow dynamic face illumination and EyeHideAll updates on frame/depsgraph changes; this can write shader and shape-key data'
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Registration must not start Live Sync. Only this user action
        # enables callbacks that can update scene data.
        handler_dispatch.reset()
        lifecycle_state.set_live_sync(True)
        self.report({'WARNING'}, 'Live Sync enabled for this session; handlers may update face lighting and EyeHideAll')
        return {'FINISHED'}


class AEF_OT_safety_fix2_disable_live_sync(bpy.types.Operator):
    bl_idname = 'sabershader.safety_fix2_disable_live_sync'
    bl_label = 'Disable Live Sync'
    bl_description = 'Stop SaberShader dynamic face-light and EyeHideAll handler updates without changing current materials or expression state'
    bl_options = {'REGISTER'}

    def execute(self, context):
        lifecycle_state.set_live_sync(False)
        self.report({'INFO'}, 'Live Sync disabled; current scene values are unchanged')
        return {'FINISHED'}


class AEF_OT_safety_fix3_rescan_eyehideall(bpy.types.Operator):
    bl_idname = 'sabershader.safety_fix3_rescan_eyehideall'
    bl_label = 'Rescan EyeHideAll'
    bl_description = (
        'Explicitly rebuild EyeHideAll shape-key bindings after importing or changing a character; '
        'also applies the current eye-hide expression value'
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = getattr(context, 'scene', None)
        if scene is None:
            self.report({'ERROR'}, 'No active scene to scan')
            return {'CANCELLED'}
        try:
            # Rescanning is an explicit action and also works with Live Sync disabled.
            # A depsgraph event must not trigger a full scan by itself.
            from . import engine
            engine._apply_eyehideall_bindings(
                scene=scene, force_detect=True)
            cached = scene.get('SaberShader_V1136_EyeHideAllBindingsJSON', '[]')
            rows = json.loads(cached) if isinstance(cached, str) else []
            if not isinstance(rows, list):
                rows = []
            scanned = int(scene.get('SaberShader_V1136_EyeHideAllScannedMeshes', 0))
        except Exception as exc:
            self.report({'ERROR'}, 'EyeHideAll rescan failed: %s' % str(exc)[:140])
            return {'CANCELLED'}
        if rows:
            self.report({'INFO'}, 'EyeHideAll: %d binding(s), %d mesh(es) scanned' % (len(rows), scanned))
        else:
            self.report({'WARNING'}, 'No EyeHideAll morphs found among %d scanned mesh(es)' % scanned)
        return {'FINISHED'}


class AEF_PT_safety_fix2_session(bpy.types.Panel):
    bl_label = 'Live Sync & Session'
    bl_idname = 'AEF_PT_safety_fix2_session'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        col = self.layout.column(align=True)
        enabled = lifecycle_state.live_sync_enabled()
        col.label(text=('Live Sync: ON' if enabled else 'Live Sync: OFF'),
                  icon=('CHECKMARK' if enabled else 'PAUSE'))
        if enabled:
            col.operator(AEF_OT_safety_fix2_disable_live_sync.bl_idname, icon='CANCEL')
        else:
            col.operator(AEF_OT_safety_fix2_enable_live_sync.bl_idname, icon='PLAY')
        col.separator()
        col.label(text='Activation does not alter scene data', icon='INFO')
        col.label(text='Live Sync may write shader and shape key values')
        col.operator(AEF_OT_safety_fix3_rescan_eyehideall.bl_idname, icon='FILE_REFRESH')
        col.label(text='Rescan after adding or changing a character')
        col.label(text='Rescan applies current EyeHideAll values')
        col.label(text='Line Art risk: audit before a reference build')
        stats = handler_dispatch.snapshot()
        col.label(text='Sync calls: {0} | skipped: {1}'.format(
            stats['calls'], stats['skipped']))
        col.label(text='Sync errors: {0}'.format(stats['errors']))
        col.label(text='Use COPIES of .blend files for validation')
