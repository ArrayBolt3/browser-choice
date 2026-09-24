#!/usr/bin/python3 -Bsu

# Copyright (C) 2025 - 2025 ENCRYPTED SUPPORT LLC <adrelanos@whonix.org>
# See the file COPYING for copying conditions.

"""
Regression guard for CodeQL py/super-not-enclosing-class.

A two-argument super(Cls, self) whose Cls is NOT the enclosing class starts
MRO resolution at the wrong point and SKIPS the immediate base's __init__.
For a QObject / QDialog subclass that drops the Qt parent-child ownership set
up by the base __init__(parent). Every super() call must be either the bare
zero-argument form or name its own enclosing class.
"""

import ast
import unittest
from pathlib import Path

PACKAGE_DIR = (
    Path(__file__).resolve().parent.parent
    / "usr"
    / "lib"
    / "python3"
    / "dist-packages"
    / "browser_choice"
)


def find_bad_super_calls(source: str, filename: str) -> list[str]:
    """
    Return a description for every super(Cls, ...) whose Cls is not the
    nearest enclosing class. Bare super() is always accepted.
    """
    tree = ast.parse(source, filename=filename)
    violations: list[str] = []

    def visit(node: ast.AST, class_stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, class_stack + [child.name])
                continue
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "super"
                and child.args
            ):
                first_arg = child.args[0]
                enclosing = class_stack[-1] if class_stack else None
                if (
                    not isinstance(first_arg, ast.Name)
                    or first_arg.id != enclosing
                ):
                    got = (
                        first_arg.id
                        if isinstance(first_arg, ast.Name)
                        else ast.dump(first_arg)
                    )
                    violations.append(
                        f"{filename}:{child.lineno}: super({got}, ...) "
                        f"inside class {enclosing}"
                    )
            visit(child, class_stack)

    visit(tree, [])
    return violations


class TestSuperEnclosingClass(unittest.TestCase):
    """
    Every super() in the package uses the bare form or its enclosing class.
    """

    def test_no_wrong_class_super(self) -> None:
        all_violations: list[str] = []
        module_list = sorted(PACKAGE_DIR.glob("*.py"))
        self.assertTrue(module_list, f"no modules under {PACKAGE_DIR}")
        for module_path in module_list:
            source = module_path.read_text(encoding="utf-8")
            all_violations.extend(
                find_bad_super_calls(source, module_path.name)
            )
        self.assertEqual(
            [],
            all_violations,
            "super() called with a non-enclosing class:\n"
            + "\n".join(all_violations),
        )

    def test_detects_planted_violation(self) -> None:
        """
        Canary: the checker must FLAG a known-bad super(Base, self) and
        ACCEPT both the bare form and the correct enclosing-class form.
        """
        bad = "class Enclosing(Base):\n    def __init__(self):\n" \
            "        super(Base, self).__init__()\n"
        self.assertEqual(1, len(find_bad_super_calls(bad, "canary.py")))

        bare = "class Enclosing(Base):\n    def __init__(self):\n" \
            "        super().__init__()\n"
        self.assertEqual([], find_bad_super_calls(bare, "canary.py"))

        good = "class Enclosing(Base):\n    def __init__(self):\n" \
            "        super(Enclosing, self).__init__()\n"
        self.assertEqual([], find_bad_super_calls(good, "canary.py"))


if __name__ == "__main__":
    unittest.main()
