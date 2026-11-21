"""E3.4.3: universal AE FX A/A2 fidelity comparison, explicit opt-in.

A is the exact current material datablock. A2 is a private copy of that node
shader, with bounded, neutral-by-default controls inserted *only* into its
source-authored active _MainTex color route and surface transparency route.
All source/actor identities are checked. No automatic assignment on Build.
No Unity shader equivalence is claimed. Blender 5.1.1 native QA required.
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

from . import ae_fx_universal_core as core
from . import ae_fx_universal as audit
from . import ae_fx_fidelity_core as policy

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = policy.REVISION
K = policy.KEY
O_TOKEN = K + 'Token'
O_ACTOR = K + 'Actor'
O_SLOT = K + 'Slot'
O_ORIG = K + 'Original'
O_A2 = K + 'A2'
O_CURRENT = K + 'Current'
O_FAKE = K + 'OriginalFakeUser'
M_TOKEN = K + 'MaterialToken'
M_VARIANT = K + 'Variant'
M_ACTOR = K + 'ActorOnMaterial'
M_SOURCE = K + 'SourceMaterial'
NODE = 'SaberShader AE E343 | '


def _readonly(obj):
    return bool(getattr(obj, 'library', None) or getattr(obj, 'override_library', None))


def has_active_comparison(objects):
    """Build fails closed even when a session is only partially tagged."""
    return any(bool(getattr(o, 'get', lambda *a: '')(O_TOKEN, ''))
               for o in (objects or ()) if getattr(o, 'type', '') == 'MESH')


def _slot_material(obj, index):
    mats = getattr(getattr(obj, 'data', None), 'materials', None)
    if mats is None or not 0 <= index < len(mats) or mats[index] is None:
        raise RuntimeError('%s: material slot missing' % obj.name)
    return mats[index]


def _main_path(entry):
    return Path(entry['texture_slots']['_MainTex']['path'])


def _file_identity(img, path):
    """Match full filesystem path, never names of Non-Color copies or fuzzy IDs."""
    try:
        candidate = Path(bpy.path.abspath(img.filepath, library=img.library)).resolve(strict=False)
        return candidate == path.resolve(strict=False)
    except (ValueError, OSError, AttributeError):
        return False


def _node_key(node):
    return node.as_pointer() if hasattr(node, 'as_pointer') else id(node)


def _is_connected_to_output(tree, node):
    """Conservative top-level graph reachability; no nested-group mutation."""
    seen, todo = set(), [node]
    for _ in range(512):
        if not todo:
            return False
        cur = todo.pop()
        identity = _node_key(cur)
        if identity in seen:
            continue
        seen.add(identity)
        if getattr(cur, 'bl_idname', '') == 'ShaderNodeOutputMaterial' and getattr(cur, 'is_active_output', True):
            return True
        todo.extend(l.to_node for l in tree.links if l.from_node == cur)
    return False


def _reaches(tree, node, target):
    seen, todo = set(), [node]
    for _ in range(512):
        if not todo:
            return False
        current = todo.pop()
        if current == target:
            return True
        if _node_key(current) in seen:
            continue
        seen.add(_node_key(current))
        todo.extend(l.to_node for l in tree.links if l.from_node == current)
    return False


def _transparency_mix(tree):
    """Only a mix with one Transparent BSDF and a linked factor, output-reachable."""
    choices = []
    for n in tree.nodes:
        if getattr(n, 'bl_idname', '') != 'ShaderNodeMixShader':
            continue
        transparent = any(l.to_node == n and l.to_socket in (n.inputs[1], n.inputs[2])
                          and getattr(l.from_node, 'bl_idname', '') == 'ShaderNodeBsdfTransparent'
                          for l in tree.links)
        factor = [l for l in tree.links if l.to_node == n and l.to_socket == n.inputs[0]]
        if transparent and len(factor) == 1 and _is_connected_to_output(tree, n):
            choices.append((n, factor[0]))
    if len(choices) != 1:
        raise RuntimeError('Expected one provable surface transparency mix (found %d); preserve original' % len(choices))
    return choices[0]


def _color_targets(tree, source):
    # Do not tint grayscale density/alpha branches. Require an actual downstream
    # Emission/Base Color path, and refuse any branch reused for transparency.
    emissions = [n for n in tree.nodes if getattr(n, 'bl_idname', '') in
                 ('ShaderNodeEmission', 'ShaderNodeBsdfPrincipled')]
    alpha_mix, factor_link = _transparency_mix(tree)
    accepted = []
    for l in list(tree.links):
        if l.from_node != source or l.from_socket != source.outputs['Color']:
            continue
        color_path = any(_reaches(tree, l.to_node, e) for e in emissions)
        opacity_path = _reaches(tree, l.to_node, factor_link.from_node)
        if color_path and not opacity_path:
            accepted.append(l)
    return accepted


def _source_node(tree, image_path):
    matches = [n for n in tree.nodes
               if getattr(n, 'bl_idname', '') == 'ShaderNodeTexImage'
               and getattr(n, 'image', None) is not None
               and _file_identity(n.image, image_path)
               and _is_connected_to_output(tree, n)]
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one output-connected top-level _MainTex node (found %d)' % len(matches))
    return matches[0]


def _preflight(context):
    actor, objects = audit._manual_scope(context)
    audit._ae_authorized(context, actor)
    active = context.active_object
    if active is None or active.type != 'MESH' or core.actor_id(active.name) != actor:
        raise RuntimeError('Select an AE FX MESH (not just armature) as active object')
    if any(o.get(O_TOKEN, '') for o in objects):
        raise RuntimeError('E3.4.3 session already active for this actor; restore first')
    from . import ae_fx_comparison as oldab
    if oldab.has_active_comparison(objects):
        raise RuntimeError('Legacy Si E3.4.1 A/B active; restore it before E3.4.3')
    idx = int(getattr(active, 'active_material_index', 0))
    original = _slot_material(active, idx)
    if _readonly(original) or not original.use_nodes or not original.node_tree:
        raise RuntimeError('Active material must be local and node-based')
    if original.get(M_VARIANT, '') == REVISION or any(
            str(n.name).startswith(NODE) for n in original.node_tree.nodes):
        raise RuntimeError('Selected material already contains E3.4.3 preview nodes; choose an untouched FX source')
    if any(str(o.get(O_ORIG, '')) == original.name and o.get(O_TOKEN, '')
           for o in context.scene.objects):
        raise RuntimeError('This original material already has an active A/A2 session; restore it first')
    source, proof = core.source_name(original.name, original.get('AEF_V11_SourceMaterial', ''))
    if proof not in ('SOURCE_PROPERTY', 'EXACT_UNITY_MATERIAL_NAME'):
        raise RuntimeError('Missing exact original source material identity')
    source_actor = core.source_owner(source)
    if source_actor and source_actor != actor:
        raise RuntimeError('Source material actor does not match selected actor')
    # Recognize actor-prefixed M_fx_<actor> names without treating a generic
    # M_fx_<effect_family> shader as another actor.
    in_scene_actors = {core.actor_id(o.name) for o in context.scene.objects}
    for other in in_scene_actors - {'', actor}:
        if source.casefold().startswith('m_fx_' + other + '_'):
            raise RuntimeError('Cross-actor FX source identity refused')
    entry = core.source_inventory(source, audit._source_folder(context), object_name=active.name)
    entry['source_owner'] = source_actor
    if not policy.authoritative_textured_row(entry, actor):
        raise RuntimeError('Exact authored _MainTex JSON + image required; procedural and DefaultHGMaterial excluded')
    path = _main_path(entry)
    source_node = _source_node(original.node_tree, path)
    _transparency_mix(original.node_tree)
    # Require a usable main texture color branch to preserve its original
    # artistic intent; alpha route may use mask/greyscale, never guessed.
    if not _color_targets(original.node_tree, source_node):
        raise RuntimeError('No independent _MainTex color path; cannot safely insert universal color controls')
    targets = []
    for obj in objects:
        for n, mat in enumerate(getattr(obj.data, 'materials', ()) or ()):
            if mat == original:
                if _readonly(obj) or _readonly(obj.data) or getattr(obj.data, 'users', 1) != 1:
                    raise RuntimeError('Material user %s has linked/shared mesh; cannot isolate actor' % obj.name)
                targets.append((obj, n))
    if not targets or len(targets) > 256:
        raise RuntimeError('Empty/oversized material target set')
    if len({_node_key(obj) for obj, n in targets}) != len(targets):
        raise RuntimeError('One material in multiple slots on one mesh is not supported')
    return actor, source, original, entry, targets


def _math(nodes, operation, name, location):
    n = nodes.new('ShaderNodeMath')
    n.name = NODE + name
    n.label = 'E3.4.3 ' + name
    n.operation = operation
    n.location = location
    return n


def _safe_replace_links(tree, links, replacement):
    for l in links:
        tree.links.new(replacement, l.to_socket)


def _build_controls(stage, path):
    tree = stage.node_tree
    main = _source_node(tree, path)
    mix, factor = _transparency_mix(tree)
    color_links = _color_targets(tree, main)
    if not color_links:
        raise RuntimeError('No independent tintable color branch on A2')
    nodes = tree.nodes
    # Apply color and contrast to the *visually rendered* texture color only.
    # Never change original image datablocks, colorspace, or alpha source.
    bright = nodes.new('ShaderNodeBrightContrast')
    bright.name = NODE + 'Color Bright Contrast'; bright.location = (main.location.x + 240, main.location.y + 180)
    tint = nodes.new('ShaderNodeMixRGB')
    tint.name = NODE + 'Color Tint'; tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = 1.0
    tint.location = (main.location.x + 470, main.location.y + 180)
    tree.links.new(main.outputs['Color'], bright.inputs['Color'])
    tree.links.new(bright.outputs['Color'], tint.inputs[1])
    _safe_replace_links(tree, color_links, tint.outputs['Color'])
    # Use the pre-existing *authored opacity* mix factor, not MainTex Alpha:
    # some real AE FX use grayscale density × _MaskTex instead of PNG alpha.
    x, y = mix.location.x - 650, mix.location.y - 250
    prehigh = _math(nodes, 'MINIMUM', 'Alpha Input Clamp High', (x - 380, y))
    prelow = _math(nodes, 'MAXIMUM', 'Alpha Input Clamp Low', (x - 190, y))
    prehigh.inputs[1].default_value = 1.0
    prelow.inputs[1].default_value = 0.0
    power = _math(nodes, 'POWER', 'Alpha Power', (x, y))
    edge = _math(nodes, 'SUBTRACT', 'Alpha Edge Threshold', (x + 190, y))
    normalize = _math(nodes, 'DIVIDE', 'Alpha Fade Normalize', (x + 380, y))
    multiplier = _math(nodes, 'MULTIPLY', 'Alpha Multiplier', (x + 570, y))
    clamp = _math(nodes, 'MINIMUM', 'Alpha Clamp High', (x + 760, y))
    floor = _math(nodes, 'MAXIMUM', 'Alpha Clamp Low', (x + 950, y))
    power.inputs[1].default_value = 1.0
    edge.inputs[1].default_value = 0.0
    normalize.inputs[1].default_value = 1.0
    multiplier.inputs[1].default_value = 1.0
    clamp.inputs[1].default_value = 1.0
    floor.inputs[1].default_value = 0.0
    tree.links.new(factor.from_socket, prehigh.inputs[0])
    tree.links.new(prehigh.outputs[0], prelow.inputs[0])
    tree.links.new(prelow.outputs[0], power.inputs[0])
    tree.links.new(power.outputs[0], edge.inputs[0])
    tree.links.new(edge.outputs[0], normalize.inputs[0])
    tree.links.new(normalize.outputs[0], multiplier.inputs[0])
    tree.links.new(multiplier.outputs[0], clamp.inputs[0])
    tree.links.new(clamp.outputs[0], floor.inputs[0])
    tree.links.new(floor.outputs[0], mix.inputs[0])
    # Emission control on each top-level Emission node contributing to output.
    em_names = []
    for n in list(nodes):
        if n.bl_idname != 'ShaderNodeEmission' or not _is_connected_to_output(tree, n):
            continue
        strength = n.inputs.get('Strength')
        if strength is None:
            continue
        old = next((l for l in tree.links if l.to_node == n and l.to_socket == strength), None)
        m = _math(nodes, 'MULTIPLY', 'Emission Gain ' + str(len(em_names)),
                  (n.location.x - 230, n.location.y - 250))
        if old:
            tree.links.new(old.from_socket, m.inputs[0])
        else:
            m.inputs[0].default_value = float(strength.default_value)
        m.inputs[1].default_value = 1.0
        tree.links.new(m.outputs[0], strength)
        em_names.append(m.name)
    stage[K + 'EmissionNodes'] = json.dumps(em_names)
    stage[K + 'SupportsEmission'] = bool(em_names)
    return {'color_routes': len(color_links), 'emission_nodes': len(em_names)}


def _settings(context):
    props = context.scene.aef_ae_universal_fx_e343
    return policy.validated_parameters({key: tuple(getattr(props, key)) if key == 'tint' else getattr(props, key)
                                        for key in policy.PARAMS})


def _set_params(stage, params):
    params = policy.validated_parameters(params)
    nodes = stage.node_tree.nodes
    def req(name):
        n = nodes.get(NODE + name)
        if n is None:
            raise RuntimeError('A2 control graph modified: missing %s' % name)
        return n
    # Two-phase update: first resolve all nodes, then modify only explicit sockets.
    bright = req('Color Bright Contrast'); tint = req('Color Tint')
    power = req('Alpha Power'); edge = req('Alpha Edge Threshold')
    normal = req('Alpha Fade Normalize'); mult = req('Alpha Multiplier')
    req('Alpha Clamp High'); req('Alpha Clamp Low')
    req('Alpha Input Clamp High'); req('Alpha Input Clamp Low')
    em_names = json.loads(str(stage.get(K + 'EmissionNodes', '[]')))
    emission = []
    for name in em_names:
        n = nodes.get(name)
        if n is None:
            raise RuntimeError('A2 emission graph modified')
        emission.append(n)
    bright.inputs['Bright'].default_value = params['brightness']
    bright.inputs['Contrast'].default_value = params['contrast']
    tint.inputs[2].default_value = (*params['tint'], 1.0)
    power.inputs[1].default_value = params['alpha_power']
    edge.inputs[1].default_value = params['edge_fade']
    normal.inputs[1].default_value = 1.0 - params['edge_fade']
    mult.inputs[1].default_value = params['alpha_multiplier']
    for n in emission:
        n.inputs[1].default_value = params['emission_gain']
    stage[K + 'Parameters'] = json.dumps(params, sort_keys=True)
    return params


def _get_active_session(context):
    active = getattr(context, 'active_object', None)
    if active is None or active.type != 'MESH' or not active.get(O_TOKEN, ''):
        raise RuntimeError('Select a mesh participating in an E3.4.3 session')
    actor = str(active.get(O_ACTOR, ''))
    if core.actor_id(active.name) != actor:
        raise RuntimeError('Active object actor identity mismatch')
    token = str(active.get(O_TOKEN, ''))
    orig_name = str(active.get(O_ORIG, ''))
    a2_name = str(active.get(O_A2, ''))
    if not token or not orig_name or not a2_name or orig_name == a2_name:
        raise RuntimeError('Session data incomplete')
    a = bpy.data.materials.get(orig_name)
    a2 = bpy.data.materials.get(a2_name)
    if a is None or a2 is None or a2 == a:
        raise RuntimeError('A/A2 materials missing: restore from .blend backup')
    if (a2.get(M_TOKEN) != token or a2.get(M_VARIANT) != REVISION or
            a2.get(M_ACTOR) != actor or a2.get(M_SOURCE) != core.source_name(a.name, a.get('AEF_V11_SourceMaterial', ''))[0]):
        raise RuntimeError('A2 provenance markers have changed')
    pairs = []
    for obj in context.scene.objects:
        if obj.get(O_TOKEN, '') != token:
            continue
        if (obj.get(O_ACTOR, '') != actor or core.actor_id(obj.name) != actor or
                obj.get(O_ORIG, '') != orig_name or obj.get(O_A2, '') != a2_name or
                _readonly(obj) or _readonly(obj.data) or getattr(obj.data, 'users', 1) != 1):
            raise RuntimeError('Session actor/material identity changed')
        n = int(obj.get(O_SLOT, -1))
        assigned = _slot_material(obj, n)
        if assigned != a and assigned != a2:
            raise RuntimeError('Session mesh manually reassigned: refuse overwrite')
        pairs.append((obj, n))
    if not pairs or not any(obj == active for obj, n in pairs):
        raise RuntimeError('Session targets missing or active object not in session')
    # Detect deleted tags on a target while it still uses A/A2. False positives
    # on other actors sharing original material are avoided via actor filter.
    for obj in context.scene.objects:
        if getattr(obj, 'type', '') != 'MESH' or core.actor_id(obj.name) != actor:
            continue
        for mat in (getattr(getattr(obj, 'data', None), 'materials', ()) or ()):
            if mat == a2 and obj.get(O_TOKEN, '') != token:
                raise RuntimeError('Untracked actor mesh uses A2; refusing partial restore')
    return actor, a, a2, pairs, token


def prepare(context):
    actor, source, original, entry, pairs = _preflight(context)
    token = uuid.uuid4().hex
    stage = None
    old_fake = bool(original.use_fake_user)
    tagged = []
    try:
        stage = original.copy()
        stage.name = 'SaberShader AE E343 | %s | A2' % actor
        stage.use_fake_user = False
        # The new preview must not impersonate legacy E3 or E3.3.1 stages.
        for k in ('SaberShader_AE_FX_E3', 'SaberShader_AE_FX_E331',
                  'SaberShader_AE_VFX_B_Revision', 'SaberShader_AE_FX_E331_Kind'):
            if k in stage:
                del stage[k]
        controls = _build_controls(stage, _main_path(entry))
        params = _set_params(stage, _settings(context))
        stage[M_TOKEN] = token
        stage[M_VARIANT] = REVISION
        stage[M_ACTOR] = actor
        stage[M_SOURCE] = source
        stage[K + 'Disclaimer'] = 'A2_EXPERIMENTAL_PREVIEW_NOT_UNITY_SHADER_EQUIVALENCE'
        original.use_fake_user = True
        stage.use_fake_user = True
        for obj, slot in pairs:
            tagged.append(obj)
            obj[O_TOKEN] = token
            obj[O_ACTOR] = actor
            obj[O_SLOT] = int(slot)
            obj[O_ORIG] = original.name
            obj[O_A2] = stage.name
            obj[O_CURRENT] = 'A'
            obj[O_FAKE] = int(old_fake)
    except Exception:
        for obj in tagged:
            for key in (O_TOKEN, O_ACTOR, O_SLOT, O_ORIG, O_A2, O_CURRENT, O_FAKE):
                try:
                    if key in obj: del obj[key]
                except Exception:
                    pass
        original.use_fake_user = old_fake
        if stage is not None:
            try:
                stage.use_fake_user = False
                if not stage.users:
                    bpy.data.materials.remove(stage)
            except Exception:
                pass
        raise
    return {'status': 'PREPARED_A', 'actor': actor, 'source': source,
            'targets': len(pairs), 'A': original.name, 'A2': stage.name,
            'controls': params, **controls}


def show(context, variant):
    if variant not in ('A', 'A2'):
        raise ValueError('Expected A or A2')
    actor, a, a2, pairs, token = _get_active_session(context)
    mat = a if variant == 'A' else a2
    changes = []
    old_modes = [(obj, str(obj.get(O_CURRENT, ''))) for obj, slot in pairs]
    try:
        for obj, slot in pairs:
            old = _slot_material(obj, slot)
            if old != mat:
                obj.data.materials[slot] = mat
                changes.append((obj, slot, old))
        for obj, _ in pairs:
            obj[O_CURRENT] = variant
    except Exception:
        for obj, old_mode in old_modes:
            try: obj[O_CURRENT] = old_mode
            except Exception: pass
        for obj, slot, old in reversed(changes):
            obj.data.materials[slot] = old
        raise
    return {'status': 'SHOW_' + variant, 'actor': actor, 'targets': len(pairs), 'material': mat.name}


def apply_controls(context):
    actor, a, a2, pairs, token = _get_active_session(context)
    # Snapshot only fixed control sockets so that an unexpected write error can
    # revert every edited value, without resetting any shared node groups.
    params = _settings(context)
    previous = json.loads(str(a2.get(K + 'Parameters', '')))
    previous = policy.validated_parameters(previous)
    try:
        _set_params(a2, params)
    except Exception:
        _set_params(a2, previous)
        raise
    return {'status': 'UPDATED_A2', 'actor': actor, 'targets': len(pairs), 'params': params,
            'emission_supported': bool(a2.get(K + 'SupportsEmission', False))}


def restore(context):
    actor, a, a2, pairs, token = _get_active_session(context)
    changes = []
    try:
        for obj, slot in pairs:
            old = _slot_material(obj, slot)
            if old != a:
                obj.data.materials[slot] = a
                changes.append((obj, slot, old))
    except Exception:
        for obj, slot, old in reversed(changes):
            obj.data.materials[slot] = old
        raise
    old_fake = bool(pairs[0][0].get(O_FAKE, 1))
    for obj, slot in pairs:
        for key in (O_TOKEN, O_ACTOR, O_SLOT, O_ORIG, O_A2, O_CURRENT, O_FAKE):
            if key in obj:
                del obj[key]
    # Never destroy A2 if someone references it externally. Remove the staged
    # preview only when positively identified and completely unused.
    a2.use_fake_user = False
    removed = False
    if a2.users == 0:
        bpy.data.materials.remove(a2)
        removed = True
    if not old_fake and not any(o.get(O_ORIG, '') == a.name for o in bpy.data.objects):
        a.use_fake_user = False
    return {'status': 'RESTORED_A', 'actor': actor, 'targets': len(pairs),
            'exact_material': a.name, 'a2_removed': removed}


def _graph_signature(mat):
    """Read-only, reproducible top-level graph record for A/A2 comparisons."""
    tree = mat.node_tree
    if tree is None:
        return {'nodes': 0, 'links': 0, 'fingerprint': '', 'image_paths': []}
    nodes, images, links = [], [], []
    for n in tree.nodes:
        image = getattr(n, 'image', None)
        image_path = str(getattr(image, 'filepath', '') or '')
        if image is not None:
            images.append(image_path)
        nodes.append((n.name, n.bl_idname, image_path))
    for link in tree.links:
        links.append((link.from_node.name, link.from_socket.name,
                      link.to_node.name, link.to_socket.name))
    data = {'nodes': sorted(nodes), 'links': sorted(links)}
    sha = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    return {'nodes': len(nodes), 'links': len(links), 'fingerprint': sha,
            'image_paths': sorted(set(images))}


def snapshot(context):
    actor, a, a2, pairs, token = _get_active_session(context)
    scene = context.scene
    return {'schema': policy.SCHEMA, 'revision': REVISION, 'read_only': True,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'blender': '.'.join(map(str, bpy.app.version[:3])),
            'blend': str(bpy.data.filepath), 'actor': actor,
            'source_material': str(a2.get(M_SOURCE, '')),
            'original': a.name, 'A2': a2.name,
            'A_graph': _graph_signature(a), 'A2_graph': _graph_signature(a2),
            'scene': {'render_engine': str(getattr(getattr(scene,'render',None),'engine','')),
                      'camera': str(getattr(getattr(scene,'camera',None),'name','')),
                      'frame_current': int(getattr(scene,'frame_current',0))},
            'parameters': json.loads(str(a2.get(K + 'Parameters', '{}'))),
            'emission_supported': bool(a2.get(K + 'SupportsEmission', False)),
            'objects': [{'name': obj.name, 'slot': slot, 'active': _slot_material(obj, slot).name}
                        for obj, slot in pairs],
            'note': 'Experimental Blender preview. No claims of Unity VFX equivalence.'}


def _export(data):
    path = Path(tempfile.gettempdir()) / ('SaberShader_AE_FX_E343_' +
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8] + '.json')
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(path)


class AEF_PG_ae_fx_fidelity_e343(bpy.types.PropertyGroup):
    alpha_power: bpy.props.FloatProperty(name='Alpha Power', default=1.0, min=0.35, max=3.0, precision=3)
    alpha_multiplier: bpy.props.FloatProperty(name='Alpha Multiplier', default=1.0, min=0.0, max=2.0, precision=3)
    edge_fade: bpy.props.FloatProperty(name='Edge Fade', default=0.0, min=0.0, max=0.75, precision=3)
    brightness: bpy.props.FloatProperty(name='Brightness', default=0.0, min=-0.5, max=0.5, precision=3)
    contrast: bpy.props.FloatProperty(name='Contrast', default=0.0, min=-0.5, max=0.5, precision=3)
    tint: bpy.props.FloatVectorProperty(name='Color Tint', subtype='COLOR', size=3,
                                          min=0.0, max=2.0, default=(1.0, 1.0, 1.0), precision=3)
    emission_gain: bpy.props.FloatProperty(name='Emission Gain', default=1.0, min=0.0, max=3.0, precision=3)


class AEF_OT_ae_fx_e343_prepare(bpy.types.Operator):
    bl_idname='sabershader.ae_fx_e343_prepare'; bl_label='Prepare A/A2 for Selected FX'
    bl_description='Preserve exact current FX as A, stage experimental A2 without changing visible material'
    bl_options={'REGISTER','UNDO'}
    def execute(self, context):
        try: r=prepare(context)
        except Exception as exc:
            self.report({'ERROR'},'E343 refused: '+str(exc)[:175]);return {'CANCELLED'}
        self.report({'INFO'},'A/A2 prepared: '+r['source']+' (%d slots)' % r['targets']);return {'FINISHED'}


class AEF_OT_ae_fx_e343_show_a(bpy.types.Operator):
    bl_idname='sabershader.ae_fx_e343_show_a';bl_label='Show A — Original'
    bl_options={'REGISTER','UNDO'}
    def execute(self, context):
        try: r=show(context,'A')
        except Exception as exc:
            self.report({'ERROR'},'E343 A: '+str(exc)[:175]);return {'CANCELLED'}
        self.report({'INFO'},'Original A active (%d slots)'%r['targets']);return {'FINISHED'}


class AEF_OT_ae_fx_e343_show_a2(bpy.types.Operator):
    bl_idname='sabershader.ae_fx_e343_show_a2';bl_label='Show A2 — Refined'
    bl_options={'REGISTER','UNDO'}
    def execute(self, context):
        try: r=show(context,'A2')
        except Exception as exc:
            self.report({'ERROR'},'E343 A2: '+str(exc)[:175]);return {'CANCELLED'}
        self.report({'INFO'},'Experimental A2 active (%d slots)'%r['targets']);return {'FINISHED'}


class AEF_OT_ae_fx_e343_apply(bpy.types.Operator):
    bl_idname='sabershader.ae_fx_e343_apply';bl_label='Apply Controls to A2'
    bl_description='Update only staged A2 control values; never touch original A'
    bl_options={'REGISTER','UNDO'}
    def execute(self, context):
        try: r=apply_controls(context)
        except Exception as exc:
            self.report({'ERROR'},'E343 controls: '+str(exc)[:175]);return {'CANCELLED'}
        self.report({'INFO'},'A2 controls updated, A untouched');return {'FINISHED'}


class AEF_OT_ae_fx_e343_restore(bpy.types.Operator):
    bl_idname='sabershader.ae_fx_e343_restore';bl_label='Restore Original FX (A/A2)'
    bl_description='Reassign the exact original material ID and clear E343 session safely'
    bl_options={'REGISTER','UNDO'}
    def execute(self, context):
        try: r=restore(context)
        except Exception as exc:
            self.report({'ERROR'},'E343 restore: '+str(exc)[:175]);return {'CANCELLED'}
        self.report({'INFO'},'Original material restored on %d slots'%r['targets']);return {'FINISHED'}


class AEF_OT_ae_fx_e343_snapshot(bpy.types.Operator):
    bl_idname='sabershader.ae_fx_e343_snapshot';bl_label='A/A2 Metadata (Read Only)'
    bl_options={'REGISTER'}
    def execute(self, context):
        try: path=_export(snapshot(context))
        except Exception as exc:
            self.report({'ERROR'},'E343 snapshot: '+str(exc)[:175]);return {'CANCELLED'}
        print('SABERSHADER AE UNIVERSAL FX E343 A/A2 JSON:',path)
        self.report({'INFO'},'E343 metadata JSON: '+path[:175]);return {'FINISHED'}


class AEF_PT_ae_fx_e343(bpy.types.Panel):
    bl_label='Universal FX Fidelity Comparison'
    bl_idname='AEF_PT_ae_fx_e343'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='SaberShader'
    bl_parent_id='AEF_PT_ui121_endfield'
    bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls, context):
        return ae_developer_tools_visible(context)

    def draw(self, context):
        layout=self.layout
        layout.label(text='Experimental: source-authorized textured FX',icon='SHADING_TEXTURE')
        layout.label(text='Active mesh + authored _MainTex; source JSON required')
        layout.operator('sabershader.ae_fx_e343_prepare',text='Prepare A / A2 (No Visual Change)',icon='DUPLICATE')
        row=layout.row(align=True)
        row.operator('sabershader.ae_fx_e343_show_a',text='Show A',icon='BACK')
        row.operator('sabershader.ae_fx_e343_show_a2',text='Show A2',icon='FORWARD')
        p=getattr(context.scene,'aef_ae_universal_fx_e343',None)
        if p is not None:
            col=layout.column(align=True)
            for field in policy.PARAMS:
                col.prop(p,field)
        layout.operator('sabershader.ae_fx_e343_apply',text='Apply Controls to A2',icon='SHADING_TEXTURE')
        layout.operator('sabershader.ae_fx_e343_snapshot',text='Record A/A2 Metadata',icon='TEXT')
        layout.operator('sabershader.ae_fx_e343_restore',text='Restore Original FX',icon='LOOP_BACK')
        layout.label(text='No auto-build changes; restore before Build')
        layout.label(text='Placeholder/procedural FX excluded until verified')
