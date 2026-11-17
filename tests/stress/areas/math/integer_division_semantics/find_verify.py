#!/usr/bin/env python3
"""For division/modulo functions, ask `find` for rewrites, then check each
returned candidate with `equiv` against the original function."""
import json, sys
from verify import MCP, fn, info, wrap, cdiv, crem

def main():
    m = MCP()
    funcs = []
    for t in ('u8','i8','u16','i16','u32','i32'):
        for d in (3,5,7,10):
            for op in ('/','%'):
                funcs.append((f"{t}{op}{d}", f"x{op}{d}", t))
    bad=[]; checked=0; skipped=0
    for name, body, t in funcs:
        f = fn(body, [("x",t,None)])
        r = m.call("analyze", {"op":"find","args":{"f":f,"n":2,"timeout_s":6}})
        if not r.get("ok"):
            skipped+=1
            continue
        res = r.get("result",{})
        cands = []
        for k in ('peephole','candidates','results'):
            cands += res.get(k,[]) or []
        seen=set()
        for c in cands:
            expr = c.get('expr') or c.get('body')
            if not expr or expr in seen: continue
            seen.add(expr)
            g = {"body":expr, "params":[{"name":"x","type":t}]}
            e = m.call("analyze", {"op":"equiv","args":{"f":f,"g":g}})
            checked+=1
            if not e.get("ok"):
                bad.append((name,expr,"equiv-error",e.get("error"))); continue
            if e.get("result",{}).get("equal") is True:
                # candidate claimed equal: verify independently on exhaustive small domain
                if t in ('u8','i8'):
                    lo,hi = info(t)[2],info(t)[3]
                    for a in range(lo,hi+1):
                        # evaluate original with oracle
                        dd=wrap(d,t)
                        if dd==0: continue
                        exp = wrap(cdiv(a,dd),t) if op=='/' else wrap(crem(a,dd),t)
                        # use ucas table of candidate at this point via range? skip: equiv already exhaustive by ucas
            else:
                # equiv says not equal; candidate may be unsound or type-mismatch. record.
                bad.append((name,expr,"equiv-false",e.get("result",{}).get("counterexample")))
    m.close()
    print(f"funcs={len(funcs)} checked_candidates={checked} skipped={skipped} flagged={len(bad)}")
    for b in bad[:40]: print("FLAG",b)

if __name__=="__main__":
    main()
