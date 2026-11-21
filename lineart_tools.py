"""Optional in-Blender, explicit read-only Line Art preflight operators."""

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'

import json
import os
import tempfile
from pathlib import Path

import bpy

from .lineart_safety import inspect_generated_lineart, inspect_scene_lineart_risk


class AEF_OT_safety_fix1_lineart_audit(bpy.types.Operator):
    bl_idname = 'sabershader.safety_fix1_lineart_audit'
    bl_label = 'Audit Line Art (Read Only)'
    bl_description = 'Inspect possible SaberShader Line Art receivers without changing the scene; full report in System Console'
    bl_options = {'REGISTER'}

    def execute(self, context):
        report = inspect_generated_lineart(bpy.data.objects)
        report['scene_wide_risk'] = inspect_scene_lineart_risk(bpy.data.objects)
        print('[SaberShader] LINE ART PREFLIGHT')
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        totals = report['totals']
        self.report({'INFO'}, 'Line Art preflight: %d receivers, %d Line Art mods; details in System Console' % (
            totals['generated_receiver_candidates'], totals['lineart_modifiers']))
        return {'FINISHED'}


class AEF_OT_safety_fix1_lineart_export(bpy.types.Operator):
    bl_idname = 'sabershader.safety_fix1_lineart_export'
    bl_label = 'Export Line Art Audit JSON'
    bl_description = 'Write a new read-only Line Art diagnostic JSON; never overwrites an existing file'
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(name='New JSON File', subtype='FILE_PATH', default='')
    filter_glob: bpy.props.StringProperty(default='*.json', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        path = Path(bpy.path.abspath(self.filepath)).expanduser()
        if path.suffix.lower() != '.json' or not path.name or path.is_dir():
            self.report({'ERROR'}, 'Select a new .json file')
            return {'CANCELLED'}
        tmp_path = None
        used_fallback = False
        try:
            report = inspect_generated_lineart(bpy.data.objects)
            report['scene_wide_risk'] = inspect_scene_lineart_risk(bpy.data.objects)
            # Write the complete report to a temporary file beside the destination.
            # A hard link publishes the finished report without overwriting an existing file.
            with tempfile.NamedTemporaryFile('w', encoding='utf-8',
                    prefix='.' + path.stem + '-', suffix='.tmp',
                    dir=str(path.parent), delete=False) as handle:
                tmp_path = Path(handle.name)
                json.dump(report, handle, indent=2, ensure_ascii=False, sort_keys=True)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(str(tmp_path), str(path))
            except FileExistsError:
                raise  # An existing report is never replaced.
            except OSError as link_exc:
                # Some filesystems, including exFAT, FAT32 and network drives, reject hard links.
                # Use the exclusive-copy fallback only for known unsupported hard-link errors.
                import errno
                unsupported = {errno.EPERM, errno.EACCES, errno.EINVAL,
                               errno.EXDEV, errno.ENOSYS, errno.ENOTSUP,
                               errno.EOPNOTSUPP}
                if link_exc.errno not in unsupported:
                    raise
                used_fallback = True
                created = False
                created_identity = None
                try:
                    # Binary exclusive mode ('xb') fails if another process already created
                    # the destination after the initial check.
                    # This fallback is not atomic, unlike the hard-link approach:
                    # another process may see the report while it is still being copied.
                    with path.open('xb') as target:
                        created = True
                        stat = os.fstat(target.fileno())
                        created_identity = (stat.st_dev, stat.st_ino)
                        with tmp_path.open('rb') as staged:
                            while True:
                                chunk = staged.read(1024 * 1024)
                                if not chunk:
                                    break
                                target.write(chunk)
                        target.flush()
                        os.fsync(target.fileno())
                except BaseException:
                    # If copying fails, remove the destination only if it is still the file
                    # created by this operation; never delete a replacement from another writer.
                    if created:
                        try:
                            stat = path.stat()
                            if (stat.st_dev, stat.st_ino) == created_identity:
                                path.unlink()
                        except OSError:
                            pass
                    raise
        except FileExistsError:
            self.report({'ERROR'}, 'The report already exists; select a new filename')
            return {'CANCELLED'}
        except (OSError, TypeError, ValueError) as exc:
            self.report({'ERROR'}, 'Could not export audit: %s' % str(exc)[:120])
            return {'CANCELLED'}
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
        if used_fallback:
            self.report({'WARNING'}, 'Saved JSON via exclusive-copy fallback (non-atomic)')
        else:
            self.report({'INFO'}, 'Saved new Line Art preflight JSON')
        return {'FINISHED'}


class AEF_PT_safety_fix1_lineart(bpy.types.Panel):
    bl_label = 'Line Art Diagnostics'
    bl_idname = 'AEF_PT_safety_fix1_lineart'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text='Read-only diagnostics', icon='INFO')
        col.operator(AEF_OT_safety_fix1_lineart_audit.bl_idname, icon='VIEWZOOM')
        col.operator(AEF_OT_safety_fix1_lineart_export.bl_idname, icon='EXPORT')
        col.separator()
        col.label(text='Line Art modifiers are never removed automatically', icon='INFO')
        col.label(text='Use a COPY of your .blend for testing')
        col.label(text='Reference build blocked if Line Art is found')
