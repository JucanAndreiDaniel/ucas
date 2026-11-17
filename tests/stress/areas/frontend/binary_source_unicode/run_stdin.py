#!/usr/bin/env python3
"""Self-checking CLI-stdin reproducers; regenerates stdin_all.got and diffs.
"""

import os
import subprocess
import sys
from pathlib import Path


def _find_root(start):
    p = Path(start).resolve()
    while True:
        if (p / "ucas").is_file() and (p / "src").is_dir():
            return p
        parent = p.parent
        if parent == p:
            raise SystemExit("cannot find repo root")
        p = parent


HERE = Path(__file__).resolve().parent
ROOT = _find_root(HERE)
BIN = ROOT / "ucas"

ENV = os.environ.copy()
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"


def _octal(data):
    r"""Reproduce POSIX printf %b for the \ooo octal escapes used in this folder."""
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        c = data[i]
        if c == "\\" and i + 1 < n and data[i + 1] in "01234567":
            j = i + 1
            while j < n and j < i + 4 and data[j] in "01234567":
                j += 1
            out.append(int(data[i + 1:j], 8) & 0xFF)
            i = j
        else:
            out.extend(c.encode("utf-8"))
            i += 1
    return bytes(out)


GOLDEN = HERE / "stdin_all.out"
GOT = HERE / "stdin_all.got"


def probe(label, data):
    payload = _octal(data)
    with open(GOT, "ab") as g:
        g.write(f"\n===== {label} =====\n".encode("utf-8"))
        try:
            p = subprocess.run([str(BIN)], input=payload,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=15, env=ENV)
            rc, out = p.returncode, p.stdout
        except subprocess.TimeoutExpired as e:
            rc, out = 124, (e.stdout or b"")
        g.write(f"exit={rc}\n".encode("ascii"))
        g.write(out)


def main():
    with open(GOT, "wb"):
        pass
    probe('nul between statements', '\\163\\150\\157\\167\\040\\061\\053\\062\\000\\163\\150\\157\\167\\040\\063\\053\\064\\012')
    probe('nul then clean line', '\\163\\150\\157\\167\\040\\061\\053\\062\\000\\163\\150\\157\\167\\040\\063\\053\\064\\012\\163\\150\\157\\167\\040\\065\\053\\066\\012')
    probe('nul at start', '\\000\\163\\150\\157\\167\\040\\071\\053\\071\\012')
    probe('nul in identifier', '\\163\\150\\157\\167\\040\\141\\142\\000\\143\\144\\012')
    probe('nul in definition', '\\146\\000\\157\\157\\050\\170\\051\\075\\170\\012\\163\\150\\157\\167\\040\\146\\157\\157\\012')
    probe('nul in comment', '\\043\\040\\150\\151\\000\\164\\150\\145\\162\\145\\012\\163\\150\\157\\167\\040\\067\\012')
    probe('nul only line', '\\000\\012')
    probe('two nuls', '\\163\\150\\157\\167\\040\\061\\000\\062\\000\\063\\012')
    probe('nul between defs', '\\141\\075\\061\\000\\142\\075\\062\\012\\163\\150\\157\\167\\040\\141\\012\\163\\150\\157\\167\\040\\142\\012')
    probe('bidi RLO ident', '\\163\\150\\157\\167\\040\\342\\200\\256\\130\\342\\200\\254\\012')
    probe('bidi RLO english', '\\151\\163\\040\\342\\200\\256\\130\\342\\200\\254\\040\\145\\166\\145\\156\\077\\012')
    probe('tags block english', '\\151\\163\\040\\363\\240\\201\\241\\170\\040\\145\\166\\145\\156\\077\\012')
    probe('bom start', '\\357\\273\\277\\163\\150\\157\\167\\040\\061\\053\\062\\012')
    probe('math <= english', '\\151\\163\\040\\061\\040\\342\\211\\244\\040\\062\\077\\012')
    probe('math integral english', '\\167\\150\\141\\164\\040\\151\\163\\040\\342\\210\\253\\040\\170\\077\\012')
    probe('esc in source', '\\163\\150\\157\\167\\040\\033\\133\\063\\061\\155\\061\\012')
    probe('overlong utf8', '\\163\\150\\157\\167\\040\\300\\257\\061\\012')
    probe('lone continuation', '\\163\\150\\157\\167\\040\\200\\012')
    probe('nfc eacute', '\\163\\150\\157\\167\\040\\303\\251\\012')
    probe('nfd eacute', '\\163\\150\\157\\167\\040\\145\\314\\201\\012')

    d = subprocess.run(["diff", "-u", str(GOLDEN), str(GOT)],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    GOT.unlink(missing_ok=True)
    sys.stdout.buffer.write(d.stdout)
    sys.stdout.buffer.flush()
    return d.returncode


if __name__ == "__main__":
    sys.exit(main())
