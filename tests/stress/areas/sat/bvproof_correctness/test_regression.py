#!/usr/bin/env python3
"""Self-contained regression checks for verify_bvproof.py.

No ucas binary or golden is needed: the certificates below are built directly
so the conflict test of the propagator is exercised in isolation.

  python3 test_regression.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_bvproof as VV


def one_step_cert(goal, nodes, inputs, nproblem):
    """A result-0 certificate whose only DRUP step is the empty clause."""
    lines = ["BVPROOF 1", "GOAL %d" % goal, "NODES %d" % nodes,
             "INPUTS %d" % len(inputs)]
    lines += ["I %d" % v for v in inputs]
    for i in range(1, nodes):
        lines.append("N %d 0 0" % i)       # an input node
    lines.append("CLAUSES %d STEPS 1 RESULT 0" % (nproblem + 1))
    lines.append("R")                       # the empty clause
    probe = VV.Cert(("\n".join(lines) + "\nHASH 0\n").encode())
    lines.append("HASH %016x" % probe.recompute_hash())
    return "\n".join(lines) + "\n"


def main():
    bad = 0

    # A satisfiable CNF: one unit clause, so unit propagation must assign the
    # variable and must NOT call it a conflict.
    asg = [-1] * 4
    if VV.propagate([[1]], asg, 1):
        print("FAIL: a SAT unit CNF was reported as a conflict")
        bad += 1
    elif asg[0] != 0:
        print("FAIL: unit literal 1 did not set var0 false (%r)" % asg)
        bad += 1
    else:
        print("PASS: SAT unit CNF propagates without a conflict")

    # A single empty clause is NOT a refutation of a SAT miter.
    sat = VV.Cert(one_step_cert(2, 2, [1, 2], 2).encode())
    errs = VV.check(sat)
    if not any("not RUP" in e for e in errs):
        print("FAIL: forged empty-clause refutation of a SAT miter accepted: %r" % errs)
        bad += 1
    else:
        print("PASS: forged empty-clause refutation of a SAT miter rejected")

    # The same step IS a short refutation of an UNSAT miter (goal is false,
    # alongside the constant unit), so the checker must still accept it.
    unsat = VV.Cert(one_step_cert(0, 2, [1, 2], 2).encode())
    errs = VV.check(unsat)
    if errs:
        print("FAIL: genuine one-step refutation of an UNSAT miter rejected: %r" % errs)
        bad += 1
    else:
        print("PASS: genuine one-step refutation of an UNSAT miter accepted")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
