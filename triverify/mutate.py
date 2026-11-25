"""Mutation testing restricted to the reference solution's added lines.

The question we ask is narrow and useful: *if an implementation got this feature
slightly wrong, would the feature tests notice?* So mutants are only generated on
lines the reference patch adds, using classic operators:

    comparison flips (``<`` → ``<=``, ``==`` → ``!=``, ``in`` → ``not in`` …),
    boolean operator swap, condition negation, ``not`` removal,
    integer +1, ``True``/``False`` swap, arithmetic operator swap,
    ``return x`` → ``return None``, ``raise …`` → ``pass``,
    call-statement deletion, ``x = expr`` → ``x = None``, and reversed
    ``for`` iteration order (catches ordering bugs).

Each mutant is a whole-module rewrite produced with :func:`ast.unparse` and is
compiled before use, so syntactically invalid mutants never reach the tests.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass

_CMP_SWAP = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}
_BIN_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.FloorDiv,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mult,
    ast.Mod: ast.FloorDiv,
}


@dataclass(frozen=True)
class Mutant:
    path: str
    line: int
    operator: str
    description: str
    source: str


def _candidates(tree: ast.AST, lines: set[int]) -> list[tuple[int, str]]:
    """``(walk_index, operator)`` pairs for nodes that sit on added lines."""
    found: list[tuple[int, str]] = []
    for idx, node in enumerate(ast.walk(tree)):
        line = getattr(node, "lineno", None)
        if line is None or line not in lines:
            continue
        if isinstance(node, ast.Compare) and type(node.ops[0]) in _CMP_SWAP:
            found.append((idx, "cmp"))
        elif isinstance(node, ast.BoolOp):
            found.append((idx, "boolop"))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            found.append((idx, "not"))
        elif isinstance(node, ast.If):
            found.append((idx, "negate-if"))
        elif isinstance(node, ast.BinOp) and type(node.op) in _BIN_SWAP:
            found.append((idx, "binop"))
        elif isinstance(node, ast.Constant) and type(node.value) is bool:
            found.append((idx, "bool"))
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            found.append((idx, "int"))
        elif isinstance(node, ast.Return) and node.value is not None and not (
            isinstance(node.value, ast.Constant) and node.value.value is None
        ):
            found.append((idx, "return-none"))
        elif isinstance(node, ast.Raise):
            found.append((idx, "raise-pass"))
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            found.append((idx, "stmt-delete"))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None and not isinstance(
            node.value, ast.Constant
        ):
            found.append((idx, "assign-none"))
        elif isinstance(node, ast.For):
            found.append((idx, "reverse-iter"))
    return found


def _apply(tree: ast.AST, index: int, op: str) -> tuple[ast.AST, str] | None:
    tree = copy.deepcopy(tree)
    target = next(n for i, n in enumerate(ast.walk(tree)) if i == index)
    desc = ""
    if op == "cmp":
        old = type(target.ops[0])
        target.ops[0] = _CMP_SWAP[old]()
        desc = f"{old.__name__} → {_CMP_SWAP[old].__name__}"
    elif op == "boolop":
        old = type(target.op)
        target.op = ast.Or() if old is ast.And else ast.And()
        desc = f"{old.__name__} → {type(target.op).__name__}"
    elif op == "binop":
        old = type(target.op)
        target.op = _BIN_SWAP[old]()
        desc = f"{old.__name__} → {_BIN_SWAP[old].__name__}"
    elif op == "bool":
        target.value = not target.value
        desc = f"{not target.value} → {target.value}"
    elif op == "int":
        target.value = target.value + 1
        desc = f"{target.value - 1} → {target.value}"
    elif op == "assign-none":
        target.value = ast.Constant(value=None)
        desc = "assign None"
    elif op == "reverse-iter":
        target.iter = ast.Call(
            func=ast.Name(id="reversed", ctx=ast.Load()),
            args=[ast.Call(func=ast.Name(id="list", ctx=ast.Load()), args=[target.iter], keywords=[])],
            keywords=[],
        )
        desc = "iterate in reverse order"
    elif op in {"not", "negate-if", "return-none", "raise-pass", "stmt-delete"}:
        parent_holder = None
        for parent in ast.walk(tree):
            for field, value in ast.iter_fields(parent):
                if value is target:
                    parent_holder = (parent, field, None)
                elif isinstance(value, list) and any(v is target for v in value):
                    parent_holder = (parent, field, next(i for i, v in enumerate(value) if v is target))
        if parent_holder is None:
            return None
        parent, field, pos = parent_holder
        if op == "not":
            replacement: ast.AST = target.operand
            desc = "drop `not`"
        elif op == "negate-if":
            target.test = ast.UnaryOp(op=ast.Not(), operand=target.test)
            replacement = target
            desc = "negate `if` condition"
        elif op == "return-none":
            replacement = ast.Return(value=ast.Constant(value=None))
            desc = "return None"
        elif op == "stmt-delete":
            replacement = ast.Pass()
            desc = "delete call statement"
        else:
            replacement = ast.Pass()
            desc = "raise → pass"
        if pos is None:
            setattr(parent, field, replacement)
        else:
            getattr(parent, field)[pos] = replacement
    ast.fix_missing_locations(tree)
    return tree, desc


def generate(path: str, source: str, added_lines: set[int], limit: int) -> list[Mutant]:
    tree = ast.parse(source)
    cands = _candidates(tree, added_lines)
    mutants: list[Mutant] = []
    seen: set[str] = set()
    walk = list(ast.walk(tree))
    for idx, op in cands:
        applied = _apply(tree, idx, op)
        if applied is None:
            continue
        new_tree, desc = applied
        try:
            new_source = ast.unparse(new_tree)
            compile(new_source, path, "exec")
        except (SyntaxError, ValueError):
            continue
        if new_source in seen:
            continue
        seen.add(new_source)
        mutants.append(Mutant(path, getattr(walk[idx], "lineno", 0), op, desc, new_source))
    return spread(mutants, limit)


def spread(items: list[Mutant], limit: int) -> list[Mutant]:
    """Pick ``limit`` items evenly across the list (deterministic, keeps operator mix)."""
    if len(items) <= limit:
        return items
    step = len(items) / limit
    return [items[int(i * step)] for i in range(limit)]
