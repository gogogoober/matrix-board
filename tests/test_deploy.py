"""tools/deploy.py: durable writes in the right order, and the manifest check."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import deploy  # noqa: E402


class DeployTest(unittest.TestCase):
    def test_code_py_is_written_last(self):
        self.assertEqual(deploy.SHIPPED[-1], "code.py")

    def test_put_writes_flushes_and_syncs(self):
        calls = []
        real = deploy._flush_to_disk
        deploy._flush_to_disk = lambda fd: calls.append(fd)
        old = deploy.DRIVE
        try:
            with tempfile.TemporaryDirectory() as d:
                deploy.DRIVE = Path(d)
                deploy.put(deploy.DEVICE / "hw.py", "hw.py")
                self.assertEqual((Path(d) / "hw.py").read_bytes(), (deploy.DEVICE / "hw.py").read_bytes())
        finally:
            deploy._flush_to_disk, deploy.DRIVE = real, old
        self.assertEqual(len(calls), 1)

    def test_parse_takes_the_last_manifest(self):
        text = "manifest: a.py=1 b.py=2\nstuff\nmanifest: a.py=3 code.py=40\nready"
        self.assertEqual(deploy.parse_manifest(text), {"a.py": 3, "code.py": 40})
        self.assertIsNone(deploy.parse_manifest("nothing here"))

    def test_compare_reports_stale_and_missing(self):
        want = {"a.py": 10, "b.py": 20, "c.py": 30}
        self.assertEqual(deploy.compare_manifest(want, dict(want)), [])
        got = {"a.py": 10, "b.py": 19, "extra.py": 5}
        problems = deploy.compare_manifest(want, got)
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("STALE" in p and "b.py" in p for p in problems))
        self.assertTrue(any("MISSING" in p and "c.py" in p for p in problems))

    def test_verify_reports_a_crash_and_passes_a_match(self):
        want = deploy.expected_sizes()
        line = "manifest: " + " ".join("%s=%d" % kv for kv in want.items()) + "\n"
        real = deploy.read_serial
        try:
            deploy.read_serial = lambda *a, **k: line + "ready: subway sign\n"
            self.assertTrue(deploy.verify(1))
            deploy.read_serial = lambda *a, **k: line + "CRASH: AttributeError x\n"
            self.assertFalse(deploy.verify(1))
            deploy.read_serial = lambda *a, **k: ""
            self.assertFalse(deploy.verify(1))
        finally:
            deploy.read_serial = real

    def test_serial_reader_never_writes(self):
        import inspect
        src = inspect.getsource(deploy.read_serial)
        self.assertIn("O_RDONLY", src)
        self.assertNotIn("os.write", src)


if __name__ == "__main__":
    unittest.main()
