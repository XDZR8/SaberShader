"""Si idle VFX E3.4.1 — explicit, reversible A/B material comparison.

A = actual existing nested Mask material when positively identified; otherwise
    a staged single-trail approximation using gfx_18 (not an exact recreation).
B = E3.3.2 Dual Layer with gfx_18 as primary and fj_09 as secondary.

No Build/automatic invocation, no changes to eye/cloth meshes, no file writes.
The experiment can be saved/reopened; Restore returns EXACT material IDs.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import bpy

from . import ae_fx_ink_sources as _fx3
from . import ae_fx_layered_materials as _fxb

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = 'AE_SI_IDLE_AB_E341_1'
PREFIX = 'SaberShader_AE_Si_E341_AB_'
PROP_TOKEN = PREFIX + 'Token'
PROP_ORIGINAL = PREFIX + 'Original'
PROP_A = PREFIX + 'A'
PROP_B = PREFIX + 'B'
PROP_CURRENT = PREFIX + 'Current'
PROP_FAKE = PREFIX + 'OriginalFakeUser'
MAT_REV = PREFIX + 'Variant'
MAT_TOKEN = PREFIX + 'TokenOnMaterial'
OBJECT_RE = re.compile(r'^S_actor_jsspsi_vfxpart_0[1-7]_lod0$', re.I)


def _objects(scene):
    return sorted((o for o in scene.objects if OBJECT_RE.fullmatch(o.name)), key=lambda o: o.name)


def _readonly(item):
    return bool(getattr(item, 'library', None) or getattr(item, 'override_library', None))


def _eligible_scene(context):
    try:
        from . import engine
        return bool(engine._xdzr8_ae_state(context).get('authorized', False))
    except Exception:
        return False


def has_active_comparison(objects):
    """Build guard: even a partially recorded test fails closed."""
    return any(OBJECT_RE.fullmatch(str(o.name)) and bool(o.get(PROP_TOKEN, ''))
               for o in (objects or ()))


def _material(obj):
    mats = getattr(getattr(obj, 'data', None), 'materials', None)
    if mats is None or len(mats) != 1:
        raise RuntimeError('%s: expected exactly one material slot' % obj.name)
    if mats[0] is None:
        raise RuntimeError('%s: empty material slot' % obj.name)
    return mats[0]


def _require_objects(context):
    # E3.4.4 may temporarily display A2 while retaining an E3.4.1 A parent.
    # Refuse nesting a new E341 session until its child preview is restored.
    if any(o.get('SaberShader_AE_Si_E344_Token', '') for o in _objects(context.scene)):
        raise RuntimeError('E3.4.4 A/A2 active; restore Original A first')
    if not _eligible_scene(context):
        raise RuntimeError('AE profile is not currently verified; no experimental write')
    objs = _objects(context.scene)
    if len(objs) != 7:
        raise RuntimeError('Expected exactly seven ORIGINAL Si vfxpart lod0 objects; found %d' % len(objs))
    for obj in objs:
        if obj.type != 'MESH' or _readonly(obj) or _readonly(obj.data) or getattr(obj.data, 'users', 1) != 1:
            raise RuntimeError('%s: not a local single-user mesh' % obj.name)
        if obj.get(PROP_TOKEN):
            raise RuntimeError('A/B session already prepared; use Show A/B or Restore')
        mat = _material(obj)
        if _readonly(mat) or mat.get('AEF_V11_SourceMaterial', '') != 'DefaultHGMaterial':
            raise RuntimeError('%s: material is linked or lacks exact DefaultHGMaterial source' % obj.name)
    originals = {_material(o).as_pointer() for o in objs}
    if len(originals) != 1:
        raise RuntimeError('Multiple different VFX materials: A/B requires one shared baseline')
    return objs, _material(objs[0])


def _is_nested_mask_a(mat):
    """Do not infer 'A' from the word Mask alone: inspect the active subgraph."""
    if not mat.name.startswith('SaberShader - Mask'):
        return False
    tree = getattr(mat, 'node_tree', None)
    if not tree:
        return False
    for node in tree.nodes:
        if node.bl_idname != 'ShaderNodeGroup' or not node.node_tree:
            continue
        inner = node.node_tree
        image_nodes = [n for n in inner.nodes if n.bl_idname == 'ShaderNodeTexImage' and n.image]
        gfx = [n for n in image_nodes if 't_fx_trail_gfx_18' in
               (str(n.image.name) + ' ' + str(n.image.filepath)).casefold()]
        if not gfx:
            continue
        has_rgb = any(l.from_node in gfx and l.from_socket.name == 'Color' and
                      l.to_node.bl_idname == 'ShaderNodeEmission' for l in inner.links)
        has_alpha = any(l.from_node in gfx and l.from_socket.name == 'Alpha' and
                        l.to_node.bl_idname == 'ShaderNodeMixShader' for l in inner.links)
        if has_rgb and has_alpha:
            return True
    return False


def _find_main_image(mat):
    filename = 'T_fx_trail_gfx_18.png'
    for im in bpy.data.images:
        try:
            if Path(bpy.path.abspath(im.filepath, library=im.library)).name.casefold() == filename.casefold():
                if im.packed_file or Path(bpy.path.abspath(im.filepath)).is_file():
                    return im
        except (ValueError, AttributeError, OSError):
            continue
    scene = bpy.context.scene
    settings = getattr(scene, 'aef_sabershader_v8', None)
    folder = str(getattr(settings, 'universal_texture_folder', '') or '')
    slot = {'image_file': filename, 'texture': filename[:-4]}
    return _fx3._find_image_slot(slot, mat, texture_dir=folder)


def _clear_inherited_stage_tags(mat):
    """An experimental child must not impersonate a Build or E332 stage."""
    for key in ( _fxb.MARKER, _fxb.KIND_KEY, _fxb.ORIGINAL_KEY,
                _fxb.ORIGINAL_FAKE_KEY, _fxb.VFX_B_KEY):
        if key in mat:
            del mat[key]
    # E3.4.5.1: keep auto-Build A provenance only on its verified material,
    # never on a private E341 A/B or E344 A2 descendant copy.
    for key in tuple(mat.keys()):
        if str(key).startswith('SaberShader_AE_Si_BuildA_'):
            del mat[key]


def _single_trail_a(mat):
    """Construct an *approximate* A when Mask.002 is not the existing baseline."""
    im = _find_main_image(mat)
    if im is None:
        raise RuntimeError('A requires T_fx_trail_gfx_18.png (not loaded/found)')
    if im.colorspace_settings.name != 'Non-Color':
        im = im.copy()
        im.name = 'SaberShader E341 | A | NonColor gfx18'
        im.use_fake_user = False
        im.colorspace_settings.name = 'Non-Color'
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    uv = nodes.new('ShaderNodeTexCoord'); uv.location = (-650, 0)
    tex = nodes.new('ShaderNodeTexImage'); tex.name = 'E341 A | Single Trail gfx18'; tex.location = (-430, 0)
    tex.image = im
    emit = nodes.new('ShaderNodeEmission'); emit.location = (-180, 140)
    transparent = nodes.new('ShaderNodeBsdfTransparent'); transparent.location = (-180, -140)
    mix = nodes.new('ShaderNodeMixShader'); mix.location = (80, 0)
    out = nodes.new('ShaderNodeOutputMaterial'); out.location = (310, 0)
    links.new(uv.outputs['UV'], tex.inputs['Vector'])
    links.new(tex.outputs['Color'], emit.inputs['Color'])
    links.new(tex.outputs['Alpha'], mix.inputs[0])
    links.new(transparent.outputs['BSDF'], mix.inputs[1])
    links.new(emit.outputs['Emission'], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs['Surface'])
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'DITHERED'
    if hasattr(mat, 'use_backface_culling'):
        mat.use_backface_culling = False


def _dual_layer_b(mat):
    """Stage original E332 nodes, then swap role of the two exact trail textures.

    Keep B's contrast, UV maps, intensity, facing and alpha at E332 baseline:
    this study changes the texture hierarchy only, not extra look dials.
    """
    _fxb._vfx_graph(mat)
    nodes = mat.node_tree.nodes
    prefix = 'SaberShader AE VFX E3.3.1 | '
    main = next((n for n in nodes if n.name.startswith(prefix + 'Main Trail | ')), None)
    detail = next((n for n in nodes if n.name.startswith(prefix + 'Detail | ')), None)
    if main is None or detail is None or main.image is None or detail.image is None:
        raise RuntimeError('B staging has no complete main/detail texture assignment')
    main_file = Path(bpy.path.abspath(main.image.filepath)).name.casefold()
    detail_file = Path(bpy.path.abspath(detail.image.filepath)).name.casefold()
    if main_file != 't_fx_trail_fj_09_1_v1d4_m.png' or detail_file != 't_fx_trail_gfx_18.png':
        raise RuntimeError('Unexpected B source textures; refuse unverified swap')
    main.image, detail.image = detail.image, main.image
    main.name = prefix + 'Main Trail | T_fx_trail_gfx_18.png'
    main.label = 'Main Trail | gfx18 (A/B)'
    detail.name = prefix + 'Detail | T_fx_trail_fj_09_1_v1d4_M.png'
    detail.label = 'Detail | fj09 (A/B)'
    mat['SaberShader_E341_B_Change'] = 'SWAP_MAIN_AND_DETAIL_ONLY'


def _remove_staged(materials, old_image_ptrs):
    for mat in materials:
        try:
            if mat is not None and not mat.users:
                bpy.data.materials.remove(mat)
        except Exception:
            pass
    for im in list(bpy.data.images):
        try:
            if im.as_pointer() not in old_image_ptrs and not im.users and not im.use_fake_user:
                bpy.data.images.remove(im)
        except Exception:
            pass


def prepare(context):
    objs, original = _require_objects(context)
    image_before = {im.as_pointer() for im in bpy.data.images}
    token = uuid.uuid4().hex
    staged, swaps = [], []
    prev_fake = bool(original.use_fake_user)
    try:
        if _is_nested_mask_a(original):
            mat_a = original  # exact, untouched Mask.002 as visual reference A
            a_mode = 'CAPTURED_EXACT_NESTED_MASK'
        else:
            mat_a = original.copy()
            staged.append(mat_a)
            mat_a.name = 'SaberShader AE Si E341 | A Single Trail'
            _clear_inherited_stage_tags(mat_a)
            _single_trail_a(mat_a)
            mat_a[MAT_REV] = 'A_APPROX'
            mat_a[MAT_TOKEN] = token
            mat_a.use_fake_user = True
            a_mode = 'APPROXIMATE_SINGLE_TRAIL'
        mat_b = original.copy()
        staged.append(mat_b)
        mat_b.name = 'SaberShader AE Si E341 | B Dual Layer gfx18-primary'
        _clear_inherited_stage_tags(mat_b)
        _dual_layer_b(mat_b)
        mat_b[MAT_REV] = 'B'
        mat_b[MAT_TOKEN] = token
        mat_b.use_fake_user = True
        original.use_fake_user = True
        for obj in objs:
            swaps.append(obj)  # rollback even if an IDProperty assignment fails midway
            obj[PROP_TOKEN] = token
            obj[PROP_ORIGINAL] = original.name
            obj[PROP_A] = mat_a.name
            obj[PROP_B] = mat_b.name
            obj[PROP_CURRENT] = 'ORIGINAL'
            obj[PROP_FAKE] = int(prev_fake)
    except Exception:
        for obj in swaps:
            for key in (PROP_TOKEN, PROP_ORIGINAL, PROP_A, PROP_B, PROP_CURRENT, PROP_FAKE):
                if key in obj: del obj[key]
        original.use_fake_user = prev_fake
        for mat in staged:
            try: mat.use_fake_user = False
            except Exception: pass
        _remove_staged(staged, image_before)
        raise
    return {'status': 'PREPARED', 'count': len(objs), 'mode_a': a_mode,
            'original': original.name, 'material_a': mat_a.name, 'material_b': mat_b.name}


def _session(context):
    objs = _objects(context.scene)
    if len(objs) != 7:
        raise RuntimeError('Seven original Si vfxpart meshes required')
    tokens = {str(o.get(PROP_TOKEN, '')) for o in objs}
    if len(tokens) != 1 or not next(iter(tokens)):
        raise RuntimeError('No complete E3.4.1 A/B session: run Prepare first')
    token = next(iter(tokens))
    name_fields = (PROP_ORIGINAL, PROP_A, PROP_B, PROP_FAKE)
    for key in name_fields:
        if len({str(o.get(key, '')) for o in objs}) != 1:
            raise RuntimeError('A/B session has inconsistent original/variant references')
    material_names = [str(objs[0].get(x, '')) for x in (PROP_ORIGINAL, PROP_A, PROP_B)]
    if any(not x for x in material_names):
        raise RuntimeError('A/B missing material ID name')
    mats = [bpy.data.materials.get(x) for x in material_names]
    if any(m is None for m in mats):
        raise RuntimeError('A/B missing original or staged material: restore via .blend backup')
    original, a, b = mats
    if (original.get('AEF_V11_SourceMaterial', '') != 'DefaultHGMaterial' or
            a.get('AEF_V11_SourceMaterial', '') != 'DefaultHGMaterial' or
            b.get('AEF_V11_SourceMaterial', '') != 'DefaultHGMaterial' or
            b.get(MAT_REV) != 'B' or b.get(MAT_TOKEN) != token or
            (a is not original and (a.get(MAT_REV) != 'A_APPROX' or a.get(MAT_TOKEN) != token))):
        raise RuntimeError('A/B material identity or staged marker mismatch')
    for obj in objs:
        if (obj.type != 'MESH' or _readonly(obj) or _readonly(obj.data) or
                getattr(obj.data, 'users', 1) != 1 or
                not any(_material(obj) is ref for ref in mats)):
            raise RuntimeError('A/B active mesh was edited/shared; fail closed')
    return objs, (original, a, b)


def show(context, variant):
    if any(o.get('SaberShader_AE_Si_E344_Token', '') for o in _objects(context.scene)):
        raise RuntimeError('Restore E3.4.4 A2 before changing E3.4.1 A/B')
    if variant not in ('A', 'B'):
        raise ValueError('Variant must be A or B')
    objs, (original, a, b) = _session(context)
    target = a if variant == 'A' else b
    changes = []
    try:
        for obj in objs:
            old = _material(obj)
            obj.data.materials[0] = target
            changes.append((obj, old))
        for obj in objs:
            obj[PROP_CURRENT] = variant
    except Exception:
        for obj, old in reversed(changes):
            obj.data.materials[0] = old
        raise
    return {'status': 'ACTIVE_' + variant, 'meshes': 7, 'material': target.name}


def restore(context):
    if any(o.get('SaberShader_AE_Si_E344_Token', '') for o in _objects(context.scene)):
        raise RuntimeError('Restore E3.4.4 A2 before restoring E3.4.1')
    objs, (original, a, b) = _session(context)
    swaps = []
    try:
        for obj in objs:
            old = _material(obj)
            obj.data.materials[0] = original
            swaps.append((obj, old))
    except Exception:
        for obj, old in reversed(swaps):
            obj.data.materials[0] = old
        raise
    original_fake = bool(objs[0].get(PROP_FAKE, 1))
    for obj in objs:
        for key in (PROP_TOKEN, PROP_ORIGINAL, PROP_A, PROP_B, PROP_CURRENT, PROP_FAKE):
            if key in obj:
                del obj[key]
    # Unshared test materials can be removed, but not if somebody else uses them.
    for stage in (a, b):
        if stage is original:
            continue
        if getattr(stage, 'users', 0) == 1 and bool(stage.use_fake_user):
            stage.use_fake_user = False
            if stage.users == 0:
                bpy.data.materials.remove(stage)
    # Do not disable the fake user if another stage still references it.
    if not original_fake and not any(o.get(PROP_ORIGINAL, '') == original.name for o in bpy.data.objects):
        original.use_fake_user = False
    return {'status': 'RESTORED', 'meshes': 7, 'material': original.name}


class AEF_OT_si_vfx_ab_prepare(bpy.types.Operator):
    bl_idname = 'sabershader.si_vfx_ab_prepare'
    bl_label = 'Prepare Si VFX Comparison'
    bl_description = 'Prepare reversible Si idle VFX A/B; does NOT change active appearance'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            r = prepare(context)
        except Exception as exc:
            self.report({'ERROR'}, 'Si FX A/B preflight: ' + str(exc)[:160]); return {'CANCELLED'}
        self.report({'INFO'}, 'A/B ready for 7 VFX; A=' + r['mode_a'])
        return {'FINISHED'}


class AEF_OT_si_vfx_ab_show_a(bpy.types.Operator):
    bl_idname = 'sabershader.si_vfx_ab_show_a'
    bl_label = 'Show A — Single Trail'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try: r = show(context, 'A')
        except Exception as exc:
            self.report({'ERROR'}, str(exc)[:180]); return {'CANCELLED'}
        self.report({'INFO'}, 'A active on 7 meshes: ' + r['material']); return {'FINISHED'}


class AEF_OT_si_vfx_ab_show_b(bpy.types.Operator):
    bl_idname = 'sabershader.si_vfx_ab_show_b'
    bl_label = 'Show B — Dual Layer gfx18 Primary'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try: r = show(context, 'B')
        except Exception as exc:
            self.report({'ERROR'}, str(exc)[:180]); return {'CANCELLED'}
        self.report({'INFO'}, 'B active on 7 meshes: ' + r['material']); return {'FINISHED'}


class AEF_OT_si_vfx_ab_restore(bpy.types.Operator):
    bl_idname = 'sabershader.si_vfx_ab_restore'
    bl_label = 'Restore Original Si VFX (A/B)'
    bl_description = 'Restore the exact materials assigned before starting the Si VFX comparison'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try: r = restore(context)
        except Exception as exc:
            self.report({'ERROR'}, str(exc)[:180]); return {'CANCELLED'}
        self.report({'INFO'}, 'Restored exact original VFX for 7 meshes'); return {'FINISHED'}


def read_only_snapshot(context):
    """Capture comparable metadata without changing any Blender datablock."""
    import hashlib
    objs, (original, a, b) = _session(context)

    def graph(mat):
        images, edges, node_count = [], [], 0
        visited = set()
        def walk(tree, path, depth):
            nonlocal node_count
            if tree is None or depth > 5:
                return
            identity = tree.as_pointer() if hasattr(tree, 'as_pointer') else id(tree)
            if identity in visited:
                return
            visited.add(identity)
            for n in tree.nodes:
                node_count += 1
                if getattr(n, 'image', None) is not None:
                    img=n.image
                    images.append({'node': path+'/'+n.name,
                                   'image':img.name,
                                   'filepath':str(getattr(img,'filepath','')),
                                   'colorspace':str(img.colorspace_settings.name)})
                if getattr(n, 'node_tree', None) is not None:
                    walk(n.node_tree, path+'/'+n.name, depth+1)
            for link in tree.links:
                edges.append((path+'/'+link.from_node.name, link.from_socket.name,
                              path+'/'+link.to_node.name, link.to_socket.name))
        walk(mat.node_tree, 'Material', 0)
        stable={'images':sorted(images, key=lambda x: x['node']),
                'links':sorted(edges), 'node_count':node_count,
                'render_method':str(getattr(mat,'surface_render_method',''))}
        digest=hashlib.sha256(__import__('json').dumps(stable,sort_keys=True).encode('utf-8')).hexdigest()
        return {'material':mat.name,'users':mat.users,'fingerprint':digest,**stable}

    active = {obj.get(PROP_CURRENT, '') for obj in objs}
    return {'revision':REVISION,'blender':'.'.join(map(str,bpy.app.version[:3])),
            'blend':str(bpy.data.filepath),'read_only':True,
            'active_modes':sorted(active),
            'scene_engine':str(getattr(context.scene.render,'engine','')),
            'camera':str(context.scene.camera.name) if context.scene.camera else '',
            'objects':[{'name':o.name,'material':_material(o).name} for o in objs],
            'original':graph(original),'A':graph(a),'B':graph(b)}


class AEF_OT_si_vfx_ab_snapshot(bpy.types.Operator):
    bl_idname='sabershader.si_vfx_ab_snapshot'
    bl_label='Record Si A/B Metadata (Read Only)'
    bl_description='Write A/B material topology and assignment metadata to a timestamped JSON; no Blender data changed'
    bl_options={'REGISTER'}

    def execute(self, context):
        import json, tempfile
        from datetime import datetime, timezone
        try:
            data=read_only_snapshot(context)
            suffix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            path=Path(tempfile.gettempdir())/('SaberShader_Si_FX_E341_AB_'+suffix+'_'+uuid.uuid4().hex[:8]+'.json')
            with path.open('x',encoding='utf-8') as stream:
                json.dump(data,stream,indent=2,ensure_ascii=False)
            print('SABERSHADER SI E341 A/B READ ONLY REPORT:',str(path))
            self.report({'INFO'}, 'Si VFX comparison JSON: '+str(path)[:170])
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},'Si VFX comparison snapshot: '+str(exc)[:175])
            return {'CANCELLED'}
