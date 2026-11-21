"""SaberShader 1.0.4 — AE Si FX Look Matching E3.3.1.

Experimental static look matching, not a reproduction of Unity shader equations.
Unlike legacy E3.3, stages copies of source FX materials, validates them,
then swaps slots as one operation. Original E3/E3.2 previews remain intact.
"""
from __future__ import annotations

import math
import re

import bpy

from . import ae_fx_ink_sources as e3
from . import ae_fx_opacity as e31
from . import ae_vfx_placeholders as e32

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = 'AE_SI_FX_E331_LOOK_MATCH_1'
MARKER = 'SaberShader_AE_FX_E331'
ORIGINAL_KEY = 'SaberShader_AE_FX_E331_Original'
ORIGINAL_FAKE_KEY = 'SaberShader_AE_FX_E331_OriginalFakeUser'
KIND_KEY = 'SaberShader_AE_FX_E331_Kind'
LEGACY_E33_MARKER = 'SaberShader_AE_FX_E33'
LEGACY_E33_REVISION = 'AE_SI_FX_E33_LOOK_MATCH_1'
LEGACY_BACKUP_KEY = 'SaberShader_AE_FX_E33_Backup'

# Absolute final preview settings. They do NOT multiply the E3.1 opacity.
# Artistic targets, NOT extracted opacity/emission values from Unity.
TARGETS = {
    'M_fx_jsspsi_cloth_04_01': {'opacity': 0.075, 'emission': 0.55, 'tint': (0.96, 1.0, 0.98), 'blend': 0.23},
    'M_fx_jsspsi_cloth_05': {'opacity': 0.050, 'emission': 0.48, 'tint': (0.96, 1.0, 0.97), 'blend': 0.22},
    'M_fx_jsspsi_cloth_06_01': {'opacity': 0.270, 'emission': 0.52, 'tint': (0.95, 1.0, 0.98), 'blend': 0.25},
    'M_fx_actor_jsspsi_cloth_08_01': {'opacity': 0.265, 'emission': 0.50, 'tint': (0.94, 1.0, 0.99), 'blend': 0.23},
    'M_fx_jsspsi_cloth_06_02': {'opacity': 0.250, 'emission': 0.48, 'tint': (0.95, 1.0, 0.97), 'blend': 0.22},
}
# Existing E3.3 legacy look values, needed only to reject edited materials
# during migration; no new construction uses these values.
_LEGACY = {
    'M_fx_jsspsi_cloth_04_01': (0.82, 0.32, (0.95, 0.99, 0.98), 0.22),
    'M_fx_jsspsi_cloth_05': (0.78, 0.22, (0.94, 0.98, 0.97), 0.18),
    'M_fx_jsspsi_cloth_06_01': (0.72, 0.38, (0.93, 0.98, 0.96), 0.24),
    'M_fx_actor_jsspsi_cloth_08_01': (0.70, 0.34, (0.92, 0.97, 0.96), 0.22),
    'M_fx_jsspsi_cloth_06_02': (0.68, 0.30, (0.92, 0.97, 0.95), 0.20),
}
VFX_B_KEY = 'SaberShader_AE_VFX_B_Revision'
VFX_B_REVISION = 'E332_DUAL_LAYER_DISTORTION_1'
VFX_RE = re.compile(r'^S_actor_jsspsi_vfxpart_0[1-7]_lod0(?:\.\d{3})?$', re.I)


def _source(mat):
    return str(mat.get('AEF_V11_SourceMaterial', '') or '')


def _material_id(mat):
    return mat.as_pointer() if hasattr(mat, 'as_pointer') else id(mat)


def _readonly(x):
    return bool(getattr(x, 'library', None) or getattr(x, 'override_library', None))


def _valid_mesh(obj):
    return (getattr(obj, 'type', None) == 'MESH' and
            'jsspsi' in str(getattr(obj, 'name', '')).casefold() and
            getattr(obj, 'data', None) is not None)


def _close(a, b):
    return math.isclose(float(a), float(b), abs_tol=1e-5, rel_tol=1e-4)


def _nodes(mat):
    tree = getattr(mat, 'node_tree', None)
    return tree.nodes if tree is not None else None


def _ink_nodes(mat):
    nodes = _nodes(mat)
    if nodes is None:
        return None
    emission = nodes.get(e3.NODE_PREFIX + 'Ink emission')
    opacity = nodes.get(e3.NODE_PREFIX + 'User opacity / preview')
    tint = nodes.get(e3.NODE_PREFIX + 'Source-tinted main')
    blend = nodes.get(e3.NODE_PREFIX + 'Blend texture (estimated)')
    if any(n is None for n in (emission, opacity, tint)):
        return None
    return (emission, opacity, tint, blend)


def _expected_ink_opacity(mat, src):
    """Expected untouched E3 / E3.1 / legacy E3.3 opacity."""
    if mat.get(LEGACY_E33_MARKER) == LEGACY_E33_REVISION:
        backup = mat.get(LEGACY_BACKUP_KEY)
        if backup is None or 'opacity' not in backup:
            return None
        try:
            return float(backup['opacity']) * _LEGACY[src][0]
        except (ValueError, TypeError, KeyError):
            return None
    if mat.get(e31.CALIBRATION_KEY) == e31.REVISION:
        previous = mat.get(e31.PREVIOUS_KEY)
        try:
            return float(previous) * e31.PREVIEW_FACTOR
        except (ValueError, TypeError):
            return None
    # No E3.1 calibration: only canonical E3 value is accepted.
    try:
        from . import ae_material_sources as catalog
        entry = catalog._source_catalog()['materials'][src]
        return e31.legacy_e3_opacity(entry)
    except (KeyError, TypeError, ValueError):
        return None


def _eligible_ink(mat):
    src = _source(mat)
    if src not in TARGETS or mat.get(e3.MARKER) != e3.REVISION:
        return False, 'NOT_E3_TARGET'
    nodes = _ink_nodes(mat)
    if nodes is None:
        return False, 'E3_NODE_TOPOLOGY_UNKNOWN'
    emiss, opacity, tint, blend = nodes
    expected = _expected_ink_opacity(mat, src)
    if expected is None:
        return False, 'NO_TRUSTED_BASELINE'
    if not _close(opacity.inputs[1].default_value, expected):
        return False, 'CUSTOM_OPACITY_PRESERVED'

    try:
        from . import ae_material_sources as catalog
        record = catalog._source_catalog()['materials'][src]
        colors = record.get('selected_colors', {}).get('_BlendTint', {})
        source_tint = tuple(float(colors.get(ch, 1.0)) for ch in ('r','g','b'))
        legacy = mat.get(LEGACY_E33_MARKER) == LEGACY_E33_REVISION
        if legacy:
            backup = mat.get(LEGACY_BACKUP_KEY)
            if backup is None or 'tint' not in backup:
                return False, 'LEGACY_TINT_BACKUP_MISSING'
            orig_tint = tuple(float(backup['tint'][i]) for i in range(3))
            # The saved E3.3 backup is expected to retain the authored source tint.
            if not all(_close(a,b) for a,b in zip(orig_tint, source_tint)):
                return False, 'CUSTOM_LEGACY_SOURCE_TINT_PRESERVED'
            wanted_tint = tuple(orig_tint[i] * _LEGACY[src][2][i] for i in range(3))
            wanted_emission = _LEGACY[src][1]
            wanted_blend = _LEGACY[src][3]
        else:
            wanted_tint = source_tint
            wanted_emission = 1.0
            wanted_blend = 0.35
        actual_tint = tint.inputs[2].default_value
        if not all(_close(actual_tint[i], wanted_tint[i]) for i in range(3)):
            return False, 'CUSTOM_TINT_PRESERVED'
        if not _close(emiss.inputs['Strength'].default_value, wanted_emission):
            return False, 'CUSTOM_EMISSION_PRESERVED'
        if blend is not None and not _close(blend.inputs[0].default_value, wanted_blend):
            return False, 'CUSTOM_BLEND_PRESERVED'
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        return False, 'UNKNOWN_E3_COLOR_OR_BLEND_BASELINE'
    return True, ''


def _eligible_old_vfx(mat):
    """Strictly recognize the untouched E3.3.1 procedural VFX stage."""
    if (mat.get(MARKER) != REVISION or mat.get(KIND_KEY) != 'VFX'
            or mat.get(VFX_B_KEY) or _source(mat) != 'DefaultHGMaterial'):
        return False
    nodes = _nodes(mat)
    if nodes is None:
        return False
    prefix = 'SaberShader AE VFX E3.3.1 | '
    try:
        noise = nodes.get(prefix+'Soft Noise')
        wave = nodes.get(prefix+'Ink Wisps')
        avg = nodes.get(prefix+'Soft Pattern Mix')
        ramp = nodes.get(prefix+'Feathered Ink Edges')
        layer = nodes.get(prefix+'Soft Facing')
        alpha = nodes.get(prefix+'VFX Opacity 12% Maximum')
        emit = nodes.get(prefix+'Low Emission')
        color = nodes.get(prefix+'Muted Ink Color')
        output = nodes.get(prefix+'Material Output')
        if any(x is None for x in (noise, wave, avg, ramp, layer, alpha, emit, color, output)):
            return False
        return (all((
            _close(noise.inputs['Scale'].default_value, 7.5),
            _close(noise.inputs['Detail'].default_value, 2.2),
            _close(wave.inputs['Scale'].default_value, 3.0),
            _close(wave.inputs['Distortion'].default_value, 3.8),
            _close(avg.inputs[0].default_value, 0.30),
            _close(ramp.color_ramp.elements[0].position, 0.26),
            _close(ramp.color_ramp.elements[1].position, 0.78),
            _close(layer.inputs['Blend'].default_value, 0.32),
            _close(alpha.inputs[1].default_value, 0.12),
            _close(emit.inputs['Strength'].default_value, 0.22),
            all(_close(a, b) for a,b in zip(color.inputs[1].default_value, (0.10,0.16,0.18,1.0))),
            all(_close(a, b) for a,b in zip(color.inputs[2].default_value, (0.58,0.68,0.69,1.0))),
            bool(mat.get(ORIGINAL_KEY)),
        )))
    except (KeyError, IndexError, AttributeError, TypeError, ValueError):
        return False


def make_plan(objects):
    """Read-only plan. Never edits Blender IDs during preflight."""
    groups, skipped, already = {}, [], 0
    for obj in objects or ():
        if not _valid_mesh(obj):
            continue
        mesh = obj.data
        if _readonly(obj) or _readonly(mesh) or getattr(mesh, 'users', 1) > 1:
            skipped.append((obj.name, 'SHARED_OR_LINKED_MESH'))
            continue
        mats = getattr(mesh, 'materials', ()) or ()
        for index, mat in enumerate(mats):
            if mat is None:
                continue
            if mat.get(MARKER) == REVISION:
                # Version B was not applied to existing E3.3.1 scenes by a
                # simple function replacement. Recognize only the untouched
                # procedural look for a safe, nested staged upgrade.
                if (VFX_RE.fullmatch(str(getattr(obj, 'name', '')))
                        and mat.get(KIND_KEY) == 'VFX'
                        and not mat.get(VFX_B_KEY)):
                    if _eligible_old_vfx(mat):
                        pass  # handled as VFX_UPGRADE below
                    else:
                        skipped.append((obj.name, 'CUSTOM_OR_UNKNOWN_E331_VFX_PRESERVED'))
                        continue
                else:
                    already += 1
                    continue
            if _readonly(mat):
                skipped.append((obj.name, 'LINKED_MATERIAL'))
                continue
            src = _source(mat)
            if (src in TARGETS and mat.get(e3.MARKER) == e3.REVISION):
                kind = 'INK'
                ok, reason = _eligible_ink(mat)
            elif (VFX_RE.fullmatch(str(getattr(obj, 'name', ''))) and
                  src == 'DefaultHGMaterial' and
                  mat.get(e32.MARKER) == e32.REVISION and
                  mat.get(e32.ORIGINAL_KEY)):
                kind = 'VFX'
                ok, reason = True, ''
            elif (VFX_RE.fullmatch(str(getattr(obj, 'name', ''))) and
                  _eligible_old_vfx(mat)):
                kind = 'VFX_UPGRADE'
                ok, reason = True, ''
            else:
                continue
            if not ok:
                skipped.append((obj.name, reason))
                continue
            key = _material_id(mat)
            group = groups.setdefault(key, {'material': mat, 'kind': kind, 'source': src, 'slots': []})
            if group['kind'] != kind:
                skipped.append((obj.name, 'MIXED_MATERIAL_KIND'))
                continue
            group['slots'].append((mesh, index))
    approved = []
    for group in groups.values():
        mat = group['material']
        # Blender's material.users includes the fake user when set.
        expected = len(group['slots']) + int(bool(getattr(mat, 'use_fake_user', False)))
        if getattr(mat, 'users', expected) > expected:
            skipped.append((mat.name, 'SHARED_OUTSIDE_BUILD_SELECTION'))
        else:
            approved.append(group)
    return approved, skipped, already


def _ink_refine(mat, src):
    nodes = _ink_nodes(mat)
    if nodes is None:
        raise RuntimeError('E3 ink topology changed during staging')
    emiss, opacity, tint, blend = nodes
    target = TARGETS[src]
    # Establish absolute look targets; no E3.1/E3.3 multiplicative stacking.
    emiss.inputs['Strength'].default_value = target['emission']
    opacity.inputs[1].default_value = target['opacity']
    base_color = tint.inputs[2].default_value
    try:
        if mat.get(LEGACY_E33_MARKER) == LEGACY_E33_REVISION:
            baseline = mat.get(LEGACY_BACKUP_KEY)
            if baseline and 'tint' in baseline:
                base_color = baseline['tint']
        vals = [float(base_color[i]) for i in range(3)]
    except (TypeError, ValueError, IndexError):
        raise RuntimeError('Cannot read original source tint')
    tint.inputs[2].default_value = tuple(vals[i] * target['tint'][i] for i in range(3)) + (1.0,)
    if blend is not None:
        blend.inputs[0].default_value = target['blend']


def _vfx_graph(mat):
    """Versión B: Dual Layer + Distorsión, para el material STAGED E3.3.1.

    Usa texturas originales de Si, sin modificar las imágenes compartidas.
    Un fallo de carga lanza RuntimeError: apply() conserva el material anterior.
    Los parámetros de scroll son drivers SOLO del material nuevo.
    """
    from pathlib import Path
    from . import ae_fx_ink_sources as e3

    # ====== PARÁMETROS DE AJUSTE / LOOK ======
    PREFIX = 'SaberShader AE VFX E3.3.1 | '
    COORD_SOURCE = 'UV'                  # 'Generated' si la geometría no tiene UV útiles
    DISTORTION_STRENGTH = 0.075          # intervalo recomendado: 0.06–0.10
    MAIN_UV_SCALE = 1.0
    DETAIL_UV_SCALE = 1.65               # detalle más pequeño/más repetido
    DETAIL_MIX = 0.40                    # 0=solo trail; 1=solo detalle
    FACING_BLEND = 0.38
    FACING_MIN = 0.40                    # facing remapeado a 0.40–1.0
    BASE_COLOR = (0.48, 0.68, 0.78, 1.0)
    EMISSION_STRENGTH = 0.55
    MAX_OPACITY = 0.23                   # intervalo recomendado: 0.20–0.26
    MAIN_THRESHOLD = (0.18, 0.73)       # negro, blanco del ramp principal
    DETAIL_THRESHOLD = (0.40, 0.81)     # contraste más acusado del detalle

    # Animación opcional de UV (UV/segundo). Si SaberRig bloquea drivers,
    # desactivar aquí; Mapping.Location sigue editable/animable manualmente.
    AUTO_SCROLL = False
    MAIN_SCROLL = (0.012, 0.002)
    DETAIL_SCROLL = (-0.030, 0.006)      # ~2.5 veces la velocidad del trail

    # Rutas controladas: no escanea el disco de forma recursiva ni inventa nombres.
    FILE_MAIN = ('T_fx_trail_fj_09_1_v1d4_M.png',)
    FILE_DETAIL = ('T_fx_trail_gfx_18.png', 'T_fx_noise_cyt_003_1.png')
    FILE_DISTORT = ('T_fx_normal_501_N.png', 'T_fx_flow_527_M.png')
    FILE_MASK = ('T_fx_jsspsi_si_mask5_M.png',)  # opcional

    # El helper E3 primero busca coincidencias en bpy.data.images y luego
    # carga SOLO el archivo exacto desde la carpeta de texturas configurada.
    settings = getattr(getattr(bpy.context, 'scene', None),
                       'aef_sabershader_v8', None)
    configured = str(getattr(settings, 'universal_texture_folder', '') or '')
    search_dirs = [configured] if configured else []
    if configured:
        root = Path(bpy.path.abspath(configured))
        search_dirs.extend((str(root / 'Si - Default'),
                            str(root / 'Si - Default' / 'Si - Default')))
    search_dirs.append('')  # permite imágenes ya abiertas/empaquetadas

    # No asignar Non-Color al datablock global compartido: afectaría a otras
    # superficies. Crear una copia local solo cuando el origen es sRGB.
    new_image_copies = []

    def resolve(filenames, required=True):
        for filename in filenames:
            slot = {'texture': filename[:-4], 'image_file': filename}
            image = None
            for directory in search_dirs:
                image = e3._find_image_slot(slot, mat, texture_dir=directory)
                if image is not None:
                    break
            if image is None:
                continue
            if image.colorspace_settings.name != 'Non-Color':
                copy = image.copy()
                new_image_copies.append(copy)
                copy.name = PREFIX + 'Data | ' + filename
                copy.use_fake_user = False
                copy.colorspace_settings.name = 'Non-Color'
                image = copy
            return image, filename
        if required:
            raise RuntimeError('Si VFX B: falta textura requerida: ' +
                               ' / '.join(filenames))
        return None, None

    try:
        main_image, main_name = resolve(FILE_MAIN)
        detail_image, detail_name = resolve(FILE_DETAIL)
        distort_image, distort_name = resolve(FILE_DISTORT)
        mask_image, mask_name = resolve(FILE_MASK, required=False)
    except Exception:
        for image in new_image_copies:
            if image.users == 0:
                bpy.data.images.remove(image)
        raise

    # SOLO sobre la copia staged: apply() maneja el commit y restore.
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    def new(kind, name, location):
        node = nodes.new(kind)
        node.name = PREFIX + name
        node.label = name
        node.location = location
        return node

    def math_node(op, name, location, clamp=False):
        node = new('ShaderNodeMath', name, location)
        node.operation = op
        node.use_clamp = clamp
        return node

    def mapping(name, position, scale, speed):
        node = new('ShaderNodeMapping', name, position)
        node.vector_type = 'POINT'
        node.inputs['Scale'].default_value = (scale, scale, 1.0)
        # Mapping Location ofrece scroll manual con keyframes.
        # El scroll por drivers (opcional) queda en el material STAGED.
        if AUTO_SCROLL:
            fps = bpy.context.scene.render.fps / max(
                1e-8, bpy.context.scene.render.fps_base)
            for axis, rate in enumerate(speed):
                fc = node.inputs['Location'].driver_add('default_value', axis)
                fc.driver.type = 'SCRIPTED'
                fc.driver.expression = f'(frame - 1.0) * ({rate:.9f}) / ({fps:.9f})'
        return node

    def image_node(name, image, location, vector):
        node = new('ShaderNodeTexImage', name, location)
        node.image = image
        node.extension = 'REPEAT'
        node.interpolation = 'Linear'
        links.new(vector, node.inputs['Vector'])
        return node

    try:
        nodes.clear()
        uv = new('ShaderNodeTexCoord', 'Source Coordinates', (-1580, 240))
        coords = uv.outputs[COORD_SOURCE]

        # --- Distorsión: mapa de datos -> (RGB - 0.5) * intensidad.
        distort_map = mapping('Distortion Mapping', (-1370, -480), 1.0, (0, 0))
        links.new(coords, distort_map.inputs['Vector'])
        disturb = image_node('Distortion | ' + distort_name, distort_image,
                             (-1150, -470), distort_map.outputs['Vector'])
        centered = new('ShaderNodeVectorMath', 'Distortion Center (-0.5)',
                       (-940, -490))
        centered.operation = 'SUBTRACT'
        centered.inputs[1].default_value = (0.5, 0.5, 0.5)
        links.new(disturb.outputs['Color'], centered.inputs[0])
        strength = new('ShaderNodeVectorMath', 'Distortion Strength',
                       (-745, -490))
        strength.operation = 'SCALE'
        strength.inputs[3].default_value = DISTORTION_STRENGTH
        links.new(centered.outputs['Vector'], strength.inputs[0])

        # --- Dos mapeados UV independientes: scroll lento y detalle 2.5x.
        main_map = mapping('Main Trail Scroll', (-1370, 320),
                           MAIN_UV_SCALE, MAIN_SCROLL)
        detail_map = mapping('Detail Scroll 2.5x', (-1370, -60),
                             DETAIL_UV_SCALE, DETAIL_SCROLL)
        links.new(coords, main_map.inputs['Vector'])
        links.new(coords, detail_map.inputs['Vector'])

        main_uv = new('ShaderNodeVectorMath', 'Main UV + Distortion',
                      (-745, 300))
        detail_uv = new('ShaderNodeVectorMath', 'Detail UV + Distortion',
                        (-745, -100))
        main_uv.operation = detail_uv.operation = 'ADD'
        links.new(main_map.outputs['Vector'], main_uv.inputs[0])
        links.new(detail_map.outputs['Vector'], detail_uv.inputs[0])
        links.new(strength.outputs['Vector'], main_uv.inputs[1])
        links.new(strength.outputs['Vector'], detail_uv.inputs[1])

        main = image_node('Main Trail | ' + main_name, main_image,
                          (-510, 320), main_uv.outputs['Vector'])
        detail = image_node('Detail | ' + detail_name, detail_image,
                            (-510, -100), detail_uv.outputs['Vector'])

        # --- Main luminance: mapas _M se interpretan como datos, no color.
        main_bw = new('ShaderNodeRGBToBW', 'Main Density', (-300, 320))
        detail_bw = new('ShaderNodeRGBToBW', 'Detail Density', (-300, -100))
        links.new(main.outputs['Color'], main_bw.inputs['Color'])
        links.new(detail.outputs['Color'], detail_bw.inputs['Color'])
        main_ramp = new('ShaderNodeValToRGB', 'Main Contrast', (-80, 320))
        main_ramp.color_ramp.elements[0].position = MAIN_THRESHOLD[0]
        main_ramp.color_ramp.elements[1].position = MAIN_THRESHOLD[1]
        detail_ramp = new('ShaderNodeValToRGB', 'Detail Contrast', (-80, -100))
        detail_ramp.color_ramp.elements[0].position = DETAIL_THRESHOLD[0]
        detail_ramp.color_ramp.elements[1].position = DETAIL_THRESHOLD[1]
        links.new(main_bw.outputs['Val'], main_ramp.inputs['Fac'])
        links.new(detail_bw.outputs['Val'], detail_ramp.inputs['Fac'])

        # --- Blend 0.4 entre las capas, antes de máscara global.
        layered = new('ShaderNodeMixRGB', 'Dual Layer Mix', (160, 155))
        layered.blend_type = 'MIX'
        layered.inputs[0].default_value = DETAIL_MIX
        links.new(main_ramp.outputs['Color'], layered.inputs[1])
        links.new(detail_ramp.outputs['Color'], layered.inputs[2])
        density = new('ShaderNodeRGBToBW', 'Dual Layer Density', (360, 155))
        links.new(layered.outputs['Color'], density.inputs['Color'])

        # --- Máscara global opcional. Sin ella, factor por defecto = 1.
        mask_mult = math_node('MULTIPLY', 'Global Mask', (570, 95))
        links.new(density.outputs['Val'], mask_mult.inputs[0])
        mask_mult.inputs[1].default_value = 1.0
        if mask_image is not None:
            mask_map = mapping('Global Mask Mapping', (-1370, -810),
                               1.0, (0, 0))
            links.new(coords, mask_map.inputs['Vector'])
            mask = image_node('Global Mask | ' + mask_name, mask_image,
                              (-1150, -800), mask_map.outputs['Vector'])
            mask_bw = new('ShaderNodeRGBToBW', 'Mask Density', (-900, -800))
            links.new(mask.outputs['Color'], mask_bw.inputs['Color'])
            links.new(mask_bw.outputs['Val'], mask_mult.inputs[1])

        # --- Facing: remap 0..1 -> 0.40..1.00 (sin transparencias duras).
        facing = new('ShaderNodeLayerWeight', 'Facing', (340, -210))
        facing.inputs['Blend'].default_value = FACING_BLEND
        facing_remap = math_node('MULTIPLY_ADD', 'Facing 0.4..1.0',
                                (570, -180))
        facing_remap.inputs[1].default_value = 1.0 - FACING_MIN
        facing_remap.inputs[2].default_value = FACING_MIN
        links.new(facing.outputs['Facing'], facing_remap.inputs[0])
        shaped = math_node('MULTIPLY', 'Mask x Facing', (770, 40))
        links.new(mask_mult.outputs[0], shaped.inputs[0])
        links.new(facing_remap.outputs[0], shaped.inputs[1])

        # --- Alpha 0..MAX_OPACITY: factor para Transparent/Emission.
        opacity = math_node('MULTIPLY', 'Maximum Opacity', (960, 40),
                            clamp=True)
        opacity.inputs[1].default_value = MAX_OPACITY
        links.new(shaped.outputs[0], opacity.inputs[0])

        # --- Emission: la mezcla con Transparent ya la pondera por alfa.
        emit = new('ShaderNodeEmission', 'Cyan Grey Ink', (950, 360))
        emit.inputs['Color'].default_value = BASE_COLOR
        emit.inputs['Strength'].default_value = EMISSION_STRENGTH
        transparent = new('ShaderNodeBsdfTransparent', 'Transparent VFX',
                          (950, -180))
        mix = new('ShaderNodeMixShader', 'Transparent + Emission',
                  (1200, 155))
        output = new('ShaderNodeOutputMaterial', 'Material Output',
                     (1420, 155))
        links.new(opacity.outputs[0], mix.inputs[0])
        links.new(transparent.outputs['BSDF'], mix.inputs[1])
        links.new(emit.outputs['Emission'], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs['Surface'])

        if hasattr(mat, 'surface_render_method'):
            mat.surface_render_method = 'BLENDED'
        if hasattr(mat, 'use_backface_culling'):
            mat.use_backface_culling = False
        mat['SaberShader_AE_VFX_B_Source'] = 'DUAL_LAYER_REAL_TEXTURES'
        mat['SaberShader_AE_VFX_B_Mask'] = ('CONNECTED' if mask_image
                                            else 'OPTIONAL_NOT_FOUND')
    except Exception:
        # La copia staged puede desecharse; no se modificó material fuente.
        nodes.clear()
        for image in new_image_copies:
            if image.users == 0:
                bpy.data.images.remove(image)
        raise


def _clear_previous_stages(mat):
    # New material uses only E3.3.1 marker. Old stage operators therefore
    # cannot accidentally modify an active final-look material.
    for k in (e3.MARKER, e31.CALIBRATION_KEY, e31.PREVIOUS_KEY,
              e32.MARKER, LEGACY_E33_MARKER, LEGACY_BACKUP_KEY):
        if k in mat:
            del mat[k]


def apply(objects):
    groups, skipped, already = make_plan(objects)
    if not groups:
        return {'status': 'ALREADY_APPLIED' if already else 'NO_ELIGIBLE',
                'new': 0, 'already': already, 'skipped': skipped}
    staged, fake_changes, swaps = [], [], []
    # Track image IDs loaded or duplicated for the Version B preview, so a
    # failed material commit doesn't leave new unused images behind. Never
    # remove images which existed before this operation.
    try:
        images_before = {im.as_pointer() if hasattr(im, 'as_pointer') else id(im)
                         for im in bpy.data.images}
    except (AttributeError, TypeError):
        images_before = None
    try:
        # PREPARE: no source material is modified before all new node graphs exist.
        for group in groups:
            original = group['material']
            stage = original.copy()
            group['stage'] = stage
            staged.append(stage)
            stage.name = 'SaberShader AE Si FX E3.3.1 | ' + group['source']
            if group['kind'] == 'INK':
                _ink_refine(stage, group['source'])
            else:
                _vfx_graph(stage)
                stage[VFX_B_KEY] = VFX_B_REVISION
            _clear_previous_stages(stage)
            stage[MARKER] = REVISION
            stage[KIND_KEY] = 'VFX' if group['kind'] == 'VFX_UPGRADE' else group['kind']
            stage[ORIGINAL_KEY] = original.name
            stage[ORIGINAL_FAKE_KEY] = int(bool(original.use_fake_user))
            stage['SaberShader_AE_FX_E331_Equivalence'] = 'UNVERIFIED_STATIC_PREVIEW'
            stage.use_fake_user = False
        # COMMIT: source materials remain available after save/reload.
        for group in groups:
            old = group['material']
            fake_changes.append((old, bool(old.use_fake_user)))
            old.use_fake_user = True
        for group in groups:
            for mesh, index in group['slots']:
                old = mesh.materials[index]
                mesh.materials[index] = group['stage']
                swaps.append((mesh, index, old))
    except Exception as exc:
        rollback_errors = []
        for mesh, index, old in reversed(swaps):
            try: mesh.materials[index] = old
            except Exception as err: rollback_errors.append(str(err))
        for mat, fake in reversed(fake_changes):
            try: mat.use_fake_user = fake
            except Exception as err: rollback_errors.append(str(err))
        for mat in staged:
            try:
                if not mat.users:
                    bpy.data.materials.remove(mat)
            except Exception as err:
                rollback_errors.append(str(err))
        if images_before is not None:
            try:
                for im in list(bpy.data.images):
                    key = im.as_pointer() if hasattr(im, 'as_pointer') else id(im)
                    if key not in images_before and not im.users and not im.use_fake_user:
                        bpy.data.images.remove(im)
            except Exception as err:
                rollback_errors.append('Image cleanup: '+str(err))
        return {'status': 'ROLLBACK_INCOMPLETE' if rollback_errors else 'ERROR_ROLLED_BACK',
                'new': 0, 'already': already, 'error': str(exc),
                'rollback_errors': rollback_errors, 'skipped': skipped}
    return {'status': 'APPLIED', 'new': sum(len(g['slots']) for g in groups),
            'ink': sum(g['kind'] == 'INK' for g in groups),
            'vfx': sum(g['kind'] in ('VFX', 'VFX_UPGRADE') for g in groups),
            'vfx_upgraded': sum(g['kind'] == 'VFX_UPGRADE' for g in groups),
            'already': already, 'skipped': skipped,
            'equivalence': 'NOT_VERIFIED_IN_BLENDER'}


def restore(objects):
    groups, issues = {}, []
    for obj in objects or ():
        if not _valid_mesh(obj):
            continue
        mesh = obj.data
        for index, mat in enumerate(getattr(mesh, 'materials', ()) or ()):
            if mat is None or mat.get(MARKER) != REVISION:
                continue
            if _readonly(obj) or _readonly(mesh) or _readonly(mat) or getattr(mesh, 'users', 1) > 1:
                issues.append((obj.name, 'UNEDITABLE_OR_SHARED'))
                continue
            old = bpy.data.materials.get(str(mat.get(ORIGINAL_KEY, '')))
            kind = mat.get(KIND_KEY, '')
            if (old is None or _readonly(old) or old is mat or
                    _source(old) != _source(mat) or
                    (kind == 'INK' and old.get(e3.MARKER) != e3.REVISION) or
                    (kind == 'VFX' and old.get(e32.MARKER) != e32.REVISION and
                     not (mat.get(VFX_B_KEY) == VFX_B_REVISION
                          and old.get(MARKER) == REVISION
                          and old.get(KIND_KEY) == 'VFX'))):
                issues.append((obj.name, 'INVALID_ORIGINAL_MATERIAL'))
                continue
            key = _material_id(mat)
            group = groups.setdefault(key, {'stage': mat, 'old': old, 'slots': []})
            group['slots'].append((mesh, index))
    for group in groups.values():
        stage = group['stage']
        expected = len(group['slots']) + int(bool(getattr(stage, 'use_fake_user', False)))
        if getattr(stage, 'users', expected) > expected:
            issues.append((stage.name, 'SHARED_OUTSIDE_SELECTION'))
    if issues:
        return {'status': 'BLOCKED', 'restored': 0, 'issues': issues}
    swaps = []
    try:
        for group in groups.values():
            for mesh, index in group['slots']:
                mesh.materials[index] = group['old']
                swaps.append((mesh, index, group['stage']))
    except Exception as exc:
        failures = []
        for mesh, index, stage in reversed(swaps):
            try: mesh.materials[index] = stage
            except Exception as err: failures.append(str(err))
        return {'status': 'ROLLBACK_INCOMPLETE' if failures else 'ERROR_ROLLED_BACK',
                'restored': 0, 'error': str(exc), 'rollback_errors': failures}
    # If other copies elsewhere still need the same source, retain fake-user.
    for group in groups.values():
        old = group['old']
        other_stages = any(m.get(MARKER) == REVISION and m.get(ORIGINAL_KEY) == old.name and m.users > 0
                           for m in bpy.data.materials)
        if not other_stages and not bool(group['stage'].get(ORIGINAL_FAKE_KEY, True)):
            try: old.use_fake_user = False
            except Exception: pass  # Safe retention is preferable to data loss.
    return {'status': 'RESTORED' if swaps else 'NO_ACTIVE_LOOK', 'restored': len(swaps)}


class AEF_OT_ae_si_fx_e331_restore(bpy.types.Operator):
    bl_idname = 'sabershader.ae_si_fx_e331_restore'
    bl_label = 'Restore Si FX Appearance'
    bl_description = 'Restore the previously assigned Si FX appearance before applying other recovery tools'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from . import ae_material_sources as catalog
        try:
            result = restore(catalog._target_meshes(context))
        except Exception as exc:
            self.report({'ERROR'}, 'Si FX appearance restore failed: ' + str(exc)[:155])
            return {'CANCELLED'}
        if result['status'] not in ('RESTORED', 'NO_ACTIVE_LOOK'):
            self.report({'ERROR'}, 'Si FX appearance restore: ' + str(result.get('issues', result.get('error', 'unknown')))[:155])
            return {'CANCELLED'}
        self.report({'INFO'}, 'Restored %d Si FX material slots' % result['restored'])
        return {'FINISHED'}
