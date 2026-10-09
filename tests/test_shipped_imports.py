"""A shipped module must not import anything the board doesn't have."""
import ast
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import deploy  # noqa: E402

# CircuitPython built-ins this project is allowed to use.
BUILTIN = {
    "time", "gc", "os", "board", "busio", "digitalio", "displayio", "terminalio",
    "framebufferio", "rgbmatrix", "microcontroller", "json", "math", "supervisor",
}
FORBIDDEN = {"typing", "dataclasses", "pathlib", "PIL", "abc", "enum", "functools", "collections.abc"}


def board_libs():
    lib = os.path.join(ROOT, "backup", "original-circuitpy", "lib")
    return {n.split(".")[0] for n in os.listdir(lib)}


def imports(path):
    with open(path) as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


class ShippedImportsTest(unittest.TestCase):
    def test_every_import_is_available_on_the_board(self):
        shipped = {m[:-3] for m in deploy.SHIPPED}
        allowed = shipped | BUILTIN | board_libs()
        for m in deploy.SHIPPED:
            path = os.path.join(ROOT, "device", m)
            self.assertTrue(os.path.isfile(path), m + " listed in SHIPPED but missing")
            bad = imports(path) - allowed
            self.assertFalse(bad, "%s imports things the board lacks: %s" % (m, sorted(bad)))
            self.assertFalse(imports(path) & FORBIDDEN, m + " uses a desktop-only module")

    def test_every_device_file_is_listed_in_shipped(self):
        on_disk = {f for f in os.listdir(os.path.join(ROOT, "device")) if f.endswith(".py")}
        self.assertEqual(on_disk, set(deploy.SHIPPED))


if __name__ == "__main__":
    unittest.main()
