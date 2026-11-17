#!/usr/bin/env python3
"""
seed_env_control stress harness.

Area: seed handling and reproducibility of the stochastic verifiers
(`pit`, `stoke`, `find`, `approx`, `numsearch`/`qmc`) across CLI, JSON and MCP
frontends.

The harness does three things:

  1. RUNS a large matrix (200+ distinct invocations) of seed-bearing commands:
     UCAS_SEED environment values (valid / invalid / negative / huge / lexical
     oddities), explicit `seed K` arguments, JSON `seed` arguments, MCP
     `seed` arguments, genuinely-equal vs genuinely-different polynomial pairs
     compared under seeds 0/1/2, and repeated runs under a fixed seed.

  2. CLASSIFIES every result (exit code, verdict, seed echoed, crash / timeout)
     into results.json so the matrix is reproducible and auditable.

  3. EMITS durable goldens that are fixed-seed deterministic only:
       NN_*.ucas + NN_*.out        (CLI, run by tests/stress/run.sh)
       json_*.jsonl + json_*.out   (--json --files none, run by run.sh)
       mcp_*.jsonl + mcp_*.out     (--mcp, run by run.sh)
     A candidate golden is written only after two identical runs (diff).
     Env-dependent cases are captured by run_seed_matrix.sh instead.

Hard rules honoured: absolute binary path; every subprocess under timeout;
writes confined to this folder; no source / Makefile / git / shared-file edits.

Usage:
    python3 harness.py            # run everything, (re)generate goldens + results.json
    python3 harness.py --no-goldens   # only run the matrix and write results.json
    python3 harness.py --quick        # smaller subset (smoke)
"""
from __future__ import annotations

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
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

BIN = str(_REPO_ROOT / "ucas")
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results.json"
DEFAULT_TIMEOUT = 15

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:16]


def run(argv: list[str], *, env: dict | None = None,
        stdin: str | None = None, timeout: int = DEFAULT_TIMEOUT,
        cwd: Path = HERE) -> dict:
    """Run one bounded subprocess, return rc / combined output / elapsed."""
    e = os.environ.copy()
    e.pop("UCAS_SEED", None)             # default: unset unless explicitly set
    if env:
        e.update(env)
    t0 = time.time()
    try:
        p = subprocess.run(argv, input=stdin, capture_output=True, text=True,
                           timeout=timeout, env=e, cwd=str(cwd))
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as ex:
        rc = 124
        out = ex.stdout or ""
        err = ex.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
    return {"rc": rc, "text": out + err, "elapsed": round(time.time() - t0, 3)}


def run_cli(script: str, *, env: dict | None = None,
            timeout: int = DEFAULT_TIMEOUT) -> dict:
    return run([BIN, "-e", script], env=env, timeout=timeout)


def run_json(lines: str, *, env: dict | None = None,
             timeout: int = DEFAULT_TIMEOUT) -> dict:
    return run([BIN, "--json", "--files", "none"], env=env, stdin=lines,
               timeout=timeout)


def run_mcp(lines: str, *, env: dict | None = None,
            timeout: int = DEFAULT_TIMEOUT) -> dict:
    return run([BIN, "--mcp"], env=env, stdin=lines, timeout=timeout)


INIT = [
    {"jsonrpc": "2.0", "id": 0, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "stress", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
]


def mcp_lines(calls: list[tuple[int, str, dict]]) -> str:
    out = [json.dumps(x) for x in INIT]
    for cid, name, args in calls:
        out.append(json.dumps({"jsonrpc": "2.0", "id": cid,
                               "method": "tools/call",
                               "params": {"name": name, "arguments": args}}))
    return "\n".join(out) + "\n"


def verdict(text: str) -> str:
    """Classify a result into a stable label (benign 'error' words in notes
    and in 'standard error' must not be mistaken for a failure)."""
    if "differ as polynomials" in text:
        return "DIFFER"
    if "equal as polynomials" in text:
        return "EQUAL"
    if "not polynomials over the integers" in text:
        return "NOPOLY"
    if ("pit: seed K" in text or "stoke: seed K" in text or
            "seed: a whole number" in text or
            '"message": "seed: an integer"' in text or
            '"message":"seed: an integer"' in text):
        return "SEED_REJECT"
    # a real diagnostic: CLI "<file>:<line>:<col>: error: ..." or JSON/MCP error
    if ": error:" in text or '"ok": false' in text or '"ok":false' in text \
            or '"isError": true' in text or '"isError":true' in text:
        return "ERROR"
    return "OK"


def echoed_seed(text: str) -> str | None:
    for line in text.splitlines():
        if "Schwartz-Zippel), seed " in line:
            return line.rsplit("seed ", 1)[-1].strip()
    return None


# ---------------------------------------------------------------------------
# case matrix
# ---------------------------------------------------------------------------

@dataclass
class Case:
    group: str
    key: str
    interface: str            # cli | json | mcp
    command: str              # human-readable description
    argv_or_script: str       # the script (cli) or jsonl (json/mcp)
    env: dict = field(default_factory=dict)
    timeout: int = DEFAULT_TIMEOUT
    # filled by run()
    rc: int | None = None
    output: str = ""
    elapsed: float = 0.0
    v: str = ""
    seed: str | None = None

    def execute(self) -> dict:
        if self.interface == "cli":
            r = run_cli(self.argv_or_script, env=self.env, timeout=self.timeout)
        elif self.interface == "json":
            r = run_json(self.argv_or_script, env=self.env, timeout=self.timeout)
        else:
            r = run_mcp(self.argv_or_script, env=self.env, timeout=self.timeout)
        self.rc, self.output, self.elapsed = r["rc"], r["text"], r["elapsed"]
        self.v = verdict(self.output)
        self.seed = echoed_seed(self.output)
        return r


# seed strings for the UCAS_SEED environment (strtoull base 10, no validation)
ENV_SEEDS = [
    # valid decimal
    "0", "1", "2", "3", "7", "42", "100", "255", "65535", "1000000",
    "2147483647", "4294967295", "9223372036854775807", "9223372036854775808",
    "18446744073709551614", "18446744073709551615",
    # overflow / negative / invalid strings
    "18446744073709551616", "9999999999999999999999999", "-1", "-0",
    "-00000000000000000001", "-9223372036854775809", "abc", "xyz", "nan",
    "inf", "1.5", "1e3", "0x10", "0b101", "1_000", "12junk", "+7abc",
    " 5x", "5 ", "   ", "+", "-", "",
]

# explicit seed tokens for CLI `pit ... seed K`
EXPLICIT_PIT_SEEDS = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
    "13", "17", "42", "100", "255", "1000", "65535", "2147483647",
    "4294967295", "9223372036854775807", "9223372036854775808",
    "18446744073709551614", "18446744073709551615",
    "-1", "-0", "+1", "1.5", "1e3", "0x10", "12junk",
]

# explicit seeds for `approx` (different parser: double, 0..9e15)
EXPLICIT_APPROX_SEEDS = [
    "0", "1", "2", "7", "42", "1000", "9000000000000000",
    "9223372036854775807", "18446744073709551615", "-1",
]

# explicit seeds for `stoke` (same parser as pit)
EXPLICIT_STOKE_SEEDS = ["0", "1", "2", "5", "42", "2147483647",
                        "18446744073709551615", "-1"]

# JSON numeric seed values (P_INT: J_NUM, integral, |v| <= 1e15)
JSON_SEEDS = [
    0, 1, 2, 7, 42, 1000, 1000000000000000, 1000000000000001,
    9223372036854775807, -1, -0, 1e3, 1.5, True, None,
]

EQUAL_FUNCS = [
    ("f(x:i64)=x+1", "g(x:i64)=1+x"),
    ("f(x:i64)=x*x", "g(x:i64)=x^2"),
    ("f(x:i64,y:i64)=(x+y)^2", "g(x:i64,y:i64)=x*x+2*x*y+y*y"),
    ("f(x:i64)=x*(x+1)", "g(x:i64)=x^2+x"),
    ("f(x:i64)=(x-1)*(x+1)", "g(x:i64)=x^2-1"),
    ("f(x:i64)=x^3+1", "g(x:i64)=(x+1)*(x*x-x+1)"),
]
DIFFER_FUNCS = [
    ("f(x:i64)=x", "g(x:i64)=x+1"),
    ("f(x:i64)=x^2", "g(x:i64)=x^3"),
    ("f(x:i64,y:i64)=x*y", "g(x:i64,y:i64)=x*y+1"),
    ("f(x:i64,y:i64)=(x+y)^2", "g(x:i64,y:i64)=x*x+y*y"),
    ("f(x:i64)=x^2+2*x+1", "g(x:i64)=x^2+2*x"),
    ("f(x:i64,y:i64)=x^3+y^3", "g(x:i64,y:i64)=(x+y)^3"),
]
# difference is an exact multiple of PIT_P = 2^61-1 -> false "equal"
FALSE_EQUAL_FUNCS = [
    ("f(x:i64)=x", "g(x:i64)=x+2305843009213693951"),
    ("f(x:i64)=0", "g(x:i64)=2305843009213693951"),
    ("f(x:i64)=x^2", "g(x:i64)=x^2+2305843009213693951"),
    ("f(x:i64,y:i64)=x*y", "g(x:i64,y:i64)=x*y+2305843009213693951*x"),
    ("f(x:i64)=x^3+2*x", "g(x:i64)=x^3+2*x+2305843009213693951*x*x"),
    ("f(x:i64,y:i64)=x^2+y^2", "g(x:i64,y:i64)=x^2+y^2+2305843009213693951*y"),
]

PIT_EQ = "f(x:i64)=x+1\ng(x:i64)=1+x\n"


def build_cases(quick: bool = False) -> list[Case]:
    c: list[Case] = []

    # A: UCAS_SEED environment values, observed via `pit` echoing the seed.
    for s in ENV_SEEDS:
        c.append(Case("A_env_seed", repr(s), "cli",
                      f"UCAS_SEED={s!r} pit on equal polys",
                      PIT_EQ + "pit f g trials 4", {"UCAS_SEED": s}))

    # B: explicit `seed K` on pit (CLI parser: cmdp_int, full uint64 bit pattern).
    for s in (EXPLICIT_PIT_SEEDS[:12] if quick else EXPLICIT_PIT_SEEDS):
        c.append(Case("B_explicit_pit", s, "cli", f"pit ... seed {s}",
                      PIT_EQ + f"pit f g trials 4 seed {s}"))

    # C: explicit seeds on stoke (small budget so it stays fast).
    for s in (EXPLICIT_STOKE_SEEDS if not quick else ["0", "1", "5", "-1"]):
        c.append(Case("C_explicit_stoke", s, "cli", f"stoke ... seed {s}",
                      "f(x:i32)=x*x+2*x+1\n"
                      f"stoke f steps 100 restarts 1 len 6 seed {s}",
                      timeout=DEFAULT_TIMEOUT))

    # D: explicit seeds on approx (double parser, 0..9e15).
    for s in EXPLICIT_APPROX_SEEDS:
        c.append(Case("D_explicit_approx", s, "cli", f"approx ... seed {s}",
                      "approx sin(x) in 0..0.7853981 degree 3 as f32 list 1 "
                      f"search anneal seed {s} budget 50", timeout=30))

    # E: qmc seeds via UCAS_SEED (env path) and explicit seed.
    for s in ["0", "1", "2", "42", "-1", "18446744073709551615", "abc"]:
        c.append(Case("E_qmc_env", s, "cli", f"qmc with UCAS_SEED={s!r}",
                      "integrate x^2 from 0 to 1 numerically qmc points 1024 "
                      "replicates 2", {"UCAS_SEED": s}))
    for s in ["0", "1", "2", "42", "1000000000000000",
              "18446744073709551615", "-1"]:
        c.append(Case("E_qmc_explicit", s, "cli", f"qmc ... seed {s}",
                      "integrate x^2 from 0 to 1 numerically qmc points 1024 "
                      f"replicates 2 seed {s}"))

    # F: JSON-mode seed args (`pit`): P_INT accepts integral |v| <= 1e15.
    for v in (JSON_SEEDS if not quick else [0, 1, -1, 1.5]):
        req = {"id": 1, "cmd": "pit",
               "args": {"f": "x^2", "g": "x*x", "trials": 2, "seed": v}}
        c.append(Case("F_json_seed", repr(v), "json", f"JSON pit seed={v!r}",
                      json.dumps(req) + "\n"))

    # F2: JSON seeds as strings / special tokens.
    for tok in ['"abc"', '"5"', '"1e3"', "1e400", "-1e400", "18446744073709551616"]:
        line = ('{"id":1,"cmd":"pit","args":{"f":"x^2","g":"x*x",'
                f'"trials":2,"seed":{tok}}}}}\n')
        c.append(Case("F_json_seed_token", tok, "json", f"JSON pit seed token={tok}",
                      line))

    # F3: JSON seed with UCAS_SEED set but no explicit seed.
    for s in ["0", "1", "42", "-1", "abc", "18446744073709551615"]:
        req = {"id": 1, "cmd": "pit",
               "args": {"f": "x^2", "g": "x*x", "trials": 2}}
        c.append(Case("F_json_env_seed", repr(s), "json",
                      f"JSON pit with UCAS_SEED={s!r}", json.dumps(req) + "\n",
                      {"UCAS_SEED": s}))

    # G: MCP seed args.
    for v in (JSON_SEEDS[:10] if quick else JSON_SEEDS):
        calls = [(1, "analyze", {"op": "pit",
                                 "args": {"f": "x^2", "g": "x*x",
                                          "trials": 2, "seed": v}})]
        c.append(Case("G_mcp_seed", repr(v), "mcp", f"MCP pit seed={v!r}",
                      mcp_lines(calls)))
    for tok in ["-1", "18446744073709551615", '"abc"', "1e400"]:
        line = ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":'
                '{"name":"analyze","arguments":{"op":"pit","args":'
                '{"f":"x^2","g":"x*x","trials":2,'
                f'"seed":{tok}}}}}}}\n')
        c.append(Case("G_mcp_seed_token", tok, "mcp",
                      f"MCP pit seed token={tok}",
                      "\n".join(json.dumps(x) for x in INIT) + "\n" + line))

    # H: genuinely equal / genuinely different / false-equal pairs under 3 seeds.
    for tag, pairs in [("equal", EQUAL_FUNCS), ("differ", DIFFER_FUNCS),
                       ("false_equal", FALSE_EQUAL_FUNCS)]:
        for i, (d1, d2) in enumerate(pairs):
            for s in (0, 1, 2):
                script = f"{d1}\n{d2}\npit f g trials 8 seed {s}\n"
                c.append(Case("H_verdict", f"{tag}_{i}_seed{s}", "cli",
                              f"{tag} pair #{i}, seed {s}", script))

    # I: repeated runs under a fixed seed must be byte-identical.
    repeat_cmds = [
        ("pit_equal_seed0", PIT_EQ + "pit f g trials 8 seed 0"),
        ("pit_equal_seed1", PIT_EQ + "pit f g trials 8 seed 1"),
        ("pit_differ_seed2", "f(x:i64)=x\ng(x:i64)=x+1\npit f g trials 8 seed 2"),
        ("stoke_seed5", "f(x:i32)=x*x+2*x+1\nstoke f steps 100 restarts 1 len 6 seed 5"),
        ("approx_seed5", "approx sin(x) in 0..0.7853981 degree 3 as f32 list 1 "
                         "search anneal seed 5 budget 50"),
        ("qmc_seed7", "integrate x^2 from 0 to 1 numerically qmc points 1024 "
                      "replicates 2 seed 7"),
    ]
    for name, script in repeat_cmds:
        for rep in range(3):
            c.append(Case("I_repeat", f"{name}_run{rep}", "cli",
                          f"repeat {name}, run {rep}", script, timeout=30))

    # J: cross-interface same-seed comparison (CLI vs JSON vs MCP).
    for s in [0, 1, 42]:
        cli = PIT_EQ + f"pit f g trials 4 seed {s}"
        c.append(Case("J_cross_cli", str(s), "cli", f"CLI pit seed {s}", cli))
        jreq = {"id": 1, "cmd": "pit",
                "args": {"f": "x^2", "g": "x*x", "trials": 4, "seed": s}}
        c.append(Case("J_cross_json", str(s), "json", f"JSON pit seed {s}",
                      json.dumps(jreq) + "\n"))
        mcall = [(1, "analyze", {"op": "pit",
                                 "args": {"f": "x^2", "g": "x*x",
                                          "trials": 4, "seed": s}})]
        c.append(Case("J_cross_mcp", str(s), "mcp", f"MCP pit seed {s}",
                      mcp_lines(mcall)))

    return c


# ---------------------------------------------------------------------------
# golden generation (deterministic only)
# ---------------------------------------------------------------------------

def write_golden(path: Path, content: str, argv: list[str], *,
                 stdin: str | None = None) -> bool:
    """Write a candidate input, run it twice; keep .out only if identical."""
    path.write_text(content)
    a = run(argv, stdin=stdin, cwd=HERE)
    b = run(argv, stdin=stdin, cwd=HERE)
    if a["rc"] != b["rc"] or a["text"] != b["text"]:
        return False
    path.with_suffix(".out").write_text(a["text"])
    return True


def build_goldens() -> list[str]:
    made: list[str] = []

    # CLI golden 1: explicit seeds on pit, valid + rejected.
    seeds = ["0", "1", "2", "7", "42", "1000", "65535", "2147483647",
             "4294967295", "9223372036854775807", "9223372036854775808",
             "18446744073709551614", "18446744073709551615", "-1", "-0",
             "+1", "1.5", "1e3", "0x10", "12junk"]
    lines = [PIT_EQ.rstrip()]
    for s in seeds:
        lines.append(f"pit f g trials 2 seed {s}")
    body = "\n".join(lines) + "\n"
    if write_golden(HERE / "01_pit_explicit_seed.ucas", body,
                    [BIN, "01_pit_explicit_seed.ucas"]):
        made.append("01_pit_explicit_seed")

    # CLI golden 2: genuinely equal / different corpus, fixed seed.
    lines = []
    for tag, pairs in [("equal", EQUAL_FUNCS), ("differ", DIFFER_FUNCS)]:
        for d1, d2 in pairs:
            lines += [d1, d2, "pit f g trials 8 seed 1"]
    body = "\n".join(lines) + "\n"
    if write_golden(HERE / "02_pit_equal_vs_differ.ucas", body,
                    [BIN, "02_pit_equal_vs_differ.ucas"]):
        made.append("02_pit_equal_vs_differ")

    # CLI golden 3: PIT_P false-equal family (WRONG verdict, deterministic).
    lines = []
    for d1, d2 in FALSE_EQUAL_FUNCS:
        lines += [d1, d2, "pit f g trials 8 seed 0"]
    body = "\n".join(lines) + "\n"
    if write_golden(HERE / "03_pit_p_multiple_false_equal.ucas", body,
                    [BIN, "03_pit_p_multiple_false_equal.ucas"]):
        made.append("03_pit_p_multiple_false_equal")

    # CLI golden 4: qmc fixed explicit seeds.
    lines = []
    for s in ["0", "1", "2", "7", "42", "1000"]:
        lines.append(f"integrate x^2 from 0 to 1 numerically qmc points 1024 "
                     f"replicates 2 seed {s}")
    body = "\n".join(lines) + "\n"
    if write_golden(HERE / "04_qmc_explicit_seed.ucas", body,
                    [BIN, "04_qmc_explicit_seed.ucas"]):
        made.append("04_qmc_explicit_seed")

    # CLI golden 5: approx fixed seed (short, fast).
    body = ("approx sin(x) in 0..0.7853981 degree 3 as f32 list 1 "
            "search anneal seed 5 budget 50\n")
    if write_golden(HERE / "05_approx_seed.ucas", body,
                    [BIN, "05_approx_seed.ucas"]):
        made.append("05_approx_seed")

    # JSON goldens: seed arg accepted / rejected + env fallback.
    jlines = []
    for i, v in enumerate([0, 1, 2, 7, 42, 1000000000000000, -1, 1.5, 1e3], 1):
        jlines.append(json.dumps({"id": i, "cmd": "pit",
                                  "args": {"f": "x^2", "g": "x*x",
                                           "trials": 2, "seed": v}}))
    body = "\n".join(jlines) + "\n"
    if write_golden(HERE / "json_seed_args.jsonl", body,
                    [BIN, "--json", "--files", "none"], stdin=body):
        made.append("json_seed_args")

    # MCP golden: seed arg accepted / rejected.
    calls = [(i + 1, "analyze", {"op": "pit",
                                "args": {"f": "x^2", "g": "x*x",
                                         "trials": 2, "seed": v}})
             for i, v in enumerate([0, 1, 2, 7, 42, 1000000000000000, -1, 1.5, 1e3])]
    body = mcp_lines(calls)
    if write_golden(HERE / "mcp_seed_args.jsonl", body,
                    [BIN, "--mcp"], stdin=body):
        made.append("mcp_seed_args")

    return made


def write_env_matrix() -> None:
    """No-op kept for API compatibility; the matrix lives in run_seed_matrix.py."""
    return


def _legacy_write_env_matrix() -> None:
    """Durable env-seed matrix runner (env is per-process, not per-statement).

    The expected seed echoes are the empirically verified strtoull(base 10)
    semantics from stoch.c:117-125: leading whitespace skipped, optional sign,
    longest decimal prefix, ULLONG_MAX saturation, '-' negation, empty -> 1.
    """
    script = r'''#!/bin/sh
# Durable UCAS_SEED matrix.  Source: stoch.c:117-125,
#   if (e && *e) return strtoull(e, NULL, 10); else return 1;
# Every run is bounded; output is compared to the seed the binary echoes.
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
BIN="$ROOT/ucas"
SCRIPT='f(x:i64)=x+1
g(x:i64)=1+x
pit f g trials 4'
fail=0; n=0
check() {
  want=$1; seed=$2
  got=$(UCAS_SEED="$seed" timeout 15 "$BIN" -e "$SCRIPT" 2>&1 | head -1)
  n=$((n+1))
  case "$got" in *"seed $want"*) : ;; *) echo "FAIL UCAS_SEED=[$seed] want seed $want got: $got"; fail=$((fail+1));; esac
}
check 0 abc
check 0 xyz
check 0 nan
check 0 inf
check 0 '+'
check 0 '-'
check 1 1.5
check 1 1e3
check 1 1_000
check 12 12junk
check 5 5x
check 7 +7abc
check 5 ' 5x'
check 5 '5 '
check 0 '   '
check 0 ' '
check 1 ''
check 0 -0
check 18446744073709551615 -1
check 18446744073709551615 -00000000000000000001
check 9223372036854775807 -9223372036854775809
check 18446744073709551615 18446744073709551616
check 18446744073709551615 9999999999999999999999999
check 18446744073709551615 18446744073709551615
check 18446744073709551614 18446744073709551614
check 9223372036854775808 9223372036854775808
check 0 0
check 1 1
check 2 2
check 42 42
check 1000000 1000000
got=$(UCAS_SEED=7 timeout 15 "$BIN" -e "$SCRIPT
pit f g trials 4 seed 0" 2>&1 | grep 'Schwartz-Zippel), seed' | tail -1)
n=$((n+1)); case "$got" in *'seed 0'*) : ;; *) echo "FAIL override got: $got"; fail=$((fail+1));; esac
got=$(env -u UCAS_SEED timeout 15 "$BIN" -e "$SCRIPT" 2>&1 | head -1)
n=$((n+1)); case "$got" in *'seed 1'*) : ;; *) echo "FAIL default got: $got"; fail=$((fail+1));; esac
echo "seed matrix: $n runs, $fail failures"
[ "$fail" -eq 0 ]
'''
    p = HERE / "run_seed_matrix.sh"
    p.write_text(script)
    p.chmod(0o755)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-goldens", action="store_true")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    cases = build_cases(quick=args.quick)
    t0 = time.time()
    for case in cases:
        case.execute()
    elapsed = time.time() - t0

    # determinism check for repeat group
    repeat_ok = True
    by_key: dict[str, list[Case]] = {}
    for cse in cases:
        if cse.group == "I_repeat":
            by_key.setdefault(cse.key.rsplit("_run", 1)[0], []).append(cse)
    repeat_detail = {}
    for key, runs in by_key.items():
        texts = {(r.rc, r.output) for r in runs}
        ok = len(texts) == 1
        repeat_ok &= ok
        repeat_detail[key] = {"identical": ok, "distinct": len(texts)}

    # results.json (compact: omit full output except for anomalies)
    anomalies = []
    for cse in cases:
        if cse.rc != 0 or cse.rc == 124 or cse.v in ("SEED_REJECT", "ERROR"):
            anomalies.append({"group": cse.group, "key": cse.key,
                              "interface": cse.interface, "command": cse.command,
                              "rc": cse.rc, "verdict": cse.v,
                              "seed": cse.seed,
                              "output": cse.output[:900]})
    payload = {
        "binary": BIN,
        "total_cases": len(cases),
        "elapsed_s": round(elapsed, 1),
        "groups": {g: sum(1 for c in cases if c.group == g)
                   for g in sorted({c.group for c in cases})},
        "env_seed_echo": {c.key: c.seed for c in cases if c.group == "A_env_seed"},
        "explicit_pit": {c.key: {"rc": c.rc, "v": c.v, "seed": c.seed}
                         for c in cases if c.group == "B_explicit_pit"},
        "verdict_matrix": {c.key: c.v for c in cases if c.group == "H_verdict"},
        "repeat_detail": repeat_detail,
        "repeat_all_identical": repeat_ok,
        "anomalies": anomalies,
        "all_cases": [{"group": c.group, "key": c.key,
                       "interface": c.interface, "command": c.command,
                       "env": c.env, "rc": c.rc, "elapsed": c.elapsed,
                       "verdict": c.v, "seed": c.seed,
                       "sha": sha(c.output)} for c in cases],
    }
    RESULTS.write_text(json.dumps(payload, indent=1))

    made: list[str] = []
    if not args.no_goldens:
        made = build_goldens()
        write_env_matrix()

    print(f"cases run        : {len(cases)}")
    print(f"elapsed          : {elapsed:.1f}s")
    print(f"groups           : {payload['groups']}")
    print(f"repeat identical : {repeat_ok} {repeat_detail}")
    print(f"anomalies        : {len(anomalies)}")
    print(f"goldens written  : {made}")
    print(f"results          : {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
