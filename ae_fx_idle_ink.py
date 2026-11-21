"""SaberShader E3.4.4 — Si idle ink fidelity A/A2 preset (opt-in).

Built on universal E3.4.3 control policy, but intentionally distinct from its
source-JSON _MainTex pipeline: Si's seven idle vfxpart use DefaultHGMaterial.

A is the *actual* E3.4.1 A material or positively identified original nested
Mask A. A2 is a private material copy. For nested A the inner group is copied
before any node is edited. No FX/eye/cloth build-time changes or Unity shader
fidelity assertions. Blender 5.1.1 native visual validation still required.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bpy

from .ae_ui_visibility import ae_developer_tools_visible

from . import ae_fx_comparison as legacy
from . import ae_fx_fidelity_core as policy
from . import ae_fx_fidelity as universal

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = 'AE_SI_IDLE_INK_E344_1'
PREFIX = 'SaberShader_AE_Si_E344_'
O_TOKEN = PREFIX + 'Token'
O_A = PREFIX + 'OriginalA'
O_A2 = PREFIX + 'A2'
O_CURRENT = PREFIX + 'Current'
O_FAKE = PREFIX + 'OriginalFakeUser'
O_HASH = PREFIX + 'OriginalGraphHash'
O_PARENT = PREFIX + 'ParentE341'
M_TOKEN = PREFIX + 'MaterialToken'
M_REV = PREFIX + 'MaterialRevision'
M_TREE = PREFIX + 'PrivateTreeName'
M_TOPO = PREFIX + 'A2Topology'
NODE = 'SaberShader AE E344 | '

# Hypotheses, not game-extracted numeric values. Deliberately close to A.
PRESET = {
    'alpha_power': 1.08,
    'alpha_multiplier': 0.96,
    'edge_fade': 0.02,
    'brightness': -0.02,
    'contrast': 0.045,
    'tint': (0.92, 0.93, 0.94),
    'emission_gain': 0.90,
}
assert policy.validated_parameters(PRESET)


def _readonly(obj):
    return bool(getattr(obj, 'library', None) or getattr(obj, 'override_library', None))


def _objects(scene):
    return legacy._objects(scene)


def has_active_comparison(objects):
    """Build guard, including partially tagged sessions; no actor inference."""
    return any(bool(o.get(O_TOKEN, '')) for o in (objects or ()) if getattr(o, 'type', '') == 'MESH')


def _material(obj):
    return legacy._material(obj)


def _image_is_gfx18(node):
    if getattr(node, 'bl_idname', '') != 'ShaderNodeTexImage':
        return False
    image = getattr(node, 'image', None)
    if image is None:
        return False
    return (Path(str(getattr(image, 'filepath', '')).replace('\\', '/')).name.casefold()
            == 't_fx_trail_gfx_18.png')


def _reachable(tree, start, end):
    todo, seen = [start], set()
    for _ in range(400):
        if not todo:
            return False
        n = todo.pop()
        if n == end:
            return True
        key = id(n)
        if key in seen:
            continue
        seen.add(key)
        todo.extend(l.to_node for l in tree.links if l.from_node == n)
    return False


def _targets(tree):
    """Require exact gfx18 RGB -> Emission and Alpha -> TransparentMix.

    Never assume another opacity route or blindly alter a group by name.
    """
    matches = []
    for img in tree.nodes:
        if not _image_is_gfx18(img):
            continue
        colors = [l for l in tree.links if l.from_node == img and
                  l.from_socket == img.outputs.get('Color') and
                  l.to_node.bl_idname == 'ShaderNodeEmission' and
                  l.to_socket == l.to_node.inputs.get('Color')]
        alpha = [l for l in tree.links if l.from_node == img and
                 l.from_socket == img.outputs.get('Alpha') and
                 l.to_node.bl_idname == 'ShaderNodeMixShader' and
                 l.to_socket == l.to_node.inputs[0]]
        for c in colors:
            for a in alpha:
                emit, mix = c.to_node, a.to_node
                if not any(l.from_node == emit and l.to_node == mix for l in tree.links):
                    continue
                if not any(l.from_node == mix and
                           l.to_node.bl_idname in ('ShaderNodeGroupOutput', 'ShaderNodeOutputMaterial')
                           for l in tree.links) and not any(
                           _reachable(tree, mix, out) for out in tree.nodes
                           if out.bl_idname in ('ShaderNodeGroupOutput', 'ShaderNodeOutputMaterial')):
                    continue
                matches.append((img, emit, mix))
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one output-reaching gfx18 RGB/Alpha ink route (found %d)' % len(matches))
    return matches[0]


def _tree_choice(material):
    """Return (node_group_node or None, tree) without mutating anything."""
    if not material.use_nodes or not material.node_tree:
        raise RuntimeError('Idle ink A has no node shader')
    matches = []
    try:
        _targets(material.node_tree)
        matches.append((None, material.node_tree))
    except RuntimeError:
        pass
    for group in material.node_tree.nodes:
        if group.bl_idname == 'ShaderNodeGroup' and group.node_tree is not None:
            try:
                _targets(group.node_tree)
                matches.append((group, group.node_tree))
            except RuntimeError:
                continue
    if len(matches) != 1:
        raise RuntimeError('Ambiguous/missing single-trail A gfx18 route; no preview built (%d)' % len(matches))
    return matches[0]


def _graph_hash(mat):
    """Stable across save/reopen; covers original shader topology and values."""
    visited = set()
    values = []
    def normalized(value):
        try:
            if isinstance(value, (float, int, bool, str)):
                return round(value, 8) if isinstance(value, float) else value
            return [normalized(x) for x in value]
        except Exception:
            return str(value)
    def walk(tree, key):
        if tree is None or id(tree) in visited:
            return
        visited.add(id(tree))
        for n in tree.nodes:
            values.append(('node', key, n.name, n.bl_idname,
                           str(n.image.filepath) if getattr(n, 'image', None) else '',
                           tuple((s.name, normalized(getattr(s, 'default_value', None)))
                                 for s in n.inputs if hasattr(s, 'default_value'))))
            if getattr(n, 'node_tree', None):
                walk(n.node_tree, key + '/' + n.name)
        for l in tree.links:
            values.append(('link', key, l.from_node.name, l.from_socket.name,
                           l.to_node.name, l.to_socket.name))
    walk(mat.node_tree, 'Material')
    return hashlib.sha256(json.dumps(sorted(values, key=str), sort_keys=True, default=str).encode()).hexdigest()


def _topology(tree):
    nodes = sorted((n.name, n.bl_idname) for n in tree.nodes)
    links = sorted((l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name)
                   for l in tree.links)
    return hashlib.sha256(json.dumps((nodes, links), sort_keys=True).encode()).hexdigest()


def _math(nodes, name, op, xy):
    n = nodes.new('ShaderNodeMath')
    n.name = NODE + name
    n.label = 'E3.4.4 ' + name
    n.operation = op
    n.location = xy
    return n


def _install_controls(tree):
    img, emit, mix = _targets(tree)
    nodes, links = tree.nodes, tree.links
    # RGB branch: no image settings/alpha data changed.
    bright = nodes.new('ShaderNodeBrightContrast')
    bright.name = NODE + 'Color Bright Contrast'
    bright.location = (img.location.x + 220, img.location.y + 180)
    tint = nodes.new('ShaderNodeMixRGB')
    tint.name = NODE + 'Color Tint'
    tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = 1.0
    tint.location = (img.location.x + 450, img.location.y + 180)
    links.new(img.outputs['Color'], bright.inputs['Color'])
    links.new(bright.outputs['Color'], tint.inputs[1])
    links.new(tint.outputs['Color'], emit.inputs['Color'])
    # Alpha branch: preserve the original source PNG alpha (not an invented mask).
    x, y = (mix.location.x - 980, mix.location.y - 300)
    high = _math(nodes, 'Input Max', 'MINIMUM', (x, y))
    low = _math(nodes, 'Input Min', 'MAXIMUM', (x + 170, y))
    power = _math(nodes, 'Alpha Power', 'POWER', (x + 340, y))
    edge = _math(nodes, 'Edge Fade', 'SUBTRACT', (x + 510, y))
    norm = _math(nodes, 'Edge Normalize', 'DIVIDE', (x + 680, y))
    mult = _math(nodes, 'Alpha Multiplier', 'MULTIPLY', (x + 850, y))
    clamp = _math(nodes, 'Output Max', 'MINIMUM', (x + 1020, y))
    floor = _math(nodes, 'Output Min', 'MAXIMUM', (x + 1190, y))
    high.inputs[1].default_value = 1.0
    low.inputs[1].default_value = 0.0
    clamp.inputs[1].default_value = 1.0
    floor.inputs[1].default_value = 0.0
    links.new(img.outputs['Alpha'], high.inputs[0])
    for s, d in ((high, low), (low, power), (power, edge),
                 (edge, norm), (norm, mult), (mult, clamp), (clamp, floor)):
        links.new(s.outputs[0], d.inputs[0])
    links.new(floor.outputs[0], mix.inputs[0])
    strength = emit.inputs.get('Strength')
    if strength is None:
        raise RuntimeError('Ink emission has no Strength input')
    strength_link = next((l for l in links if l.to_node == emit and l.to_socket == strength), None)
    gain = _math(nodes, 'Emission Gain', 'MULTIPLY', (emit.location.x - 220, emit.location.y - 260))
    if strength_link:
        links.new(strength_link.from_socket, gain.inputs[0])
    else:
        gain.inputs[0].default_value = float(strength.default_value)
    links.new(gain.outputs[0], strength)


def _settings(context):
    props = context.scene.aef_ae_si_idle_ink_e344
    return policy.validated_parameters({key: tuple(getattr(props, key)) if key == 'tint' else getattr(props, key)
                                        for key in policy.PARAMS})


def _apply_to_tree(tree, params):
    params = policy.validated_parameters(params)
    def get(name):
        node = tree.nodes.get(NODE + name)
        if node is None:
            raise RuntimeError('A2 graph modified: ' + name)
        return node
    bright = get('Color Bright Contrast'); tint = get('Color Tint')
    power = get('Alpha Power'); edge = get('Edge Fade'); norm = get('Edge Normalize')
    mult = get('Alpha Multiplier'); gain = get('Emission Gain')
    for n in ('Input Max', 'Input Min', 'Output Max', 'Output Min'):
        get(n)
    bright.inputs['Bright'].default_value = params['brightness']
    bright.inputs['Contrast'].default_value = params['contrast']
    tint.inputs[2].default_value = (*params['tint'], 1.0)
    power.inputs[1].default_value = params['alpha_power']
    edge.inputs[1].default_value = params['edge_fade']
    norm.inputs[1].default_value = 1.0 - params['edge_fade']
    mult.inputs[1].default_value = params['alpha_multiplier']
    gain.inputs[1].default_value = params['emission_gain']
    return params


def _preflight(context):
    if not legacy._eligible_scene(context):
        raise RuntimeError('Verified AE profile required')
    objs = _objects(context.scene)
    if len(objs) != 7:
        raise RuntimeError('Exactly seven original Si vfxpart lod0 meshes required')
    for obj in objs:
        if obj.type != 'MESH' or _readonly(obj) or _readonly(obj.data) or obj.data.users != 1:
            raise RuntimeError('Unsupported linked/shared Si mesh: ' + obj.name)
        if obj.get(O_TOKEN, ''):
            raise RuntimeError('E3.4.4 already prepared; Restore first')
        mat = _material(obj)
        if _readonly(mat) or mat.get('AEF_V11_SourceMaterial', '') != 'DefaultHGMaterial':
            raise RuntimeError('Expected exact Si DefaultHGMaterial source')
        if obj.get(universal.O_TOKEN, ''):
            raise RuntimeError('Universal E3.4.3 comparison on Si mesh active')
    if len({m.as_pointer() for m in map(_material, objs)}) != 1:
        raise RuntimeError('Si idle VFX must use one shared A material')
    original = _material(objs[0])
    # Do not allow someone to use an already refined A2 as the new A.
    if original.get(M_REV, '') == REVISION or any(str(n.name).startswith(NODE) for n in original.node_tree.nodes):
        raise RuntimeError('Selected A is already an E3.4.4 preview')
    parent = any(obj.get(legacy.PROP_TOKEN, '') for obj in objs)
    if parent:
        previous, (parent_original, a, b) = legacy._session(context)
        if sorted(o.name for o in previous) != sorted(o.name for o in objs) or original is not a or any(obj.get(legacy.PROP_CURRENT) != 'A' for obj in objs):
            raise RuntimeError('First choose Show A in E3.4.1; B cannot be refined')
    elif not legacy._is_nested_mask_a(original):
        # E3.4.5.1: the main Si Build can produce the *same verified A graph*
        # without opening an E341 A/B parent session. Accept it only if its
        # exact per-object provenance/hash validation passes; never accept an
        # arbitrary material that merely happens to resemble an A shader.
        from . import ae_fx_auto_appearance as build_a
        auto_objs, _baseline, auto_material = build_a._verified_session(
            context, objs, mode='ACTIVE')
        if original is not auto_material or [o.name for o in auto_objs] != [o.name for o in objs]:
            raise RuntimeError('Si Build A provenance does not match seven VFX')
    _tree_choice(original)
    return objs, original, bool(parent)


def prepare(context):
    objs, a, parent = _preflight(context)
    token, stage, group_copy = uuid.uuid4().hex, None, None
    old_fake, tagged = bool(a.use_fake_user), []
    try:
        stage = a.copy()
        stage.name = 'SaberShader AE Si E344 | A2 Idle Ink'
        stage.use_fake_user = False
        for key in (legacy.MAT_REV, legacy.MAT_TOKEN, 'SaberShader_AE_FX_E331',
                    'SaberShader_AE_VFX_B_Revision', universal.M_VARIANT, universal.M_TOKEN):
            if key in stage:
                del stage[key]
        for key in tuple(stage.keys()):
            if str(key).startswith('SaberShader_AE_Si_BuildA_'):
                del stage[key]
        group, tree = _tree_choice(stage)
        if group is not None:
            group_copy = tree.copy()
            group_copy.name = 'SaberShader AE Si E344 | Private Ink Nodes | ' + token[:10]
            group_copy.use_fake_user = False
            group.node_tree = group_copy
            tree = group_copy
        _install_controls(tree)
        params = _apply_to_tree(tree, _settings(context))
        stage[M_TOKEN] = token
        stage[M_REV] = REVISION
        stage[M_TREE] = str(group_copy.name) if group_copy is not None else ''
        stage[M_TOPO] = _topology(tree)
        stage[PREFIX + 'Params'] = json.dumps(params, sort_keys=True)
        stage[PREFIX + 'Disclaimer'] = 'VISUAL_PRESET_EXPERIMENTAL_NOT_GAME_EXTRACTED'
        a.use_fake_user = True
        stage.use_fake_user = True
        digest = _graph_hash(a)
        for obj in objs:
            tagged.append(obj)
            obj[O_TOKEN] = token
            obj[O_A] = a.name
            obj[O_A2] = stage.name
            obj[O_CURRENT] = 'A'
            obj[O_FAKE] = int(old_fake)
            obj[O_HASH] = digest
            obj[O_PARENT] = int(parent)
    except Exception:
        for obj in tagged:
            for k in (O_TOKEN, O_A, O_A2, O_CURRENT, O_FAKE, O_HASH, O_PARENT):
                try:
                    if k in obj: del obj[k]
                except Exception: pass
        a.use_fake_user = old_fake
        if stage is not None:
            stage.use_fake_user = False
            if stage.users == 0:
                bpy.data.materials.remove(stage)
        if group_copy is not None and group_copy.users == 0:
            bpy.data.node_groups.remove(group_copy)
        raise
    return {'status': 'PREPARED_A', 'count': 7, 'mode': 'E341_A' if parent else 'NESTED_MASK_A',
            'original': a.name, 'A2': stage.name, 'preset': params}


def _session(context):
    objs = _objects(context.scene)
    if len(objs) != 7:
        raise RuntimeError('Seven Si vfxpart meshes required')
    token = {str(o.get(O_TOKEN, '')) for o in objs}
    if len(token) != 1 or not next(iter(token)):
        raise RuntimeError('No complete E3.4.4 session')
    token = next(iter(token))
    for key in (O_A, O_A2, O_FAKE, O_HASH, O_PARENT):
        if len({str(o.get(key, '')) for o in objs}) != 1:
            raise RuntimeError('E3.4.4 session metadata mismatch')
    a = bpy.data.materials.get(str(objs[0][O_A]))
    a2 = bpy.data.materials.get(str(objs[0][O_A2]))
    if a is None or a2 is None or a == a2:
        raise RuntimeError('Session material ID unavailable; recover from blend backup')
    if a2.get(M_TOKEN) != token or a2.get(M_REV) != REVISION or a2.get('AEF_V11_SourceMaterial') != 'DefaultHGMaterial':
        raise RuntimeError('A2 identity and provenance mismatch')
    if _graph_hash(a) != str(objs[0].get(O_HASH, '')):
        raise RuntimeError('Original A graph changed during comparison; refuse overwrite')
    # A2 no longer has direct gfx18 -> Emission/Mix links after controls: use
    # the private group ID recorded at prepare, never re-discover by raw links.
    private_name = str(a2.get(M_TREE, ''))
    if private_name:
        matches = [n for n in a2.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup'
                   and n.node_tree is not None and n.node_tree.name == private_name]
        if len(matches) != 1 or matches[0].node_tree.users != 1:
            raise RuntimeError('Private A2 node group replaced/shared')
        tree = matches[0].node_tree
    else:
        tree = a2.node_tree
    if _topology(tree) != str(a2.get(M_TOPO, '')):
        raise RuntimeError('A2 graph topology modified; refuse operations')
    if bool(int(objs[0].get(O_PARENT, 0))):
        if (any(o.get(legacy.PROP_CURRENT, '') != 'A' for o in objs) or
                any(o.get(legacy.PROP_A, '') != a.name for o in objs) or
                len({str(o.get(legacy.PROP_TOKEN, '')) for o in objs}) != 1 or
                not objs[0].get(legacy.PROP_TOKEN)):
            raise RuntimeError('Parent E3.4.1 session changed')
    for obj in objs:
        if (obj.type != 'MESH' or _readonly(obj) or _readonly(obj.data) or obj.data.users != 1 or
                _readonly(_material(obj)) or not any(_material(obj) is m for m in (a, a2))):
            raise RuntimeError('Si VFX assignment/mesh changed; no silent overwrite')
    # Any extra material user outside the tracked seven makes restore ambiguous.
    for obj in context.scene.objects:
        if obj not in objs and getattr(obj, 'type', '') == 'MESH':
            if any(m is a2 for m in (getattr(obj.data, 'materials', ()) or ())):
                raise RuntimeError('Untracked mesh uses A2; refuse unsafe restore')
    return objs, a, a2, tree


def show(context, variant):
    if variant not in ('A', 'A2'):
        raise ValueError('Expected A or A2')
    objs, a, a2, tree = _session(context)
    goal = a if variant == 'A' else a2
    before, mode = [], [str(o.get(O_CURRENT, '')) for o in objs]
    try:
        for obj in objs:
            before.append((obj, _material(obj)))
            obj.data.materials[0] = goal
        for obj in objs:
            obj[O_CURRENT] = variant
    except Exception:
        for obj, old in reversed(before):
            obj.data.materials[0] = old
        for obj, old in zip(objs, mode):
            obj[O_CURRENT] = old
        raise
    return {'status': 'ACTIVE_' + variant, 'material': goal.name, 'count': 7}


def apply(context):
    objs, a, a2, tree = _session(context)
    p = _settings(context)
    # All nodes and topology are prevalidated before touching controls.
    for name in ('Color Bright Contrast', 'Color Tint', 'Alpha Power', 'Edge Fade',
                 'Edge Normalize', 'Alpha Multiplier', 'Emission Gain',
                 'Input Max', 'Input Min', 'Output Max', 'Output Min'):
        if tree.nodes.get(NODE + name) is None:
            raise RuntimeError('A2 is missing node ' + name)
    _apply_to_tree(tree, p)
    a2[PREFIX + 'Params'] = json.dumps(p, sort_keys=True)
    return {'status': 'UPDATED_A2', 'params': p, 'count': 7}


def restore(context):
    objs, a, a2, tree = _session(context)
    old = []
    try:
        for obj in objs:
            old.append((obj, _material(obj)))
            obj.data.materials[0] = a
    except Exception:
        for obj, mat in reversed(old):
            obj.data.materials[0] = mat
        raise
    prev_fake = bool(int(objs[0].get(O_FAKE, 1)))
    for obj in objs:
        for k in (O_TOKEN, O_A, O_A2, O_CURRENT, O_FAKE, O_HASH, O_PARENT):
            if k in obj:
                del obj[k]
    group = None
    tree_name = str(a2.get(M_TREE, ''))
    if tree_name:
        group = bpy.data.node_groups.get(tree_name)
    if a2.use_fake_user:
        a2.use_fake_user = False
    if a2.users == 0:
        bpy.data.materials.remove(a2)
    if group is not None and group.users == 0 and not group.use_fake_user:
        bpy.data.node_groups.remove(group)
    if not prev_fake and not any(o.get(O_A, '') == a.name for o in bpy.data.objects):
        a.use_fake_user = False
    return {'status': 'RESTORED_A', 'material': a.name, 'count': 7}


def snapshot(context):
    objs, a, a2, tree = _session(context)
    return {'schema': 'SaberShader_AE_Si_IdleInk_AA2_E344',
            'revision': REVISION, 'read_only': True,
            'blender': '.'.join(map(str, bpy.app.version[:3])),
            'blend': str(bpy.data.filepath),
            'camera': context.scene.camera.name if context.scene.camera else '',
            'render_engine': context.scene.render.engine,
            'A': {'material': a.name, 'graph_sha256': _graph_hash(a)},
            'A2': {'material': a2.name, 'private_tree': str(a2.get(M_TREE, '')),
                   'topology_sha256': str(a2.get(M_TOPO, '')),
                   'parameters': json.loads(str(a2.get(PREFIX + 'Params', '{}')))},
            'parent_e341': bool(int(objs[0].get(O_PARENT, 0))),
            'objects': [{'name': obj.name, 'material': _material(obj).name,
                         'state': str(obj.get(O_CURRENT, ''))} for obj in objs]}


class AEF_PG_si_idle_ink_e344(bpy.types.PropertyGroup):
    alpha_power: bpy.props.FloatProperty(name='Alpha Power', default=PRESET['alpha_power'], min=0.35, max=3.0, precision=3)
    alpha_multiplier: bpy.props.FloatProperty(name='Alpha Multiplier', default=PRESET['alpha_multiplier'], min=0.0, max=2.0, precision=3)
    edge_fade: bpy.props.FloatProperty(name='Edge Fade', default=PRESET['edge_fade'], min=0.0, max=0.75, precision=3)
    brightness: bpy.props.FloatProperty(name='Brightness', default=PRESET['brightness'], min=-0.5, max=0.5, precision=3)
    contrast: bpy.props.FloatProperty(name='Contrast', default=PRESET['contrast'], min=-0.5, max=0.5, precision=3)
    tint: bpy.props.FloatVectorProperty(name='Carbon / Silver Tint', subtype='COLOR', size=3,
                                        min=0.0, max=2.0, default=PRESET['tint'], precision=3)
    emission_gain: bpy.props.FloatProperty(name='Emission Gain', default=PRESET['emission_gain'], min=0.0, max=3.0, precision=3)


class _Base(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    action = None
    def execute(self, context):
        try:
            result = self.action(context)
        except Exception as exc:
            self.report({'ERROR'}, 'Si ink preset: ' + str(exc)[:176])
            return {'CANCELLED'}
        self.report({'INFO'}, 'Si ink comparison ' + str(result.get('status', 'OK')) + ' — 7 Si idle VFX')
        return {'FINISHED'}


class AEF_OT_si_idle_ink_e344_prepare(_Base):
    bl_idname = 'sabershader.si_idle_ink_e344_prepare'
    bl_label = 'Prepare A/A2 Si Idle Ink'
    bl_description = 'Create a reversible ink comparison while preserving the original and its active VFX session'
    action = staticmethod(prepare)


class AEF_OT_si_idle_ink_e344_show_a(_Base):
    bl_idname = 'sabershader.si_idle_ink_e344_show_a'
    bl_label = 'Show Original A'
    action = staticmethod(lambda context: show(context, 'A'))


class AEF_OT_si_idle_ink_e344_show_a2(_Base):
    bl_idname = 'sabershader.si_idle_ink_e344_show_a2'
    bl_label = 'Show Refined A2'
    action = staticmethod(lambda context: show(context, 'A2'))


class AEF_OT_si_idle_ink_e344_apply(_Base):
    bl_idname = 'sabershader.si_idle_ink_e344_apply'
    bl_label = 'Apply Idle Ink Controls to A2'
    action = staticmethod(apply)


class AEF_OT_si_idle_ink_e344_restore(_Base):
    bl_idname = 'sabershader.si_idle_ink_e344_restore'
    bl_label = 'Restore Original A'
    action = staticmethod(restore)


class AEF_OT_si_idle_ink_e344_reset(_Base):
    bl_idname = 'sabershader.si_idle_ink_e344_reset'
    bl_label = 'Reset Si Idle Ink Preset Dials'
    def execute(self, context):
        try:
            p = context.scene.aef_ae_si_idle_ink_e344
            for k, v in PRESET.items(): setattr(p, k, v)
        except Exception as exc:
            self.report({'ERROR'}, 'Si ink preset controls: ' + str(exc)[:170]); return {'CANCELLED'}
        self.report({'INFO'}, 'Si ink slider defaults restored; click Apply to update A2')
        return {'FINISHED'}


class AEF_OT_si_idle_ink_e344_snapshot(bpy.types.Operator):
    bl_idname = 'sabershader.si_idle_ink_e344_snapshot'
    bl_label = 'Record Si Idle Ink A/A2 (Read Only)'
    bl_options = {'REGISTER'}
    def execute(self, context):
        try:
            data = snapshot(context)
            suffix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            path = Path(tempfile.gettempdir()) / ('SaberShader_Si_E344_AA2_' + suffix + '_' + uuid.uuid4().hex[:8] + '.json')
            with path.open('x', encoding='utf8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.report({'ERROR'}, 'Si ink comparison metadata: ' + str(exc)[:168]); return {'CANCELLED'}
        print('SABERSHADER SI IDLE INK E344 READ ONLY:', path)
        self.report({'INFO'}, 'E344 A/A2 JSON: ' + str(path)[:180])
        return {'FINISHED'}


class AEF_PT_si_idle_ink_e344(bpy.types.Panel):
    bl_label = 'Si Idle Ink Appearance Preset'
    bl_idname = 'AEF_PT_si_idle_ink_e344'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls, context):
        return ae_developer_tools_visible(context)

    def draw(self, context):
        layout = self.layout
        layout.label(text='Si-only visual preset; universal FX engine unchanged')
        layout.label(text='Use E341 Show A, native Mask A, or verified Build A')
        layout.operator('sabershader.si_idle_ink_e344_prepare', text='Prepare A / A2 (No Visual Change)', icon='DUPLICATE')
        row = layout.row(align=True)
        row.operator('sabershader.si_idle_ink_e344_show_a', text='Show A', icon='BACK')
        row.operator('sabershader.si_idle_ink_e344_show_a2', text='Show A2', icon='FORWARD')
        p = getattr(context.scene, 'aef_ae_si_idle_ink_e344', None)
        if p:
            col = layout.column(align=True)
            for key in policy.PARAMS: col.prop(p, key)
        layout.operator('sabershader.si_idle_ink_e344_apply', text='Apply Controls to A2', icon='SHADING_TEXTURE')
        layout.operator('sabershader.si_idle_ink_e344_reset', text='Reset Preset Dials', icon='LOOP_BACK')
        layout.operator('sabershader.si_idle_ink_e344_snapshot', text='Record A/A2 Metadata', icon='TEXT')
        layout.operator('sabershader.si_idle_ink_e344_restore', text='Restore Original A', icon='FILE_REFRESH')
        layout.label(text='Restore E344 before using E341 or main Build')
