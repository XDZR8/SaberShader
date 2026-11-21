"""E3.2: conservative, reversible Si VFX placeholder preview.

The seven DefaultHGMaterial vfxpart meshes have no authored base-color
texture.  A weak neutral translucent visualization replaces the *incorrect*
Hair shader only on verified meshes. This is NOT an emulation of Unity's
particle / VFX system. Native source geometry and original materials remain.
"""
from __future__ import annotations

import re
import bpy

from . import ae_material_sources as source

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = 'AE_SI_VFX_E32_GHOST_PREVIEW_1'
MARKER = 'SaberShader_AE_Si_VFX_E32'
ORIGINAL_KEY = 'SaberShader_AE_Si_VFX_E32_OriginalMaterial'
ORIGINAL_FAKE_KEY = 'SaberShader_AE_Si_VFX_E32_OriginalFakeUser'
PREVIEW_NAME = 'SaberShader AE Si VFX E3.2 | Translucent Placeholder'
PREVIEW_ALPHA = 0.06  # Experimental visibility, NOT measured from game.
PATTERN = re.compile(r'^S_actor_jsspsi_vfxpart_0[1-7]_lod0(?:\.\d{3})?$', re.I)


def _source_id(mat):
    try:
        return str(mat.get('AEF_V11_SourceMaterial', '') or '')
    except (AttributeError, TypeError):
        return ''


def _in_scope(obj):
    return getattr(obj, 'type', None) == 'MESH' and bool(PATTERN.fullmatch(str(getattr(obj, 'name', ''))))


def _materials(obj):
    return getattr(getattr(obj, 'data', None), 'materials', None)


def inspect(objects, *, catalog=None):
    """No scene changes: report exact eligible meshes and unresolved cases."""
    catalog = catalog or source._source_catalog()
    rows = []
    if 'DefaultHGMaterial' not in catalog.get('materials', {}):
        return {'eligible': [], 'already': [], 'skipped': [('catalog', 'SOURCE_NOT_IN_CATALOG')]}
    eligible, already, skipped = [], [], []
    for obj in objects or ():
        if not _in_scope(obj):
            continue
        mesh = getattr(obj, 'data', None)
        mats = _materials(obj)
        mat = mats[0] if mats is not None and len(mats) == 1 else None
        if mat is not None and mat.get('SaberShader_AE_FX_E331') == 'AE_SI_FX_E331_LOOK_MATCH_1':
            already.append(obj)
            continue
        if mat is None or _source_id(mat) != 'DefaultHGMaterial':
            skipped.append((obj.name, 'MISSING_OR_UNVERIFIED_DEFAULT_HG_MATERIAL'))
            continue
        if mat.get(MARKER, '') == REVISION:
            already.append(obj)
            continue
        if not str(getattr(mat, 'name', '')).startswith('SaberShader - Hair'):
            skipped.append((obj.name, 'CUSTOM_OR_UNKNOWN_SHADER_PRESERVED'))
            continue
        if (getattr(obj, 'library', None) is not None or
            getattr(obj, 'override_library', None) is not None or
            getattr(mesh, 'library', None) is not None or
            getattr(mesh, 'override_library', None) is not None or
            getattr(mat, 'library', None) is not None or
            getattr(mat, 'override_library', None) is not None or
            getattr(mesh, 'users', 1) > 1):
            skipped.append((obj.name, 'LINKED_OR_SHARED_SOURCE_PRESERVED'))
            continue
        eligible.append((obj, mat))
    return {'eligible': eligible, 'already': already, 'skipped': skipped}


def _preview_material(original):
    """New material instead of modifying shared hair material in place."""
    mat = bpy.data.materials.new(PREVIEW_NAME)
    mat.use_nodes = True
    mat[MARKER] = REVISION
    mat['AEF_V11_SourceMaterial'] = 'DefaultHGMaterial'
    mat[ORIGINAL_KEY] = original.name
    mat[ORIGINAL_FAKE_KEY] = int(bool(original.use_fake_user))
    mat.surface_render_method = 'BLENDED'
    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (450, 70)
    trans = nodes.new('ShaderNodeBsdfTransparent')
    trans.location = (-280, -100)
    emit = nodes.new('ShaderNodeEmission')
    emit.location = (-280, 150)
    emit.inputs['Color'].default_value = (0.10, 0.18, 0.18, 1.0)
    emit.inputs['Strength'].default_value = 0.25
    mix = nodes.new('ShaderNodeMixShader')
    mix.name = 'SaberShader AE Si VFX E3.2 | Preview opacity'
    mix.label = 'Unverified VFX placeholder opacity (0 = invisible)'
    mix.location = (90, 70)
    mix.inputs[0].default_value = PREVIEW_ALPHA
    links.new(trans.outputs['BSDF'], mix.inputs[1])
    links.new(emit.outputs['Emission'], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs['Surface'])
    return mat


def apply(objects, *, catalog=None):
    """Reversible replacement of only wrong opaque Hair slots on verified Si vfxpart.

    Does not hide meshes, alter vertex data, change rig or edit native effects.
    """
    plan = inspect(objects, catalog=catalog)
    groups = {}
    for obj, old in plan['eligible']:
        key = old.as_pointer() if hasattr(old, 'as_pointer') else id(old)
        groups.setdefault(key, {'original': old, 'objects': []})['objects'].append(obj)
    if not groups:
        return {'status': 'ALREADY_APPLIED' if plan['already'] else 'NO_ELIGIBLE',
                'applied': 0, 'already': len(plan['already']), 'skipped': plan['skipped']}
    made = []
    changes = []
    fake_state = []
    try:
        # All previews are created and verified before the first material swap.
        for group in groups.values():
            preview = _preview_material(group['original'])
            made.append(preview)
            group['preview'] = preview
        for group in groups.values():
            original = group['original']
            fake_state.append((original, bool(original.use_fake_user)))
            original.use_fake_user = True  # Survive save/reopen, even if no other users.
            for obj in group['objects']:
                obj.data.materials[0] = group['preview']
                changes.append((obj, original))
    except Exception as exc:
        failures = []
        for obj, old in reversed(changes):
            try: obj.data.materials[0] = old
            except Exception as err: failures.append(str(err))
        for original, was_fake in fake_state:
            try: original.use_fake_user = was_fake
            except Exception as err: failures.append(str(err))
        for mat in made:
            try:
                if not mat.users: bpy.data.materials.remove(mat)
            except Exception: pass
        return {'status': 'ROLLBACK_INCOMPLETE' if failures else 'ERROR_ROLLED_BACK',
                'applied': 0, 'error': str(exc), 'rollback_errors': failures,
                'skipped': plan['skipped']}
    return {'status': 'PREVIEW_APPLIED', 'applied': len(changes),
            'already': len(plan['already']), 'skipped': plan['skipped'],
            'alpha': PREVIEW_ALPHA, 'render_equivalence': 'NOT_VERIFIED'}


def restore(objects):
    """Restore saved material pointers by exact original material identity."""
    changes = []
    errors = []
    if any(any(m and m.get('SaberShader_AE_FX_E331') == 'AE_SI_FX_E331_LOOK_MATCH_1'
                   for m in (_materials(obj) or ()))
           for obj in objects or () if _in_scope(obj)):
        return {'status': 'BLOCKED', 'restored': 0,
                'errors': [('E3.3.1', 'RESTORE_FINAL_LOOK_FIRST')]}
    for obj in objects or ():
        if not _in_scope(obj): continue
        mesh = getattr(obj, 'data', None)
        mats = _materials(obj)
        preview = mats[0] if mats is not None and len(mats) == 1 else None
        if preview is None or preview.get(MARKER, '') != REVISION:
            continue
        original_name = preview.get(ORIGINAL_KEY, '')
        original = bpy.data.materials.get(original_name)
        if (original is None or _source_id(original) != 'DefaultHGMaterial' or
            getattr(mesh, 'users', 1) > 1 or getattr(mesh, 'library', None) is not None or
            getattr(obj, 'library', None) is not None or getattr(obj, 'override_library', None) is not None or
            getattr(mesh, 'override_library', None) is not None):
            errors.append((obj.name, 'ORIGINAL_MISSING_OR_UNEDITABLE'))
            continue
        changes.append((obj, preview, original))
    if errors:
        return {'status': 'BLOCKED', 'restored': 0, 'errors': errors}
    completed = []
    try:
        for obj, prev, original in changes:
            obj.data.materials[0] = original
            completed.append((obj, prev))
    except Exception as exc:
        failures = []
        for obj, prev in reversed(completed):
            try: obj.data.materials[0] = prev
            except Exception as err: failures.append(str(err))
        return {'status': 'ROLLBACK_INCOMPLETE' if failures else 'ERROR_ROLLED_BACK',
                'restored': 0, 'error': str(exc), 'rollback_errors': failures}
    # Preserve originals while ANY E3.2 preview in this .blend still uses
    # them, including previews in actors not in the current selection.
    for original in {original for _, _, original in changes}:
        previews = [m for m in bpy.data.materials
                    if m.get(MARKER, '') == REVISION
                    and m.get(ORIGINAL_KEY, '') == original.name]
        if (previews and all(not bool(m.get(ORIGINAL_FAKE_KEY, True)) for m in previews)
                and not any(m.users for m in previews)):
            original.use_fake_user = False
    return {'status': 'RESTORED' if changes else 'NO_PREVIEW', 'restored': len(changes)}


class AEF_OT_ae_si_vfx_e32_restore(bpy.types.Operator):
    bl_idname = 'sabershader.ae_si_vfx_e32_restore'
    bl_label = 'Restore Si VFX Placeholder Materials'
    bl_description = 'Restore the exact original materials saved before the translucent VFX preview'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            result = restore(source._target_meshes(context))
        except Exception as exc:
            self.report({'ERROR'}, 'VFX restore: ' + str(exc)[:155])
            return {'CANCELLED'}
        if result['status'] != 'RESTORED':
            self.report({'WARNING'}, 'VFX restore: ' + str(result.get('errors', result.get('error', result['status'])))[:155])
            return {'CANCELLED'}
        self.report({'INFO'}, 'Restored original VFX materials for %d objects' % result['restored'])
        return {'FINISHED'}
