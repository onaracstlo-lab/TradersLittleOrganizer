"""Offline F401-oriented import audit of every source and test Python file.

This checks the entire staged tree, unlike older per-file AST smoke tests.
It is an additional guard only: release preflight must still run Ruff.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path


def audit_source(source: str, *, filename: str = "<fixture>") -> list[str]:
    """Report import names never loaded, except documented/noqa re-exports."""
    tree = ast.parse(source, filename=filename)
    used = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    # In a module, __all__ may intentionally re-export an import by string.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                used.update(
                    e.value for e in node.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                )
    lines = source.splitlines()
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates = [(alias.asname or alias.name.split(".")[0], alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            candidates = [(alias.asname or alias.name, alias.name) for alias in node.names if alias.name != "*"]
        else:
            continue
        inline = lines[node.lineno - 1].lower() if node.lineno <= len(lines) else ""
        comment = inline.split("#", 1)[1].strip() if "#" in inline else ""
        if comment.startswith("noqa"):
            directives = comment[4:].strip()
            if not directives or (directives.startswith(":") and "f401" in directives):
                continue
        for local, origin in candidates:
            # Explicit self-aliases (`from x import y as y`) are re-exports.
            if local in used or (isinstance(node, ast.ImportFrom) and any(
                a.asname == a.name == local for a in node.names
            )):
                continue
            problems.append(f"{filename}:{node.lineno}: unused import {origin} as {local} (F401-oriented)")
    return problems


def audit_tree(root: Path) -> tuple[int, list[str]]:
    inspected = 0
    errors: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in {"__pycache__", ".pytest_cache", ".git"} for part in path.parts):
            continue
        inspected += 1
        errors.extend(audit_source(path.read_text(encoding="utf-8"), filename=path.relative_to(root).as_posix()))
    return inspected, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    count, errors = audit_tree(args.root)
    for error in errors:
        print(error)
    print(f"Offline import-use audit: {count} Python files checked; {len(errors)} issues")
    if errors:
        print("FAIL: Repair unused imports and run Ruff on the native build host.")
        return 1
    print("PASS: no unused imports detected by AST audit. Native Ruff remains mandatory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
