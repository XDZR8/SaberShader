"""Si AE ink FX approximation E3 -- Blender 5.1, opt-in by verified AE Build.

Only exact authored FX source materials; never operate on DefaultHGMaterial,
procedural FX, source mesh transforms, other characters, or generated outlines.
The shader graph is a *documented approximation*, not Unity shader equivalence.
"""
from __future__ import annotations

import os
from pathlib import Path

import bpy

from . import ae_material_sources as source

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = 'AE_SI_FX_E3_PREVIEW_1'
MARKER = 'SaberShader_AE_FX_E3'
ORIGINAL_KEY = 'SaberShader_AE_FX_E3_OriginalMaterial'
TARGET_SOURCES = frozenset({
    'M_fx_jsspsi_cloth_04_01', 'M_fx_jsspsi_cloth_05',
    'M_fx_jsspsi_cloth_06_01', 'M_fx_actor_jsspsi_cloth_08_01',
    'M_fx_jsspsi_cloth_06_02',
})
# Offline image-channel review of the original PNGs: these main images
# have an informative A channel; others encode strokes in grayscale RGB.
MAIN_HAS_ALPHA = frozenset({
    'M_fx_jsspsi_cloth_04_01', 'M_fx_actor_jsspsi_cloth_08_01'
})
NODE_PREFIX = 'SaberShader AE FX E3 | '


def _source_identity(material, catalog):
    name, entry, identity = source.resolve_source(material, catalog)
    if name in TARGET_SOURCES and entry.get('category') == 'fx_maintex' and not entry.get('is_lod_variant'):
        return name, entry
    return None, None


def _path_ok(path, expected_file):
    try:
        return os.path.isfile(path) and os.path.basename(path).casefold() == expected_file.casefold()
    except (OSError, TypeError):
        return False


def _find_image_slot(slot, main_material, texture_dir=''):
    """Reuse a matching image, or load its *exact* name from selected folders.

    No recursive scanning; no guess based solely on a mask/normal suffix.
    """
    filename = slot['image_file']
    wanted = source.normalize_basename(slot['texture'])
    for img in bpy.data.images:
        if source.normalize_basename(img.name) != wanted and source.normalize_basename(img.filepath) != wanted:
            continue
        try:
            packed = bool(img.packed_file) or bool(len(img.packed_files))
        except (AttributeError, TypeError):
            packed = False
        full = ''
        try:
            full = bpy.path.abspath(img.filepath, library=img.library)
        except (AttributeError, TypeError, ValueError):
            pass
        if packed or _path_ok(full, filename):
            return img

    # Only inspect exact named file in folders derived from previously linked
    # source images or the user-specified texture folder.
    dirs = []
    if texture_dir:
        dirs.append(Path(texture_dir))
    for node_info in source._linked_images(main_material).values():
        for item in node_info:
            p = item.get('filepath') or ''
            if not p:
                continue
            try:
                abs_path = bpy.path.abspath(p)
                dirs.append(Path(abs_path).parent)
            except (ValueError, TypeError):
                pass
    checked = set()
    for folder in dirs:
        for root in (folder, folder / 'Textures'):
            key = str(root).casefold()
            if key in checked:
                continue
            checked.add(key)
            filepath = root / filename
            if not _path_ok(str(filepath), filename):
                continue
            try:
                img = bpy.data.images.load(str(filepath), check_existing=True)
                if source.normalize_basename(img.name) == wanted or _path_ok(bpy.path.abspath(img.filepath), filename):
                    return img
            except (OSError, RuntimeError, ValueError):
                continue
    return None


def _c(x, default=1.0):
    try:
        return max(0.0, min(1.0, float(x)))
    except (ValueError, TypeError):
        return default


def make_plan(objects, catalog, texture_dir=''):
    """Preflight without material writes. Returns groups and diagnostic skips."""
    plans, skipped = [], []
    seen = {}
    for obj in objects or ():
        if getattr(obj, 'type', '') != 'MESH' or 'jsspsi' not in str(getattr(obj,'name','')).casefold():
            continue
        mesh = getattr(obj, 'data', None)
        if mesh is None or getattr(mesh, 'library', None) is not None or getattr(mesh, 'override_library', None) is not None:
            skipped.append((obj.name, 'READ_ONLY_MESH'))
            continue
        # Mutating slots on a shared Mesh datablock could affect another actor.
        if getattr(mesh, 'users', 1) > 1:
            skipped.append((obj.name, 'SHARED_MESH'))
            continue
        for idx, mat in enumerate(getattr(mesh, 'materials', ()) or ()):
            if mat is None:
                continue
            if mat.get('SaberShader_AE_FX_E331', '') == 'AE_SI_FX_E331_LOOK_MATCH_1':
                continue
            if mat.get(MARKER, '') == REVISION:
                continue
            name, record = _source_identity(mat, catalog)
            if not name:
                continue
            if mat.library is not None or getattr(mat,'override_library',None) is not None:
                skipped.append((obj.name, 'LINKED_MATERIAL'))
                continue
            key = (mat.as_pointer() if hasattr(mat, 'as_pointer') else id(mat), name)
            group = seen.get(key)
            if group is None:
                required = ('_MainTex','_MaskTex','_DisturbTex1')
                if any(s not in record['slots'] for s in required):
                    skipped.append((obj.name, 'SOURCE_SLOTS_INCOMPLETE'))
                    continue
                images = {}
                missing = []
                for slot, rec in record['slots'].items():
                    image = _find_image_slot(rec, mat, texture_dir)
                    if image is None:
                        missing.append(slot + ':' + rec['image_file'])
                    else:
                        images[slot] = image
                if missing:
                    skipped.append((obj.name, 'MISSING_IMAGES ' + ', '.join(missing)))
                    continue
                group = {'material': mat, 'source': name, 'record': record, 'images': images, 'targets': []}
                seen[key] = group
                plans.append(group)
            group['targets'].append((mesh, idx))
    return plans, skipped


def _node(tree, kind, name, xy):
    n = tree.nodes.new(kind)
    n.name = NODE_PREFIX + name
    n.label = name
    n.location = xy
    return n


def _mapping(tree, uv_output, slot, y):
    rec = slot['data']
    m = _node(tree, 'ShaderNodeMapping', slot['name'] + ' UV', (-790, y))
    m.inputs['Location'].default_value = (*rec.get('offset',(0,0)), 0.0)
    m.inputs['Scale'].default_value = (*rec.get('scale',(1,1)), 1.0)
    tree.links.new(uv_output, m.inputs['Vector'])
    return m.outputs['Vector']


def _tex(tree, uv_output, slot_name, rec, image, y):
    data={'name':slot_name,'data':rec}
    uv = _mapping(tree, uv_output, data, y)
    tex = _node(tree,'ShaderNodeTexImage',slot_name + ' / ' + rec['texture'],(-525,y))
    tex.image = image
    tex.extension = 'REPEAT'
    tree.links.new(uv, tex.inputs['Vector'])
    return tex


def _math(tree, op, name, x, y):
    n=_node(tree,'ShaderNodeMath',name,(x,y))
    n.operation=op
    return n


def _build_graph(mat, plan):
    """Ink-stroke approximation: source UVs, main/mask/blend/disturb, emissive transparency.

    Main A is used only for two confirmed alpha-bearing PNGs. For others
    main RGB lightness acts as a stroke density; MASK lightness gates coverage.
    Unity shader's true time/particle blending and color channels are unknown.
    """
    mat.use_nodes = True
    tree=mat.node_tree
    tree.nodes.clear()
    src=plan['record']; slots=src['slots']; imgs=plan['images']; flags=src['selected_flags']
    uv = _node(tree,'ShaderNodeTexCoord','Source UV',(-1190,260))
    uv_out=uv.outputs['UV']
    # Distortion maps are sampled in the authored UV domain; normal XY is
    # centered and converted to a small static offset (no unverified time animation).
    disturb = _tex(tree,uv_out,'_DisturbTex1',slots['_DisturbTex1'],imgs['_DisturbTex1'],-570)
    center = _node(tree,'ShaderNodeVectorMath','Disturb centered',(-300,-520))
    center.operation='SUBTRACT'; center.inputs[1].default_value=(0.5,0.5,0.0)
    tree.links.new(disturb.outputs['Color'],center.inputs[0])
    strength=_node(tree,'ShaderNodeVectorMath','Static disturbance strength',(-105,-540))
    strength.operation='SCALE'; strength.inputs[3].default_value=0.035
    tree.links.new(center.outputs['Vector'],strength.inputs[0])
    add=_node(tree,'ShaderNodeVectorMath','Disturbed UV for main',(-890,310))
    add.operation='ADD'; tree.links.new(uv_out,add.inputs[0]);tree.links.new(strength.outputs['Vector'],add.inputs[1])
    main=_tex(tree,add.outputs['Vector'],'_MainTex',slots['_MainTex'],imgs['_MainTex'],350)
    mask=_tex(tree,uv_out,'_MaskTex',slots['_MaskTex'],imgs['_MaskTex'],-40)
    blend=None
    if '_BlendTex' in slots:
        blend=_tex(tree,uv_out,'_BlendTex',slots['_BlendTex'],imgs['_BlendTex'],-325)
    # Transparent surface: the source FX does not have an opaque _BaseMap.
    output=_node(tree,'ShaderNodeOutputMaterial','Material Output',(1050,270))
    trans=_node(tree,'ShaderNodeBsdfTransparent','Transparent ink',(620,80))
    emission=_node(tree,'ShaderNodeEmission','Ink emission',(620,340))
    emission.inputs['Strength'].default_value=1.0
    # The original _BlendTint contains values >1; expose it as editable
    # RGB (no clamp) while keeping source alpha controlled separately.
    tint=src.get('selected_colors',{}).get('_BlendTint',{})
    mult=_node(tree,'ShaderNodeMixRGB','Source-tinted main',(50,370))
    mult.blend_type='MULTIPLY'; mult.inputs[0].default_value=1.0
    tree.links.new(main.outputs['Color'],mult.inputs[1])
    mult.inputs[2].default_value=tuple(float(tint.get(k,1.0)) for k in ('r','g','b'))+(1.0,)
    color=mult.outputs['Color']
    if blend is not None and float(flags.get('_UseBlend',0)) >= 0.5:
        bn=_node(tree,'ShaderNodeMixRGB','Blend texture (estimated)',(315,340))
        bn.blend_type='MULTIPLY';bn.inputs[0].default_value=0.35
        tree.links.new(color,bn.inputs[1]);tree.links.new(blend.outputs['Color'],bn.inputs[2]);color=bn.outputs['Color']
    tree.links.new(color,emission.inputs['Color'])
    maskrgb=_node(tree,'ShaderNodeRGBToBW','Mask luminance',(-20,-70))
    tree.links.new(mask.outputs['Color'], maskrgb.inputs['Color'])
    # Some grayscale main images have constant alpha=1. Use their intensity.
    if plan['source'] in MAIN_HAS_ALPHA:
        main_density=main.outputs['Alpha']
    else:
        mainbw=_node(tree,'ShaderNodeRGBToBW','Ink stroke grayscale',(-20,125))
        tree.links.new(main.outputs['Color'],mainbw.inputs['Color'])
        main_density=mainbw.outputs['Val']
    alpha=_math(tree,'MULTIPLY','Stroke × Mask',250,-20)
    tree.links.new(main_density,alpha.inputs[0]);tree.links.new(maskrgb.outputs['Val'],alpha.inputs[1])
    fade=_math(tree,'MULTIPLY','User opacity / preview',460,-30)
    tree.links.new(alpha.outputs[0],fade.inputs[0])
    # A meaningful editable alpha node. The real Unity FX is additionally
    # affected by vertex/particle alpha, which the static FBX cannot supply.
    fade.inputs[1].default_value=max(0.12,_c(tint.get('a',0.65),0.65))
    mix=_node(tree,'ShaderNodeMixShader','Alpha mix',(825,260))
    tree.links.new(fade.outputs[0],mix.inputs[0]);tree.links.new(trans.outputs[0],mix.inputs[1]);tree.links.new(emission.outputs[0],mix.inputs[2]);tree.links.new(mix.outputs[0],output.inputs['Surface'])
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method='BLENDED'
    if hasattr(mat, 'use_nodes'):
        mat.use_nodes=True
    if hasattr(mat, 'use_backface_culling'):
        mat.use_backface_culling=False


def apply_fx(objects, catalog=None, texture_dir=''):
    """All-or-nothing material-slot commit; retains original material datablocks.

    This routine runs AFTER the legacy AE shader Build. If FX fails, legacy
    Build is still successful and a warning is returned, not a false rollback.
    """
    catalog=catalog or source._source_catalog()
    plans, skipped=make_plan(objects,catalog,texture_dir)
    existing=sum(1 for obj in (objects or ())
                 if getattr(obj,'type','')=='MESH' and 'jsspsi' in str(getattr(obj,'name','')).casefold()
                 for mat in getattr(getattr(obj,'data',None),'materials',()) or ()
                 if mat is not None and mat.get(MARKER,'')==REVISION)
    prepared=[]
    committed=[]
    prior_fake_users=[]
    try:
        for plan in plans:
            old=plan['material']
            new=old.copy()
            new.use_fake_user=False
            prepared.append(new)
            new.name='SaberShader AE FX E3 | '+plan['source']
            _build_graph(new,plan)
            new[MARKER]=REVISION
            new[ORIGINAL_KEY]=old.name
            new['AEF_V11_SourceMaterial']=plan['source']
            new['SaberShader_AE_FX_E3_Disclaimer']='APPROXIMATION_NOT_UNITY_EQUIVALENCE'
            plan['new']=new
        for plan in plans:
            old = plan['material']
            was_fake = bool(old.use_fake_user)
            plan['new']['SaberShader_AE_FX_E3_OriginalFakeUser'] = int(was_fake)
            if not was_fake:
                old.use_fake_user = True
                prior_fake_users.append(old)
        for plan in plans:
            for mesh,idx in plan['targets']:
                old=mesh.materials[idx]
                mesh.materials[idx]=plan['new']
                committed.append((mesh,idx,old))
    except Exception as exc:
        for mesh, idx, old in reversed(committed):
            try: mesh.materials[idx]=old
            except Exception: pass
        for old in prior_fake_users:
            try: old.use_fake_user=False
            except Exception: pass
        for new in prepared:
            try:
                if not new.users: bpy.data.materials.remove(new)
            except Exception: pass
        return {'status':'ERROR_ROLLED_BACK','error':type(exc).__name__+': '+str(exc),
                'applied':0,'skipped':skipped}
    return {'status':'APPLIED' if plans else ('ALREADY_APPLIED' if existing else 'NO_APPLICABLE_MATERIALS'),
            'applied':len(plans)+existing,'new':len(plans),'existing':existing,
            'slots':len(committed),'skipped':skipped,
            'sources':[p['source'] for p in plans]}


def restore_fx(objects):
    """Explicit recovery tool; never restores other actors or unknown materials."""
    edits=[]; originals=[]; errors=[]
    if any(getattr(obj, 'type', '') == 'MESH' and 'jsspsi' in str(obj.name).casefold()
           and any(m and m.get('SaberShader_AE_FX_E331') == 'AE_SI_FX_E331_LOOK_MATCH_1'
                   for m in getattr(getattr(obj, 'data', None), 'materials', ()) or ())
           for obj in objects or ()):
        return {'status': 'BLOCKED', 'errors': ['RESTORE_E3_3_1_FIRST'], 'restored': 0}
    for obj in objects or ():
        if getattr(obj,'type','') != 'MESH' or 'jsspsi' not in str(obj.name).casefold():
            continue
        mesh=getattr(obj,'data',None)
        if mesh is None or getattr(mesh,'users',1)>1:
            continue
        for idx,mat in enumerate(getattr(mesh,'materials',()) or ()):
            if mat is None or mat.get(MARKER,'') != REVISION:
                continue
            original_name=mat.get(ORIGINAL_KEY,'')
            original=bpy.data.materials.get(original_name)
            if original is None or original is mat:
                errors.append(obj.name+': ORIGINAL_MISSING '+str(original_name))
                continue
            expected=mat.get('AEF_V11_SourceMaterial','')
            if original.get('AEF_V11_SourceMaterial','') != expected:
                errors.append(obj.name+': ORIGINAL_SOURCE_MISMATCH')
                continue
            edits.append((mesh,idx,mat,original))
            originals.append((original,bool(mat.get('SaberShader_AE_FX_E3_OriginalFakeUser',1))))
    if errors:
        return {'status':'BLOCKED','errors':errors,'restored':0}
    completed=[]
    try:
        for mesh,idx,mat,original in edits:
            mesh.materials[idx]=original
            completed.append((mesh,idx,mat))
    except Exception as exc:
        for mesh,idx,mat in reversed(completed):
            try: mesh.materials[idx]=mat
            except Exception: pass
        return {'status':'ERROR_ROLLED_BACK','error':str(exc),'restored':0}
    for orig,had_fake in originals:
        if not had_fake:
            try: orig.use_fake_user=False
            except Exception: pass
    return {'status':'RESTORED','restored':len(edits)}


class AEF_OT_ae_si_fx_e3_restore(bpy.types.Operator):
    bl_idname='sabershader.ae_si_fx_e3_restore'
    bl_label='Restore Original Si FX Materials'
    bl_description='Restore original SaberShader materials preserved before E3 preview'
    bl_options={'REGISTER','UNDO'}

    def execute(self, context):
        result=restore_fx(source._target_meshes(context))
        if result['status'] != 'RESTORED':
            self.report({'ERROR'}, 'Si FX E3 restore: '+str(result.get('errors', result.get('error','unknown')))[:155])
            return {'CANCELLED'}
        self.report({'INFO'},'Si FX E3: restored %d material slots'%result['restored'])
        return {'FINISHED'}
