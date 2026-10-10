"""Software double-tap detection from raw accelerometer samples.

A tap shows up as a sudden change between consecutive samples (measured on
this board: 0.8 to 3 g, lasting 40 to 80 ms). Two such bumps 0.12 to 0.6 s
apart make a double tap. The LIS3DH's built-in detector was unreliable on this
board, so this runs on the raw samples. No display, no network.
"""
G = 9.80665


class DoubleTap:
    def __init__(self, onset_g=0.5, min_gap=0.12, max_gap=0.6, refractory=0.1, lockout=0.5):
        self.onset_g = onset_g
        self.min_gap = min_gap          # shorter than this is the same bump ringing
        self.max_gap = max_gap
        self.refractory = refractory
        self.lockout = lockout          # quiet time after a double tap (no triples)
        self.prev = None
        self.prev_t = 0.0
        self.last_tap = -1000.0
        self.locked_until = 0.0
        self.pending = False            # one tap seen, still waiting to learn if a second follows

    def single(self, now):
        """True once, max_gap after a lone tap (a double tap never counts as a single)."""
        if self.pending and now - self.last_tap > self.max_gap:
            self.pending = False
            return True
        return False

    def update(self, now, x, y, z):
        """Feed one sample (m/s^2). Returns True when a double tap completes."""
        prev = self.prev
        prev_t = self.prev_t
        self.prev = (x, y, z)
        self.prev_t = now
        if prev is None or now - prev_t > 0.05:
            return False   # first sample, or we were busy (network): just reseed
        d = (((x - prev[0]) ** 2 + (y - prev[1]) ** 2 + (z - prev[2]) ** 2) ** 0.5) / G
        if d < self.onset_g or now < self.locked_until:
            return False
        gap = now - self.last_tap
        if gap < self.refractory:
            return False   # still the same bump
        self.last_tap = now
        if self.min_gap <= gap <= self.max_gap:
            self.last_tap = -1000.0
            self.pending = False
            self.locked_until = now + self.lockout
            return True
        self.pending = True
        return False
