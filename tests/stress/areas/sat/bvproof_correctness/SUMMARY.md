# Counts

- 4 CLI goldens, 4 JSON goldens, 1 independent verifier, 2 docs.

# Issues by severity

- No CRASH, HANG, WRONG or DETERMINISM finding in this area.
- LIMIT: top-level `proof.kind` wording is fixed by files outside this
  area's ownership; the checkable object is exposed through `checks[]`,
  `notes[]`, `sat.why` and `files[]`.

# Takeaway

A bit-vector refutation is more than a node/conflict count: recording the
miter AIG plus the solver's DRUP steps (or its model) makes the result
independently checkable, provided the checker's conflict test is the actual
falsification test. Word-level polynomial normal forms prove a useful class
of multiplier identities without building that circuit at all, and a sampled
small-domain guard (4096 tuples, 8 values per parameter) cross-checks the
shortcut without claiming exhaustiveness.
