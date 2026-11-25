"""Static analysis of the target repository (no target code is imported).

Produces a compact *capability map* that grounds the proposal prompt: the public
surface of each source module, the existing test modules, and the extension
points (subclassable classes, keyword parameters of public constructors).
Everything is sorted so the map, and therefore the prompt, is deterministic.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModuleSurface:
    path: str
    classes: dict[str, list[str]] = field(default_factory=dict)
    functions: list[str] = field(default_factory=list)
    init_kwargs: dict[str, list[str]] = field(default_factory=dict)


def _first_line(node: ast.AST) -> str:
    doc = ast.get_docstring(node) if isinstance(node, (ast.ClassDef, ast.FunctionDef)) else None
    return (doc or "").strip().splitlines()[0][:90] if doc else ""


def module_surface(path: Path, rel: str) -> ModuleSurface:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    surface = ModuleSurface(path=rel)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            methods = sorted(
                {
                    n.name
                    for n in node.body
                    if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
                }
            )
            surface.classes[node.name] = methods
            for n in node.body:
                if isinstance(n, ast.FunctionDef) and n.name == "__init__":
                    kwargs = [a.arg for a in n.args.args[1:]] + [a.arg for a in n.args.kwonlyargs]
                    surface.init_kwargs[node.name] = kwargs
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            surface.functions.append(node.name)
    surface.functions = sorted(set(surface.functions))
    return surface


def capability_map(repo: Path, source_dirs: tuple[str, ...], tests_dir: str) -> dict:
    modules = []
    for src in source_dirs:
        for py in sorted((repo / src).rglob("*.py")):
            rel = py.relative_to(repo).as_posix()
            if py.name.startswith("_"):  # private helpers and __init__ re-exports
                continue
            modules.append(module_surface(py, rel))
    tests = sorted(p.relative_to(repo).as_posix() for p in (repo / tests_dir).rglob("test_*.py"))
    return {
        "modules": [
            {
                "path": m.path,
                "classes": {k: v for k, v in sorted(m.classes.items())},
                "constructor_kwargs": {k: v for k, v in sorted(m.init_kwargs.items())},
                "functions": m.functions,
            }
            for m in modules
        ],
        "test_modules": tests,
    }


def render_capability_map(cmap: dict, max_methods: int = 14) -> str:
    """Human/LLM-readable rendering, bounded in size."""
    lines: list[str] = []
    for m in cmap["modules"]:
        if not m["classes"] and not m["functions"]:
            continue
        lines.append(f"## {m['path']}")
        for cls, methods in m["classes"].items():
            shown = ", ".join(methods[:max_methods]) + (" …" if len(methods) > max_methods else "")
            kw = m["constructor_kwargs"].get(cls)
            kw_s = f"  init({', '.join(kw[:16])}{' …' if kw and len(kw) > 16 else ''})" if kw else ""
            lines.append(f"- class {cls}: {shown}{kw_s}")
        if m["functions"]:
            lines.append(f"- functions: {', '.join(m['functions'][:30])}")
    lines.append("## existing test modules")
    lines.append(", ".join(cmap["test_modules"]))
    return "\n".join(lines)


def enclosing_symbols(source: str, lines: set[int]) -> set[str]:
    """Qualified names of the functions/classes that contain the given lines."""
    tree = ast.parse(source)
    found: set[str] = set()

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                start, end = child.lineno, getattr(child, "end_lineno", child.lineno)
                if any(start <= ln <= end for ln in lines):
                    found.add(name)
                visit(child, name + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    # Keep only the innermost names (drop a class if one of its methods matched).
    return {s for s in found if not any(o != s and o.startswith(s + ".") for o in found)} or {
        "<module>"
    }


def referenced_api(test_source: str, module: str) -> set[str]:
    """Attributes of ``module`` referenced by a test file (``click.X`` → ``X``)."""
    tree = ast.parse(test_source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == module:
                names.add(node.attr)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == module:
            names.update(a.name for a in node.names)
    return names
