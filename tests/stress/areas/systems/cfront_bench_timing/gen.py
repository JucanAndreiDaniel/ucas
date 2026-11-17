#!/usr/bin/env python3
"""Generate a broad matrix of c optimize bench/timing cases (exploration only)."""
import os, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "cases")
os.makedirs(CASES, exist_ok=True)

# name -> C source (one or more functions)
FN = {
 "add":      "int add(int a,int b){return a+b;}",
 "div7":     "unsigned div7(unsigned x){return x/7;}",
 "lo4":      "unsigned char lo4(unsigned x){return (unsigned char)(x&15);}",
 "clamp":    "unsigned char sat(unsigned char a){unsigned s=a+200u;return s>255?255:s;}",
 "avg":      "int avg(int a,int b){return (a+b)/2;}",
 "pop":      "int pop(unsigned x){int c=0;while(x){c+=x&1;x>>=1;}return c;}",
 "sum":      "int sum(int n){int s=0;for(int i=0;i<n;i++)s+=i;return s;}",
 "sum2":     "int sum2(int n){int s=0;for(int i=0;i<n;i++)s+=i*i;return s;}",
 "bright":   "void bright(unsigned char*d,const unsigned char*s,int n){for(int i=0;i<n;i++)d[i]=s[i]+1;}",
 "intmul":   "int imul(int a,int b){return a*b+b;}",
 "fadd":     "float fadd(float a,float b){return a+b;}",
 "ffma":     "float ffma(float a,float b,float c){return a*b+c;}",
 "fdiv":     "double fdiv(double a,double b){return a/b;}",
 "fscale":   "float fscale(float x){return x*3.14159265f;}",
 "bitrev":   "unsigned bitrev(unsigned x){unsigned r=0;for(int i=0;i<32;i++){r=(r<<1)|(x&1);x>>=1;}return r;}",
 "cntnz":    "int cntnz(unsigned x){int c=0;while(x){x&=x-1;c++;}return c;}",
 "mix":      "unsigned mix(unsigned a,unsigned b){return (a^b)+((a&b)<<1);}",
 "large":    ("int large(int a,int b,int c){int x=a+b; x^=c; x=(x<<3)|(x>>29); "
             "y=x*c; return (int)(x+y+((a*b)^c));} int y;"),
}

# budgets, targets, modes
BUDGETS = [0, 1, 3, 100]
TARGETS = ["zen4", "skl", "gt1030", "bogus"]
MODES = ["bench", "check bench", "bench check", "plain", "check", "timed bench", "timed"]

manifest = []
i = 0
for fname, src in FN.items():
    for b in BUDGETS:
        for mode in MODES:
            i += 1
            name = f"{i:03d}_{fname}_b{b}_{mode.replace(' ','_')}"
            opts = f"budget {b}"
            if "check" in mode:
                opts += " check"
            if "bench" in mode:
                opts += " bench"
            if "timed" in mode:
                opts += " timed"
            txt = f"c optimize nofile {opts}\n```c\n{src}\n```\n"
            with open(os.path.join(CASES, name + ".ucas"), "w") as f:
                f.write(txt)
            manifest.append((name, fname, b, mode, ""))

# target matrix on a vectorizable loop and a tiny fn
for t in TARGETS:
    for fname in ["add", "sum", "bright", "pop", "ffma"]:
        for bench in ["bench", "plain"]:
            i += 1
            name = f"{i:03d}_tgt_{fname}_{t}_{bench}"
            opts = f"target {t} budget 1"
            if bench == "bench":
                opts += " bench"
            txt = f"c optimize nofile {opts}\n```c\n{FN[fname]}\n```\n"
            with open(os.path.join(CASES, name + ".ucas"), "w") as f:
                f.write(txt)
            manifest.append((name, fname, 1, bench, t))

with open(os.path.join(HERE, "cases_manifest.txt"), "w") as f:
    for row in manifest:
        f.write(" ".join(map(str, row)) + "\n")
print("generated", len(manifest), "cases")
