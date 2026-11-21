"""Small process-local dispatcher for opt-in dynamic updates.

No Blender import, no disk I/O, no timers, and no deferred scene writes. All
scene edits remain in the opt-in engine callbacks. The narrow
Depsgraph filter excludes only changes to image/texture/material datablocks;
unknown Blender IDs always run (fail open for correctness).

Handler behavior and stability must still be evaluated in actual Blender scenes.
"""
from time import perf_counter_ns

_STATS = {}
_RUNNING = False
_UNRELATED_IDS = frozenset({'Material', 'Image', 'Texture'})


def reset():
    global _RUNNING
    _RUNNING = False
    _STATS.clear()
    _STATS.update({
        'calls': 0, 'frame_calls': 0, 'depsgraph_calls': 0,
        'executed': 0, 'skipped': 0, 'reentrant_skips': 0,
        'errors': 0, 'total_ms': 0.0, 'peak_ms': 0.0,
        'last_error': '',
    })


def snapshot():
    # A copy prevents callers accidentally modifying live counters.
    result = dict(_STATS)
    result['total_ms'] = round(result['total_ms'], 3)
    result['peak_ms'] = round(result['peak_ms'], 3)
    return result


def _identifier(blender_id):
    """Only an explicit Blender RNA identifier is trusted for filtering."""
    rna = getattr(blender_id, 'bl_rna', None)
    return getattr(rna, 'identifier', None)


def should_run_depsgraph(depsgraph):
    """Unknown or empty updates must not be dropped, avoiding missed actions."""
    if depsgraph is None:
        return True
    updates = getattr(depsgraph, 'updates', None)
    if updates is None:
        return True
    try:
        count = 0
        for update in updates:
            count += 1
            # Never scan an unbounded update stream: prefer correctness.
            if count > 4096:
                return True
            ident = _identifier(update.id)
            if ident not in _UNRELATED_IDS:
                return True
        return count == 0
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return True


def dispatch(event, scene, depsgraph, callback):
    """Run synchronous callback, guarding recursion and gathering telemetry.

 Errors are recorded *and re-raised* so Blender logs preserve tracebacks.
 No time-based throttling is used: all frame updates remain eligible.
 """
    global _RUNNING
    if event not in ('frame', 'depsgraph'):
        raise ValueError('Unknown handler event: ' + str(event))
    _STATS['calls'] += 1
    _STATS[event + '_calls'] += 1
    if _RUNNING:
        _STATS['skipped'] += 1
        _STATS['reentrant_skips'] += 1
        return False
    if event == 'depsgraph' and not should_run_depsgraph(depsgraph):
        _STATS['skipped'] += 1
        return False
    _RUNNING = True
    start = perf_counter_ns()
    try:
        callback(scene, depsgraph)
        return True
    except Exception as exc:
        _STATS['errors'] += 1
        _STATS['last_error'] = type(exc).__name__ + ': ' + str(exc)[:200]
        raise
    finally:
        elapsed = (perf_counter_ns() - start) / 1e6
        _STATS['executed'] += 1
        _STATS['total_ms'] += elapsed
        _STATS['peak_ms'] = max(_STATS['peak_ms'], elapsed)
        _RUNNING = False


reset()
