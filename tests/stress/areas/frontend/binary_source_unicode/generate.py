#!/usr/bin/env python3
"""Generate the binary_source_unicode stress corpus.

Deterministic byte-level generator: every weird character is written as an
explicit byte sequence so the reproducers are exact and re-runnable.
Binary: $ROOT/ucas
"""
# PORTABILITY: '$ROOT' in repro commands means the ucas checkout root; set ROOT=/path/to/ucas before copy-pasting.
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE)

def w(name, data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    with open(os.path.join(B, name), 'wb') as f:
        f.write(data)

# ---- byte helpers -----------------------------------------------------------
NUL = b'\x00'
ESC = b'\x1b'
# bidi / format controls (UTF-8)
RLO = b'\xe2\x80\xae'  # U+202E RIGHT-TO-LEFT OVERRIDE
LRE = b'\xe2\x80\xaa'  # U+202A LEFT-TO-RIGHT EMBEDDING
RLE = b'\xe2\x80\xab'  # U+202B RIGHT-TO-LEFT EMBEDDING
PDF = b'\xe2\x80\xac'  # U+202C POP DIRECTIONAL FORMATTING
LRO = b'\xe2\x80\xad'  # U+202D LEFT-TO-RIGHT OVERRIDE
LRM = b'\xe2\x80\x8e'  # U+200E LEFT-TO-RIGHT MARK
RLM = b'\xe2\x80\x8f'  # U+200F RIGHT-TO-LEFT MARK
ZWSP = b'\xe2\x80\x8b'  # U+200B ZERO WIDTH SPACE
ZWNJ = b'\xe2\x80\x8c'  # U+200C ZERO WIDTH NON-JOINER
ZWJ = b'\xe2\x80\x8d'  # U+200D ZERO WIDTH JOINER
BOM = b'\xef\xbb\xbf'  # U+FEFF BOM
WJ = b'\xe2\x81\xa0'   # U+2060 WORD JOINER
SHY = b'\xc2\xad'      # U+00AD SOFT HYPHEN
# Tags block
TAG_a = b'\xf3\xa0\x81\xa1'  # U+E0061 tag 'a'
TAG_A = b'\xf3\xa0\x81\x81'  # U+E0041 tag 'A'
TAG_CANCEL = b'\xf3\xa0\x81\xbf'  # U+E007F cancel tag
TAG_LANG = b'\xf3\xa0\x80\x81'  # U+E0001 language tag
# homoglyphs
CYR_a = b'\xd0\xb0'  # а
CYR_o = b'\xd0\xbe'  # о
CYR_e = b'\xd0\xb5'  # е
CYR_p = b'\xd1\x80'  # р
CYR_c = b'\xd1\x81'  # с
CYR_x = b'\xd1\x85'  # х
GRK_o = b'\xce\xbf'  # ο
MATHBOLD_x = b'\xf0\x9d\x90\xb1'  # 𝐱
FW_s = b'\xef\xbd\x93'  # ｓ
FW_h = b'\xef\xbd\x88'  # ｈ
FW_o = b'\xef\xbd\x8f'  # ｏ
FW_w = b'\xef\xbd\x97'  # ｗ
FW_1 = b'\xef\xbc\x91'  # １
FW_2 = b'\xef\xbc\x92'  # ２
# NFC / NFD
E_ACUTE_NFC = b'\xc3\xa9'       # é
E_ACUTE_NFD = b'e\xcc\x81'      # e + combining acute
U_DIA_NFC = b'\xc3\xbc'         # ü
U_DIA_NFD = b'u\xcc\x88'        # u + combining diaeresis
N_TILDE_NFC = b'\xc3\xf1'       # ñ
N_TILDE_NFD = bn = b'n\xcc\x83'
# combining marks
C_ACUTE = b'\xcc\x81'
C_GRAVE = b'\xcc\x80'
C_DIA = b'\xcc\x88'
C_CEDILLA = b'\xcc\xa7'
C_KEYCAP = b'\xe2\x83\xa3'
# math symbols
LE = b'\xe2\x89\xa4'   # ≤
GE = b'\xe2\x89\xa5'   # ≥
NE = b'\xe2\x89\xa0'   # ≠
APPROX = b'\xe2\x89\x88'  # ≈
INT = b'\xe2\x88\xab'  # ∫
SUM = b'\xe2\x88\x91'  # ∑
PROD = b'\xe2\x88\x8f'  # ∏
SQRT = b'\xe2\x88\x9a'  # √
INF = b'\xe2\x88\x9e'   # ∞
IN = b'\xe2\x88\x88'    # ∈
PART = b'\xe2\x88\x82'  # ∂
NABLA = b'\xe2\x88\x87'  # ∇
PM = b'\xc2\xb1'        # ±
TIMES = b'\xc3\x97'     # ×
DIV = b'\xc3\xb7'       # ÷
MINUS = b'\xe2\x88\x92'  # −
FORALL = b'\xe2\x88\x80'  # ∀
EXISTS = b'\xe2\x88\x83'  # ∃
REALS = b'\xe2\x84\x9d'   # ℝ
DEG = b'\xc2\xb0'       # °
PRIME = b'\xe2\x80\xb2'  # ′
# invalid UTF-8
BAD_CONT = b'\x80'
BAD_FF = b'\xff'
OVERLONG_SLASH = b'\xc0\xaf'
TRUNC_E2 = b'\xe2\x80'
LONE_SURROGATE = b'\xed\xa0\x80'  # CESU-8 D800

# ===========================================================================
# CLI FILE GOLDENS (.ucas). Each line is one statement; NUL truncates per line.
# ===========================================================================

# 01: NUL bytes at many positions
nul_file = b''.join([
    b'show 1+2' + NUL + b'show 3+4\n',         # NUL between two statements, same line
    b'show 5+6' + NUL + b'\n',                  # NUL before newline
    NUL + b'show 7+8\n',                        # NUL at line start
    b'show ab' + NUL + b'cd\n',                 # NUL inside an identifier
    b'f' + NUL + b'oo(x)=x\n',                  # NUL inside a definition name
    b'show ' + NUL + b'9\n',                    # NUL where an expression should start
    b'show 1' + NUL + b'2' + NUL + b'3\n',      # multiple NULs
    b'a=1' + NUL + b'b=2\n',                    # NUL between two defs, same line
    b'# comment' + NUL + b'hidden\n',           # NUL inside a comment
    b'show ' + b'1+2' + NUL + b'garbage\n',     # NUL then garbage
    b'show 4+4\n',                              # clean control line
    NUL + b'\n',                                # NUL-only line
    b'show 10' + NUL + NUL + b'11\n',           # consecutive NULs
    b'sho' + NUL + b'w 2+2\n',                  # NUL inside the 'show' keyword
    b'show 2*' + NUL + b'3\n',                  # NUL inside an operator position
])
w('01_nul_lines.ucas', nul_file)

# 02: bidi and format controls inside identifiers / source
w('02_bidi_identifiers.ucas', b''.join([
    b'show ' + RLO + b'X' + PDF + b'\n',
    b'show A' + LRE + b'B' + PDF + b'\n',
    b'show X' + RLE + b'Y' + PDF + b'\n',
    b'show P' + LRO + b'Q' + PDF + b'\n',
    b'show ' + LRM + b'X\n',
    b'show X' + RLM + b'\n',
    b'show A' + ZWSP + b'B\n',
    b'show A' + ZWNJ + b'B\n',
    b'show A' + ZWJ + b'B\n',
    b'show ' + WJ + b'X\n',
    b'show X' + SHY + b'Y\n',
    b'show 1+2\n',  # clean control
]))

# 03: bidi / format controls inside English requests (trailing ?)
w('03_bidi_english.ucas', b''.join([
    b'is ' + RLO + b'X' + PDF + b' even?\n',
    b'what is ' + RLO + b'x' + PDF + b' squared?\n',
    b'is ' + ZWSP + b'x even?\n',
    b'is x' + ZWNJ + b' even?\n',
    b'what is 2 plus ' + ZWJ + b'2?\n',
    b'range of x' + LRM + b' squared?\n',
    b'is ' + BOM + b'x positive?\n',
    b'what is 2+2?\n',  # clean control
]))

# 04: Unicode Tags block payloads
w('04_tags.ucas', b''.join([
    b'is ' + TAG_a + b'x even?\n',
    b'what is ' + TAG_A + b'x squared?\n',
    b'show ' + TAG_a + b'x\n',
    b'show x' + TAG_CANCEL + b'\n',
    b'is ' + TAG_LANG + b'x positive?\n',
    b'# ' + TAG_a + b'hidden comment\nshow 3\n',
    b'what is ' + TAG_a + b'x plus ' + TAG_a + b'x?\n',
    b'what is 3+3?\n',  # clean control
]))

# 05: homoglyphs
w('05_homoglyphs.ucas', b''.join([
    b'show ' + CYR_o + b'\n',
    b'show ' + CYR_a + b'\n',
    b'show ' + GRK_o + b'\n',
    b'show ' + MATHBOLD_x + b'\n',
    b'show ' + FW_1 + b'+' + FW_2 + b'\n',
    FW_s + FW_h + FW_o + FW_w + b' 1+2\n',
    b'show ' + CYR_x + b'\n',
    b'show a' + CYR_c + b'\n',
    b'show ' + CYR_p + b'\n',
    b'show 2+2\n',  # clean control
]))

# 06: NFC vs NFD / combining marks
w('06_normalization.ucas', b''.join([
    b'show ' + E_ACUTE_NFC + b'\n',
    b'show ' + E_ACUTE_NFD + b'\n',
    b'show ' + U_DIA_NFC + b'\n',
    b'show ' + U_DIA_NFD + b'\n',
    b'show x' + C_ACUTE + b'\n',
    b'show x' + C_GRAVE + b'\n',
    b'show x' + C_DIA + b'\n',
    b'show x' + C_CEDILLA + b'\n',
    b'show 1' + C_KEYCAP + b'\n',
    b'show ' + b'x' * 40 + b'\n',  # clean control
]))

# 07: terminal escape sequences
w('07_escapes.ucas', b''.join([
    b'show ' + ESC + b'[31m1+2' + ESC + b'[0m\n',
    b'show ' + ESC + b'[2J1\n',
    b'show ' + ESC + b'[?25l1\n',
    b'show ' + ESC + b']0;title' + b'\x07' + b'1\n',  # OSC + BEL
    b'show 1' + ESC + b'[1K\n',
    b'show ' + ESC + b'[A1\n',
    b'show 5\n',  # clean control
]))

# 08: math symbols (English + CLI)
w('08_math_symbols.ucas', b''.join([
    b'is 1 ' + LE + b' 2?\n',
    b'is 3 ' + GE + b' 2?\n',
    b'is 3 ' + NE + b' 2?\n',
    b'is 1 ' + APPROX + b' 1?\n',
    b'what is ' + INT + b' x from 0 to 1?\n',
    b'what is ' + SUM + b' x?\n',
    b'what is ' + PROD + b' x?\n',
    b'what is ' + SQRT + b' 16?\n',
    b'show ' + SQRT + b'16\n',
    b'show ' + INF + b'\n',
    b'show 2' + TIMES + b'3\n',
    b'show 6' + DIV + b'3\n',
    b'show 1' + PM + b'2\n',
    b'show 3' + MINUS + b'1\n',
    b'show ' + PART + b'x\n',
    b'show ' + NABLA + b'x\n',
    b'is ' + FORALL + b' x positive?\n',
    b'show ' + REALS + b'\n',
    b'show ' + DEG + b'\n',
    b'show x' + PRIME + b'\n',
    b'show 6\n',  # clean control
]))

# 09: invalid UTF-8 byte sequences
w('09_invalid_utf8.ucas', b''.join([
    b'show ' + BAD_CONT + b'\n',
    b'show ' + BAD_FF + b'\n',
    b'show ' + OVERLONG_SLASH + b'1\n',
    b'show ' + TRUNC_E2 + b'\n',
    b'show ' + LONE_SURROGATE + b'\n',
    b'is ' + BAD_CONT + b' x even?\n',
    b'is ' + TRUNC_E2 + b' even?\n',
    b'show 8\n',  # clean control
]))

# 10: long combining-mark tail (moderate; a 5000-mark version is a FINDINGS probe)
w('10_combining_tail.ucas', b'show x' + C_ACUTE * 120 + b'\n' + b'show 9\n')

# ===========================================================================
# MCP JSONL goldens
# ===========================================================================
def jline(obj):
    return json.dumps(obj, ensure_ascii=False)

def rpc(i, method="tools/call", params=None, with_id=True):
    d = {}
    if with_id:
        d["id"] = i
    d["jsonrpc"] = "2.0"
    d["method"] = method
    if params is not None:
        d["params"] = params
    return jline(d)

def handshake():
    return [
        rpc(0, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "stress", "version": "1"}}),
        rpc(None, "notifications/initialized", with_id=False),
    ]

def tool(i, name, args):
    return rpc(i, params={"name": name, "arguments": args})

# mcp_unicode_english.jsonl : English text with every weird class
eng = handshake()
eng_texts = [
    "is \u202eX\u202c even?",                      # id 1 bidi RLO
    "what is \u200b x squared?",                    # id 2 ZWSP
    "is \u200dx even?",                             # id 3 ZWJ
    "is " + chr(0xE0061) + "x even?",               # id 4 tags block
    "what is \u2264 2?",                            # id 5 <=
    "is 3 \u2265 2?",                               # id 6 >=
    "what is \u222b x from 0 to 1?",               # id 7 integral
    "what is \u221a 16?",                           # id 8 sqrt
    "is 1 \u2248 1?",                              # id 9 approx
    "\ufeffwhat is 2+2?",                          # id 10 BOM
    "what is \u00e9 plus \u00e9?",                  # id 11 NFC
    "what is e\u0301 plus e\u0301?",                # id 12 NFD
    "what is \u043e?",                              # id 13 Cyrillic homoglyph
    "what is \U0001d431 squared?",                  # id 14 math bold x
    "what is \uff11+\uff12?",                       # id 15 fullwidth digits
    "show 1+2",                                     # id 16 clean control
]
for i, t in enumerate(eng_texts, 1):
    eng.append(tool(i, "english", {"text": t}))
w('mcp_unicode_english.jsonl', "\n".join(eng) + "\n")

# mcp_unicode_source.jsonl : ucas source strings with weird bytes (JSON-escaped)
src = handshake()
sources = [
    "show 1+2\u0000show 3+4",     # id 1 raw NUL via JSON escape (becomes -32700)
    "show \u202eX",              # id 2 bidi RLO in source
    "show \u200bX",              # id 3 ZWSP
    "show \u00e9",               # id 4 NFC e-acute
    "show e\u0301",              # id 5 NFD e-acute
    "show \u221e",               # id 6 infinity
    "show \u00d7",               # id 7 times
    "show \u00001",              # id 8 leading NUL
    "show \u001b[31m1",          # id 9 ESC control
    "show 2+2",                  # id 10 clean control
]
for i, s in enumerate(sources, 1):
    src.append(tool(i, "ucas", {"source": s}))
w('mcp_unicode_source.jsonl', "\n".join(src) + "\n")

# mcp_tool_names.jsonl : tool names / args containing weird chars
tn = handshake()
tn.append(rpc(1, params={"name": "an\u0430lyze", "arguments": {"op": "equiv",
           "args": {"f": "x*y", "g": "y*x"}}}))          # Cyrillic а in name
tn.append(rpc(2, params={"name": "englis\u0068", "arguments": {"text": "what is 2+2?"}}))  # normal 'h'
tn.append(rpc(3, params={"name": "englis\u202eh", "arguments": {"text": "what is 2+2?"}}))  # RLO in name
tn.append(rpc(4, params={"name": "english", "arguments": {"tex\u202et": "what is 2+2?"}})) # RLO in arg key
tn.append(rpc(5, params={"name": "analysis", "arguments": {}}))  # unknown but ASCII
tn.append(rpc(6, params={"name": "\u202eenglish", "arguments": {"text": "what is 2+2?"}}))  # leading RLO
w('mcp_tool_names.jsonl', "\n".join(tn) + "\n")

# json_unicode.jsonl : --json frontend, cmd (tool-name analogue) + source/text args
js = []
def jreq(i, cmd, args):
    return jline({"id": i, "cmd": cmd, "args": args})
js.append(jreq(1, "english", {"text": "is \u202eX\u202c even?"}))
js.append(jreq(2, "english", {"text": "is " + chr(0xE0061) + "x even?"}))
js.append(jreq(3, "ucas", {"source": "show \u202eX"}))
js.append(jreq(4, "ucas", {"source": "show e\u0301"}))
js.append(jreq(5, "english", {"text": "what is \u2264 2?"}))
js.append(jreq(6, "english", {"text": "what is \u222b x?"}))
js.append(jreq(7, "ucas", {"source": "show 1+2"}))
js.append(jreq(8, "\u202eenglish", {"text": "what is 2+2?"}))  # bidi in cmd name
js.append(jreq(9, "english", {"text": "what is 3+3?"}))
w('json_unicode.jsonl', "\n".join(js) + "\n")

# ===========================================================================
# CLI stdin runner (self-checking against stdin_all.out)
# ===========================================================================
stdin_cases = [
    ("nul between statements", b"show 1+2\000show 3+4\n"),
    ("nul then clean line", b"show 1+2\000show 3+4\nshow 5+6\n"),
    ("nul at start", b"\000show 9+9\n"),
    ("nul in identifier", b"show ab\000cd\n"),
    ("nul in definition", b"f\000oo(x)=x\nshow foo\n"),
    ("nul in comment", b"# hi\000there\nshow 7\n"),
    ("nul only line", b"\000\n"),
    ("two nuls", b"show 1\0002\0003\n"),
    ("nul between defs", b"a=1\000b=2\nshow a\nshow b\n"),
    ("bidi RLO ident", b"show \xe2\x80\xaeX\xe2\x80\xac\n"),
    ("bidi RLO english", b"is \xe2\x80\xaeX\xe2\x80\xac even?\n"),
    ("tags block english", ("is " + chr(0xE0061) + "x even?\n").encode('utf-8')),
    ("bom start", b"\xef\xbb\xbfshow 1+2\n"),
    ("math <= english", "is 1 \u2264 2?\n".encode()),
    ("math integral english", "what is \u222b x?\n".encode()),
    ("esc in source", b"show \x1b[31m1\n"),
    ("overlong utf8", b"show \xc0\xaf1\n"),
    ("lone continuation", b"show \x80\n"),
    ("nfc eacute", "show \u00e9\n".encode()),
    ("nfd eacute", b"show e\xcc\x81\n"),
]

# Build a runnable sh script. Each case is a printf of octal-escaped bytes.
def oct_escape(bs):
    return ''.join('\\%03o' % c for c in bs)

sh = ['#!/bin/sh', '# Self-checking CLI-stdin reproducers; regenerates stdin_all.got and diffs.',
      'cd "$(dirname "$0")" || exit 1', 'B=$ROOT/ucas',
      ': > stdin_all.got', 'probe() {',
      '  printf "\\n===== %s =====\\n" "$1" >> stdin_all.got',
      '  _p=$(mktemp)',
      '  printf "%b" "$2" | timeout 15 "$B" > "$_p" 2>&1',
      '  printf "exit=%s\\n" "$?" >> stdin_all.got',
      '  cat "$_p" >> stdin_all.got', '  rm -f "$_p"', '}']
for label, bs in stdin_cases:
    sh.append("probe '%s' '%s'" % (label.replace("'", ""), oct_escape(bs)))
sh.append('diff -u stdin_all.out stdin_all.got')
sh.append('_rc=$?')
sh.append('rm -f stdin_all.got')
sh.append('exit $_rc')
w('run_stdin.sh', "\n".join(sh) + "\n")

print("generated files in", B)
