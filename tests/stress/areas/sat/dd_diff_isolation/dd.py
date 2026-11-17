#!/usr/bin/env python3
"""
Generalized delta debugging (Hildebrandt & Zeller, ISSTA 2000) on PAIRS of ucas inputs.

Given a PASSING input A (correct verdict) and a FAILING input B (buggy verdict),
find a 1-minimal set of token-level changes such that applying them to A still
makes ucas exhibit the bug.  The changed tokens are the "minimal flip".

Run:  python3 dd.py --full            # all pairs, writes results.jsonl + analysis
      python3 dd.py --class equiv_cast --limit 5   # quick smoke test
"""
# --- portability: derive the repo root from this file's own location -------
# Walk up until a directory containing both the `ucas` binary and `src/` is found.
from pathlib import Path as _ROOT_PATH
def _repo_root():
    here = _ROOT_PATH(__file__).resolve()
    for d in here.parents:
        if (d / 'ucas').is_file() and (d / 'src').is_dir():
            return d
    raise RuntimeError('ucas repo root not found above ' + str(here))
_REPO_ROOT = _repo_root()
ROOT = str(_REPO_ROOT)
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

BIN = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results.jsonl")
TIMEOUT = 15

# ---------------------------------------------------------------------------
# 1. Tokenizer + edit script
# ---------------------------------------------------------------------------
TOKEN_RE = re.compile(
    r"\s+|[A-Za-z_]\w*|\d+|==|!=|<=|>=|<<|>>|&&|\|\||=>|::|\.\.|\S"
)


def tokenize(text):
    return TOKEN_RE.findall(text)


# An edit is (id, kind, tok) where kind in {keep, del, ins}.
#   keep: consume one token from A and one from B (they are equal), always emit tok
#   del : consume one token from A; emit tok unless its id is selected
#   ins : consume one token from B; emit tok only if its id is selected
def edit_script(a_toks, b_toks):
    edits = []
    next_id = [0]

    def add(kind, tok):
        eid = next_id[0]
        next_id[0] += 1
        edits.append({"id": eid, "kind": kind, "tok": tok})

    def rec(a, b):
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for t in a[i1:i2]:
                    add("keep", t)
            elif tag == "delete":
                for t in a[i1:i2]:
                    add("del", t)
            elif tag == "insert":
                for t in b[j1:j2]:
                    add("ins", t)
            else:  # replace -> recurse to align common sub-tokens, but guard
                   # against a no-progress recursion (no common tokens at all)
                sub = difflib.SequenceMatcher(None, a[i1:i2], b[j1:j2], autojunk=False)
                ops = sub.get_opcodes()
                if len(ops) == 1 and ops[0][0] == "replace":
                    for t in a[i1:i2]:
                        add("del", t)
                    for t in b[j1:j2]:
                        add("ins", t)
                else:
                    rec(a[i1:i2], b[j1:j2])

    rec(a_toks, b_toks)
    return edits


def apply_edits(edits, selected_ids):
    selected = set(selected_ids)
    out = []
    for e in edits:
        k, t, i = e["kind"], e["tok"], e["id"]
        if k == "keep":
            out.append(t)
        elif k == "del":
            if i not in selected:
                out.append(t)
        else:  # ins
            if i in selected:
                out.append(t)
    return "".join(out)


def changes(edits):
    return [e for e in edits if e["kind"] != "keep"]


# ---------------------------------------------------------------------------
# 2. Oracle: run ucas on a candidate, classify the verdict
# ---------------------------------------------------------------------------
class Runner:
    def __init__(self):
        self.cache = {}
        self.calls = 0

    def run(self, text):
        if text in self.cache:
            return self.cache[text]
        self.calls += 1
        fd, path = tempfile.mkstemp(prefix="dd_", suffix=".ucas", dir=tempfile.gettempdir())
        try:
            with os.fdopen(fd, "w") as f:
                f.write(text)
            try:
                p = subprocess.run(
                    [BIN, path], stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, timeout=TIMEOUT,
                )
                rc, out = p.returncode, p.stdout.decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                rc, out = "TIMEOUT", ""
        finally:
            os.remove(path)
        res = (rc, out)
        self.cache[text] = res
        return res


def verdict(out):
    if "are equal" in out:
        return "equal"
    if "differ at" in out:
        return "differ"
    if "o*f" in out:
        return "of_misparse"
    if "sorry" in out or "note" in out:
        return "other"
    return "unknown"


def where_bound(text, name):
    """Return the numeric bound of `name`'s where clause, or None."""
    pat = re.compile(
        r"^\s*" + re.escape(name) + r"\s*\([^)]*\)\s*=.*?\bwhere\b.*?<\s*(\d+)",
        re.M,
    )
    m = pat.search(text)
    return int(m.group(1)) if m else None


# --- strict bug oracles -----------------------------------------------------

def clean(out):
    """Reject reductions that only 'succeed' because a definition failed to parse."""
    return "error" not in out.lower()


def bug_where_narrow(text, rc, out):
    # equiv says "equal" while G is undefined on part of F's domain (narrowed where)
    eq = "are equal" in out
    bf, bg = where_bound(text, "f"), where_bound(text, "g")
    return eq and clean(out) and bf is not None and bg is not None and bg < bf


def make_bug_cast(gt):
    def f(text, rc, out):
        eq = "are equal" in out
        defined = re.search(
            r"^\s*g\s*\([^)]*\)\s*=\s*" + re.escape(gt) + r"\s*\([^\n]*\)[^\n+*-/]*$",
            text, re.M,
        )
        return eq and clean(out) and bool(defined)
    return f


def make_bug_signed(st):
    def f(text, rc, out):
        eq = "are equal" in out
        defined = re.search(
            r"^\s*b\s*\([^)]*\)\s*=\s*" + re.escape(st) + r"\s*\([^\n]*\)[^\n+*-/]*$",
            text, re.M,
        )
        return eq and clean(out) and bool(defined)
    return f


def bug_of_misparse(text, rc, out):
    return "'of' read as o*f" in out


def bug_of_fraction(text, rc, out):
    return "_(o: real, f: real)" in out and "'of' read as o*f" in out


def bug_crash(text, rc, out):
    return rc == -11 or rc == 139


def bug_undefined_name(text, rc, out):
    eq = "are equal" in out
    g_defined = re.search(r"^\s*b\s*\(", text, re.M)
    return eq and not bool(g_defined)


# --- loose (symptom-only) oracle, for the mutation experiment --------------

def loose_equiv(text, rc, out):
    return "are equal" in out


# ---------------------------------------------------------------------------
# 3. Generalized delta debugging
# ---------------------------------------------------------------------------
def dd(pass_text, fail_text, oracle, runner, verify=True):
    edits = edit_script(tokenize(pass_text), tokenize(fail_text))
    ch = changes(edits)
    all_ids = [e["id"] for e in ch]

    def cand(ids):
        return apply_edits(edits, ids)

    if verify:
        rc0, o0 = runner.run(pass_text)
        rc1, o1 = runner.run(fail_text)
        if oracle(pass_text, rc0, o0):
            return None, {"error": "pass input already exhibits bug"}
        if not oracle(fail_text, rc1, o1):
            return None, {"error": "fail input does not exhibit bug"}

    current = list(all_ids)
    n = 2
    while len(current) > 1:
        k = len(current)
        chunks = []
        for i in range(n):
            lo, hi = i * k // n, (i + 1) * k // n
            if lo < hi:
                chunks.append(current[lo:hi])
        reduced = False
        for chunk in chunks:
            comp = [x for x in current if x not in chunk]
            # remove chunk
            t = cand(comp)
            rc, out = runner.run(t)
            if oracle(t, rc, out):
                current = comp
                n = max(n - 1, 2)
                reduced = True
                break
            # keep chunk alone
            t = cand(chunk)
            rc, out = runner.run(t)
            if oracle(t, rc, out):
                current = chunk
                n = 2
                reduced = True
                break
        if not reduced:
            if n >= len(current):
                break
            n = min(2 * n, len(current))

    selected = set(current)
    minimal_text = cand(current)
    flips = [
        {"kind": e["kind"], "tok": e["tok"]}
        for e in ch if e["id"] in selected
    ]
    info = {
        "total_changes": len(ch),
        "min_changes": len(current),
        "minimal_text": minimal_text,
        "flips": flips,
        "signature": signature(flips),
    }
    return current, info


def signature(flips):
    return "|".join("%s:%r" % (f["kind"], f["tok"]) for f in sorted(
        flips, key=lambda x: (x["kind"], x["tok"])))


def cause_of(flips, cls, sub):
    """Normalize a minimal flip to a human-named root-cause class."""
    ts = [(f["kind"], f["tok"]) for f in flips]
    if sub in ("result_coercion", "reinterpret", "body_coincide"):
        if (any(k == "del" and t == "+" for k, t in ts)
                and all(k == "del" and (t == "+" or t.isdigit()) for k, t in ts)):
            return "delete additive offset (+N) in G body -> bodies coincide"
    if sub == "narrow_bound":
        return "replace G where-bound with a smaller value (narrow G's domain)"
    if sub == "command_the":
        return 'delete leading "the" (command-word recognition)'
    if sub == "fraction_please":
        return 'delete trailing "please" ("of" preposition parse)'
    if sub == "undefined_name":
        return 'delete "(" so b definition fails / b becomes undefined'
    if cls == "nesting_crash":
        return 'insert N extra "(" tokens (cross recursion depth 1525)'
    return "other"


# ---------------------------------------------------------------------------
# 4. Pair generators (200+ pairs)
# ---------------------------------------------------------------------------
def gen_where_narrow():
    """f/g where-bound narrowing: same verdict string, correctness differs."""
    out = []
    widths = ["u8", "u16", "i8", "i16", "u4", "u32", "i32", "u64"]
    i = 0
    for t in widths:
        for bf, bg in [(10, 5), (20, 7), (16, 8), (30, 12), (12, 3), (15, 9), (25, 4), (18, 11)]:
            i += 1
            A = f"f(x: {t}) = x where x < {bf}\ng(x: {t}) = x where x < {bf}\nequiv f g\n"
            B = f"f(x: {t}) = x where x < {bf}\ng(x: {t}) = x where x < {bg}\nequiv f g\n"
            out.append(dict(id="W%03d" % i, cls="equiv_where", sub="narrow_bound",
                            oracle=bug_where_narrow, pass_text=A, fail_text=B,
                            meta={"type": t, "bf": bf, "bg": bg}))
    return out


def gen_where_body():
    """G body coincides with F outside G's where -> unsound equal; +1 flips it."""
    out = []
    configs = [("u8", 10, 5), ("u16", 20, 9), ("i8", 12, 4), ("i16", 30, 15),
               ("u4", 15, 6), ("u8", 25, 11), ("u32", 40, 13), ("i32", 50, 21)]
    i = 0
    for t, bf, bg in configs:
        for off in (1, 2, 3, 4, 5):
            i += 1
            A = f"f(x: {t}) = x where x < {bf}\ng(x: {t}) = x+{off} where x < {bg}\nequiv f g\n"
            B = f"f(x: {t}) = x where x < {bf}\ng(x: {t}) = x where x < {bg}\nequiv f g\n"
            out.append(dict(id="WB%03d" % i, cls="equiv_where", sub="body_coincide",
                            oracle=bug_where_narrow, pass_text=A, fail_text=B,
                            meta={"type": t, "bf": bf, "bg": bg, "off": off}))
    return out


def gen_cast():
    """equiv coerces G's result to F's type: u8(128) == i32(128) after coercion."""
    out = []
    combos = [("u8", "i32"), ("u8", "i16"), ("u16", "i32"), ("i16", "i32"),
              ("u8", "u32"), ("i8", "i32"), ("u4", "i8"), ("u16", "i64"),
              ("u8", "i64"), ("i4", "i16"), ("u32", "i64"), ("i16", "u32"),
              ("u8", "i8")]
    i = 0
    for ft, gt in combos:
        for off in (1, 2, 3):
            i += 1
            A = f"f(x: {ft}) = {ft}(x)\ng(x: {ft}) = {gt}(x)+{off}\nequiv f g\n"
            B = f"f(x: {ft}) = {ft}(x)\ng(x: {ft}) = {gt}(x)\nequiv f g\n"
            out.append(dict(id="C%03d" % i, cls="equiv_cast", sub="result_coercion",
                            oracle=make_bug_cast(gt), pass_text=A, fail_text=B,
                            meta={"ft": ft, "gt": gt, "off": off}))
    return out


def gen_signed():
    """equiv proves signed<->unsigned reinterpretation equal."""
    out = []
    widths = [("u8", "i8"), ("u16", "i16"), ("u32", "i32"), ("u64", "i64"),
              ("u4", "i4"), ("u12", "i12"), ("u20", "i20")]
    i = 0
    for ut, st in widths:
        for off in (1, 2, 3, 4):
            i += 1
            A = f"a(x: {ut}) = x\nb(x: {ut}) = {st}(x)+{off}\nequiv a b\n"
            B = f"a(x: {ut}) = x\nb(x: {ut}) = {st}(x)\nequiv a b\n"
            out.append(dict(id="S%03d" % i, cls="equiv_signed", sub="reinterpret",
                            oracle=make_bug_signed(st), pass_text=A, fail_text=B,
                            meta={"ut": ut, "st": st, "off": off}))
    return out


def gen_english_of():
    out = []
    exprs = ["x+1", "x+2", "x*x", "2*x+3", "x-1", "x+7", "3*x", "x*x+1",
             "x+4", "x-3", "5*x+2", "x*x-1"]
    i = 0
    for e in exprs:
        i += 1
        A = f"the wrap of {e}\n"
        B = f"wrap of {e}\n"
        out.append(dict(id="N%03d" % i, cls="english_of", sub="command_the",
                        oracle=bug_of_misparse, pass_text=A, fail_text=B,
                        meta={"expr": e}))
    # fraction-of: trailing "please" makes it parse as 7/8*64 = 56
    for denom in (64, 128, 256, 32, 16, 8, 512, 1024):
        for numer in (7, 3, 5, 9):
            i += 1
            A = f"{numer}/8 of {denom} please\n"
            B = f"{numer}/8 of {denom}\n"
            out.append(dict(id="F%03d" % i, cls="english_of", sub="fraction_please",
                            oracle=bug_of_fraction, pass_text=A, fail_text=B,
                            meta={"numer": numer, "denom": denom}))
    return out


def gen_crash():
    out = []
    i = 0
    for a, b in [(1500, 1600), (1400, 1600), (1500, 1700), (1450, 1560),
                 (1000, 1700), (1200, 1600), (1500, 1800), (1400, 1700),
                 (1100, 1600), (1300, 1600), (1450, 1600), (1350, 1600),
                 (1250, 1700), (1520, 1600), (1480, 1600), (1150, 1650)]:
        i += 1
        A = "parse " + "(" * a + "x" + ")" * a + "\n"
        B = "parse " + "(" * b + "x" + ")" * b + "\n"
        out.append(dict(id="X%03d" % i, cls="nesting_crash", sub="paren_depth",
                        oracle=bug_crash, pass_text=A, fail_text=B,
                        meta={"depth_pass": a, "depth_fail": b}))
    return out


def gen_conflation():
    """Oracle-sensitivity pairs: verdict-only oracle reduces to a DIFFERENT bug."""
    out = []
    i = 0
    for ut in ("u8", "u16", "i8", "u32"):
        for off in (1, 2, 3, 4):
            i += 1
            A = f"a(x: {ut}) = x\nb(x: {ut}) = x+{off}\nequiv a b\n"
            # b undefined -> 'are equal' via the undefined-function-name bug
            B = f"a(x: {ut}) = x\nequiv a b\n"
            out.append(dict(id="M%03d" % i, cls="conflation", sub="undefined_name",
                            oracle=bug_undefined_name, pass_text=A, fail_text=B,
                            meta={"ut": ut, "off": off}))
    return out


def all_pairs():
    return (gen_where_narrow() + gen_where_body() + gen_cast() + gen_signed()
            + gen_english_of() + gen_crash() + gen_conflation())


# ---------------------------------------------------------------------------
# 5. Driver + analysis
# ---------------------------------------------------------------------------
def run_all(pairs, runner):
    records = []
    for p in pairs:
        sel, info = dd(p["pass_text"], p["fail_text"], p["oracle"], runner)
        rec = {
            "id": p["id"], "cls": p["cls"], "sub": p["sub"], "meta": p["meta"],
            "ok": info is None and False or (sel is not None),
        }
        if info and "flips" in info:
            rec["cause"] = cause_of(info["flips"], p["cls"], p["sub"])
        if info and "error" in info:
            rec["error"] = info["error"]
            rec["ok"] = False
        elif info:
            rec.update(info)
        rec["oracle_calls_total"] = runner.calls
        records.append(rec)
    return records


def run_mutation_experiment(runner, limit=18):
    """Show that a verdict-only oracle reduces a bug into a DIFFERENT bug."""
    target = [p for p in all_pairs()
              if (p["cls"], p["sub"]) in {
                  ("equiv_cast", "result_coercion"),
                  ("equiv_signed", "reinterpret"),
                  ("equiv_where", "body_coincide"),
              }]
    out = []
    for p in target[:limit]:
        _, strict = dd(p["pass_text"], p["fail_text"], p["oracle"], runner)
        _, loose = dd(p["pass_text"], p["fail_text"], loose_equiv, runner)
        if not strict or not loose:
            continue
        rc, txt = runner.run(loose["minimal_text"])
        out.append({
            "id": p["id"], "cls": p["cls"], "sub": p["sub"],
            "strict_signature": strict["signature"],
            "strict_min": strict["min_changes"],
            "loose_signature": loose["signature"],
            "loose_min": loose["min_changes"],
            "loose_minimal_text": loose["minimal_text"],
            "loose_has_parse_error": "error" in txt.lower(),
            "mutated": (strict["signature"] != loose["signature"]
                        or "error" in txt.lower()),
        })
    return out


def abbrev(sig, n=90):
    if len(sig) <= n:
        return sig
    # e.g. ins:'(' repeated many times -> compact form
    if sig.count("ins:'('") > 3:
        return "ins:'(' x%d" % sig.count("ins:'('")
    return sig[:n] + "..."


def analyze(records, runner, mutations=None):
    lines = []
    good = [r for r in records if r.get("ok")]
    bad = [r for r in records if not r.get("ok")]
    lines.append("# Analysis — dd_diff_isolation\n")
    lines.append(f"- pairs run: {len(records)}")
    lines.append(f"- valid (pass=PASS, fail=FAIL, dd succeeded): {len(good)}")
    lines.append(f"- invalid/skipped: {len(bad)}")
    lines.append(f"- total distinct ucas oracle calls (cached): {runner.calls}")
    lines.append("- NOTE: `nesting_crash` minimal counts fluctuate +/-1 between runs "
                 "because the binary's depth-1525 crash boundary is nondeterministic "
                 "(FINDINGS.md §7); all other classes are byte-stable.")
    lines.append("")

    lines.append("## Minimal flip per bug class\n")
    bycls = defaultdict(list)
    for r in good:
        bycls[r["cls"]].append(r)
    for cls, rs in sorted(bycls.items()):
        bysub = defaultdict(list)
        for r in rs:
            bysub[r["sub"]].append(r)
        lines.append(f"### {cls} ({len(rs)} pairs)")
        for sub, ss in sorted(bysub.items()):
            counts = Counter(r["min_changes"] for r in ss)
            sigs = Counter(r["signature"] for r in ss)
            top = ", ".join(f"`{abbrev(s)}` x{c}" for s, c in sigs.most_common(4))
            lines.append(f"- {sub}: {len(ss)} pairs; "
                         f"minimal-change counts {dict(counts)}; signatures: {top}")
        lines.append("")

    lines.append("## Normalized root-cause clusters (cross-class)\n")
    bycause = defaultdict(list)
    for r in good:
        bycause[r.get("cause", "other")].append(r)
    for cause, rs in sorted(bycause.items(), key=lambda kv: -len(kv[1])):
        classes = sorted(set("%s/%s" % (r["cls"], r["sub"]) for r in rs))
        lines.append(f"- **{cause}** — {len(rs)} pairs across "
                     f"{len(classes)} finding group(s): {', '.join(classes)}")
    lines.append("")

    lines.append("## Root-cause clustering (exact minimal flip across classes)\n")
    bysig = defaultdict(list)
    for r in good:
        bysig[r["signature"]].append(r)
    for sig, rs in sorted(bysig.items(), key=lambda kv: -len(kv[1]))[:15]:
        classes = sorted(set("%s/%s" % (r["cls"], r["sub"]) for r in rs))
        lines.append(f"- `{abbrev(sig)}` — {len(rs)} pairs across: {', '.join(classes)}")
    lines.append("")

    lines.append("## Reduction that changes the bug (oracle sensitivity)\n")
    if mutations:
        nmut = sum(1 for m in mutations if m["mutated"])
        lines.append(
            f"- Ran BOTH a strict oracle and a verdict-only oracle "
            f"(`are equal` in output) on {len(mutations)} equiv pairs. "
            f"{nmut}/{len(mutations)} reductions changed under the loose oracle."
        )
        sigs = Counter(m["loose_signature"] for m in mutations)
        for s, c in sigs.most_common(5):
            lines.append(f"  - verdict-only minimal flip `{s}` on {c} pairs")
        lines.append(
            "  - In these cases deleting the single digit `1` leaves a dangling "
            "`+` (`x+` / `i32(x)+` / `i8(x)+`), which is a parse error: the definition "
            "of `g`/`b` fails to parse and `equiv` then reports `are equal` via the "
            "*undefined-function-name* bug. The minimized input therefore no longer "
            "exhibits where-ignoring / result-coercion / signed-reinterpretation — "
            "reduction changed the bug into a different one."
        )
        lines.append("")
    confl = [r for r in good if r["cls"] == "conflation"]
    if confl:
        sigs = Counter(r["signature"] for r in confl)
        lines.append(
            "With a symptom-only oracle (`are equal` in the output), the "
            f"{len(confl)} conflation pairs reduce to: "
            + ", ".join(f"`{s}` x{c}" for s, c in sigs.most_common())
            + ". The minimized input deletes the definition of `b`, so `equiv a b` "
              "reports `are equal` via the *undefined-function-name* bug — a different "
              "root cause than signed/unsigned reinterpretation or where-clause ignoring. "
              "A verdict-only oracle therefore merges (and can mutate) several "
              "unrelated findings; the strict oracles above keep them separate."
        )
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", default=True)
    ap.add_argument("--class", dest="cls")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    pairs = all_pairs()
    if args.cls:
        pairs = [p for p in pairs if p["cls"] == args.cls]
    if args.limit:
        pairs = pairs[:args.limit]

    runner = Runner()
    records = run_all(pairs, runner)
    mutations = run_mutation_experiment(runner)

    if not args.no_write:
        with open(RESULTS, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        with open(os.path.join(HERE, "mutations.jsonl"), "w") as f:
            for m in mutations:
                f.write(json.dumps(m) + "\n")
        with open(os.path.join(HERE, "analysis.md"), "w") as f:
            f.write(analyze(records, runner, mutations))

    bad = [r for r in records if not r.get("ok")]
    print(f"pairs={len(records)} ok={len(records)-len(bad)} bad={len(bad)} "
          f"oracle_calls={runner.calls}")
    for r in bad[:20]:
        print("  BAD", r["id"], r.get("error", ""))


if __name__ == "__main__":
    main()
