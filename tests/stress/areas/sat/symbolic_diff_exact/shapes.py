"""Shape reduction: verified variable-renaming reuse of one oracle proof.

Two pairs are the *same claim* if a bijection of variable names maps one to the
other.  We detect this structurally (canonical form = AST with variable names
replaced by first-appearance indices v0, v1, ...) and verify that ucas gives the
same equivalence verdict to every member of a class.  Each class needs only one
engine query; the rest are discharged by the verified renaming.
"""

from collections import defaultdict


def canonical_pair(f, g):
    order = []

    def walk(e):
        if e.op == "var":
            if e.val not in order:
                order.append(e.val)
        elif e.op != "num":
            walk(e.a)
            if e.b is not None:
                walk(e.b)

    walk(f)
    walk(g)
    mp = {nm: "v%d" % i for i, nm in enumerate(order)}
    return (f.rename(mp).render(), g.rename(mp).render())


def shape_classes(pairs):
    """Group pairs by canonical (rename-invariant) form."""
    groups = defaultdict(list)
    for p in pairs:
        groups[canonical_pair(p["f"], p["g"])].append(p)
    return groups


def verify(pairs, results):
    groups = shape_classes(pairs)
    report = []
    reusable = 0
    inconsistent = []
    for canon, members in sorted(groups.items()):
        # structural check: every member really has this canonical form
        structural_ok = all(canonical_pair(m["f"], m["g"]) == canon for m in members)
        verdicts = {
            m["id"]: {
                "oracle": results[m["id"]]["oracle"]["is_identity"],
                "equiv_real": results[m["id"]]["queries"].get("equiv_real", {}).get("equal"),
                "equiv_int": results[m["id"]]["queries"].get("equiv_int", {}).get("equal"),
            }
            for m in members
        }
        real_set = set(str(v["equiv_real"]) for v in verdicts.values())
        int_set = set(str(v["equiv_int"]) for v in verdicts.values())
        consistent = len(real_set) == 1 and len(int_set) == 1
        if len(members) > 1:
            reusable += len(members) - 1
        if not consistent:
            inconsistent.append(canon)
        report.append({
            "canonical": list(canon),
            "members": [m["id"] for m in members],
            "structural_ok": structural_ok,
            "equiv_real_verdicts": sorted(real_set),
            "equiv_int_verdicts": sorted(int_set),
            "consistent": consistent,
            "oracle": verdicts[members[0]["id"]]["oracle"],
        })
    return report, reusable, inconsistent
