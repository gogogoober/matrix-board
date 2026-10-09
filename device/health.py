"""Liveness tracking and the few bytes that must survive a reboot.

Health is pure logic: it is told when a fetch worked and says what recovery
step is due. The counters live in microcontroller.nvm (like creds.py and
picks.py): b"HB2", data crashes, quiet reboots,
code-bug crashes, checksum. Anything invalid reads
as zero. See docs/reliability.md.
"""
OK, RADIO, REBOOT = 0, 1, 2
MAGIC = b"HB2"
OFFSET = 1024
MAX_COUNT = 250


def retry_delay(fails, base, cap):
    """Seconds to wait after `fails` consecutive failures: base, 2x, 4x ... capped."""
    d = base
    for _ in range(fails - 1):
        d *= 2
        if d >= cap:
            return cap
    return cap if d > cap else d


def reboot_after(base, cap, quiet):
    """Quiet time before a reboot, doubling for every earlier reboot that did not help."""
    d = base
    for _ in range(quiet):
        d *= 2
        if d >= cap:
            return cap
    return cap if d > cap else d


class Health:
    """Tracks the last good fetch. action() says what to do when the data stopped."""

    def __init__(self, now, radio_after, reboot_after_s):
        self.radio_after = radio_after
        self.reboot_after = reboot_after_s
        self.last_ok = now
        self.radio_done = False

    def good(self, now):
        self.last_ok = now
        self.radio_done = False

    def reset(self, now):
        """Restart the clock without claiming data arrived (e.g. after setup mode)."""
        self.last_ok = now
        self.radio_done = False

    def quiet(self, now):
        return now - self.last_ok

    def action(self, now):
        q = now - self.last_ok
        if q >= self.reboot_after:
            return REBOOT
        if q >= self.radio_after and not self.radio_done:
            self.radio_done = True
            return RADIO
        return OK


# --- counters in NVM ---------------------------------------------------------

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


def _nvm(nvm):
    if nvm is not None:
        return nvm
    import microcontroller
    return microcontroller.nvm


def _checksum(a, b, c):
    return (a + b + c + 0x3C) & 0xFF


def _load3(nvm=None):
    try:
        mem = _nvm(nvm)
        if bytes(mem[OFFSET:OFFSET + 3]) != MAGIC:
            return 0, 0, 0
        a, b, c, k = mem[OFFSET + 3], mem[OFFSET + 4], mem[OFFSET + 5], mem[OFFSET + 6]
        if k != _checksum(a, b, c) or a > MAX_COUNT or b > MAX_COUNT or c > MAX_COUNT:
            return 0, 0, 0
        return a, b, c
    except Exception:
        return 0, 0, 0


def load(nvm=None):
    """(data_crashes, quiet_reboots); (0, 0) if the record is missing or damaged."""
    a, b, _ = _load3(nvm)
    return a, b


def bugs(nvm=None):
    """Consecutive code-bug crashes (drives the hold; never a reason to wipe anything)."""
    return _load3(nvm)[2]


def _save(crashes, quiet, bug, nvm=None):
    """Write only when something changed (NVM has a finite write life)."""
    if _load3(nvm) == (crashes, quiet, bug):
        return
    try:
        mem = _nvm(nvm)
        mem[OFFSET:OFFSET + 7] = MAGIC + bytes((crashes, quiet, bug, _checksum(crashes, quiet, bug)))
    except Exception:
        pass


def note_crash(nvm=None):
    """Count a software-detected data crash; returns the new count."""
    crashes, quiet, bug = _load3(nvm)
    crashes = min(crashes + 1, MAX_COUNT)
    _save(crashes, quiet, bug, nvm)
    return crashes


def note_bug(nvm=None):
    """Count a code-bug crash; returns the new count."""
    crashes, quiet, bug = _load3(nvm)
    bug = min(bug + 1, MAX_COUNT)
    _save(crashes, quiet, bug, nvm)
    return bug


def note_healthy(nvm=None):
    """The app ran long enough to be trusted: forget earlier crashes."""
    _, quiet, _ = _load3(nvm)
    _save(0, quiet, 0, nvm)


def note_quiet_reboot(nvm=None):
    crashes, quiet, bug = _load3(nvm)
    _save(crashes, min(quiet + 1, MAX_COUNT), bug, nvm)


def clear_quiet(nvm=None):
    crashes, _, bug = _load3(nvm)
    _save(crashes, 0, bug, nvm)


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
        _save(0, 0, 0, nvm)    # start counting again from a fresh state
    return what
