#!/usr/bin/env python3
"""Triage clang/gcc static analyzer warnings into categories.
Writes artifacts only into this folder. Read-only w.r.t. source.
"""
import re, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "analysis")

def load(path):
    out = []
    with open(path, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r'^(src/[^:]+):(\d+):(\d+): warning: (.*)$', line)
            if m:
                out.append((m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)))
    return out

clang = load(os.path.join(A, "clang_warnings.txt"))
gcc = load(os.path.join(A, "gcc_warnings.txt"))

# Classification heuristics. fail()/xmalloc() never return, so anything
# downstream of "if (!p) fail()" or a null-check-then-fail is a false positive.
FP_PAT = re.compile(
    r"Dereference of null pointer|dereference of NULL|dereference of possibly-NULL|"
    r"Null pointer passed|use of NULL|"
    r"double.?fclose|Use of a stream that might be already closed|"
    r"Already released|already released|Attempt to release already released|"
    r"Read function called when stream is in EOF|File position of the stream|"
    r"Addition of a null pointer", re.I)

STYLE_PAT = re.compile(
    r"Value stored to|Although the value stored|Potential memory leak|"
    r"can be made static|discards .const. qualifier|switching on non-enum|"
    r"potential uncovered code path|no header providing|use of a signed integer|"
    r"deadcode|Dead store|unused", re.I)

def classify(msg):
    if FP_PAT.search(msg):
        return "b_false_positive"
    if STYLE_PAT.search(msg):
        return "c_stylistic"
    return "a_plausible_real"

rows = []
for origin, lst in (("clang", clang), ("gcc", gcc)):
    for f, l, c, msg in lst:
        rows.append((classify(msg), origin, f, l, c, msg))

cnt = collections.Counter(r[0] for r in rows)
print("TOTAL:", len(rows))
for k in sorted(cnt):
    print(f"  {k}: {cnt[k]}")

with open(os.path.join(A, "triage_all.tsv"), "w") as f:
    for r in rows:
        f.write("\t".join(map(str, r)) + "\n")

print("\n=== a_plausible_real (deduped by file:line) ===")
seen = set()
n = 0
for cat, origin, fn, l, c, msg in rows:
    if cat != "a_plausible_real":
        continue
    key = (fn, l)
    if key in seen:
        continue
    seen.add(key)
    n += 1
    print(f"{n:3d} {fn}:{l} [{origin}] {msg}")
print("distinct a_plausible_real sites:", n)
