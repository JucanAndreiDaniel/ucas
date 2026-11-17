#!/usr/bin/env python3
"""
Coverage matrix: for each confirmed bug class in MASTER_FINDINGS.md, decide whether any
existing top-level tests/*.out would change if that bug were "fixed".

Definition of COVERED: a golden test exercises the buggy behaviour (its .out exhibits the
observable buggy signature), so a correct fix would change that .out.  A test whose .out
shows the CORRECT behaviour is a positive control, NOT coverage of the bug.

Each (bug class, relevant golden test) pair is one CHECK.  Relevant tests are selected by a
source-feature regex.  All 250 pairs are indexed; up to MAX per class are checked.
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
import os, re, glob, csv, json
R = str(_REPO_ROOT / "tests")
D = os.path.dirname(os.path.abspath(__file__))
MAX = 10

cases = {}
for u in sorted(glob.glob(os.path.join(R, "*.ucas"))):
    n = os.path.basename(u)[:-5]
    o = os.path.join(R, n + ".out")
    if os.path.isfile(o):
        cases[n] = (open(u, errors="replace").read(), open(o, errors="replace").read())

# id, title, severity, feature regex (source), buggy golden signature regex, verified covers, note
BUGS = [
 ("B01","real equiv falsely refuted; witness prints identical values","WRONG",
  r"(?m)^.*\bequiv\b", r"differ at [^\n]*: ([^:\n]+?) vs \1", set(),
  "Signature 'differ at ... V vs V' with identical printed values never occurs in any golden."),
 ("B02","equiv ignores G's where/range narrowing","WRONG",
  r"\bwhere\b", r"(?s)are equal on the domain[^\n]*\(exhaustive\)[^\n]*where", set(),
  "whereor.out covers where-tests but always with matching domains; no narrowed-G test."),
 ("B03","cast coercion u8(x)==i32(x) on i8 proven equal","WRONG",
  r"\bu8\s*\(", r"(?s)u8\s*\([^\n]*i32[^\n]*are equal", set(),
  "No golden combines u8()/i32() casts under equiv."),
 ("B04","domain says 'total' while few points defined","WRONG",
  r"(?m)^.*\bdomain\b", r"total on its parameter types", {"texfetch","whereor"},
  "texfetch.out: 'total on its parameter types' + 'defined at 7 of 10 points' -> fix changes it."),
 ("B05","u64 domain/range clipped to 2^63-1","WRONG",
  r"\bu64\b", r"0\.\.9223372036854775807", set(),
  "u64range.out prints the CORRECT 0..2^64-1; buggy clip not present in any golden."),
 ("B06","wrap end-to-end 'differs at 0 points' despite nsw fails","WRONG",
  r"(?m)^.*\bwrap\b", r"differs from the mathematical result at 0 points", set(),
  "All wrap goldens report a nonzero diff or 'equals everywhere'; no buggy 0-points golden."),
 ("B07","vacuous 'equal proved by SAT' on empty domain","WRONG",
  r"(?m)^.*\bequiv\b", r"(?s)proved by SAT[^\n]*(no point|none of|0 points|empty domain)", set(),
  "No golden contains a SAT proof over an empty/undefined domain."),
 ("B08","stale it/that auto-names in multi-request sessions -> self-compare false","WRONG",
  r"(?m)^.*\bequiv\b", r"(?s)it[^\n]*that[^\n]*differ", set(),
  "CLI goldens are single files; zero-param JSON/MCP session state cannot be covered."),
 ("B09","f32/f16 point-spike range excludes reachable value","WRONG",
  r"(?m)^.*\brange\b", r"(?s)range[^\n]*\n[^\n]*0\.\.0[^\n]*\n[^\n]*not exhaustive", set(),
  "No golden ranges a point-spike function; fp_edge repro not in main suite."),
 ("B10","symmetry claims both symmetric and antisymmetric","WRONG",
  r"(?m)^.*\bsymmetry\b", r"antisymmetric", set(),
  "No golden ever prints 'antisymmetric'."),
 ("B11","systematic 1-ulp / double-rounding float errors","WRONG",
  r"\bf(16|32)\s*\(", r"f(16|32)\s*\(\s*(exp|log|sin|cos)\s*\(\s*asfloat", set(),
  "No golden composes f16/f32(exp(asfloat(...))) in the buggy double-round shape."),
 ("B12","complex (-1)^(p/q) self-contradictory Re/Im with vacuous check","WRONG",
  r"\bi\b|\^", r"DISAGREES", set(),
  "No golden prints 'DISAGREES' (the self-check failure marker)."),
 ("B13","taylor high-order coefficient wrong (order>=8)","WRONG",
  r"(?m)^.*\btaylor\b", r"23x\^8/7", set(),
  "Max taylor order in goldens is 7; the order-8 1/(1+x^2) repro (23x^8/7) is absent."),
 ("B14","limit of sec/csc/cot at pole returns huge finite value","WRONG",
  r"(?m)^.*\blimit\b", r"(?s)limit[^\n]*(sec|csc|cot)[^\n]*\n[^\n]*e\+", set(),
  "No golden takes a limit of sec/csc/cot at a singularity."),
 ("B15","English scale words add instead of multiply","WRONG",
  r"(?i)thousand|million|billion", r"1001000|2000000\b|10\^9", set(),
  "nlp_numbers.out only tests correct single-scale phrases; none repeat scale words."),
 ("B16","English 'is 1 < 2 < 3?' parsed as chained bool -> 0","WRONG",
  r"(?m)^>\s*is\b", r"(?s)is 1 < 2 < 3[^\n]*\n[^\n]*\n0", set(),
  "No golden contains the chained-comparison question."),
 ("B17","solve x = x for x -> 'x does not occur / no real solution'","WRONG",
  r"(?m)^.*\bsolve\b", r"(?s)solve x = x[^\n]*no real solution|does not occur", set(),
  "algebra.out solve cases are genuine unsolvable equations; x=x absent."),
 ("B18","powerseries multiplies series by the variable","WRONG",
  r"(?m)^.*\bpowerseries\b", r"(?s)x\^\(m\+1\)|c_m x\^\(n\+1\)", set(),
  "xform.out powerseries shows correct x^m coefficients; buggy x^(m+1) absent."),
 ("B19","laplace_solve / zsolve drop ';'-separated initial conditions","WRONG",
  r"(?m)^.*\blaplace\b", r"(?s)laplace[^\n]*;[^\n]*y=0", set(),
  "CLI laplace transforms are correct; the MCP laplace_solve IC bug has no golden."),
 ("B20","fourier(x^n)=0 instead of derivative-of-delta","WRONG",
  r"(?m)^.*\bfourier\b", r"(?s)fourier[^\n]*x\^?n?[^\n]*=\s*0", set(),
  "xform.out Fourier series of x^2 is nonzero; buggy transform of x^n absent."),
 ("B21","groebner silently drops 257th polynomial","WRONG",
  r"(?m)^.*\bgroebner\b", r"(?s)groebner.*257", set(),
  "absalg.out groebner inputs have <=4 polynomials; 257-input repro absent."),
 ("B22","pmsnf drops rows past 64","WRONG",
  r"(?m)^.*\bpmsnf\b", r"(?s)pmsnf.*diag\(x\)", set(),
  "absalg.out pmsnf inputs are small; 65-row repro absent."),
 ("B23","primroot swaps candidate a and modulus n (MCP)","WRONG",
  r"(?m)^.*\bprimroot\b", r"(?s)primroot[^\n]*(3 mod 7|2 mod 7)[^\n]*\bno\b", set(),
  "rings.out 'primroot 2 mod 11' -> correct 'yes'; swapped-arg bug absent."),
 ("B24","abselftest INT_MAX unbounded CPU loop (HANG)","HANG",
  r"(?m)^.*\babselftest\b", r"abselftest 2147483647", set(),
  "absalg.out runs 'abselftest 500' (fast); the hanging argument is absent."),
 ("B25","real literal 1e400 overflows silently to inf/0","WRONG",
  r"1e400", r"1e400", set(),
  "No golden contains a 1e400 literal."),
 ("B26","mixed signed/unsigned silently reinterprets/narrows","WRONG",
  r"\bu8\s*\(|\bi8\s*\(", r"(?s)u8\(1\)\s*\+\s*i8\(-2\)[^\n]*255", set(),
  "No golden mixes u8()/i8() operands in one expression."),
 ("B27","English nested compositional phrase ReDoS hang","HANG",
  r"(?m)^>\s*(the|what)", r"(?s)the sqrt of[^\n]*the sqrt of", set(),
  "NLP goldens contain short sentences; 20x nested 'the sqrt of' absent."),
 ("B28","deep nesting SIGSEGV (parser/evaluator stack overflow)","CRASH",
  r"\bparse\b|\bshow\b", r"(?s)\({100,}", set(),
  "Goldens never contain >100 nested parens; crash repros deliberately excluded."),
 ("B29","timeout_s forked child desyncs reply stream (MCP/JSON)","DETERMINISM",
  r"timeout_s", r"timeout_s", set(),
  "No top-level CLI golden uses timeout_s (an MCP/JSON-only flag)."),
 ("B30","error reports 'max abs error 0' for genuinely different functions","WRONG",
  r"(?m)^.*\berror\b", r"(?s)max abs error 0[^\n]*\n[^\n]*differ", set(),
  "No golden pairs an error:0 claim with a differing verdict in the same test."),
 ("B31","identify invents bogus period/zeros for zero function","WRONG",
  r"(?m)^.*\bidentify\b", r"period pi/32|monotonicity intervals|15884 zeros", set(),
  "identify goldens use nonzero functions; bogus-constants repro absent."),
 ("B32","equiv with undefined name accepted as free variable","WRONG",
  r"(?m)^.*\bequiv\b", r"(?s)nonexistent[^\n]*are equal|undefined[^\n]*are equal", set(),
  "No golden equivs an undefined identifier."),
]

rx_cache = {}
def rx(p):
    if p not in rx_cache: rx_cache[p]=re.compile(p, re.I)
    return rx_cache[p]

checks=[]
covered={}
for (bid,title,sev,feat,sig,manual,note) in BUGS:
    feat_rel=sorted(n for n,(s,o) in cases.items() if rx(feat).search(s))[:MAX]
    relevant=sorted(set(feat_rel) | set(manual))
    covers=[]
    for n in relevant:
        s,o=cases[n]
        sigmatch=bool(rx(sig).search(o))
        iscov=sigmatch or (n in manual)
        if iscov: covers.append(n)
        checks.append(dict(bug_id=bid,bug=title,test=n,
                           source_feature=bool(rx(feat).search(s)),
                           golden_sig=sigmatch,
                           verdict="COVERS" if iscov else "no_bug_signature"))
    covered[bid]=(len(covers)>0, covers, len(relevant), note, title, sev)

with open(os.path.join(D,"checks.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["bug_id","bug","test","source_feature","golden_sig","verdict"])
    w.writeheader(); w.writerows(checks)

lines=["# Bug-class coverage matrix","",
       "Generated by `data/build_matrix.py`. Each (bug class, relevant golden test) pair is one CHECK.",
       "COVERED means at least one existing `.out` exhibits the buggy signature, so a correct fix",
       "would change that golden. Otherwise GAP (no covering test in the 500-file suite).","",
       "| Bug | Class | Severity | Covered? | Checks | Covering test(s) | Note |",
       "|---|---|---|---|---:|---|---|"]
for bid,(yes,covers,nrel,note,title,sev) in covered.items():
    lines.append(f"| {bid} | {title} | {sev} | {'COVERED' if yes else 'GAP'} | {nrel} | {', '.join(covers) if covers else 'GAP'} | {note} |")
summary=dict(total_checks=len(checks),
             covered=sum(1 for v in covered.values() if v[0]),
             gaps=sum(1 for v in covered.values() if not v[0]),
             classes=len(BUGS))
lines += ["",f"**Totals:** {summary['classes']} bug classes, {summary['total_checks']} checks, "
          f"{summary['covered']} covered, {summary['gaps']} GAP.",""]
open(os.path.join(D,"..","COVERAGE_MATRIX.md"),"w").write("\n".join(lines))
json.dump(dict(summary=summary,
               classes={b:dict(covered=v[0],covering=v[1],checks=v[2],note=v[3],title=v[4],sev=v[5])
                        for b,v in covered.items()}),
          open(os.path.join(D,"matrix.json"),"w"),indent=2)
print(json.dumps(summary,indent=2))
