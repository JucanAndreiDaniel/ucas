#!/usr/bin/env python3
"""Independent checker for ucas's machine-checkable bit-vector proof object.

Usage:  python3 verify_bvproof.py RESPONSE.jsonl [...]

Each argument is a JSON frontend response (one JSON object per line).  A
response that carries a `bvproof.cert` file with base64 content is decoded;
its AIG miter, Tseitin clauses and DRUP/model evidence are rechecked here
without using any part of ucas's SAT solver.  The hash of the canonical byte
stream is recomputed too, so a checker can tell that the printed object is
the one ucas hashed.

Exits 0 when every certificate verifies, 1 otherwise.
"""
import base64
import json
import struct
import sys


class Cert:
    def __init__(self, raw):
        self.raw = raw
        self.lines = raw.decode("ascii").splitlines()
        self.goal = self.nodes = self.nin = None
        self.ncl = self.steps = self.result = None
        self.f0 = self.f1 = self.inputs = None
        self.clauses = []
        self.model_inputs = None
        self.hash = None
        self.truncated = False
        self._parse()

    def _parse(self):
        i = 0
        if self.lines[i] != "BVPROOF 1":
            raise ValueError("bad magic")
        i += 1
        self.ncl = self.steps = self.result = None
        nodes_seen = False
        for line in self.lines[i:]:
            p = line.split()
            if not p:
                continue
            k = p[0]
            if k == "GOAL":
                self.goal = int(p[1])
            elif k == "NODES":
                self.nodes = int(p[1])
            elif k == "INPUTS":
                self.nin = int(p[1])
                self.f0 = [0] * self.nodes
                self.f1 = [0] * self.nodes
                self.inputs = []
            elif k == "I":
                self.inputs.append(int(p[1]))
            elif k == "N":
                self.f0[int(p[1])] = int(p[2])
                self.f1[int(p[1])] = int(p[3])
                nodes_seen = True
            elif k == "CLAUSES":
                self.ncl = int(p[1])
                self.steps = int(p[p.index("STEPS") + 1])
                self.result = int(p[p.index("RESULT") + 1])
            elif k in ("C", "R"):
                self.clauses.append([int(x) for x in p[1:]])
            elif k == "MODEL":
                self.model_inputs = [int(x) for x in p[1:]]
            elif k == "HASH":
                self.hash = int(p[1], 16)
                self.truncated = len(p) > 2
        if None in (self.goal, self.nodes, self.nin, self.ncl, self.steps,
                    self.result, self.hash) or not nodes_seen:
            raise ValueError("incomplete certificate")

    def problem_clauses(self):
        """Rebuild the Tseitin CNF from the AIG, in ucas's emission order.

        ucas walks the cone from the goal with an explicit stack, pushing the
        first fan-in then the second, and emits three clauses per gate.  The
        only axioms outside the gates are the constant and the goal unit.
        """
        cl = [[1]]
        seen = {self.goal >> 1}
        stack = [self.goal >> 1]
        while stack:
            v = stack.pop()
            if v == 0:
                continue
            a, b = self.f0[v], self.f1[v]
            if a == 0 and b == 0:
                continue
            o = 2 * v
            cl.append([o ^ 1, a])
            cl.append([o ^ 1, b])
            cl.append([o, a ^ 1, b ^ 1])
            for lit in (a, b):
                u = lit >> 1
                if u not in seen:
                    seen.add(u)
                    stack.append(u)
        cl.append([self.goal])
        return cl

    def recompute_hash(self, model=None):
        h = 0
        def fb(data):
            nonlocal h
            for byte in data:
                h ^= byte
                h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
        fb(struct.pack("<i", self.nodes))
        fb(struct.pack("<I", self.goal))
        for a in self.f0:                   # all f0, then all f1 (as ucas hashes)
            fb(struct.pack("<I", a))
        for b in self.f1:
            fb(struct.pack("<I", b))
        for cl in self.problem_clauses() + self.clauses:
            fb(struct.pack("<i", len(cl)))
            for lit in cl:
                fb(struct.pack("<I", lit))
        if self.result == 1 and model is not None:
            fb(bytes(model))
        return h


def lval(asg, lit):
    v = asg[lit >> 1]
    return -1 if v < 0 else v ^ (lit & 1)


def propagate(db, asg, limit):
    while True:
        changed = False
        for cl in db[:limit]:
            sat = False
            un = 0
            last = None
            for lit in cl:
                v = lval(asg, lit)
                if v == 1:
                    sat = True
                    break
                if v < 0:
                    un += 1
                    last = lit
            if sat:
                continue
            # a clause conflicts when all its literals are falsified
            # (zero unassigned), not when they are all unassigned.  An
            # empty clause has zero literals and also conflicts.
            if un == 0:
                return True             # conflict
            if un == 1:
                asg[last >> 1] = 0 if (last & 1) else 1
                changed = True
        if not changed:
            return False


def check(c):
    errs = []
    for i in range(1, c.nodes):
        if (c.f0[i] >> 1) >= i or (c.f1[i] >> 1) >= i:
            errs.append("node %d has a forward fan-in" % i)
    rebuild = c.problem_clauses()
    nproblem = c.ncl - c.steps
    if len(rebuild) != nproblem or len(c.clauses) != c.steps:
        errs.append("clause counts disagree with the AIG's Tseitin CNF")
    # The full stream ucas hashed: definitional clauses (rebuilt from the
    # AIG) followed by the learned DRUP steps carried in the certificate.
    full = rebuild + c.clauses

    model = None
    if c.result == 1:
        if len(c.model_inputs) != c.nin:
            errs.append("model has %d inputs, expected %d" %
                        (len(c.model_inputs), c.nin))
        else:
            model = [0] * c.nodes
            for idx, var in enumerate(c.inputs):
                model[var] = c.model_inputs[idx]
            for i in range(1, c.nodes):
                a, b = c.f0[i], c.f1[i]
                if a == 0 and b == 0:
                    continue
                av = ((model[a >> 1] if (a >> 1) else 0) ^ (a & 1))
                bv = ((model[b >> 1] if (b >> 1) else 0) ^ (b & 1))
                model[i] = av & bv
            if lval(model, c.goal) != 1:
                errs.append("the model does not satisfy the goal")
            for cl in rebuild:
                if not any(lval(model, lit) == 1 for lit in cl):
                    errs.append("the model falsifies a problem clause")
                    break
    else:
        asg = [-1] * c.nodes
        db = list(rebuild)                  # definitional clauses, rebuilt
        for i, cl in enumerate(c.clauses):
            saved = [(v, asg[v]) for v in range(c.nodes) if asg[v] >= 0]
            contradict = False
            for lit in cl:
                if lval(asg, lit ^ 1) == 0:
                    contradict = True
                    break
                if lval(asg, lit ^ 1) < 0:
                    asg[(lit ^ 1) >> 1] = 0 if ((lit ^ 1) & 1) else 1
            if not contradict and not propagate(db, asg, len(db)):
                errs.append("DRUP step %d is not RUP" % i)
            asg = [-1] * c.nodes
            for v, val in saved:
                asg[v] = val
            db.append(cl)
            if not cl and i != c.steps - 1:
                errs.append("the empty clause is not last")
        if len(c.clauses) != c.steps or not c.clauses or c.clauses[-1]:
            errs.append("no final empty clause in the refutation")
        if not propagate(db, [-1] * c.nodes, len(db)):
            errs.append("the final clause set is satisfiable")
    if c.truncated:
        errs.append("certificate was truncated")
    elif c.recompute_hash(model) != c.hash:
        errs.append("hash mismatch: %016x vs %016x" %
                    (c.recompute_hash(model), c.hash))
    return errs


def main():
    bad = 0
    for path in sys.argv[1:]:
        with open(path) as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                resp = json.loads(line)
                for f in resp.get("files", []):
                    if f.get("name") != "bvproof.cert":
                        continue
                    b64 = f.get("base64")
                    if not b64:
                        print("SKIP %s: no inline certificate" % path)
                        continue
                    try:
                        c = Cert(base64.b64decode(b64))
                        errs = check(c)
                    except Exception as ex:
                        errs = ["parse/check error: %s" % ex]
                    tag = "%s#%s" % (path, resp.get("id"))
                    if errs:
                        bad += 1
                        print("FAIL %s: %s" % (tag, "; ".join(errs)))
                    else:
                        print("PASS %s: %s, %d nodes, %d DRUP steps" %
                              (tag, "model" if c.result == 1 else "refutation",
                               c.nodes, c.steps))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
