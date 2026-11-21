"""Apply Si's verified single-trail VFX appearance during Build.

This is the normal visual output, not an A/B research session. Rebuilding a
verified Si actor temporarily restores the previous material slots, lets the
core Build run, then reattaches the same verified VFX material.

Never create variant B, change another character's VFX, or discard the
restoration snapshot. Exactly seven recognized Si meshes are eligible.
Historical scene keys and revision constants are deliberately preserved.
"""
from __future__ import annotations

import uuid

import bpy

from . import ae_fx_comparison as ab
from . import ae_fx_idle_ink as ink

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = 'AE_SI_BUILD_A_E3451_1'
PREFIX = 'SaberShader_AE_Si_BuildA_'
TOKEN = PREFIX + 'Token'
ORIGINAL = PREFIX + 'Original'
STAGE = PREFIX + 'Material'
MODE = PREFIX + 'State'
ORIG_FAKE = PREFIX + 'OriginalFakeUser'
HASH = PREFIX + 'AHash'
ORIG_HASH = PREFIX + 'OriginalHash'
MAT_TOKEN = PREFIX + 'MaterialToken'
MAT_REV = PREFIX + 'Revision'
IMAGE_TOKEN = PREFIX + 'ImageToken'
STAGED_IMAGE = PREFIX + 'PrivateImage'


def has_active_build_a(objects):
    """Direct guarded AE Full Setup must not overwrite a visible Build A."""
    return any(bool(obj.get(TOKEN, '')) and obj.get(MODE) == 'ACTIVE'
               for obj in objects or () if getattr(obj, 'type', '') == 'MESH')


def _seven(context, selected):
    objs = ab._objects(context.scene)
    selected_ids = {obj.as_pointer() if hasattr(obj, 'as_pointer') else id(obj)
                    for obj in selected}
    if len(objs) != 7 or any((obj.as_pointer() if hasattr(obj, 'as_pointer') else id(obj))
                             not in selected_ids for obj in objs):
        raise RuntimeError('Requires all seven selected original Si VFX LOD0 meshes')
    if any(obj.type != 'MESH' or ab._readonly(obj) or ab._readonly(obj.data)
           or obj.data.users != 1 for obj in objs):
        raise RuntimeError('Si VFX meshes must be local and single-user')
    for obj in objs:
        slots = getattr(obj, 'material_slots', None)
        if slots is not None and (len(slots) != 1 or slots[0].link != 'DATA'):
            raise RuntimeError('Si VFX requires one DATA-linked material slot: ' + obj.name)
    return objs


def _uses_material(obj, material):
    data = getattr(obj, 'data', None)
    if any(m is material for m in (getattr(data, 'materials', ()) or ())):
        return True
    return any(s.material is material for s in (getattr(obj, 'material_slots', ()) or ()))


def _verified_session(context, selected, *, mode):
    objs = _seven(context, selected)
    if ink.has_active_comparison(objs) or ab.has_active_comparison(objs):
        raise RuntimeError('Restore manual Si E3.4.1/E3.4.4 comparison first')
    tokens = {str(obj.get(TOKEN, '')) for obj in objs}
    if len(tokens) != 1 or not next(iter(tokens)):
        raise RuntimeError('Incomplete or absent Build A session')
    token = next(iter(tokens))
    for key in (ORIGINAL, STAGE, ORIG_FAKE, HASH, ORIG_HASH, MODE):
        if len({str(obj.get(key, '')) for obj in objs}) != 1:
            raise RuntimeError('Inconsistent Build A session metadata: ' + key)
    if any(obj.get(MODE) != mode for obj in objs):
        raise RuntimeError('Build A state differs from expected ' + mode)
    original = bpy.data.materials.get(str(objs[0].get(ORIGINAL, '')))
    stage = bpy.data.materials.get(str(objs[0].get(STAGE, '')))
    if original is None or stage is None or original is stage:
        raise RuntimeError('Build A original/staged material missing')
    if (ab._readonly(original) or ab._readonly(stage) or
            original.get('AEF_V11_SourceMaterial', '') != 'DefaultHGMaterial' or
            stage.get('AEF_V11_SourceMaterial', '') != 'DefaultHGMaterial' or
            stage.get(MAT_TOKEN) != token or stage.get(MAT_REV) != REVISION or
            ink._graph_hash(stage) != str(objs[0].get(HASH, '')) or
            ink._graph_hash(original) != str(objs[0].get(ORIG_HASH, '')) or
            not original.use_fake_user):
        raise RuntimeError('Build A material changed or provenance cannot be verified')
    for obj in objs:
        assigned = ab._material(obj)
        if assigned is not (stage if mode == 'ACTIVE' else original):
            raise RuntimeError('Si VFX material assignment changed: ' + obj.name)
    # Both A and the original baseline must remain exclusively scoped to Si:
    # otherwise the next legacy Build could rewrite another actor's material.
    tracked_ids = {obj.as_pointer() if hasattr(obj, 'as_pointer') else id(obj) for obj in objs}
    for obj in context.scene.objects:
        if (obj.as_pointer() if hasattr(obj, 'as_pointer') else id(obj)) not in tracked_ids and getattr(obj, 'type', '') == 'MESH':
            if _uses_material(obj, stage) or _uses_material(obj, original):
                raise RuntimeError('Si VFX Build A source or stage shared with an untracked mesh')
    return objs, original, stage


def apply_after_build(context, selected):
    """Apply A once, after the ordinary verified Si Build/E332 stages.

    Fail closed on unsupported source materials and never create a manual A/B
    session. The exact visual A constructor is shared with E3.4.1.
    """
    objs = _seven(context, selected)
    if any(obj.get(TOKEN, '') for obj in objs):
        raise RuntimeError('Build A session exists; resume or resolve it before apply')
    if ink.has_active_comparison(objs) or ab.has_active_comparison(objs):
        raise RuntimeError('Manual Si A/B or A/A2 session active')
    # Reuse the strict same-source, 7-mesh, verified Blender scene preflight.
    inspected, original = ab._require_objects(context)
    if [o.name for o in inspected] != [o.name for o in objs]:
        raise RuntimeError('Si auto A preflight actor mismatch')
    tracked_ids = {o.as_pointer() if hasattr(o, 'as_pointer') else id(o) for o in objs}
    for outside in context.scene.objects:
        outside_id = outside.as_pointer() if hasattr(outside, 'as_pointer') else id(outside)
        if outside_id not in tracked_ids and getattr(outside, 'type', '') == 'MESH':
            if _uses_material(outside, original):
                raise RuntimeError('Si source material is shared with another mesh; refuse auto A')
    if ab._is_nested_mask_a(original):
        return {'status': 'ALREADY_EXACT_A', 'meshes': 7}
    if ab._find_main_image(original) is None:
        return {'status': 'SKIPPED_GFX18_UNAVAILABLE', 'meshes': 0}
    token = uuid.uuid4().hex
    old_image_ids = {im.as_pointer() for im in bpy.data.images}
    old_fake = bool(original.use_fake_user)
    stage = None
    swapped = []
    try:
        stage = original.copy()
        stage.name = 'SaberShader AE Si Build | A Single Trail gfx18'
        ab._clear_inherited_stage_tags(stage)
        stage.use_fake_user = False
        ab._single_trail_a(stage)
        # Do not duplicate or mutate source image colorspace. The E341 helper
        # creates a private Non-Color copy only when required.
        new_images = [im for im in bpy.data.images if im.as_pointer() not in old_image_ids]
        if len(new_images) > 1:
            raise RuntimeError('Unexpected additional images during A staging')
        for im in new_images:
            im[IMAGE_TOKEN] = token
        stage[STAGED_IMAGE] = new_images[0].name if new_images else ''
        stage[MAT_TOKEN] = token
        stage[MAT_REV] = REVISION
        graph_hash = ink._graph_hash(stage)
        original.use_fake_user = True
        for obj in objs:
            swapped.append((obj, ab._material(obj)))
            obj.data.materials[0] = stage
            for k, value in ((TOKEN, token), (ORIGINAL, original.name),
                             (STAGE, stage.name), (MODE, 'ACTIVE'),
                             (ORIG_FAKE, int(old_fake)), (HASH, graph_hash),
                             (ORIG_HASH, ink._graph_hash(original))):
                obj[k] = value
    except Exception:
        for obj, mat in reversed(swapped):
            obj.data.materials[0] = mat
        for obj in objs:
            for k in (TOKEN, ORIGINAL, STAGE, MODE, ORIG_FAKE, HASH, ORIG_HASH):
                if k in obj:
                    del obj[k]
        original.use_fake_user = old_fake
        if stage is not None:
            stage.use_fake_user = False
            if stage.users == 0:
                bpy.data.materials.remove(stage)
        for im in list(bpy.data.images):
            if im.as_pointer() not in old_image_ids and im.users == 0 and not im.use_fake_user:
                bpy.data.images.remove(im)
        raise
    return {'status': 'ACTIVE_A', 'meshes': 7, 'material': stage.name}


def suspend_for_build(context, selected):
    """Expose original material to the legacy Build without deleting A."""
    objs, original, stage = _verified_session(context, selected, mode='ACTIVE')
    swaps = []
    try:
        stage.use_fake_user = True  # Keep the A material alive while unassigned.
        for obj in objs:
            swaps.append((obj, stage))
            obj.data.materials[0] = original
        for obj in objs:
            obj[MODE] = 'SUSPENDED'
    except Exception:
        for obj, mat in reversed(swaps):
            obj.data.materials[0] = mat
        for obj in objs:
            obj[MODE] = 'ACTIVE'
        stage.use_fake_user = False
        raise
    return {'status': 'SUSPENDED_A', 'meshes': 7}


def resume_after_build(context, selected):
    """Return exactly the same Build A datablock; safe after failed Build too."""
    objs, original, stage = _verified_session(context, selected, mode='SUSPENDED')
    swapped = []
    try:
        for obj in objs:
            swapped.append((obj, original))
            obj.data.materials[0] = stage
        for obj in objs:
            obj[MODE] = 'ACTIVE'
        stage.use_fake_user = False
    except Exception:
        for obj, mat in reversed(swapped):
            obj.data.materials[0] = mat
        for obj in objs:
            obj[MODE] = 'SUSPENDED'
        stage.use_fake_user = True
        raise
    return {'status': 'ACTIVE_A_REUSED', 'meshes': 7, 'material': stage.name}


def status(context):
    """Read-only UI overview, including an incomplete/suspended recovery flag."""
    objs = ab._objects(context.scene)
    tagged = [o for o in objs if o.get(TOKEN, '')]
    if not tagged:
        return 'NONE'
    if len(tagged) != 7 or len({o.get(TOKEN, '') for o in tagged}) != 1:
        return 'INCOMPLETE'
    states = {str(o.get(MODE, '')) for o in tagged}
    return next(iter(states)) if len(states) == 1 else 'INCOMPLETE'


def restore_original(context, selected):
    """Explicit opt-out of current auto A; next Build may apply A again.

    Unlike the Build suspend, this closes the automatic A session. It does not
    restore any other FX stage or change an active manual A/B comparison.
    """
    objs, original, stage = _verified_session(context, selected, mode='ACTIVE')
    token = str(objs[0].get(TOKEN))
    private_image_name = str(stage.get(STAGED_IMAGE, '') or '')
    if stage.users > len(objs):
        raise RuntimeError('Build A has unexpected users; refuse material deletion')
    old = []
    try:
        for obj in objs:
            old.append((obj, ab._material(obj)))
            obj.data.materials[0] = original
    except Exception:
        for obj, material in reversed(old):
            obj.data.materials[0] = material
        raise
    # Slots have been safely changed. Close tags only after that succeeds.
    was_fake = bool(int(objs[0].get(ORIG_FAKE, 0)))
    for obj in objs:
        for k in (TOKEN, ORIGINAL, STAGE, MODE, ORIG_FAKE, HASH, ORIG_HASH):
            if k in obj:
                del obj[k]
    original.use_fake_user = was_fake
    stage.use_fake_user = False
    if stage.users == 0:
        bpy.data.materials.remove(stage)
    if private_image_name:
        image = bpy.data.images.get(private_image_name)
        if (image is not None and image.get(IMAGE_TOKEN, '') == token and
                image.users == 0 and not image.use_fake_user):
            bpy.data.images.remove(image)
    return {'status': 'ORIGINAL_RESTORED', 'meshes': 7, 'material': original.name}


class AEF_OT_si_build_a_restore(bpy.types.Operator):
    bl_idname = 'sabershader.si_build_a_restore'
    bl_label = 'Restore Pre-A Si VFX'
    bl_description = ('Explicitly restore Si VFX materials as they were before automatic Build A; '
                      'a later Build can apply A again')
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            from . import engine
            settings = context.scene.aef_sabershader_v8
            selection = engine._aef11_target_objects(context, settings, preview_only=True) or {}
            result = restore_original(context, list(selection.get('objects') or ()))
        except Exception as exc:
            self.report({'ERROR'}, 'Restore Si Build A: ' + str(exc)[:160])
            return {'CANCELLED'}
        context.scene['SaberShader_AE_SiBuildA_Status'] = 'MANUALLY_RESTORED'
        self.report({'INFO'}, 'Restored pre-A material for %d Si meshes' % result['meshes'])
        return {'FINISHED'}


class AEF_OT_si_build_a_resume(bpy.types.Operator):
    bl_idname = 'sabershader.si_build_a_resume'
    bl_label = 'Recover Suspended Build A'
    bl_description = 'Safely restore previous A after interrupted Build, only if source materials are unchanged'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            from . import engine
            settings = context.scene.aef_sabershader_v8
            selection = engine._aef11_target_objects(context, settings, preview_only=True) or {}
            result = resume_after_build(context, list(selection.get('objects') or ()))
        except Exception as exc:
            self.report({'ERROR'}, 'Recover Si Build A: ' + str(exc)[:160])
            return {'CANCELLED'}
        context.scene['SaberShader_AE_SiBuildA_Status'] = result['status']
        self.report({'INFO'}, 'Recovered original Build A without re-staging')
        return {'FINISHED'}
