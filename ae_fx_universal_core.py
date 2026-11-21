"""E3.4.2 pure, read-only source identity and FX classification for AE.

This module is intentionally independent from Blender. It reports *candidates*
from exact Unity material JSON and never infers shader equivalence, applies
materials, or assumes a particular character's FX texture names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REVISION = 'AE_UNIVERSAL_FX_FOUNDATION_E342_1'
SCHEMA = 'SaberShader_AE_UniversalFX_Inventory_E342'
ACTOR_RE = re.compile(r'^s_actor_(?:lod_)?([a-z0-9]+)_(?:[a-z0-9_]+)(?:\.\d{3})?$', re.I)
SUFFIX_RE = re.compile(r'\.\d{3}$')
TEXTURE_EXTS = ('.png', '.tga', '.dds', '.exr', '.jpg', '.jpeg', '.webp')


def actor_id(name):
    match = ACTOR_RE.match(str(name or ''))
    return match.group(1).casefold() if match else ''


def source_name(material_name, source_property, *, vfx_hint=False):
    """Return (exact source ID, proof). Only authoritative property or literal source name.

    A generic material is not declared VFX merely because its mesh is named vfxpart.
    """
    if isinstance(source_property, str) and source_property.strip():
        s = source_property.strip()
        if re.fullmatch(r'[A-Za-z0-9_\-]+', s):
            return s, 'SOURCE_PROPERTY'
        return '', 'INVALID_SOURCE_PROPERTY'
    s = SUFFIX_RE.sub('', str(material_name or ''))
    if re.fullmatch(r'(?:M_fx_[A-Za-z0-9_\-]+|DefaultHGMaterial)', s):
        return s, 'EXACT_UNITY_MATERIAL_NAME'
    return '', 'NO_EXACT_SOURCE_IDENTITY'


def source_owner(source_id):
    """Strong owner identity only for explicit M_fx_actor_<actor> export syntax."""
    m = re.match(r'^m_fx_actor_(?:lod_)?([a-z0-9]+)_(?:.+)$', str(source_id or ''), re.I)
    return m.group(1).casefold() if m else ''


def candidate_kind(object_name, source_id):
    """Filter potential FX without turning normal body/hair into an FX."""
    source = str(source_id or '').casefold()
    name = str(object_name or '').casefold()
    if source.startswith('m_fx_'):
        return 'FX_SOURCE'
    if re.search(r'_vfxpart_[a-z0-9]+_', name) and source == 'defaulthgmaterial':
        return 'VFX_DEFAULT_PLACEHOLDER'
    if re.search(r'_vfxpart_[a-z0-9]+_', name):
        return 'VFX_UNVERIFIED_SOURCE'
    return ''


def source_folders(configured_folder):
    """Enumerate only exact sibling Material/Textures directories, never recurse."""
    root = Path(str(configured_folder or '')).expanduser()
    if not str(configured_folder or '').strip():
        return ((), ())
    if root.name.casefold() in ('materials', 'textures'):
        root = root.parent
    bases = [root]
    mats, textures = [], []
    for base in bases:
        mats.append(base / 'Materials')
        textures.append(base / 'Textures')
    return (tuple(mats), tuple(textures))


def locate_exact_json(name, folder):
    if not re.fullmatch(r'[A-Za-z0-9_\-]+', str(name or '')):
        return ('INVALID_NAME', None)
    dirs, _ = source_folders(folder)
    matches = [d / (name + '.json') for d in dirs if (d / (name + '.json')).is_file()]
    if len(matches) == 0:
        return ('JSON_MISSING', None)
    if len(matches) > 1:
        return ('JSON_AMBIGUOUS', None)
    return ('JSON_FOUND', matches[0])


def read_json(path, expected_name):
    try:
        if path.stat().st_size > 8_000_000:
            return ('JSON_TOO_LARGE', None)
        with path.open('r', encoding='utf-8-sig') as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError, UnicodeError):
        return ('JSON_UNREADABLE', None)
    if not isinstance(data, dict):
        return ('JSON_INVALID', None)
    actual = data.get('m_Name')
    if actual != expected_name:
        return ('JSON_IDENTITY_MISMATCH', None)
    saved = data.get('m_SavedProperties')
    env = saved.get('m_TexEnvs') if isinstance(saved, dict) else None
    if not isinstance(env, dict):
        return ('JSON_INVALID_TEXENVS', None)
    return ('JSON_VALID', data)


def texture_slots(data):
    env = data['m_SavedProperties']['m_TexEnvs']
    slots = {}
    for slot_name, record in env.items():
        if not isinstance(record, dict):
            continue
        texture = record.get('m_Texture')
        if not isinstance(texture, dict):
            continue
        name = texture.get('Name')
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_\-]+', name)
                or texture.get('IsNull', False)):
            continue
        slots[str(slot_name)] = name
    return slots


def find_exact_texture(name, folder):
    _, dirs = source_folders(folder)
    matches = []
    for directory in dirs:
        for ext in TEXTURE_EXTS:
            path = directory / (name + ext)
            if path.is_file():
                matches.append(path)
    if not matches:
        return ('TEXTURE_MISSING', None)
    if len(matches) != 1:
        return ('TEXTURE_AMBIGUOUS', None)
    return ('TEXTURE_FOUND', matches[0])


def classify(json_id, data, kind):
    """Conservative source-family label, not a visual shader/equation claim."""
    if kind == 'VFX_DEFAULT_PLACEHOLDER':
        return ('VFX_PLACEHOLDER_UNVERIFIED', 'Generic DefaultHGMaterial has no authored FX shader identity')
    if data is None:
        return ('SOURCE_UNVERIFIED', 'Exact source JSON unavailable or invalid')
    slots = texture_slots(data)
    if kind == 'VFX_UNVERIFIED_SOURCE':
        return ('VFX_FAMILY_UNVERIFIED', 'VFX mesh identity only; no exact FX shader mapping')
    if kind != 'FX_SOURCE':
        return ('NOT_FX', 'No authored FX source evidence')
    if '_MainTex' in slots:
        return ('TEXTURED_FX_CANDIDATE', 'Authored _MainTex; native shader family/equations unverified')
    if slots:
        return ('NON_MAIN_TEX_FX_UNVERIFIED', 'FX JSON has textures but no authored _MainTex')
    return ('PROCEDURAL_FX_UNVERIFIED', 'FX JSON declares no bound textures')


def source_inventory(source_id, folder, *, object_name=''):
    kind = candidate_kind(object_name, source_id)
    status, json_path = locate_exact_json(source_id, folder)
    raw, parsed = (read_json(json_path, source_id) if json_path is not None else (status, None))
    family, rationale = classify(source_id, parsed, kind)
    slots = texture_slots(parsed) if parsed is not None else {}
    textures = {}
    for slot, texture in sorted(slots.items()):
        tstatus, path = find_exact_texture(texture, folder)
        textures[slot] = {'source_name': texture, 'status': tstatus, 'path': str(path) if path else ''}
    return {
        'source_material': source_id,
        'source_kind': kind,
        'source_json_status': raw,
        'source_json_path': str(json_path) if json_path else '',
        'source_shader_path_id': str(parsed.get('m_Shader', {}).get('m_PathID', '')) if parsed else '',
        'family': family,
        'reason': rationale,
        'texture_slots': textures,
        'missing_textures': [s for s, t in textures.items() if t['status'] != 'TEXTURE_FOUND'],
        'native_shader_verified': False,
        'preview_supported': False,
        'automatic_shader_assignment': 'DISABLED_E342',
    }
