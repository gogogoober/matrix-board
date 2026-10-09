"""Wi-Fi credentials saved by the setup portal, in microcontroller.nvm.

NVM is used instead of a file because CIRCUITPY is read-only to code while a
computer mounts it. Record: b"WF1", ssid length, password length, ssid,
password, 1-byte checksum. Anything that does not validate reads as "none".
Never print what load() returns.
"""
MAGIC = b"WF1"
MAX_SSID = 32
MAX_PASSWORD = 63


def _nvm(nvm):
    if nvm is not None:
        return nvm
    import microcontroller
    return microcontroller.nvm


def _checksum(data):
    total = 0
    for b in data:
        total = (total + b) & 0xFF
    return total ^ 0x5A


def load(nvm=None):
    """(ssid, password) or None."""
    try:
        mem = _nvm(nvm)
        if bytes(mem[0:3]) != MAGIC:
            return None
        s = mem[3]
        p = mem[4]
        if s < 1 or s > MAX_SSID or p > MAX_PASSWORD:
            return None
        end = 5 + s + p
        body = bytes(mem[0:end])
        if mem[end] != _checksum(body):
            return None
        return str(body[5:5 + s], "utf-8"), str(body[5 + s:end], "utf-8")
    except Exception:
        return None


def save(ssid, password, nvm=None):
    """Store credentials. Raises ValueError if they do not fit."""
    s = ssid.encode("utf-8")
    p = password.encode("utf-8")
    if not 1 <= len(s) <= MAX_SSID or len(p) > MAX_PASSWORD:
        raise ValueError("credentials too long")
    body = MAGIC + bytes((len(s), len(p))) + s + p
    rec = body + bytes((_checksum(body),))
    mem = _nvm(nvm)
    mem[0:len(rec)] = rec


def clear(nvm=None):
    mem = _nvm(nvm)
    mem[0:3] = b"\xff\xff\xff"
