#!/usr/bin/env python3
"""Generate 160 small, fast, representative ucas command fixtures in corpus/."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "corpus")
os.makedirs(OUT, exist_ok=True)
for _f in os.listdir(OUT):
    if _f.startswith("c") and _f.endswith(".ucas"):
        os.unlink(os.path.join(OUT, _f))

# Each entry is one command line (plus optional preceding definitions).
CMDS = [
    # analysis / representation
    "show 1+2", "show sin(x)", "show u8(x+1)", "parse x*x+2*x+1",
    "table x*x x: u4", "table (x+3)>>1 x: u5 max 40", "range x*x x: u8",
    "range sin(x) x in -3..3", "domain 1/(x-2)", "wrap x+200 x: u8",
    "crit x*x x: u8", "diff x^3", "diff sin(x)*x", "diff (x^2+1)^5 x",
    "equiv (x*y)^5 (y*x)^5", "equiv x+1 1+x", "error x*x x*x+1",
    "fit a*x+b ~ 2*x+1", "fit a*x^2+b*x+c ~ x*x+1 metric maxrel",
    "gates x xor (y and z)", "gates (x and y) or z basis nand",
    "find x*x+3*x x: u4", "cost x*x+3*x", "cost x*x+3*x model zen2",
    "phash x*x x: u8", "pit x*x x*x+1", "stoke x*3+1 steps 20 restarts 2",
    # calculus
    "integrate x^2 from 0 to 1", "integrate sin(x) from 0 to 3.141592653589793",
    "antiderivative x^3", "taylor sin(x) order 6", "taylor exp(x) at 0 order 5",
    "limit sin(x)/x x -> 0", "grad x^2*y+y^3", "hessian x^2+x*y+y^2",
    "laplacian x^2+y^2+z^2", "jacobian x^2, y^2", "F'(3) where F(x)=x^2",
    "diff x^5 n 3", "closed x[k+1]=x[k]+1", "continuous x*x",
    "dsolve y' = y from 0 to 2 steps 100",
    # algebra
    "expand (x+1)^5", "factor x^2-1", "simplify (x^2-1)/(x-1)",
    "together 1/x+1/y", "cancel (x^2-1)/(x-1)", "collect x^2+2*x*y+y^2 in x",
    "apart 1/((x-1)*(x+2))", "gcd x^2-1 x^2-2*x+1",
    "lcm x^2-1 x+1", "quo x^3+1 x+1", "rem x^3+1 x+1",
    "solve x^2 = 4 for x", "solve x+y=3, x-y=1 for x, y",
    "resultant x^2-1 x-2", "discriminant x^2+2*x+1", "substitute x = 2 in x^2+1",
    # properties
    "monotonic x^3", "parity x^3+x", "period sin(x)", "zeros x^2-1",
    "bounded sin(x)", "injective x^3 x: u8", "continuity 1/x",
    "identify 1 - 1/2 + 1/6 - 1/24", "asymptotes 1/(x-1)",
    # complex / quaternion
    "complex (1+2i)*(3-i)", "re (1+2i)^2", "im (1+2i)^2",
    "conj 1+2i", "modulus 3+4i", "arg 1+i", "nthroots 3 1",
    "unity 4", "trig sin(x)^2+cos(x)^2 expand", "quaternion i*j",
    "rotate 1,0,0 by 90 about 0,0,1", "commutator i j",
    # rings / number theory
    "ring Z/12 units", "ring Z/7 field", "inverse 3 mod 11",
    "order 2 mod 7", "phi 12", "carmichael 561", "factorint 360",
    "legendre 2 7", "jacobi 3 11", "sqrtmod 2 7", "primroot 7",
    "crt 2 3 3 5", "gf2matrix x^2+x+1", "magic 3", "algebra quaternion property",
    # loops / series
    "sum(i, 1, 10, i*i)", "prod(i, 1, 5, i)", "identify sum(i,1,n,i)",
    # approximation (small)
    "approx exp(x) in -1..1 degree 4 as f32",
    "compare_a x*x", "texalu x*x", "dword sin(x)", "banks x*x, x+1",
    # English front end
    "what is the range of x squared for a signed byte x?",
    "factor x squared minus 1", "integrate x cubed from 0 to 2",
    "is x cubed monotonic?", "expand x plus 1 to the 5th",
    "simplify (x squared minus 1)/(x minus 1)",
    "find the zeros of x squared minus 4", "differentiate x to the 4th",
    "prove x plus y equals y plus x", "compute 2 to the 10th power",
    "range of sine for real x", "table of x times 2 for unsigned nibble x",
    "gcd of 12 and 18", "inverse of 3 modulo 11",
    # file-writing commands (no 'to NAME' so they don't leave artifacts)
    "plot sin(x), cos(x)", "plot3d x*y", "neighbourhood x*x at 2",
    "animate scan n 8", "show sin(x) at 1,2,3",
    # more analysis variety to reach 160
    "show (x+y)^4", "parse 1/(x^2+1)", "table sin(x) x: u4",
    "range x^3 x: i8", "wrap x*7 x: u6", "crit (x+1)*(x+2) x: u8",
    "diff exp(x)*sin(x)", "equiv x x", "error x+1 x+1",
    "fit a*x+b ~ 3*x-2 metric rms", "gates x and y basis c",
    "find x+1 x: u4", "cost (x+1)^2 basis c", "range (x*x)>>2 x: u8",
    "show 0x1234", "show 3.14159", "parse -x+1", "show [1,2,3,4]",
    "match x { 0 => 1, 1 => 2, _ => 0 }", "show {x if x>0, 0}",
    "sum(i,1,100,i)", "limit (x^2-1)/(x-1) x -> 1",
    "taylor cos(x) order 8", "integrate 1/x from 1 to 2",
    "solve 2*x+3=7 for x", "simplify sin(x)^2+cos(x)^2",
    "ring Z/5 table", "order 3 mod 11", "phi 100", "factorint 9973",
    "identify 0.1+0.2", "show 2^100", "range x x: u4",
]

# De-duplicate while preserving order, cap at 160.
seen = set()
cmds = []
for c in CMDS:
    if c not in seen:
        seen.add(c)
        cmds.append(c)
cmds = cmds[:160]

# Two definitions prepended to commands that need them.
for i, c in enumerate(cmds, 1):
    path = os.path.join(OUT, "c%03d.ucas" % i)
    with open(path, "w") as f:
        f.write(c + "\n")

# Manifest
with open(os.path.join(OUT, "manifest.txt"), "w") as f:
    for i, c in enumerate(cmds, 1):
        f.write("c%03d\t%s\n" % (i, c))
print("wrote", len(cmds), "fixtures to", OUT)
