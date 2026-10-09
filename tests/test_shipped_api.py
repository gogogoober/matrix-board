"""Every `module.attr` / `from module import name` that shipped code uses on another
shipped module must exist in that module. (The 2026-10-09 crash loop was code.py calling
picks.with_names while the board still had an old picks.py.)"""
import ast
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import deploy  # noqa: E402

DEVICE = os.path.join(ROOT, "device")


def tree(m):
    with open(os.path.join(DEVICE, m + ".py")) as f:
        return ast.parse(f.read())


def top_level_names(m):
    names = set()
    for node in tree(m).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


def uses(m, shipped):
    """(module, attr) pairs that module `m` reads from other shipped modules."""
    t = tree(m)
    imported = set()
    out = set()
    for node in ast.walk(t):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names if a.name in shipped and not a.asname)
        elif isinstance(node, ast.ImportFrom) and node.module in shipped:
            out.update((node.module, a.name) for a in node.names)
    for node in ast.walk(t):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id in imported):
            out.add((node.value.id, node.attr))
    return out


class ShippedApiTest(unittest.TestCase):
    def test_every_cross_module_name_exists(self):
        shipped = {m[:-3] for m in deploy.SHIPPED}
        tops = {m: top_level_names(m) for m in shipped}
        checked = 0
        for m in sorted(shipped):
            for mod, attr in sorted(uses(m, shipped)):
                checked += 1
                self.assertIn(attr, tops[mod], "%s.py uses %s.%s, which %s.py does not define"
                              % (m, mod, attr, mod))
        self.assertGreater(checked, 50)       # the scan really found the calls

    def test_the_check_catches_a_missing_function(self):
        shipped = {m[:-3] for m in deploy.SHIPPED}
        self.assertIn(("picks", "with_names"), uses("code", shipped))
        self.assertNotIn("no_such_function", top_level_names("picks"))
        self.assertIn("with_names", top_level_names("picks"))


if __name__ == "__main__":
    unittest.main()
