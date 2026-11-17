#!/usr/bin/env python3
"""Systematic range-soundness harness.

Generates many single-variable functions on u16/u32/i16/i32/f32, computes an
INDEPENDENT Python oracle (full brute force for exhaustive domains; a dense
edge-heavy grid for 32-bit and f32 domains), runs ucas `range`, and compares
headline min/max, sound-bound line, proved-bound line and witness attainment.

This is a scratch analysis tool, not a golden test.
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
import json, math, os, random, re, struct, subprocess, sys

UCAS = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "gen")
os.makedirs(GEN, exist_ok=True)

# ---------------------------------------------------------------- type helpers
def mask(w): return (1 << w) - 1
def half(w): return 1 << (w - 1)
def wrap_x(v, w, signed):
    v &= mask(w)
    if signed and v & half(w): v -= (1 << w)
    return v

class T:
    def __init__(self, name):
        self.name = name
        self.signed = name[0] == 'i'
        self.w = int(name[1:])
    def R(self, v): return wrap_x(v, self.w, self.signed)
    def rng(self):
        if self.signed: return (-half(self.w), half(self.w) - 1)
        return (0, mask(self.w))
    def lit(self, v): return self.R(v)

# ---------------------------------------------------------------- dense grid
DENSE_CACHE = {}
def dense_points(t, extra=()):
    """Curated dense set of display values for a 32-bit type."""
    key = (t.name, tuple(extra))
    if key in DENSE_CACHE: return DENSE_CACHE[key]
    lo, hi = t.rng()
    pts = set()
    # evenly spaced (mimic + exceed ucas 65536 sample)
    n = 65536
    for i in range(n + 1):
        pts.add(lo + (hi - lo) * i // n)
    # edges
    for d in range(0, 3000):
        pts.add(lo + d); pts.add(hi - d)
    # around powers of two boundaries
    for k in range(0, t.w):
        b = (1 << k)
        for v in (b - 1, b, b + 1, -b - 1, -b, -b + 1):
            pts.add(t.R(v))
    # around extra constants
    for c in extra:
        for d in range(-130, 131):
            pts.add(t.R(c + d))
    # random
    r = random.Random(12345 + t.w + (7 if t.signed else 0))
    for _ in range(30000):
        pts.add(r.randint(lo, hi))
    out = sorted(pts)
    DENSE_CACHE[key] = out
    return out

# ---------------------------------------------------------------- specs
SPECS = []
def spec(name, decl, t, oracle, extra=(), kind="int", exhaustive=None, domain=None):
    SPECS.append(dict(name=name, decl=decl, t=t, oracle=oracle,
                      extra=list(extra), kind=kind, exhaustive=exhaustive, domain=domain))

u16, u32, i16, i32 = T('u16'), T('u32'), T('i16'), T('i32')

def add_family(t, tag, consts):
    lo, hi = t.rng()
    # identity
    spec(f"id_{tag}", f"id_{tag}(x: {t.name}) = x", t,
         lambda x, t=t: t.R(x), kind=t.name, exhaustive=(t.w <= 16))
    for i, c in enumerate(consts):
        cw = t.lit(c)
        # x + c
        spec(f"add{tag}_{i}", f"add{tag}_{i}(x: {t.name}) = x + {c}", t,
             lambda x, cw=cw, t=t: t.R(x + cw), extra=(c,), kind=t.name, exhaustive=(t.w <= 16))
        # x - c
        spec(f"sub{tag}_{i}", f"sub{tag}_{i}(x: {t.name}) = x - {c}", t,
             lambda x, cw=cw, t=t: t.R(x - cw), extra=(c,), kind=t.name, exhaustive=(t.w <= 16))
        # c - x
        spec(f"rsub{tag}_{i}", f"rsub{tag}_{i}(x: {t.name}) = {c} - x", t,
             lambda x, cw=cw, t=t: t.R(cw - x), extra=(c,), kind=t.name, exhaustive=(t.w <= 16))
        # x * c
        spec(f"mul{tag}_{i}", f"mul{tag}_{i}(x: {t.name}) = x * {c}", t,
             lambda x, cw=cw, t=t: t.R(x * cw), extra=(c,), kind=t.name, exhaustive=(t.w <= 16))
        # spike x==c ? A : B (int result)
        spec(f"spk{tag}_{i}", f"spk{tag}_{i}(x: {t.name}) = x == {c} ? 1000000007 : 0", t,
             lambda x, c=c, t=t: 1000000007 if x == c else 0,
             extra=(c,), kind="int", exhaustive=(t.w <= 16))
        # step x<c ? A : B (int result)
        spec(f"stp{tag}_{i}", f"stp{tag}_{i}(x: {t.name}) = x < {c} ? 111 : 222", t,
             lambda x, c=c: 111 if x < c else 222,
             extra=(c,), kind="int", exhaustive=(t.w <= 16))

add_family(u16, 'u16', [1, 2, 3, 7, 255, 256, 1000, 32768, 65535, 60000])
add_family(i16, 'i16', [1, 2, 3, 7, 100, 1000, 32767, -1, -2, -1000, -32768])
add_family(u32, 'u32', [1, 2, 3, 7, 255, 65536, 1000000, 2147483647, 4294967295, 4000000000])
add_family(i32, 'i32', [1, 2, 3, 7, 1000, 65536, 2147483647, -1, -2, -1000000, -2147483648])

def bit_family(t, tag):
    lo, hi = t.rng()
    w = t.w
    masks = [0, 1, 15, 255, mask(w), mask(w) >> 1, 0xAAAAAAAA & mask(w), 0x55555555 & mask(w)]
    for i, m in enumerate(masks):
        mw = t.lit(m)
        spec(f"and{tag}_{i}", f"and{tag}_{i}(x: {t.name}) = x & {mw}", t,
             lambda x, mw=mw, t=t: t.R((t.R(x)) & mw), kind=t.name, exhaustive=(w <= 16))
        spec(f"orr{tag}_{i}", f"orr{tag}_{i}(x: {t.name}) = x | {mw}", t,
             lambda x, mw=mw, t=t: t.R((t.R(x)) | mw), kind=t.name, exhaustive=(w <= 16))
    # not
    spec(f"not{tag}", f"not{tag}(x: {t.name}) = ~x", t,
         lambda x, t=t: t.R(~t.R(x)), kind=t.name, exhaustive=(w <= 16))
    # neg
    spec(f"neg{tag}", f"neg{tag}(x: {t.name}) = -x", t,
         lambda x, t=t: t.R(-t.R(x)), kind=t.name, exhaustive=(w <= 16))
    # shifts
    for k in [1, 2, 4, 8, w // 2, w - 1]:
        kk = k & (w - 1) if False else k  # ucas shift >= width? test separately
        spec(f"shl{tag}_{k}", f"shl{tag}_{k}(x: {t.name}) = x << {k}", t,
             lambda x, k=k, t=t: t.R((t.R(x) & mask(t.w)) << k), kind=t.name, exhaustive=(w <= 16))
        spec(f"shr{tag}_{k}", f"shr{tag}_{k}(x: {t.name}) = x >> {k}", t,
             lambda x, k=k, t=t: t.R(t.R(x) >> k), kind=t.name, exhaustive=(w <= 16))
    # rotate (a + b = w)
    for a in [1, 4, 8]:
        b = w - a
        spec(f"rot{tag}_{a}",
             f"rot{tag}_{a}(x: {t.name}) = (x << {a}) | (x >> {b})", t,
             lambda x, a=a, b=b, t=t: t.R(t.R((t.R(x) & mask(t.w)) << a) | t.R(t.R(x) >> b)),
             kind=t.name, exhaustive=(w <= 16))

bit_family(u16, 'u16'); bit_family(u32, 'u32')
bit_family(i16, 'i16'); bit_family(i32, 'i32')

def quad_family(t, tag, pairs):
    for i, (a, b) in enumerate(pairs):
        aw, bw = t.lit(a), t.lit(b)
        spec(f"quad{tag}_{i}",
             f"quad{tag}_{i}(x: {t.name}) = (x - {a}) * (x - {b})", t,
             lambda x, aw=aw, bw=bw, t=t: t.R(t.R(t.R(x) - aw) * t.R(t.R(x) - bw)),
             extra=(a, b), kind=t.name, exhaustive=(t.w <= 16))

quad_family(i16, 'i16', [(0, 10), (-5, 5), (100, 200), (-1000, 1000), (32767, -32768)])
quad_family(i32, 'i32', [(0, 10), (-5, 5), (1000, 2000), (-1000000, 1000000), (2147483647, -2147483648)])
quad_family(u16, 'u16', [(0, 10), (100, 200), (1000, 2000), (0, 65535)])

def abs_family(t, tag):
    if not t.signed: return
    spec(f"absx{tag}", f"absx{tag}(x: {t.name}) = x < 0 ? 0 - x : x", t,
         lambda x, t=t: t.R(-t.R(x)) if t.R(x) < 0 else t.R(x),
         kind=t.name, exhaustive=(t.w <= 16))
    spec(f"negabs{tag}", f"negabs{tag}(x: {t.name}) = x < 0 ? x : 0 - x", t,
         lambda x, t=t: t.R(x) if t.R(x) < 0 else t.R(-t.R(x)),
         kind=t.name, exhaustive=(t.w <= 16))

abs_family(i16, 'i16'); abs_family(i32, 'i32')

# match / table with narrowed domain (exhaustive small)
spec("tab_u16", "tab_u16(x: u8 in 0..15) = [10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160][x]",
     T('u8'), lambda x: [10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160][x],
     kind="int", exhaustive=True, domain=range(0,16))
spec("match_u8", "match_u8(x: u8 in 0..15) = match x { 0..3 => 100, 4..7 => 5, 8 => 999, _ => 0 }",
     T('u8'), lambda x: 100 if x<=3 else 5 if x<=7 else 999 if x==8 else 0,
     kind="int", exhaustive=True, domain=range(0,16))
spec("nested_spk", "nested_spk(x: u16) = x==0 ? 1 : (x==32767 ? 2 : (x==65535 ? 4 : 0))",
     u16, lambda x: 1 if x==0 else 2 if x==32767 else 4 if x==65535 else 0,
     kind="int", exhaustive=True)
spec("poly_i16", "poly_i16(x: i16) = (x+3)*(x-5)*(x+100)",
     i16, lambda x: i16.R(i16.R(i16.R(i16.R(x)+3)*i16.R(i16.R(x)-5))*i16.R(i16.R(x)+100)),
     kind="i16", exhaustive=True)
def _div_oracle(x):
    d = u16.R(x + 1)
    return None if d == 0 else 100 // d
spec("div_u16", "div_u16(x: u16) = 100 / (x+1)",
     u16, _div_oracle, kind="int", exhaustive=True)
spec("mod_u16", "mod_u16(x: u16) = x % 7",
     u16, lambda x: x % 7, kind="int", exhaustive=True)

# f32 sampled cases
def f32grid():
    pts = set()
    for i in range(20001):
        pts.add(i / 20000.0)
    for v in [0.0, 0.5, 0.1, 0.25, 0.75, 1.0, 1e-30, 1e30, 3.4028235e38, -0.0]:
        pts.add(v)
    return sorted(pts)

F32 = None
fspecs = [
    ("f_id", "f_id(x: f32 in 0..1) = x", lambda x: x),
    ("f_sq", "f_sq(x: f32 in 0..1) = x*x", lambda x: x*x),
    ("f_spk05", "f_spk05(x: f32 in 0..1) = x==0.5 ? 1e30 : x", lambda x: 1e30 if x==0.5 else x),
    ("f_spkgrid", "f_spkgrid(x: f32 in 0..1) = x==0.125 ? 1e30 : x", lambda x: 1e30 if x==0.125 else x),
    ("f_step", "f_step(x: f32 in 0..1) = x<0.5 ? -5.0 : 7.0", lambda x: -5.0 if x<0.5 else 7.0),
    ("f_abs", "f_abs(x: f32 in -1..1) = x<0 ? -x : x", lambda x: -x if x<0 else x),
    ("f_shift", "f_shift(x: f32 in 0..1) = x*100 - 50", lambda x: x*100-50),
]
for name, decl, oracle in fspecs:
    SPECS.append(dict(name=name, decl=decl, t=None, oracle=oracle, extra=(), kind="f32",
                      exhaustive=False))

# ---------------------------------------------------------------- run ucas
def run_batch(batch, idx):
    ucas = "\n".join(s['decl'] + "\nrange " + s['name'] for s in batch) + "\n"
    fp = os.path.join(GEN, f"case_{idx:03d}.ucas")
    op = fp + ".out"
    with open(fp, "w") as f: f.write(ucas)
    try:
        p = subprocess.run([UCAS, fp], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=15, cwd=GEN)
        out = p.stdout.decode('utf-8', 'replace'); rc = p.returncode
    except subprocess.TimeoutExpired:
        out, rc = "", "TIMEOUT"
    with open(op, "w") as f: f.write(out)
    return fp, op, out, rc

HEAD = re.compile(r"^range of (\S+) -> (\S+):$", re.M)

def parse_block(text, name):
    m = re.search(r"^range of " + re.escape(name) + r" -> (\S+):\n(.*?)(?=^range of |\Z)", text, re.M | re.S)
    if not m: return None
    body = m.group(2)
    d = {"rtype": m.group(1)}
    hm = re.search(r"^  (.+)$", body, re.M)
    if hm: d["headline"] = hm.group(1).strip()
    sm = re.search(r"^  sound bound \(intervals\): (.+)$", body, re.M)
    if sm: d["sound"] = sm.group(1).strip()
    pm = re.search(r"^  proved bound \(monotonicity, exact algebra\): (.+)$", body, re.M)
    if pm: d["proved"] = pm.group(1).strip()
    d["sampled"] = "sampled " in body
    d["exhaustive"] = "over all" in body and "not exhaustive" not in body
    d["witnesses"] = re.findall(r"take x = (-?\d+)", body)
    d["body"] = body
    return d

def to_int(s):
    s = s.strip()
    try: return int(s)
    except: pass
    try: return float(s)
    except: pass
    return None

def range_vals(headline, rtype):
    """Return (min,max) floats from headline text."""
    if headline is None: return None
    m = re.search(r"(-?[\d.eE+]+)\s*\.\.\s*(-?[\d.eE+]+)", headline)
    if m: return float(m.group(1)), float(m.group(2))
    m = re.search(r"\[\s*(-?[\d.eE+]+)\s*,\s*(-?[\d.eE+]+)\s*\]", headline)
    if m: return float(m.group(1)), float(m.group(2))
    return None

def main():
    print(f"Total specs: {len(SPECS)}")
    # batch 14 per file
    results = {}
    for bi in range(0, len(SPECS), 14):
        batch = SPECS[bi:bi+14]
        idx = bi // 14
        fp, op, out, rc = run_batch(batch, idx)
        for s in batch:
            blk = parse_block(out, s['name'])
            results[s['name']] = (s, blk, rc, op)
    # analyze
    issues = []
    stats = {"exh_correct":0,"samp_sound":0,"samp_unsound":0,"proved_wrong":0,"parse_fail":0,"sound_wrong":0}
    for name, (s, blk, rc, op) in results.items():
        if blk is None:
            stats["parse_fail"] += 1
            issues.append((name,"PARSE_FAIL",f"rc={rc}",op)); continue
        rv = range_vals(blk.get("headline"), blk["rtype"])
        if s['kind'] == "f32":
            grid = f32grid()
        elif s.get('domain') is not None:
            grid = s['domain']
        elif s['t'].w <= 16:
            lo, hi = s['t'].rng()
            grid = range(lo, hi+1)
        else:
            grid = dense_points(s['t'], s['extra'])
        tmin = tmax = None
        amin = amax = None
        for xv in grid:
            y = s['oracle'](xv)
            if y is None: continue
            if tmin is None or y < tmin: tmin, amin = y, xv
            if tmax is None or y > tmax: tmax, amax = y, xv
        rec = dict(name=name, type=s['kind'], headline=blk.get("headline"),
                   sound=blk.get("sound"), proved=blk.get("proved"),
                   sampled=blk["sampled"], exhaustive=blk["exhaustive"],
                   true=(tmin,tmax), argmin=amin, argmax=amax,
                   witnesses=blk["witnesses"], rc=rc)
        # classify headline
        if rv is None:
            issues.append((name,"HEADLINE_UNPARSED",blk.get("headline"),op)); continue
        hmin,hmax = rv
        # integer tolerance: exact
        head_bad = (abs(hmin - tmin) > 1e-6 or abs(hmax - tmax) > 1e-6)
        if s['exhaustive'] is None:
            pass
        if blk["exhaustive"]:
            if not head_bad: stats["exh_correct"] += 1
            else: issues.append((name,"EXH_WRONG",f"headline {hmin}..{hmax} vs true {tmin}..{tmax}",op))
        else:
            # sound bound check
            sb = blk.get("sound")
            sound_bad = False
            if sb:
                sv = range_vals(sb, blk['rtype'])
                if sv and (sv[0] > tmin + 1e-6 or sv[1] < tmax - 1e-6):
                    sound_bad = True
                    stats["sound_wrong"] += 1
                    issues.append((name,"SOUND_BOUND_WRONG",f"sound {sv} vs true {tmin}..{tmax}",op))
            if head_bad:
                stats["samp_unsound"] += 1
                issues.append((name,"HEADLINE_UNSOUND",f"headline {hmin}..{hmax} vs true {tmin}..{tmax}; sound={sb}",op))
            else:
                stats["samp_sound"] += 1
            # witness attainment
            for w in blk["witnesses"]:
                wv = int(w)
                yv = s['oracle'](wv) if s['t'] and s['t'].w <= 32 else None
                if yv is not None and not (abs(yv - hmin) < 1e-3 or abs(yv - hmax) < 1e-3):
                    stats["proved_wrong"] += 1
                    issues.append((name,"WITNESS_WRONG",f"witness x={wv} -> f={yv}, claimed {hmin}..{hmax}",op))
        # save record
        results[name] = (s, blk, rc, op, rec)
    # dump
    with open(os.path.join(HERE, "results.json"), "w") as f:
        json.dump({k:(v[-1] if len(v)>4 else {"blk":v[1],"rc":v[2]}) for k,v in results.items()}, f, indent=1, default=str)
    print("STATS", stats)
    print("ISSUES", len(issues))
    for it in issues[:200]:
        print(it[0], it[1], it[2][:150], it[3])

if __name__ == "__main__":
    main()
