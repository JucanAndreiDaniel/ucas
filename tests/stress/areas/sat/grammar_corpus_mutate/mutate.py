#!/usr/bin/env python3
"""Seeded, AFL-style grammar-aware corpus mutator for ucas .ucas sources.

Everything lives in this folder.  The tool:

  * seeds a small corpus from the read-only ``tests/*.ucas`` files,
  * renames identifiers uniformly to ``v0, v1, ...`` (keywords/builtins kept),
  * builds a lightweight delimiter/AST tree per source (fenced ``` blocks are
    opaque leaves, so GLSL/SPIR-V/C bodies are never mangled internally),
  * applies AFL-ts style tree mutations:
        ts-del       delete a statement / subexpression
        ts-swap      swap two same-type siblings
        ts-shrink    replace a subtree by one of its descendants
        ts-dup       duplicate a subtree next to itself
        ts-ins       insert a token from a dictionary at a random position
        ts-kdel      kill a member of a comma-separated list
        ts-kins      insert a member into a comma-separated list
        ts-stutter   duplicate an enclosing statement / command keyword
  * uses a token dictionary of operators, types and boundary literals
    (0, -1, MIN, MAX, 2^63, 2^64, NaN payloads, ...).

Generation is fully deterministic for a fixed ``--seed`` (no set iteration,
no hash-order dependence).  Usage:

    python3 mutate.py gen --count 240 --seed 0x5EED
    python3 mutate.py stats

The generated corpus is ``_scratch/corpus.jsonl`` and the mutant sources are
``_scratch/mutants/mNNNN.ucas``.  ``run_fuzz.py`` executes every mutant under
``timeout 10`` and records crashes / hangs.
"""
import argparse
import copy
import json
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, "_scratch")
MUTDIR = os.path.join(SCRATCH, "mutants")
TESTS = os.path.normpath(os.path.join(HERE, "..", ".."))
os.makedirs(MUTDIR, exist_ok=True)

# ---------------------------------------------------------------------------
# token dictionary
# ---------------------------------------------------------------------------
OPS = ["+", "-", "*", "/", "%", "^", "**", "<<", ">>", "&", "|", "xor",
       "~", "==", "!=", "<", "<=", ">", ">=", "?", ":", "=", "=>", "->",
       ",", ";", "and", "or", "not"]
TYPES = ["u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64", "f16",
         "f32", "f64", "real", "int", "bool", "uint"]
COMMANDS = ["show", "parse", "range", "domain", "wrap", "crit", "diff",
            "equiv", "fit", "find", "more", "cost", "gates", "stoke",
            "phash", "dword", "foldproof", "approx", "simplify", "expand",
            "factor", "table", "solve", "prove", "check", "axioms",
            "theorem", "rule", "model", "use", "basis", "sum", "prod",
            "limit", "integrate", "taylor", "closed", "scheme", "identify",
            "fact", "gcd", "resultant"]
# Boundary literals the compiler is known to be sensitive to.  Some are not
# valid ucas in every context -- that is intentional: parse errors are simply
# one more fingerprint cluster for the fuzzer.
LITERALS = ["0", "1", "-1", "2", "-2", "0x7fffffff", "0x80000000",
            "0xffffffff", "0x7fffffffffffffff", "0x8000000000000000",
            "9223372036854775807", "9223372036854775808",
            "18446744073709551615", "2^63", "2^64", "MIN", "MAX",
            "0x7fc00000", "0x7ff8000000000000", "0xffc00000", "nan",
            "inf", "-inf", "0.0", "-0.0", "1e-45", "3.4028235e38"]
BANK = OPS + TYPES + COMMANDS + LITERALS

# Tokens / statement lines inserted into fenced SPIR-V / GLSL bodies.
SPV_LINES = [
    "%t = OpIAdd %uint %a %b", "%t = OpIMul %uint %a %b",
    "%t = OpISub %uint %a %b", "%t = OpUDiv %uint %a %b",
    "%t = OpShiftRightLogical %uint %a %uint_1",
    "%t = OpBitwiseAnd %uint %a %uint_255",
    "%t = OpBitcast %int %a",
    "%t = OpExtInst %uint %glsl UClamp %a %uint_0 %uint_255",
    "%t = OpSelect %uint %c %a %b", "OpStore %out %a",
    "OpSelectionMerge %m None", "OpBranchConditional %c %l1 %l2",
    "OpReturn", "%t = OpPhi %uint %a %l1 %b %l2",
]
GLSL_LINES = [
    "uint t = 0u;", "t += 1u;", "t = t >> 1u;",
    "if (t < 4u) { t = 0u; }", "atomicAdd(cnt[2], 1u);",
    "barrier();", "t = clamp(t, 0u, 255u);", "outb.o[l] = t;",
    "float f = asfloat(t);", "t = floatBitsToUint(1.0);",
]

# Words that must never be renamed (commands, types, builtins, keywords).
PROTECTED = set(
    OPS + TYPES + COMMANDS + LITERALS + [
        "in", "where", "wrt", "from", "to", "at", "as", "mod", "over",
        "nofile", "min", "max", "abs", "clz", "ctz", "popcount", "min",
        "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh",
        "tanh", "sqrt", "exp", "log", "ln", "floor", "ceil", "round",
        "sign", "copysign", "fma", "pow", "isqrt", "match", "i", "e",
        "pi", "true", "false", "nan", "inf", "int", "uint", "bool",
        "class", "fuse", "cost", "gate", "inputs", "width", "size",
        "steps", "restarts", "len", "seed", "model", "n", "name",
        "relative", "absolute", "odd", "even", "nosym", "fma", "nofma",
        "left", "right", "mid", "trapezoid", "simpson", "disk", "washer",
        "shell", "still", "rotate", "contour", "heatmap", "wireframe",
        "deriv", "tangent", "polar", "field", "accumulate", "more",
    ]
)
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MULTI_OPS = ["=>", "->", "==", "!=", "<=", ">=", "<<", ">>", "**",
             "//", "..", "&&", "||"]

# ---------------------------------------------------------------------------
# tree
# ---------------------------------------------------------------------------
class Node:
    __slots__ = ("kind", "text", "op", "cl", "children", "ws")

    def __init__(self, kind, text="", op="", cl="", children=None, ws=""):
        self.kind = kind            # file item fence comment atom group
        self.text = text
        self.op = op
        self.cl = cl
        self.children = children if children is not None else []
        self.ws = ws                # whitespace before this node in its parent

    def render(self):
        if self.kind == "file":
            return "\n".join(c.render() for c in self.children) + "\n"
        if self.kind == "fence":
            return self.text
        if self.kind in ("atom", "comment"):
            return self.ws + self.text
        if self.kind == "item":
            return self.ws + "".join(c.render() for c in self.children)
        if self.kind == "group":
            inside = "".join(c.render() for c in self.children)
            return self.ws + self.op + inside + self.cl
        raise ValueError("render " + self.kind)

    def clone(self):
        return copy.deepcopy(self)


def tokenize_item(line):
    """Turn one source line into an ``item`` Node with atom/group children."""
    root = Node("item")
    i, n, ws = 0, len(line), ""
    while i < n:
        ch = line[i]
        if ch in " \t\r":
            ws += ch
            i += 1
            continue
        if ch in "([{":
            close = {"(": ")", "[": "]", "{": "}"}[ch]
            inner, i = [], i + 1
            depth = 0
            buf = []
            # Collect the raw text up to the matching close delimiter.
            start = i
            while i < n:
                c = line[i]
                if c in "\"'":
                    quote = c
                    j = i + 1
                    while j < n and line[j] != quote:
                        j += 2 if line[j] == "\\" else 1
                    i = min(j + 1, n)
                    continue
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    if depth == 0 and c == close:
                        break
                    depth -= 1
                i += 1
            raw = line[start:i]
            if i < n:
                i += 1  # consume closing delimiter
            grp = Node("group", op=ch, cl=close, ws=ws)
            grp.children = _tokenize_fragment(raw).children
            root.children.append(grp)
            ws = ""
            continue
        if ch in ")]}":
            root.children.append(Node("atom", text=ch, ws=ws))
            ws = ""
            i += 1
            continue
        if ch == "#":
            root.children.append(Node("comment", text=line[i:], ws=ws))
            break
        if ch in "\"'":
            quote = ch
            j = i + 1
            while j < n and line[j] != quote:
                j += 2 if line[j] == "\\" else 1
            root.children.append(Node("atom", text=line[i:j + 1], ws=ws))
            i = min(j + 1, n)
            ws = ""
            continue
        # longest multi-char operator
        matched = None
        for op in MULTI_OPS:
            if line.startswith(op, i):
                matched = op
                break
        if matched:
            root.children.append(Node("atom", text=matched, ws=ws))
            i += len(matched)
            ws = ""
            continue
        if ch.isalnum() or ch == "_" or ch == ".":
            j = i
            while j < n and (line[j].isalnum() or line[j] in "_."):
                j += 1
            root.children.append(Node("atom", text=line[i:j], ws=ws))
            i = j
            ws = ""
            continue
        root.children.append(Node("atom", text=ch, ws=ws))
        i += 1
        ws = ""
    return root


def _tokenize_fragment(fragment):
    """Tokenize the inside of a group by pretending it is a whole line."""
    fake = Node("item")
    # Reuse the main tokenizer on a single synthetic line.
    fake = tokenize_item(fragment)
    fake.kind = "fragment"
    return fake


def parse_source(src, max_lines=90):
    """Parse source text into a ``file`` Node tree."""
    lines = src.splitlines()
    lines = lines[:max_lines]
    root = Node("file")
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.lstrip().startswith("```"):
            block = [line]
            i += 1
            while i < n:
                block.append(lines[i])
                done = lines[i].lstrip().startswith("```")
                i += 1
                if done:
                    break
            root.children.append(Node("fence", text="\n".join(block)))
            continue
        if line.lstrip().startswith("#"):
            root.children.append(Node("comment", text=line))
        else:
            root.children.append(tokenize_item(line))
        i += 1
    return root


def all_nodes(root, include_root=False):
    """Yield (node, parent, index) for every node (deterministic order)."""
    out = []

    def rec(node, parent, idx, is_root):
        if is_root and not include_root:
            pass
        else:
            out.append((node, parent, idx))
        for j, child in enumerate(node.children):
            rec(child, node, j, False)

    rec(root, None, None, True)
    return out


def render_source(root):
    return root.render()


# ---------------------------------------------------------------------------
# identifier renaming
# ---------------------------------------------------------------------------
def rename_identifiers(root):
    """Rename every non-protected identifier uniformly to v0, v1, ..."""
    mapping = {}
    for node, parent, idx in all_nodes(root):
        if node.kind == "atom" and IDENT_RE.match(node.text) and node.text not in PROTECTED:
            if node.text not in mapping:
                mapping[node.text] = "v%d" % len(mapping)
            node.text = mapping[node.text]
    return mapping


# ---------------------------------------------------------------------------
# tree mutations (AFL-ts style)
# ---------------------------------------------------------------------------
def _atom_class(node):
    if node.kind == "group":
        return "g" + node.op
    if node.kind == "atom":
        t = node.text
        if t.isdigit():
            return "num"
        if IDENT_RE.match(t):
            return "ident"
        return "op"
    return node.kind


def _insert_bank_node():
    tok = random.choice(BANK)
    if tok in ("(", "[", "{"):
        close = {"(": ")", "[": "]", "{": "}"}[tok]
        return Node("group", op=tok, cl=close, ws=" ", children=[Node("atom", text=random.choice(LITERALS))])
    return Node("atom", text=tok, ws=" ")


def _mut_del(root, rng):
    cands = [(n, p, i) for n, p, i in all_nodes(root) if p is not None
             and n.kind not in ("file",)]
    if not cands:
        return False
    n, p, i = rng.choice(cands)
    del p.children[i]
    # if we emptied an item line, drop the whole item to avoid blank noise
    if p.kind in ("item", "fragment") and not p.children and p in getattr(root, "children", []):
        root.children.remove(p)
    return True


def _mut_swap(root, rng):
    parents = []
    for n, p, i in all_nodes(root):
        if n.kind in ("file", "item", "fragment", "group"):
            groups = {}
            for j, ch in enumerate(n.children):
                groups.setdefault(_atom_class(ch), []).append(j)
            for cls, idxs in groups.items():
                if len(idxs) >= 2:
                    parents.append((n, idxs))
            del groups
    if not parents:
        return False
    par, idxs = rng.choice(parents)
    a, b = rng.sample(idxs, 2)
    par.children[a], par.children[b] = par.children[b], par.children[a]
    return True


def _mut_shrink(root, rng):
    cands = [(n, p, i) for n, p, i in all_nodes(root)
             if n.kind == "group" and p is not None and n.children]
    rng.shuffle(cands)
    for n, p, i in cands:
        desc = [(d) for d, _, _ in all_nodes(n) if d is not n]
        desc = [d for d in desc if d.kind in ("atom", "group")]
        if desc:
            pick = rng.choice(desc).clone()
            pick.ws = n.ws
            p.children[i] = pick
            return True
    return False


def _mut_dup(root, rng):
    cands = [(n, p, i) for n, p, i in all_nodes(root)
             if p is not None and n.kind in ("item", "atom", "group", "fence", "comment")]
    if not cands:
        return False
    n, p, i = rng.choice(cands)
    c = n.clone()
    c.ws = " " if n.kind in ("atom", "group") else ""
    p.children.insert(i + 1, c)
    return True


def _mut_ins(root, rng):
    cands = [(n, p, i) for n, p, i in all_nodes(root)
             if n.kind in ("file", "item", "fragment", "group")]
    if not cands:
        return False
    n, p, i = rng.choice(cands)
    node = _insert_bank_node()
    if n.kind == "file":
        node.ws = ""
    n.children.insert(rng.randint(0, len(n.children)), node)
    return True


def _comma_lists(root):
    """Return (container, comma-index-list) for groups containing commas."""
    out = []
    for n, p, i in all_nodes(root):
        if n.kind == "group" or n.kind in ("item", "fragment"):
            commas = [j for j, ch in enumerate(n.children)
                      if ch.kind == "atom" and ch.text == ","]
            if commas:
                out.append((n, commas))
    return out


def _mut_kdel(root, rng):
    lists = _comma_lists(root)
    if not lists:
        return False
    n, commas = rng.choice(lists)
    ci = rng.choice(commas)
    # choose to remove the member after this comma (or before if it is last)
    if ci + 1 < len(n.children) and commas and (ci == commas[-1] or ci + 1 not in commas):
        end = ci + 1
        while end < len(n.children) and end not in commas:
            end += 1
        lo, hi = ci, end  # remove comma + following member
    else:
        start = ci - 1
        while start >= 0 and start not in commas:
            start -= 1
        lo, hi = start + 1, ci + 1  # remove preceding member + this comma
    if hi <= lo:
        lo, hi = ci, ci + 1
    del n.children[lo:hi]
    return True


def _mut_kins(root, rng):
    lists = _comma_lists(root)
    if not lists:
        return False
    n, commas = rng.choice(lists)
    ci = rng.choice(commas)
    member = _insert_bank_node()
    member.ws = " "
    comma = Node("atom", text=",", ws=" ")
    # insert a ", member" after the chosen comma's member
    pos = ci + 1
    while pos < len(n.children) and pos not in commas:
        pos += 1
    n.children[pos:pos] = [comma, member]
    return True


def _fence_parts(node):
    """Return (header, body_lines, closing) for a fenced block node."""
    text = node.text
    parts = text.split("\n")
    if not parts:
        return "", [], ""
    header = parts[0]
    closing = parts[-1] if len(parts) > 1 and parts[-1].lstrip().startswith("```") else ""
    body = parts[1:-1] if closing else parts[1:]
    return header, body, closing


def _set_fence(node, header, body, closing):
    node.text = "\n".join([header] + body + ([closing] if closing else []))


def _mut_fdel(root, rng):
    fences = [n for n, p, i in all_nodes(root) if n.kind == "fence"]
    fences = [f for f in fences if len(_fence_parts(f)[1]) >= 2]
    if not fences:
        return False
    f = rng.choice(fences)
    h, body, c = _fence_parts(f)
    del body[rng.randrange(len(body))]
    _set_fence(f, h, body, c)
    return True


def _mut_fdup(root, rng):
    fences = [n for n, p, i in all_nodes(root) if n.kind == "fence"]
    fences = [f for f in fences if _fence_parts(f)[1]]
    if not fences:
        return False
    f = rng.choice(fences)
    h, body, c = _fence_parts(f)
    i = rng.randrange(len(body))
    body.insert(i + 1, body[i])
    _set_fence(f, h, body, c)
    return True


def _mut_fins(root, rng):
    fences = [n for n, p, i in all_nodes(root) if n.kind == "fence"]
    if not fences:
        return False
    f = rng.choice(fences)
    h, body, c = _fence_parts(f)
    bank = GLSL_LINES if "glsl" in h else SPV_LINES
    body.insert(rng.randint(0, len(body)), rng.choice(bank))
    _set_fence(f, h, body, c)
    return True


def _mut_wrap(root, rng):
    """Envelope stutter: wrap a subtree in several nested parentheses."""
    cands = [(n, p, i) for n, p, i in all_nodes(root)
             if p is not None and n.kind in ("atom", "group")]
    if not cands:
        return False
    n, p, i = rng.choice(cands)
    inner = n.clone()
    inner.ws = ""
    k = rng.randint(1, 12)
    for _ in range(k):
        g = Node("group", op="(", cl=")", ws=n.ws, children=[inner])
        inner = g
    p.children[i] = inner
    return True


def _mut_fbreak(root, rng):
    """Insert a fence delimiter line into a fenced body (nested/unclosed fence)."""
    fences = [n for n, p, i in all_nodes(root) if n.kind == "fence"]
    if not fences:
        return False
    f = rng.choice(fences)
    h, body, c = _fence_parts(f)
    ins = rng.choice(["```", "```glsl", "```spv", "```c"])
    body.insert(rng.randint(0, len(body)), ins)
    _set_fence(f, h, body, c)
    return True


def _mut_stutter(root, rng):
    items = [c for c in root.children if c.kind in ("item", "fence")]
    if items and rng.random() < 0.7:
        target = rng.choice(items)
        idx = root.children.index(target)
        root.children.insert(idx + 1, target.clone())
        return True
    # keyword stutter: repeat the first atom/keyword of a random item
    its = [c for c in root.children if c.kind == "item" and c.children]
    if not its:
        return False
    it = rng.choice(its)
    head = it.children[0]
    dup = head.clone()
    dup.ws = head.ws
    it.children.insert(0, dup)
    return True


MUTATORS = [
    ("ts-del", _mut_del),
    ("ts-swap", _mut_swap),
    ("ts-shrink", _mut_shrink),
    ("ts-dup", _mut_dup),
    ("ts-ins", _mut_ins),
    ("ts-kdel", _mut_kdel),
    ("ts-kins", _mut_kins),
    ("ts-stutter", _mut_stutter),
    ("ts-fdel", _mut_fdel),
    ("ts-fdup", _mut_fdup),
    ("ts-fins", _mut_fins),
    ("ts-wrap", _mut_wrap),
    ("ts-fbreak", _mut_fbreak),
]


def mutate_tree(root, rng, n_ops=2):
    applied = []
    for _ in range(n_ops):
        name, fn = rng.choice(MUTATORS)
        if fn(root, rng):
            applied.append(name)
    return applied


# ---------------------------------------------------------------------------
# corpus seeding
# ---------------------------------------------------------------------------
SEEDS = [
    # fast, grammar-diverse seeds (all < ~3 s standalone)
    "parse.ucas", "ops2.ucas", "rules.ucas", "calc.ucas",
    "float.ucas", "forms.ucas", "lambert.ucas", "phashtable.ucas",
    "prove.ucas", "nlp_numbers.ucas", "roundmagic.ucas",
    "fp64minmax.ucas", "f16bits.ucas", "simplify.ucas",       # SPIR-V fences
    "glslline.ucas", "atomkinds.ucas", "execfconst.ucas", "gates.ucas",
]


def load_seeds(max_lines=90):
    seeds = []
    for name in SEEDS:
        path = os.path.join(TESTS, name)
        if not os.path.exists(path):
            continue
        with open(path, "r", errors="replace") as fh:
            src = fh.read()
        root = parse_source(src, max_lines=max_lines)
        mapping = rename_identifiers(root)
        seeds.append({"name": name, "tree": root, "rename_map": mapping})
    return seeds


def gen(count=240, seed=0x5EED, max_lines=90):
    rng = random.Random(seed)
    seeds = load_seeds(max_lines=max_lines)
    cases = []
    seen = set()
    for k in range(count):
        base = seeds[rng.randrange(len(seeds))]
        root = base["tree"].clone()
        n_ops = rng.randint(1, 3)
        applied = mutate_tree(root, rng, n_ops=n_ops)
        src = render_source(root)
        # de-dup identical mutants (keep the corpus honest)
        tries = 0
        while src in seen and tries < 6:
            more = mutate_tree(root, rng, n_ops=1)
            applied += more
            src = render_source(root)
            tries += 1
        seen.add(src)
        mid = k
        path = os.path.join(MUTDIR, "m%04d.ucas" % mid)
        with open(path, "w") as fh:
            fh.write(src)
        cases.append({
            "id": mid,
            "seed": base["name"],
            "ops": applied,
            "n_ops": n_ops,
            "source": src,
            "file": os.path.relpath(path, HERE),
        })
    with open(os.path.join(SCRATCH, "corpus.jsonl"), "w") as fh:
        for c in cases:
            fh.write(json.dumps(c) + "\n")
    return cases


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("gen")
    g.add_argument("--count", type=int, default=240)
    g.add_argument("--seed", type=lambda x: int(x, 0), default=0x5EED)
    g.add_argument("--max-lines", type=int, default=90)
    a = sub.add_parser("stats")
    args = ap.parse_args()
    if args.cmd == "gen":
        cases = gen(args.count, args.seed, args.max_lines)
        print("generated %d mutants with seed %#x" % (len(cases), args.seed))
        print("seeds:", ", ".join(sorted(set(c["seed"] for c in cases))))
        from collections import Counter
        c = Counter(op for case in cases for op in case["ops"])
        print("mutations:", dict(sorted(c.items())))
    elif args.cmd == "stats":
        path = os.path.join(SCRATCH, "corpus.jsonl")
        cases = [json.loads(l) for l in open(path)]
        print("corpus size:", len(cases))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
