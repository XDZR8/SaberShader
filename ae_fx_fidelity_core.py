"""Pure E3.4.3 rules. No Blender dependency or character-specific look.

Source-authored FX previews are not Unity shader equivalence. Controls default to
identity; A is never modified. Missing/ambiguous provenance fails closed.
"""
from __future__ import annotations

import math

REVISION = 'AE_UNIVERSAL_FX_A_A2_E343_1'
SCHEMA = 'SaberShader_AE_UniversalFX_AA2_E343'
KEY = 'SaberShader_AE_E343_'
PARAMS = ('alpha_power', 'alpha_multiplier', 'edge_fade', 'brightness',
          'contrast', 'tint', 'emission_gain')
DEFAULTS = {
    'alpha_power': 1.0, 'alpha_multiplier': 1.0, 'edge_fade': 0.0,
    'brightness': 0.0, 'contrast': 0.0, 'tint': (1.0, 1.0, 1.0),
    'emission_gain': 1.0,
}
BOUNDS = {
    'alpha_power': (0.35, 3.0), 'alpha_multiplier': (0.0, 2.0),
    'edge_fade': (0.0, 0.75), 'brightness': (-0.5, 0.5),
    'contrast': (-0.5, 0.5), 'emission_gain': (0.0, 3.0),
}


def validated_parameters(p):
    """Return all parameters as finite, bounded, immutable values."""
    if not isinstance(p, dict):
        raise ValueError('Controls must be a dictionary')
    if set(p) != set(DEFAULTS):
        raise ValueError('Controls require exact parameter set: ' + ', '.join(DEFAULTS))
    r = {}
    for key, (low, high) in BOUNDS.items():
        value = p[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError('%s must be a finite number' % key)
        if not low <= value <= high:
            raise ValueError('%s out of range [%s, %s]' % (key, low, high))
        r[key] = float(value)
    tint = p['tint']
    if (not isinstance(tint, (tuple, list)) or len(tint) != 3 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                not math.isfinite(v) or not 0.0 <= v <= 2.0 for v in tint)):
        raise ValueError('tint must be three finite components in [0, 2]')
    r['tint'] = tuple(float(x) for x in tint)
    return r


def is_neutral(p):
    p = validated_parameters(p)
    return all(p[k] == DEFAULTS[k] for k in PARAMS)


def alpha_preview(alpha, *, power=1.0, multiplier=1.0, fade=0.0):
    """Reference formula for the graph, not gamma/color-space calibration."""
    if not all(math.isfinite(x) for x in (alpha, power, multiplier, fade)):
        raise ValueError('Nonfinite alpha control')
    if not 0.0 <= fade < 1.0 or power <= 0 or multiplier < 0:
        raise ValueError('Bad alpha control')
    a = max(0.0, min(1.0, float(alpha)))
    return max(0.0, min(1.0, ((a**power) - fade) / (1.0 - fade) * multiplier))


def authoritative_textured_row(row, actor):
    """No placeholder/procedural/unknown FX permitted for A2 graph insertion."""
    if not isinstance(row, dict):
        return False
    if row.get('family') != 'TEXTURED_FX_CANDIDATE' or row.get('source_json_status') != 'JSON_VALID':
        return False
    if row.get('source_kind') != 'FX_SOURCE' or not row.get('source_material', '').casefold().startswith('m_fx_'):
        return False
    if row.get('source_owner') and row['source_owner'] != actor:
        return False
    main = row.get('texture_slots', {}).get('_MainTex', {})
    if main.get('status') != 'TEXTURE_FOUND' or not main.get('path'):
        return False
    return True
