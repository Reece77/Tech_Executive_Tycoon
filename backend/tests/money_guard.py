"""The float-money guard (M36r, Codex review 7; ADR-0003): an AST scan of `tst/sim/` for money
arithmetic done in binary floats.

A **money** expression names cents: a variable, attribute or function whose name contains
"cents" (`price_cents`, `q.tax_cents`, `app_revenue_cents(...)`), directly or through `min`,
`max`, `abs`, `sum`, `round` or `int`. A **float** expression is a float literal, a `float()`
call, a true division `/`, a `math` function, a field, parameter or function declared `float`
anywhere in `tst/sim/` (by annotation), or a local assigned from any of these. Anything inside
`exact()`, `Fraction()`, `times()`, `pct_of()` or `to_millicents()` (tst.sim.money's exact
helpers) is exact, and f-strings are display.

A violation is money multiplied by a float, or money divided with `/` outside exact
arithmetic. Each is fixed, or carries an allow-list comment on its line or the line above,
`# money-exact: <why>`:

- `rate`: a unit rate in float cents (a price or cost a unit, a wafer, a CU-month), not an
  amount; the amount it makes is rounded once where it is posted;
- `ratio`: a ratio, share, weight, score or threshold between amounts, not money;
- `estimate`: a float estimate only ranked or compared, never posted or stored;
- `display`: text for the player;
- `Fraction`: exact rational arithmetic the scan cannot type (checked by hand).

DEFERRED lists lines in files another lane is editing in flight: they are recorded in the
M36r audit table and handed to that lane."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SIM = Path(__file__).resolve().parents[1] / "tst" / "sim"
ALLOW = "money-exact:"
EXACT_CALLS = frozenset({"exact", "Fraction", "times", "pct_of", "to_millicents"})
THROUGH = frozenset({"min", "max", "abs", "sum", "round", "int"})
MATH = frozenset({"sqrt", "exp", "log", "log10", "pow", "tanh", "erf", "log1p", "expm1"})
SKIP_FILES = frozenset({"money.py"})
# M43r (Codex review 9 finding 10): money carried under other names. A name is money when one
# of its words (split on "_") is one of these, or it contains "cents".
ALIASES = frozenset(
    {
        "revenue",
        "revenues",
        "sales",
        "cost",
        "costs",
        "amount",
        "fee",
        "fees",
        "spend",
        "payout",
        "debt",
        "interest",
        "ebitda",
        "capex",
    }
)
FLOAT_ITERS = frozenset({"items", "values"})  # a float mapping's iteration yields floats


@dataclass(frozen=True, slots=True)
class Hit:
    path: str  # relative to tst/sim, with forward slashes
    line: int
    code: str

    def __str__(self) -> str:
        return f"tst/sim/{self.path}:{self.line}: {self.code}"


def money_name(name: str) -> bool:
    """`price_cents`, `revenue`, `drug_sales`, `cost`: a name that carries money."""
    return "cents" in name or any(part in ALIASES for part in name.lower().split("_"))


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_float_annotation(node: ast.AST | None) -> bool:
    if node is None:
        return False
    text = ast.unparse(node)
    parts = {
        p.strip() for p in text.replace("|", ",").replace("[", ",").replace("]", ",").split(",")
    }
    return "float" in parts and "Fraction" not in parts


def declared_floats(files: list[Path]) -> tuple[frozenset[str], frozenset[str]]:
    """(field or parameter names, function names) declared `float` anywhere in the package."""
    fields: set[str] = set()
    funcs: set[str] = set()
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                fields.update(
                    item.target.id
                    for item in node.body
                    if isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                    and _is_float_annotation(item.annotation)
                )
            elif isinstance(node, ast.FunctionDef) and _is_float_annotation(node.returns):
                funcs.add(node.name)
    return frozenset(fields), frozenset(funcs)


class _Scan:
    def __init__(self, fields: frozenset[str], funcs: frozenset[str]) -> None:
        self.fields, self.funcs = fields, funcs
        self.locals: set[str] = set()
        self.exacts: set[str] = set()  # locals holding an exact rational
        self.monies: set[str] = set()  # locals assigned money under any name

    def exact_call(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Call) and _name(node.func) in EXACT_CALLS

    def exactish(self, node: ast.AST) -> bool:
        """An exact rational: an exact helper's result, a local holding one, or arithmetic
        with one (int or Fraction arithmetic stays exact; a float in it is caught as floaty)."""
        if self.exact_call(node):
            return True
        match node:
            case ast.Name(id=name):
                return name in self.exacts
            case ast.BinOp(left=left, right=right):
                return self.exactish(left) or self.exactish(right)
            case ast.UnaryOp(operand=operand):
                return self.exactish(operand)
        return False

    def floaty(self, node: ast.AST) -> bool:
        if self.exact_call(node):
            return False
        match node:
            case ast.Constant(value=float()):
                return True
            case ast.Name(id=name):
                return name in self.locals
            case ast.Attribute(attr=attr):
                return attr in self.fields
            case ast.Subscript(value=value):
                return self.floaty(value)  # shares[account]
            case ast.BinOp(op=ast.Div(), left=left, right=right):
                exact_div = self.exactish(left) or self.exactish(right)
                return not exact_div or self.floaty(left) or self.floaty(right)
            case ast.BinOp(left=left, right=right):
                return self.floaty(left) or self.floaty(right)
            case ast.UnaryOp(operand=operand):
                return self.floaty(operand)
            case ast.IfExp(body=body, orelse=orelse):
                return self.floaty(body) or self.floaty(orelse)
            case ast.BoolOp(values=values):
                return any(self.floaty(v) for v in values)
            case ast.Call(func=func, args=args):
                name = _name(func)
                if name == "float" or name in self.funcs:
                    return True
                if isinstance(func, ast.Attribute) and _name(func.value) == "math":
                    return func.attr in MATH
                if isinstance(func, ast.Attribute) and func.attr == "get":
                    return self.floaty(func.value)  # shares.get(account, 0.0)
                if name in ("min", "max", "abs", "sum"):
                    return any(self.floaty(a) for a in args)
                return False
        return False

    def money(self, node: ast.AST) -> bool:
        if self.exact_call(node):
            return False
        match node:
            case ast.Name(id=name):
                return money_name(name) or name in self.monies
            case ast.Attribute(attr=name):
                return money_name(name)
            case ast.Subscript(value=value):
                return self.money(value)  # revenue[cid]
            case ast.BinOp(left=left, right=right):
                return self.money(left) or self.money(right)
            case ast.UnaryOp(operand=operand):
                return self.money(operand)
            case ast.Call(func=func, args=args):
                name = _name(func) or ""
                if "cents" in name:
                    return True
                if name in THROUGH:
                    return any(self.money(a) for a in args)
                if name == "get" and isinstance(func, ast.Attribute):
                    return self.money(func.value)  # revenue.get(pid, 0)
                return False
            case ast.IfExp(body=body, orelse=orelse):
                return self.money(body) or self.money(orelse)
            case ast.BoolOp(values=values):
                return any(self.money(v) for v in values)
        return False

    def violation(self, node: ast.BinOp) -> bool:
        if isinstance(node.op, ast.Div):
            if not (self.money(node.left) or self.money(node.right)):
                return False
            return self.floaty(node)
        if isinstance(node.op, ast.Mult):
            return (self.money(node.left) and self.floaty(node.right)) or (
                self.money(node.right) and self.floaty(node.left)
            )
        return False

    def function_locals(self, fn: ast.AST) -> None:
        """Locals declared or assigned float in this function (two passes: a fixpoint)."""
        self.locals, self.exacts = set(), set()
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            for arg in [*fn.args.args, *fn.args.kwonlyargs, *fn.args.posonlyargs]:
                if _is_float_annotation(arg.annotation):
                    self.locals.add(arg.arg)
                elif arg.annotation is not None and "Fraction" in ast.unparse(arg.annotation):
                    self.exacts.add(arg.arg)
        for _ in range(2):
            for node in ast.walk(fn):
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    if _is_float_annotation(node.annotation) or (
                        node.value is not None and self.floaty(node.value)
                    ):
                        self.locals.add(node.target.id)
                    elif "Fraction" in ast.unparse(node.annotation):
                        self.exacts.add(node.target.id)
                elif isinstance(node, ast.Assign | ast.AugAssign):
                    value = node.value
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    names = [n for t in targets for n in _target_names(t)]
                    if self.floaty(value):
                        self.locals.update(names)
                    elif self.exactish(value):
                        self.exacts.update(names)
                    elif isinstance(node, ast.Assign) and self.money(value):
                        self.monies.update(n for t in targets for n in _plain_names(t))
                elif isinstance(node, ast.For | ast.AsyncFor | ast.comprehension):
                    self.loop_target(node.target, node.iter)

    def loop_target(self, target: ast.AST, iterable: ast.AST) -> None:
        """`for s in shares.values()`, `for k, s in sorted(shares.items())`, `for r in rates`:
        a float mapping's values, or a float sequence's items, are floats."""
        while isinstance(iterable, ast.Call) and _name(iterable.func) in ("sorted", "reversed"):
            if not iterable.args:
                return
            iterable = iterable.args[0]
        if (
            isinstance(iterable, ast.Call)
            and isinstance(iterable.func, ast.Attribute)
            and iterable.func.attr in FLOAT_ITERS
        ):
            if not self.floaty(iterable.func.value):
                return
            if iterable.func.attr == "items" and isinstance(target, ast.Tuple) and target.elts:
                target = target.elts[-1]
            self.locals.update(_target_names(target))
        elif self.floaty(iterable):
            self.locals.update(_target_names(target))


def _target_names(target: ast.AST) -> list[str]:
    """Every name an assignment target binds (`a`, `a, b`, `(a, (b, c))`, `*rest`)."""
    match target:
        case ast.Name(id=name):
            return [name]
        case ast.Tuple(elts=elts) | ast.List(elts=elts):
            return [n for e in elts for n in _target_names(e)]
        case ast.Starred(value=value):
            return _target_names(value)
    return []


def _plain_names(target: ast.AST) -> list[str]:
    """A single-name target only: a tuple's parts may be anything (`cents, share = ...`)."""
    return [target.id] if isinstance(target, ast.Name) else []


def _display(tree: ast.AST) -> set[int]:
    """ids of nodes inside f-strings (display text)."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            out.update(id(x) for x in ast.walk(node))
    return out


def _scopes(tree: ast.Module) -> Iterator[ast.AST]:
    """Each function (its own locals), and the module's top level."""
    yield tree
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def scan(root: Path = SIM) -> list[Hit]:
    files = sorted(p for p in root.rglob("*.py") if p.name not in SKIP_FILES)
    fields, funcs = declared_floats(files)
    hits: dict[tuple[str, int], Hit] = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        tree = ast.parse(text)
        display = _display(tree)
        rel = path.relative_to(root).as_posix()
        for scope in _scopes(tree):
            s = _Scan(fields, funcs)
            s.function_locals(scope)
            body = scope.body if isinstance(scope, ast.Module) else [scope]
            for top in body:
                if isinstance(scope, ast.Module) and isinstance(
                    top, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
                ):
                    continue  # functions are their own scopes
                for node in ast.walk(top):
                    if not isinstance(node, ast.BinOp) or id(node) in display:
                        continue
                    if not s.violation(node):
                        continue
                    first, last = node.lineno, node.end_lineno or node.lineno
                    if any(ALLOW in lines[i - 1] for i in range(max(1, first - 1), last + 1)):
                        continue
                    key = (rel, first)
                    if key not in hits:
                        hits[key] = Hit(rel, first, lines[first - 1].strip())
    return sorted(hits.values(), key=lambda h: (h.path, h.line))


if __name__ == "__main__":
    found = scan()
    for h in found:
        print(h)
    print(len(found))
