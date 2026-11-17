#!/usr/bin/env python3
"""Re-run randomness-prone goldens (find/stoke/pit/gates/approx) many times and
report any run-to-run output drift. These are slower than the main golden sample."""
import argparse, json, os, sys
import soak

TARGETS = [
    "fp_edge/05_rounding", "fp_edge/07_approx",
    "nlp_arith/06_find", "nlp_checklist/01_mft_core", "nlp_checklist/mcp_mft",
    "nlp_checklist/mcp_dir_cost", "nlp_session_state/08_prompts_and_scope",
    "sat_crypto_circuits/10_sbox_tables", "sat_crypto_circuits/12_gates_crypto",
    "sat_crypto_circuits/13_find_crypto", "sat_crypto_circuits/15_gates_budget",
    "sat_crypto_circuits/mcp_sat_crypto",
    "sat_ranges_where/06_multiparam_uniform", "sat_ranges_where/mcp_sat_ranges_where",
    "mcp_api_fuzz/mcp_state",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--budget", type=float, default=420)
    a = ap.parse_args()
    cases = {c["key"]: c for c in soak.discover()}
    import time
    t0 = time.time()
    for key in TARGETS:
        if key not in cases:
            print("SKIP (gone)", key); continue
        c = cases[key]
        soak.stage(c)
        ref = None
        diffs = 0
        outs = set()
        for i in range(a.reps):
            if time.time() - t0 > a.budget:
                print("budget reached"); return
            rc, out, dt, to = soak.run_golden(c)
            outs.add(soak.sha(out))
            if ref is None:
                ref = out
            elif out != ref:
                diffs += 1
                line, x, y = soak.first_diff(ref, out)
                print(f"DRIFT {key} rep={i} line={line}\n   ref={x!r}\n   got={y!r}")
            if to or rc not in (0,):
                print(f"ANOMALY {key} rep={i} rc={rc} timeout={to}")
        print(f"{key}: reps={a.reps} distinct={len(outs)} drift_runs={diffs}")


if __name__ == "__main__":
    main()
