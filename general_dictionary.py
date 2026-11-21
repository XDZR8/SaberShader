"""General / MMD name hints for material and texture classification.

These entries describe possible exporter names. They do not identify a game,
character, owner or guaranteed texture channel. They are advisory unless other
material evidence confirms a role.
"""

import re
import unicodedata

# Exact material or PMX slot aliases are resolved conservatively. The engine
# rejects conflicting categories and never assigns a role from a weak match.
GENERAL_MATERIAL_NAME_ROLES = {
    'Face': 'face',
    'Eyes': 'eyes',
    'Eyes2': 'eyes3',
    'Eyelids': 'eyes5',
    '口内.001': 'mouth',
    'Hair': 'hair',
    'Arms': 'body',
    'Hands': 'body',
    '耳饰.001': 'accessory',
    'Clothes': 'cloth',
    'Deco1': 'accessory',
    'Clothes2': 'cloth',
    'Deco2': 'accessory',
    'Clothes3': 'cloth',
    'Stocks': 'stockings',
    'Face2': 'face',
    '表情2.001': 'expression',
    'Mask': 'mask',
    'Guitar1': 'guitar',
    'Guitar2': 'guitar',
    'Guitar3': 'guitar',
    'Clothes4': 'cloth',
    '面': 'face',
    '目': 'eyes',
    '目白': 'eyes3',
    '睫眉': 'eyes5',
    '口内': 'mouth',
    '表情': 'expression',
    '表情2': 'expression2',
    '发': 'hair',
    '肌': 'body',
    '耳饰': 'accessory',
    '面具': 'mask',
    '领带': 'tie',
    '手套': 'glove',
    '蝴蝶结': 'bow',
    '服': 'cloth',
    '裙': 'skirt',
    '裙透': 'transparent_cloth',
    '丝袜': 'stockings',
    '靴子': 'boots',
}

# Known basename candidates are optional and must exist in Blender's images.
# These are name conventions, not embedded textures or model dependencies.
GENERAL_BASE_TEXTURE_BY_MATERIAL = {
    'Face': 'FC_1.jpg',
    'Face2': 'FC_1.jpg',
    '面': 'face.png',
    '表情2': 'face.png',
    'Mask': 'Htn_MJ.png',
    '面具': 'MianJu_透.png',
}

# Auxiliary sources may use these variants after importers append .001, etc.
GENERAL_FACE_TEXTURE_FALLBACKS = ('FC_1.jpg', 'BQ_2.png.001', 'BQ_2.png', 'BQ.png.001', 'BQ.png')

# A filename suffix is only a clue. P/ST/HN/RS can have different channel
# semantics depending on the source. No shader wiring is inferred from them.
GENERAL_TEXTURE_SUFFIX_HINTS = {
    "HN": "hair/normal auxiliary candidate",
    "P": "packed control candidate (channels unverified)",
    "ST": "secondary control candidate (channels unverified)",
    "RS": "hair/specular or rim control candidate (channels unverified)",
    "C": "MMD color/base candidate",
    "H": "MMD toon candidate",
    "S": "MMD shadow candidate",
    "NM": "normal-map candidate",
    "NORMAL": "normal-map candidate",
    "ALPHA": "alpha candidate",
    "MASK": "mask candidate",
}

GENERAL_TEXTURE_EXACT_HINTS = {
    "FC_1.JPG": "face/base image candidate",
    "FACE.PNG": "face/base image candidate",
    "HTN_MJ.PNG": "mask/alpha image candidate",
    "MIANJU_透.PNG": "mask/alpha image candidate",
    "BQ_2.PNG": "face/expression candidate",
    "BQ.PNG": "face/expression candidate",
}


def general_texture_filename_hints(names):
    """Return readable, non-authoritative role hints for imported images."""
    result = {}
    for name in names:
        basename = str(name or "").replace("\\", "/").rsplit("/", 1)[-1]
        # Blender appends .001 to duplicate images; ignore only that suffix.
        cleaned = re.sub(r"\.\d{3}$", "", basename)
        normalized = unicodedata.normalize("NFKC", cleaned).upper()
        hints = []
        exact = GENERAL_TEXTURE_EXACT_HINTS.get(normalized)
        if exact:
            hints.append(exact)
        stem = re.sub(r"\.[^.]+$", "", normalized)
        match = re.search(r"(?:^|[_\-.])([A-Z]{1,6})$", stem)
        if match:
            suffix_hint = GENERAL_TEXTURE_SUFFIX_HINTS.get(match.group(1))
            if suffix_hint:
                hints.append(suffix_hint)
        if hints:
            result[basename] = tuple(dict.fromkeys(hints))
    return result


# Endfield materials use an actor-scoped registry. The legacy General/MMD name
# hints above are never used as authoritative Endfield shader definitions.
# To support another actor, add its verified package record to the registry;
# never reuse the first actor's textures as an unverified fallback.
from pathlib import Path as _Path
import json as _json

AE_SOURCE_REGISTRY_PATH = _Path(__file__).parent / "assets" / "AE_Material_Source_Registry.json"

def load_ae_material_source_registry():
    """Read the unified Endfield source index without modifying any scene data."""
    with AE_SOURCE_REGISTRY_PATH.open('r', encoding='utf-8') as stream:
        data = _json.load(stream)
    if data.get('schema') != 'SaberShader_AE_MaterialRegistry_V1':
        raise RuntimeError('Unsupported Endfield source material registry')
    records = data.get('characters')
    if not isinstance(records, dict):
        raise RuntimeError('Invalid Endfield material registry: missing characters')
    return data

def ae_material_catalog_for_actor(actor_code):
    """Return exact source records for this actor only, never a global fallback."""
    code = str(actor_code or '').strip().casefold()
    if not code:
        return None
    records = load_ae_material_source_registry()['characters']
    data = records.get(code)
    if data is None:
        return None
    if (not isinstance(data, dict) or
        data.get('schema') != 'SaberShader_AE_SourceDictionary_V1' or
        str(data.get('source_actor_code', '')).casefold() != code or
        not isinstance(data.get('materials'), dict)):
        raise RuntimeError('Invalid Endfield source records for actor: ' + code)
    return data
