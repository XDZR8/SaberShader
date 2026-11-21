"""Process-local, opt-in dynamic face-light / expression synchronization."""
_LIVE_SYNC = False


def set_live_sync(enabled):
    global _LIVE_SYNC
    _LIVE_SYNC = bool(enabled)


def live_sync_enabled():
    return _LIVE_SYNC

# Keep this flag in the child module across package-root reloads.
# Detect a second root import while the original root still owns RNA resources.
# This does NOT try to hot-unload Blender classes; a restart is mandatory.
_REGISTRATION_ACTIVE = False


def set_registration_active(enabled):
    global _REGISTRATION_ACTIVE
    _REGISTRATION_ACTIVE = bool(enabled)


def registration_active():
    return _REGISTRATION_ACTIVE
