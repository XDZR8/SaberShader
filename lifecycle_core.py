"""SaberShader Fix2 lifecycle ledger; deliberately independent of bpy.

Only successfully installed registrations are owned; rollback executes in
reverse order. No scene datablocks are touched by this module. A failed undo
is reported instead of being mistaken for a complete transaction.
"""


class LifecycleConflict(RuntimeError):
    """Refuse to overwrite registration owned by an earlier add-on instance."""


class LifecycleLedger:
    def __init__(self):
        self._undo = []

    def step(self, label, install, undo):
        install()
        self._undo.append((str(label), undo))

    def register_class(self, utils, cls):
        self.step('class:' + cls.__name__,
                  lambda: utils.register_class(cls),
                  lambda: utils.unregister_class(cls))

    def register_property(self, owner, name, factory):
        if hasattr(owner, name):
            raise LifecycleConflict('Existing RNA property: ' + name + '; restart Blender')
        value = factory()
        self.step('property:' + name,
                  lambda: setattr(owner, name, value),
                  lambda: delattr(owner, name))

    def register_handler(self, collection, callback):
        if callback in collection:
            raise LifecycleConflict('Existing handler: ' + callback.__name__ + '; restart Blender')
        self.step('handler:' + callback.__name__,
                  lambda: collection.append(callback),
                  lambda: collection.remove(callback))

    def rollback(self):
        failures = []
        pending_retry = []
        while self._undo:
            label, undo = self._undo.pop()
            try:
                undo()
            except Exception as exc:
                failures.append('%s: %s' % (label, exc))
                pending_retry.append((label, undo))
        # Undo callbacks which failed must remain available for a later retry.
        # Reverse for correct dependency order on the next attempt.
        self._undo = list(reversed(pending_retry))
        return failures

    @property
    def has_pending(self):
        return bool(self._undo)
