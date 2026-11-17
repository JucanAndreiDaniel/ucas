#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter, defaultdict
rows=[json.loads(l) for l in Path('results.jsonl').read_text().splitlines() if l.strip()]
print("TOTAL scenarios:",len(rows))
print("by category:",dict(Counter(r['category'] for r in rows)))
print("fresh_ok=False:",sum(1 for r in rows if not r['fresh_ok']))
print("orphans>0:",sum(1 for r in rows if len(r['orphans'])>0))
print("core-ish rc (SIGSEGV=-11,SIGABRT=-6,SIGQUIT=-3):",
      [r['id'] for r in rows if r['rc'] in (-11,-6,-3)])
print("rc values:",dict(Counter(r['rc'] for r in rows)))
print()
print("=== ORPHAN-PRODUCING scenarios (category mode/sig) ===")
o=defaultdict(int)
for r in rows:
    if r['orphans']: o[(r['category'],tuple(r['signals']))]+=1
for k,v in sorted(o.items()): print(" ",k,v)
print()
print("=== json/mcp json_valid=False ===")
for r in rows:
    if r.get('json_valid') is False:
        print(" ",r['id'],r['category'],r['name'],r.get('json_detail'))
print()
print("=== tstp state_at_stop values ===")
print(dict(Counter(r.get('state_at_stop') for r in rows if r['category']=='tstp_cont')))
print()
print("=== parent_alive_after_child_kill ===")
print(dict(Counter(str(r.get('parent_alive_after_child_kill')) for r in rows if 'childkill' in r['category'])))
print()
print("=== representative outputs (first of each category) ===")
seen=set()
for r in rows:
    if r['category'] in seen: continue
    seen.add(r['category'])
    outp=Path('runs')/f"{r['name']}_{r['delay_s']}.out"
    if not outp.exists():
        # some names lack delay suffix
        cand=list(Path('runs').glob(r['name']+'*.out'))
        outp=cand[0] if cand else None
    tail = outp.read_bytes()[-400:].decode('utf-8','replace') if outp and outp.exists() else 'N/A'
    print(f"-- {r['category']} id={r['id']} rc={r['rc']} kids={r['kids_before']} orph={r['orphans']}")
    print("   tail:",repr(tail[-200:]))
