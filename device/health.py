"""Liveness tracking and the few bytes that must survive a reboot.

Health is pure logic: it is told when a fetch worked and says what recovery
step is due. The counters live in microcontroller.nvm (like creds.py and
picks.py): b"HB1", crashes, quiet reboots, checksum. Anything invalid reads
as zero. See docs/reliability.md.
"""
OK, RADIO, REBOOT = 0, 1, 2
MAGIC = b"HB1"
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

def _nvm(nvm):
    if nvm is not None:
        return nvm
    import microcontroller
    return microcontroller.nvm


def _checksum(a, b):
    return (a + b + 0x3C) & 0xFF


def load(nvm=None):
    """(crashes, quiet_reboots); (0, 0) if the record is missing or damaged."""
    try:
        mem = _nvm(nvm)
        if bytes(mem[OFFSET:OFFSET + 3]) != MAGIC:
            return 0, 0
        a, b, c = mem[OFFSET + 3], mem[OFFSET + 4], mem[OFFSET + 5]
        if c != _checksum(a, b) or a > MAX_COUNT or b > MAX_COUNT:
            return 0, 0
        return a, b
    except Exception:
        return 0, 0


def _save(crashes, quiet, nvm=None):
    """Write only when something changed (NVM has a finite write life)."""
    if load(nvm) == (crashes, quiet):
        return
    try:
        mem = _nvm(nvm)
        mem[OFFSET:OFFSET + 6] = MAGIC + bytes((crashes, quiet, _checksum(crashes, quiet)))
    except Exception:
        pass


def note_crash(nvm=None):
    """Count a software-detected crash; returns the new count."""
    crashes, quiet = load(nvm)
    crashes = min(crashes + 1, MAX_COUNT)
    _save(crashes, quiet, nvm)
    return crashes


def note_healthy(nvm=None):
    """The app ran long enough to be trusted: forget earlier crashes."""
    crashes, quiet = load(nvm)
    _save(0, quiet, nvm)


def note_quiet_reboot(nvm=None):
    crashes, quiet = load(nvm)
    _save(crashes, min(quiet + 1, MAX_COUNT), nvm)


def clear_quiet(nvm=None):
    crashes, quiet = load(nvm)
    _save(crashes, 0, nvm)


def escalate(crashes, stops_at, all_at):
    """'none', 'stops' (forget saved stops) or 'all' (forget stops and Wi-Fi)."""
    if crashes >= all_at:
        return "all"
    if crashes >= stops_at:
        return "stops"
    return "none"


def handle_crash(picks_mod, creds_mod, stops_at, all_at, nvm=None):
    """Count the crash and wipe bad persisted state if crashes keep repeating.
    Returns what was cleared: 'none', 'stops' or 'all'."""
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
        _save(0, 0, nvm)    # start counting again from a fresh state
    return what
