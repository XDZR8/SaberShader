"""AE UI visibility policy only; never changes shader, Build, or scene data.

The public Endfield interface shows the Build result and optional artist
actions. Audits, comparisons, experiments and JSON exports remain accessible
only through Add-on Preferences > Developer Tools. Hiding a panel must never
disable the underlying Build stage or mutate project state.

Older operator and property identifiers intentionally retain their revision
suffixes for compatibility with saved .blend files. UI-facing labels must use
plain feature names, not those suffixes.
"""

# Blender's AddonPreferences identifier is the add-on package name.
ADDON_MODULE = __package__
DEVELOPER_PROPERTY = 'show_ae_developer_panels'


def ae_developer_tools_visible(context):
    """Fail closed when preferences are absent (e.g. during background tests)."""
    try:
        addons = context.preferences.addons
        addon = addons.get(ADDON_MODULE)
        prefs = addon.preferences if addon is not None else None
        return bool(getattr(prefs, DEVELOPER_PROPERTY, False))
    except (AttributeError, KeyError, TypeError):
        return False
