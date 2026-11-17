#!/usr/bin/env python3
"""Independently verify ucas `magic D <type>` constants against Python integer
arithmetic.  Exhaustive for u8/u16/i8/i16, dense/sampled for 32/64-bit."""
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
import subprocess, re, sys, random

BIN = str(_REPO_ROOT / "ucas")

def run_magic(d, t, timeout=10):
    try:
        p = subprocess.run([BIN], input=f"magic {d} {t}\n", text=True,
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ("TIMEOUT", "")
    return (p.returncode, p.stdout + p.stderr)

def cdiv(a,b):
    q=abs(a)//abs(b)
    return -q if (a<0)!=(b<0) else q

def parse(out):
    # unsigned: m = ceil(2^K / d) = M ... shift s = S
    m = re.search(r'm = ceil\(2\^(\d+)\s*/\s*\d+\)\s*=\s*(\d+)\s*\(0x[0-9a-fA-F]+,\s*(\d+) bits\),\s*shift s = (\d+)', out)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(4)))
    # signed uses same m = ceil(2^K / d) line
    return None

def pts_for(t, d, n):
    if t[0]=='u':
        lo=0
        if n<=16: return range(0, 1<<n)
        hi=(1<<n)-1
    else:
        if n<=16: return range(-(1<<(n-1)), 1<<(n-1))
        hi=(1<<(n-1))-1; lo=-(1<<(n-1))
    pts = set([0,1,2,hi,hi-1,lo,lo+1,-1 if t[0]=='i' else 0])
    for k in range(max(1,hi//d-3), min(hi,d>0 and hi//d+4)):
        for v in (k*d-1,k*d,k*d+1):
            if 0<=v<=hi: pts.add(v)
    rnd = random.Random(12345)
    for _ in range(20000):
        pts.add(rnd.randint(0 if t[0]=='u' else lo, hi))
    return pts

def verify(d, t):
    rc, out = run_magic(d, t)
    if rc != 0:
        return ("RC", rc, out[:200])
    if "q = x >>" in out or "q = (x +" in out or "x itself" in out:
        return ("SPECIAL", out.splitlines()[1].strip() if len(out.splitlines())>1 else "")
    pm = parse(out)
    if not pm:
        return ("NOPARSE", out[:300])
    K, M, s = pm
    n = int(t[1:])
    unsigned = t[0]=='u'
    # expected K from type/shift: unsigned n+s ; signed n-1+s
    expK = n+s if unsigned else n-1+s
    expM = -(-(1<<expK)//d)  # ceil
    bade = []
    if K != expK or M != expM:
        bade.append(("K/M",K,expK,M,expM))
    for x in pts_for(t, d, n):
        q = (x*M) >> K
        if not unsigned:
            q += 1 if x<0 else 0
        exp = x//d if unsigned else cdiv(x,d)
        if q != exp:
            bade.append((x,q,exp))
            if len(bade)>5: break
    return ("OK" if not bade else "BAD", bade, out.splitlines()[1].strip())

def main():
    types = ['u8','u16','u32','u64','i8','i16','i32','i64']
    ds = list(range(2,80)) + [100,127,128,129,255,256,257,1000,65535,65536,
                              65537,(1<<31)-1,1<<31,(1<<31)+1,(1<<32)-1,1<<32,
                              (1<<63)-1]
    total=0; bad=[]; specials=0; rcerrs=[]
    for t in types:
        for d in ds:
            # skip divisors larger than type max for small types
            n=int(t[1:]); mx = (1<<n)-1 if t[0]=='u' else (1<<(n-1))-1
            if d>mx: continue
            total+=1
            r = verify(d,t)
            if r[0]=="BAD": bad.append((t,d,r))
            elif r[0]=="SPECIAL": specials+=1
            elif r[0] in ("RC","TIMEOUT","NOPARSE"): rcerrs.append((t,d,r))
    print(f"total={total} specials={specials} bad={len(bad)} rcerrs={len(rcerrs)}")
    for b in bad[:20]: print("BAD",b)
    for b in rcerrs[:20]: print("RCERR",b)

if __name__=="__main__":
    main()
