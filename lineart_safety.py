"""SaberShader read-only Line Art inventory.

No bpy import and no scene mutations; suitable for unit testing with stubs.
Object names / addon markers are evidence of *possible* origin, not proof.
"""

# LINEART is confirmed in Blender 5.1 modifier enums. The RNA class is
# bpy.types.GreasePencilLineartModifier. Keep alternate spelling support for
# old files/stubs, but never use a modifier's display name as proof.
LINEART_TYPES = frozenset(('LINEART', 'GREASEPENCIL_LINEART', 'GREASE_PENCIL_LINEART'))
LINEART_RNA_IDENTIFIER = 'GreasePencilLineartModifier'
RECEIVER_PREFIX = 'AEF V9 • LineArt • '
MODIFIER_PREFIX = 'AEF V9'
SCHEMA_VERSION = 2


def _property(obj, key, default=None):
    try:
        return obj.get(key, default)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return default


def receiver_provenance(obj):
    """Return the weakly-evidenced provenance, if this is a GP receiver."""
    if obj is None or str(getattr(obj, 'type', '')) != 'GREASEPENCIL':
        return None
    if bool(_property(obj, 'AEF_V9_LineArtObject', False)):
        return 'id_property'
    if str(getattr(obj, 'name', '')).startswith(RECEIVER_PREFIX):
        return 'name_prefix_only'
    return None


def is_generated_lineart_receiver(obj):
    return receiver_provenance(obj) is not None


def is_lineart_modifier(mod):
    """Identify actual Line Art by Blender modifier type or RNA identity.

 Names / SaberShader prefixes are NOT authoritative. The RNA fallback also
 handles a future enum spelling change without deleting non-Line-Art mods.
 """
    try:
        mod_type = str(getattr(mod, 'type', '') or '').upper()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        mod_type = ''
    if mod_type in LINEART_TYPES or mod_type.replace('_', '') == 'GREASEPENCILLINEART':
        return True
    for attr in ('bl_rna', 'rna_type'):
        try:
            rna = getattr(mod, attr, None)
            if str(getattr(rna, 'identifier', '') or '') == LINEART_RNA_IDENTIFIER:
                return True
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
    return False


def inspect_generated_lineart(objects):
    """Build a serializable, *read-only* inventory; includes no file paths.

 Historical prefix matches are candidates, not authoritative attribution.
 A native Blender crash cannot be detected or prevented by this routine.
 """
    rows = []
    actual_lineart = 0
    prefixed_non_lineart = 0
    legacy_named_receivers = 0
    total_modifiers = 0
    for obj in objects:
        provenance = receiver_provenance(obj)
        if provenance is None:
            continue
        if provenance == 'name_prefix_only':
            legacy_named_receivers += 1
        mods = []
        for mod in list(getattr(obj, 'modifiers', ())):
            name = str(getattr(mod, 'name', ''))
            mtype = str(getattr(mod, 'type', ''))
            lineart = is_lineart_modifier(mod)
            generated_name = name.startswith(MODIFIER_PREFIX)
            actual_lineart += int(lineart)
            prefixed_non_lineart += int(generated_name and not lineart)
            total_modifiers += 1
            mods.append({
                'name': name,
                'type': mtype,
                'lineart_type': lineart,
                'legacy_prefixed_name': generated_name,
                'would_remove_under_fix1': lineart,
                'would_remove_under_fix2': False,
                'blocks_reference_build_fix2': lineart,
                'would_remove_under_original': lineart or generated_name,
            })
        rows.append({
            'object': str(getattr(obj, 'name', '')),
            'provenance': provenance,
            'hide_viewport': bool(getattr(obj, 'hide_viewport', False)),
            'hide_render': bool(getattr(obj, 'hide_render', False)),
            'modifiers': mods,
        })
    return {
        'schema': 'sabershader.lineart_preflight',
        'schema_version': SCHEMA_VERSION,
        'read_only': True,
        'warning': 'Legacy names are not proof of provenance. The diagnostics never delete Line Art; a native Blender evaluator crash remains unverified.',
        'totals': {
            'generated_receiver_candidates': len(rows),
            'legacy_name_only_receivers': legacy_named_receivers,
            'lineart_modifiers': actual_lineart,
            'prefixed_non_lineart_modifiers': prefixed_non_lineart,
            'all_receiver_modifiers': total_modifiers,
        },
        'objects': rows,
    }


def inspect_scene_lineart_risk(objects):
    """Read-only fail-closed scan across *all* GP objects, not only candidates.

 A source Line Art modifier on a manually named GP object can also carry
 risk. Therefore builds block on any actual Line Art modifier.
 """
    found = []
    for obj in objects:
        if str(getattr(obj, 'type', '')) != 'GREASEPENCIL':
            continue
        for mod in getattr(obj, 'modifiers', ()):
            if is_lineart_modifier(mod):
                found.append({
                    'object': str(getattr(obj, 'name', '')),
                    'modifier': str(getattr(mod, 'name', '')),
                    'type': str(getattr(mod, 'type', '')),
                    'provenance': receiver_provenance(obj),
                })
    return {'schema': 'sabershader.scene_lineart_risk',
            'schema_version': 2,
            'read_only': True,
            'lineart_modifiers_all': len(found),
            'blocks_reference_build': bool(found),
            'modifiers': found}
