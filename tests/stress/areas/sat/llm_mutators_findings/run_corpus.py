#!/usr/bin/env python3
"""
Validate + execute the neighbourhood-mutation corpus.

For every mutation produced by generate.py:
  * materialise the input (a .ucas file for CLI, JSON-RPC/JSON-Lines for the
    wire frontends) in a scratch dir under /tmp/opencode,
  * run it under `timeout 15`,
  * classify the outcome as: semantic | parse_error | structured_error |
    crash | hang | empty  (i.e. which mutations "still parse / produce a
    structured response" and which reach a semantic pass vs only parse
    errors),
  * apply a per-family oracle that recognises the signature of the *known*
    bug class, so we can count new instances in new types/commands/frontends
    and flag anything anomalous.

Writes results.jsonl (one record per mutation) and prints run_summary.txt.
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
import json
import os
import re
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = str(_REPO_ROOT / "ucas")
SCRATCH = "/tmp/opencode/llm_mut_scratch"
os.makedirs(SCRATCH, exist_ok=True)

with open(os.path.join(HERE, "mutations.json")) as fh:
    MUTS = json.load(fh)

# output keywords that indicate a semantic pass actually ran
RESULT_KW = [
    "are equal", "differ at", "range of", "domain of", "wrap analysis",
    "symmetry of", "power series", "Taylor coefficients", "max abs error",
    "max rel error", "note: mixing", "-> u8", "-> i8", "-> bool", "-> real",
    "∫", "y(t)", "sorry:", "ucas: it", "fits in", "over all", "defined at",
    "undefined e.g.", "C undefined behaviour", "samples", "identify",
    "headline", "not exhaustive", "equal:", "equal,", "max error",
    "value:", "=>", "has no", "read the interval", "disagrees",
    "ucas:", "not a word I know", "does not fit bool", "literal",
]
PARSE_KW = ["expected an expression", "unexpected character", "parse error",
            "parse_error", "bad_json", "expected a number", "expected a name",
            "unclosed", "unmatched", "too many nested"]


def classify_cli(out, rc):
    t = out
    if rc == 124:
        return "hang"
    if rc < 0 or rc >= 128:
        return "crash"
    has_result = any(k in t for k in RESULT_KW)
    has_err = bool(re.search(r":\d+:\d+: error:", t)) or "error:" in t
    if has_result:
        return "semantic"
    if has_err or any(k in t for k in PARSE_KW):
        return "parse_error"
    if not t.strip():
        return "empty"
    return "other"


def classify_json(out, rc):
    if rc == 124:
        return "hang"
    if rc < 0 or rc >= 128:
        return "crash"
    objs = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            objs.append(json.loads(line))
        except Exception:
            pass
    if not objs:
        return "empty" if not out.strip() else "other"
    sem = err = 0
    parse = crash = False
    for o in objs:
        if o.get("structured") is True:
            sem += 1
        if o.get("id") in (None, False) and "error" in o:
            err += 1
        e = o.get("error")
        if isinstance(e, dict):
            code = e.get("code", "")
            if code in ("parse_error", "ambiguous", "bad_json", "not_understood"):
                parse = True
            if code == "internal" and "signal" in str(e.get("message", "")):
                crash = True
    if crash:
        return "crash"
    if sem:
        return "semantic"
    if parse:
        return "parse_error"
    if err or any("error" in o for o in objs):
        return "structured_error"
    return "other"


def classify_mcp(out, rc):
    if rc == 124:
        return "hang"
    if rc < 0 or rc >= 128:
        return "crash"
    responses = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("id", -1) == 0:
            continue
        responses.append(o)
    if not responses:
        return "empty" if not out.strip() else "other"
    sem = parse = crash = False
    for o in responses:
        txt = json.dumps(o)
        # structuredContent lives inside result{}, not at the top level
        if '"structuredContent"' in txt and '"isError": true' not in txt:
            sem = True
        if "error (parse_error)" in txt or '"code": "parse_error"' in txt \
           or '"code":"parse_error"' in txt or '"code": "ambiguous"' in txt:
            parse = True
        if '"code": "internal"' in txt and "signal" in txt:
            crash = True
        if "evaluation crashed" in txt or "signal 11" in txt:
            crash = True
    if crash:
        return "crash"
    if sem:
        return "semantic"
    if parse:
        return "parse_error"
    if any("error" in o for o in responses):
        return "structured_error"
    return "other"


def oracle(family, t, cls):
    """Return list of known-bug signatures present in output t."""
    h = []
    if family == "equiv_domain":
        if ("are equal" in t and "on the domain of" in t) or '"equal": true' in t:
            h.append("equiv_ignores_G_domain")
        if '"where"' in t or "ignored" in t.lower():
            h.append("where_key_ignored?")
    elif family == "real_identity":
        if "differ at" in t:
            h.append("true_identity_refuted")
        m = re.search(r":\s*(-?[\d.]+)\s+vs\s+(-?[\d.]+)", t)
        if m and m.group(1) == m.group(2):
            h.append("identical_counterexample")
    elif family == "cast_coercion":
        if "are equal" in t and "domain of" in t:
            h.append("cast_coercion_equal")
    elif family == "domain_total":
        if "no conditions: total" in t and "defined at 0 of" in t:
            h.append("total_but_0_defined")
    elif family == "range_spike":
        if re.search(r"\[0,\s*0\]", t) or re.search(r"\b0\.\.0\b", t) \
           or "0..65408" in t:
            h.append("range_excludes_reachable")
    elif family == "mixed_sign":
        if "note: mixing" in t:
            h.append("mixed_sign_reinterpret")
    elif family == "symmetry_both":
        if "yes (symmetric)" in t and "yes (antisymmetric)" in t:
            h.append("symmetric_and_antisymmetric")
    elif family == "powerseries_var":
        m = re.search(r"power series of ([^\n]+)", t)
        if m and ("*x" in m.group(1) or "* x" in m.group(1)):
            h.append("powerseries_times_x")
    elif family == "laplace_ic":
        if "y(0) not given" in t or '"value": "0"' in t or "y(t) = 0" in t:
            h.append("laplace_ic_dropped")
    elif family == "stale_autoname":
        if '"equal": false' in t or "differ at" in t:
            h.append("stale_autoname_false")
    elif family == "english_boundflip":
        if "read the interval as [" in t:
            h.append("english_ascending_flip")
    elif family == "vacuous":
        if "are equal" in t and "domain of" in t and "defined at 0 of" in t:
            h.append("vacuous_equal")
    elif family == "deep_nesting":
        if cls in ("crash", "parse_error"):
            h.append("parser_limit")
    elif family == "nlp_number":
        if any(k in t for k in ["read as", "juxtaposition", "_()", "it(",
                                "sorry:", "-> u8", "note:"]):
            h.append("nlp_misparse")
    return h


def materialise(m):
    """Return (argv, stdin_bytes)."""
    fe = m["frontend"]
    prog = m["program"]
    name = "mut_%03d" % m["id"]
    if fe == "cli":
        path = os.path.join(SCRATCH, name + ".ucas")
        with open(path, "w") as fh:
            fh.write(prog)
        return [BIN, path], None
    if fe == "json":
        return [BIN, "--json", "--files", "none"], ("\n".join(prog) + "\n").encode()
    if fe == "mcp":
        return [BIN, "--mcp"], ("\n".join(prog) + "\n").encode()
    if fe == "mcp_flat":
        return [BIN, "--mcp", "--flat"], ("\n".join(prog) + "\n").encode()
    raise ValueError("bad frontend " + fe)


results = []
t0 = time.time()
for m in MUTS:
    argv, stdin = materialise(m)
    started = time.time()
    try:
        p = subprocess.run(argv, input=stdin, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=15)
        rc, out = p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        rc = 124
        out = (e.stdout or b"").decode("utf-8", "replace")
    elapsed = round(time.time() - started, 3)
    fe = m["frontend"]
    if fe == "cli":
        cls = classify_cli(out, rc)
    elif fe == "json":
        cls = classify_json(out, rc)
    else:
        cls = classify_mcp(out, rc)
    hits = oracle(m["family"], out, cls)
    results.append({
        "id": m["id"], "family": m["family"], "shape": m["shape"],
        "frontend": fe, "origin": m["origin"], "rc": rc, "sec": elapsed,
        "cls": cls, "hits": hits, "out": out[:6000],
    })

with open(os.path.join(HERE, "results.jsonl"), "w") as fh:
    for r in results:
        fh.write(json.dumps(r) + "\n")

# ---- aggregate ----
from collections import Counter, defaultdict
by_cls = Counter(r["cls"] for r in results)
by_fam = defaultdict(Counter)
hits = Counter()
for r in results:
    by_fam[r["family"]][r["cls"]] += 1
    for h in r["hits"]:
        hits[h] += 1

lines = ["# Corpus run summary", "",
         "seed 20261116 | %d mutations | %.1fs wall" % (len(results), time.time() - t0),
         "", "## By outcome class", ""]
for k in ["semantic", "parse_error", "structured_error", "crash", "hang", "empty", "other"]:
    lines.append("  %-17s %d" % (k, by_cls.get(k, 0)))
lines += ["", "## By family", ""]
for fam in sorted(by_fam):
    c = by_fam[fam]
    lines.append("  %-18s sem=%-3d parse=%-3d crash=%-2d hang=%-2d other=%d" % (
        fam, c.get("semantic", 0), c.get("parse_error", 0),
        c.get("crash", 0), c.get("hang", 0),
        sum(v for k, v in c.items() if k not in
            ("semantic", "parse_error", "crash", "hang"))))
lines += ["", "## Known-bug signatures matched", ""]
for k, v in hits.most_common():
    lines.append("  %-32s %d" % (k, v))
lines += ["", "## Anomalies that need eyeballing (crash/hang/structured_error,",
          "or semantic with no known signature)", ""]
for r in results:
    odd = r["cls"] in ("crash", "hang", "structured_error") or \
          (r["cls"] == "semantic" and not r["hits"])
    if odd:
        lines.append("  #%d %-18s %-9s rc=%-4s hits=%s | %s" % (
            r["id"], r["family"], r["cls"], r["rc"], r["hits"],
            r["shape"][:60]))
lines.append("")
txt = "\n".join(lines)
with open(os.path.join(HERE, "run_summary.txt"), "w") as fh:
    fh.write(txt)
print(txt)
