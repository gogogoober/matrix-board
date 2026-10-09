"""Stand-in for CircuitPython's `board`: every pin name resolves to a string."""


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return "PIN_" + name
