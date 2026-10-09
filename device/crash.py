"""What to do after a crash: classify it, count it, wipe bad saved state only when the
crash looks like bad saved data, and say how long to hold before the reset.
Imported lazily by code.py's crash handler only: the sign has little RAM to spare
(docs/reliability.md). Counters live in health.py."""
import health

DATA_CRASHES = (MemoryError, ValueError, KeyError)


def is_data_crash(exc):
    """True when the crash looks like bad saved data (counts toward wiping stops/Wi-Fi).
    Everything else (AttributeError, ImportError, NameError, SyntaxError, TypeError,
    OSError ...) is a code or environment bug: wiping the user's settings cannot fix it,
    so it never counts toward a wipe (see docs/reliability.md)."""
    return isinstance(exc, DATA_CRASHES)


def hold_seconds(bugs, steps):
    """How long to sit still after the `bugs`-th consecutive code-bug crash (1-based),
    so a host that is still writing files is not cut off by yet another hard reset."""
    return steps[min(max(bugs, 1), len(steps)) - 1]


def bugs(nvm=None):
    """Consecutive code-bug crashes (drives the hold; never a reason to wipe anything)."""
    return health.load3(nvm)[2]


def note_crash(nvm=None):
    """Count a software-detected data crash; returns the new count."""
    crashes, quiet, bug = health.load3(nvm)
    crashes = min(crashes + 1, health.MAX_COUNT)
    health.save(crashes, quiet, bug, nvm)
    return crashes


def note_bug(nvm=None):
    """Count a code-bug crash; returns the new count."""
    crashes, quiet, bug = health.load3(nvm)
    bug = min(bug + 1, health.MAX_COUNT)
    health.save(crashes, quiet, bug, nvm)
    return bug


def escalate(crashes, stops_at, all_at):
    """'none', 'stops' (forget saved stops) or 'all' (forget stops and Wi-Fi)."""
    if crashes >= all_at:
        return "all"
    if crashes >= stops_at:
        return "stops"
    return "none"


def handle_crash(picks_mod, creds_mod, stops_at, all_at, nvm=None, exc=None):
    """Count the crash. Only a crash that looks like bad saved data (is_data_crash)
    can escalate to wiping persisted state; a code bug is counted separately and
    returns 'none'. Returns what was cleared: 'none', 'stops' or 'all'."""
    if exc is not None and not is_data_crash(exc):
        note_bug(nvm)
        return "none"
    what = escalate(note_crash(nvm), stops_at, all_at)
    if what != "none":
        try:
            picks_mod.clear()
        except Exception:
            pass
    if what == "all":
        try:
            creds_mod.clear()
        except Exception:
            pass
        health.save(0, 0, 0, nvm)    # start counting again from a fresh state
    return what


def handle(exc, picks_mod, creds_mod, config):
    """The whole crash handler: print, count, wipe if due. Returns seconds to hold before
    the reset (3 for bad-data crashes, longer and growing for code bugs)."""
    try:
        import sys
        sys.print_exception(exc)
    except Exception:
        pass
    print("cleared:", handle_crash(picks_mod, creds_mod, config.CRASHES_CLEAR_STOPS,
                                   config.CRASHES_CLEAR_ALL, None, exc))
    if is_data_crash(exc):
        return 3
    return hold_seconds(bugs(), config.BUG_HOLD_S)
