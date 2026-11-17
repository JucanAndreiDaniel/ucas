#!/usr/bin/env python3
"""
Mutation testing over 30 existing tests/*.ucas.

Each mutation is a single semantic token change (operator / bound / type / constant)
applied to a COPY in ../mutations/.  The mutant is run with the shipped binary and compared
to the stored original .out.  Two comparisons are reported:
  raw      - byte-for-byte (the '> ' command echo already changes)
  semantic - after stripping '> ' echo lines and floating-point check-noise lines
A test DETECTS the mutation when the semantic output changes.
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
import os, re, subprocess, csv, json, hashlib
R=str(_REPO_ROOT / "tests")
D=os.path.dirname(os.path.abspath(__file__))
M=os.path.join(D,"..","mutations")
BIN=str(_REPO_ROOT / "ucas")
os.makedirs(M,exist_ok=True)

# name, file, old, new, kind, description
MUTS=[
 ("m01","calc","1, 10, i^2","1, 11, i^2","bound","sum upper bound 10->11"),
 ("m02","find","0 => 3, 1 => 5, 2 => 7, 3 => 9","0 => 3, 1 => 5, 2 => 7, 3 => 10","const","match value 9->10"),
 ("m03","gates","isqrt4(x: u4) = isqrt(x)","isqrt4(x: u5) = isqrt(x)","type","param type u4->u5"),
 ("m04","prove","1 <= r and a in H","2 <= r and a in H","bound","quantifier bound 1<=r -> 2<=r"),
 ("m05","rules","rules infer inputs 1 width 32 cost 2","rules infer inputs 1 width 32 cost 3","bound","rule cost 2->3"),
 ("m06","scheme","3x^5 - 2x^4","3x^5 - 3x^4","const","coefficient 2->3"),
 ("m07","satdefined","(x >> n) * 3 - x","(x >> n) * 4 - x","const","multiplier 3->4"),
 ("m08","paramsets","= x / 5","= x / 6","const","divisor 5->6"),
 ("m09","nlp_requests","x squared for x from -3 to 3","x squared for x from -3 to 4","bound","English upper bound 3->4"),
 ("m10","snippets","& ~((a + b) & (a - b))","& ~((a + b) | (a - b))","operator","inner & -> |"),
 ("m11","f16","bits(b: u16) = asuint(asfloat(b))","bits(b: u32) = asuint(asfloat(b))","type","param type u16->u32"),
 ("m12","float","x + 1e-8 - x","x + 1e-4 - x","const","epsilon 1e-8->1e-4"),
 ("m13","intfloat","cv(i: u32 in 0..1000)","cv(i: u32 in 0..1001)","bound","range 0..1000 -> 0..1001"),
 ("m14","fp64cmp","< f64(z) * f64(w)","<= f64(z) * f64(w)","operator","comparison < -> <="),
 ("m15","counter","x*(x - 1)/2","x*(x - 2)/2","const","subtrahend 1->2"),
 ("m16","ops2","fma(2, 3, 1)","fma(2, 3, 2)","const","fma addend 1->2"),
 ("m17","u64range","odd32(r: u32 in 1..65535)","odd32(r: u32 in 1..65534)","bound","range end 65535->65534"),
 ("m18","equivalg","y*t*w + x*t","y*t*w - x*t","operator","+ -> -"),
 ("m19","whereor","a(x: u32) = x + 1 where x == 3 || x == 17","a(x: u32) = x + 2 where x == 3 || x == 17","operator","+1 -> +2"),
 ("m20","cost","rsqrt(x: f32) = 1/sqrt(x)","rsqrt(x: f64) = 1/sqrt(x)","type","param type f32->f64"),
 ("m21","parse","2x^2 + 3x - 1","2x^2 + 3x - 2","const","constant 1->2"),
 ("m22","stoke","(x | y) - (x & y)","(x | y) + (x & y)","operator","- -> +"),
 ("m23","nlp_numbers","two hundred fifty-six divided by 4","two hundred fifty-seven divided by 4","const","English 256->257"),
 ("m24","nlp","x times 2 plus 1","x times 3 plus 1","const","English multiplier 2->3"),
 ("m25","algebra","solve x^2 + 1 = 0","solve x^2 + 2 = 0","const","equation 1->2"),
 ("m26","xform","laplace t^2 e^-t","laplace t^3 e^-t","const","power t^2->t^3"),
 ("m27","calculus2","taylor sin(x) order 7","taylor sin(x) order 6","bound","taylor order 7->6"),
 ("m28","rings","primroot 11","primroot 13","const","modulus 11->13"),
 ("m29","absalg","abselftest 500","abselftest 501","const","count 500->501"),
 ("m30","fpsat","l2a(x: f32, y: f32) = x * y","l2a(x: f32, y: f32) = x + y","operator","* -> +"),
]

NOISE=re.compile(r"(max relative difference|max difference|residual |check:.*e[+-]\d+|elapsed|in \d+\.\d+ s)")
def sem(text):
    out=[]
    for l in text.splitlines():
        if l.startswith("> "): continue
        if NOISE.search(l): continue
        out.append(l.rstrip())
    return "\n".join(out)

def run(path):
    try:
        p=subprocess.run([BIN,os.path.basename(path)],cwd=M,stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,timeout=20)
        return p.stdout.decode("utf-8","replace"),p.returncode,0
    except subprocess.TimeoutExpired as e:
        return (e.stdout or b"").decode("utf-8","replace"),124,1

rows=[]
for name,base,old,new,kind,desc in MUTS:
    src=open(os.path.join(R,base+".ucas"),encoding="utf-8",errors="replace").read()
    want=open(os.path.join(R,base+".out"),encoding="utf-8",errors="replace").read()
    applied = old in src
    mutant = src.replace(old,new,1) if applied else src
    mp=os.path.join(M,name+".ucas")
    open(mp,"w",encoding="utf-8").write(mutant)
    g1,rc1,t1=run(mp)
    g2,rc2,t2=run(mp)
    det = (g1==g2)
    open(os.path.join(M,name+".out"),"w",encoding="utf-8").write(g1)
    rows.append(dict(mutation=name,base=base,kind=kind,desc=desc,applied=applied,
                     raw_detect=(g1!=want),sem_detect=(sem(g1)!=sem(want)),
                     deterministic=det,rc=rc1,timeout=t1,
                     changed_chars=len(mutant)-len(src)))
with open(os.path.join(D,"mutations.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
print(json.dumps(dict(total=len(rows),applied=sum(r["applied"] for r in rows),
      raw_detected=sum(r["raw_detect"] for r in rows),
      sem_detected=sum(r["sem_detect"] for r in rows),
      nondeterministic=[r["mutation"] for r in rows if not r["deterministic"]],
      not_applied=[r["mutation"] for r in rows if not r["applied"]],
      missed=[r["mutation"] for r in rows if not r["sem_detect"]]),indent=2))
