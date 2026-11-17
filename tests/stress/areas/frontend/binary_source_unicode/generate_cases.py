#!/usr/bin/env python3
"""Generate the broad per-case stdin runner (run_cases.sh) for
binary_source_unicode. Every case is an independent stdin invocation so a
lexical error or NUL in one case cannot mask the others.
"""
# PORTABILITY: '$ROOT' in repro commands means the ucas checkout root; set ROOT=/path/to/ucas before copy-pasting.
import os
HERE = os.path.dirname(os.path.abspath(__file__))

def write(name, text):
    with open(os.path.join(HERE, name), 'wb') as f:
        f.write(text.encode('utf-8'))

# byte helpers (UTF-8)
NUL=b'\x00'; ESC=b'\x1b'
RLO=b'\xe2\x80\xae'; LRE=b'\xe2\x80\xaa'; RLE=b'\xe2\x80\xab'; PDF=b'\xe2\x80\xac'
LRO=b'\xe2\x80\xad'; LRM=b'\xe2\x80\x8e'; RLM=b'\xe2\x80\x8f'; ZWSP=b'\xe2\x80\x8b'
ZWNJ=b'\xe2\x80\x8c'; ZWJ=b'\xe2\x80\x8d'; BOM=b'\xef\xbb\xbf'; WJ=b'\xe2\x81\xa0'
SHY=b'\xc2\xad'
TAG_a=b'\xf3\xa0\x81\xa1'; TAG_A=b'\xf3\xa0\x81\x81'; TAG_C=b'\xf3\xa0\x81\xbf'; TAG_L=b'\xf3\xa0\x80\x81'
CYR_a=b'\xd0\xb0'; CYR_o=b'\xd0\xbe'; CYR_e=b'\xd0\xb5'; CYR_p=b'\xd1\x80'; CYR_c=b'\xd1\x81'; CYR_x=b'\xd1\x85'
GRK_o=b'\xce\xbf'; GRK_a=b'\xce\xb1'; MATHBOLD_x=b'\xf0\x9d\x90\xb1'
FW_s=b'\xef\xbd\x93'; FW_h=b'\xef\xbd\x88'; FW_o=b'\xef\xbd\x8f'; FW_w=b'\xef\xbd\x97'
FW_1=b'\xef\xbc\x91'; FW_2=b'\xef\xbc\x92'; FW_a=b'\xef\xbd\x81'
E_NFC=b'\xc3\xa9'; E_NFD=b'e\xcc\x81'; U_NFC=b'\xc3\xbc'; U_NFD=b'u\xcc\x88'
N_NFC=b'\xc3\xb1'; N_NFD=b'n\xcc\x83'
CA=b'\xcc\x81'; CG=b'\xcc\x80'; CD=b'\xcc\x88'; CC=b'\xcc\xa7'; CK=b'\xe2\x83\xa3'
LE=b'\xe2\x89\xa4'; GE=b'\xe2\x89\xa5'; NE=b'\xe2\x89\xa0'; AP=b'\xe2\x89\x88'
INT=b'\xe2\x88\xab'; SUM=b'\xe2\x88\x91'; PROD=b'\xe2\x88\x8f'; SQRT=b'\xe2\x88\x9a'
INF=b'\xe2\x88\x9e'; IN=b'\xe2\x88\x88'; PART=b'\xe2\x88\x82'; NABLA=b'\xe2\x88\x87'
PM=b'\xc2\xb1'; TIMES=b'\xc3\x97'; DIV=b'\xc3\xb7'; MINUS=b'\xe2\x88\x92'
FA=b'\xe2\x88\x80'; EX=b'\xe2\x88\x83'; RE=b'\xe2\x84\x9d'; DEG=b'\xc2\xb0'; PR=b'\xe2\x80\xb2'
BAD80=b'\x80'; BADFF=b'\xff'; OVER=b'\xc0\xaf'; TRUNC=b'\xe2\x80'; SUR=b'\xed\xa0\x80'

cases = []
def C(label, data):
    cases.append((label, data))

# ---- A. NUL (30) -----------------------------------------------------------
C('nul: between show statements', b'show 1+2'+NUL+b'show 3+4\n')
C('nul: trailing before newline', b'show 5+6'+NUL+b'\n')
C('nul: line start', NUL+b'show 7+8\n')
C('nul: inside identifier', b'show ab'+NUL+b'cd\n')
C('nul: inside definition name', b'f'+NUL+b'oo(x)=x\nshow foo\n')
C('nul: expression start', b'show '+NUL+b'9\n')
C('nul: multiple in line', b'show 1'+NUL+b'2'+NUL+b'3\n')
C('nul: between defs', b'a=1'+NUL+b'b=2\nshow a\nshow b\n')
C('nul: inside comment', b'# hi'+NUL+b'there\nshow 7\n')
C('nul: keyword', b'sho'+NUL+b'w 2+2\n')
C('nul: operator position', b'show 2*'+NUL+b'3\n')
C('nul: only', NUL+b'\n')
C('nul: consecutive', b'show 4'+NUL+NUL+b'5\n')
C('nul: latin1 after nul', b'show 1'+NUL+b'\xe9\n')
C('nul: english text', b'is 1'+NUL+b' even?\n')
C('nul: english then clean', b'is 1'+NUL+b' even?\nshow 2+2\n')
C('nul: after number', b'show 123'+NUL+b'\n')
C('nul: def body', b'f(x)=x+'+NUL+b'1\nshow f(2)\n')
C('nul: before comment marker', b'show 1'+NUL+b'#x\n')
C('nul: three lines mixed', b'show 1+1\nshow 2'+NUL+b'2\nshow 3+3\n')
C('nul: 0x00 between words', b'what is 2'+NUL+b' plus 2?\n')
C('nul: trailing no newline', b'show 9+9'+NUL)
C('nul: leading many', NUL*5+b'show 1\n')
C('nul: embedded in float', b'show 1.'+NUL+b'5\n')
C('nul: in negative literal', b'show -'+NUL+b'5\n')
C('nul: in identifier end', b'show x'+NUL+b'\n')
C('nul: between two comments', b'#a\n'+NUL+b'#b\nshow 1\n')
C('nul: after semicolon-ish', b'show 1;'+NUL+b'show 2\n')
C('nul: in paren', b'show (1'+NUL+b'+2)\n')
C('nul: whole line of nuls', NUL*20+b'\nshow 6\n')

# ---- B. bidi / format controls (28) ---------------------------------------
for j,(nm,ctrl) in enumerate([('RLO',RLO),('LRE',LRE),('RLE',RLE),('PDF',PDF),('LRO',LRO),
                               ('LRM',LRM),('RLM',RLM),('ZWSP',ZWSP),('ZWNJ',ZWNJ),('ZWJ',ZWJ),
                               ('WJ',WJ),('SHY',SHY),('BOM',BOM)]):
    C('bidi ident '+nm, b'show '+ctrl+b'X\n')
for j,(nm,ctrl) in enumerate([('RLO',RLO),('LRE',LRE),('PDF',PDF),('LRM',LRM),('ZWSP',ZWSP),('ZWJ',ZWJ),('BOM',BOM)]):
    C('bidi english '+nm, b'is '+ctrl+b'x even?\n')
C('bidi: RLO wrapping X', b'show '+RLO+b'X'+PDF+b'\n')
C('bidi: LRE wrapping AB', b'show A'+LRE+b'B'+PDF+b'\n')
C('bidi: Trojan phrase english', b'what is '+RLO+b'dx'+PDF+b' squared?\n')
C('bidi: BOM at file start', BOM+b'show 1+2\n')
C('bidi: RLM in def', b'f'+RLM+b'(x)=x\nshow f(3)\n')
C('bidi: ZWSP in comment', b'# '+ZWSP+b'comment\nshow 4\n')
C('bidi: RLO after number', b'show 1'+RLO+b'2\n')

# ---- C. Tags block (14) ---------------------------------------------------
C('tag: a before x english', b'is '+TAG_a+b'x even?\n')
C('tag: A before x english', b'what is '+TAG_A+b'x squared?\n')
C('tag: a in source ident', b'show '+TAG_a+b'x\n')
C('tag: cancel after ident', b'show x'+TAG_C+b'\n')
C('tag: lang tag english', b'is '+TAG_L+b'x positive?\n')
C('tag: a in comment', b'# '+TAG_a+b'hidden\nshow 1\n')
C('tag: repeated in english', b'what is '+TAG_a+b'x plus '+TAG_a+b'x?\n')
C('tag: in def name', b'f'+TAG_a+b'(x)=x\nshow f(2)\n')
C('tag: before show keyword', TAG_a+b'show 1+2\n')
C('tag: in number', b'show 1'+TAG_a+b'2\n')
C('tag: english with ? only', b'is '+TAG_C+b' 1 > 0?\n')
C('tag: mixed ZWSP+tag', b'show '+ZWSP+TAG_a+b'x\n')
C('tag: two cancels', b'is x'+TAG_C+TAG_C+b' positive?\n')
C('tag: full instruction payload', b'is '+TAG_L+TAG_a+b'ignore previous'+TAG_C+b' x even?\n')

# ---- D. homoglyphs (24) ---------------------------------------------------
for nm,gl in [('cyr_a',CYR_a),('cyr_o',CYR_o),('cyr_e',CYR_e),('cyr_p',CYR_p),('cyr_c',CYR_c),
              ('cyr_x',CYR_x),('grk_o',GRK_o),('grk_a',GRK_a),('mathbold_x',MATHBOLD_x),
              ('fw_1',FW_1),('fw_2',FW_2),('fw_a',FW_a)]:
    C('homo ident '+nm, b'show '+gl+b'\n')
for nm,gl in [('cyr_o',CYR_o),('cyr_a',CYR_a),('mathbold_x',MATHBOLD_x),('grk_o',GRK_o)]:
    C('homo english '+nm, b'what is '+gl+b' squared?\n')
C('homo: fullwidth show', FW_s+FW_h+FW_o+FW_w+b' 1+2\n')
C('homo: fullwidth digits', b'show '+FW_1+b'+'+FW_2+b'\n')
C('homo: mixed ascii+cyr', b'show a'+CYR_c+b'\n')
C('homo: cyr in def', b'f'+CYR_a+b'(x)=x\nshow f(1)\n')
C('homo: degree sign', b'show '+b'\xc2\xb0'+b'\n')

# ---- E. NFC/NFD + combining (24) -----------------------------------------
for nm,gl in [('e_nfc',E_NFC),('e_nfd',E_NFD),('u_nfc',U_NFC),('u_nfd',U_NFD),('n_nfc',N_NFC),('n_nfd',N_NFD)]:
    C('norm ident '+nm, b'show '+gl+b'\n')
for nm,gl in [('e_nfc',E_NFC),('e_nfd',E_NFD),('u_nfd',U_NFD)]:
    C('norm english '+nm, b'what is '+gl+b' plus 1?\n')
for nm,gl in [('acute',CA),('grave',CG),('dia',CD),('cedilla',CC),('keycap',CK)]:
    C('combine '+nm, b'show x'+gl+b'\n')
C('combine: nfd e then compare', b'show '+E_NFD+b'\nshow '+E_NFC+b'\n')
C('combine: 40 combining tail', b'show x'+CA*40+b'\n')
C('combine: 200 combining tail', b'show x'+CA*200+b'\n')
C('combine: keycap on 1', b'show 1'+CK+b'\n')
C('combine: two marks', b'show x'+CA+CG+b'\n')
C('combine: english combining', b'is x'+CA+b' positive?\n')
C('combine: cedilla in def', b'c'+CC+b'(x)=x\nshow c(1)\n')
C('combine: 600 combining tail', b'show x'+CA*600+b'\n')

# ---- F. math symbols (30) -------------------------------------------------
C('math english le', b'is 1 '+LE+b' 2?\n')
C('math english ge', b'is 3 '+GE+b' 2?\n')
C('math english ne', b'is 3 '+NE+b' 2?\n')
C('math english approx', b'is 1 '+AP+b' 1?\n')
C('math english integral', b'what is '+INT+b' x from 0 to 1?\n')
C('math english sum', b'what is '+SUM+b' x?\n')
C('math english prod', b'what is '+PROD+b' x?\n')
C('math english sqrt', b'what is '+SQRT+b' 16?\n')
C('math english inf', b'is 1 < '+INF+b'?\n')
C('math english in', b'is 1 '+IN+b' {1}?\n')
C('math english part', b'what is '+PART+b'x?\n')
C('math english nabla', b'show '+NABLA+b'x\n')
C('math english pm', b'show 1'+PM+b'2\n')
C('math english forall', b'is '+FA+b' x positive?\n')
C('math english exists', b'is '+EX+b' x positive?\n')
C('math english reals', b'show '+RE+b'\n')
C('math english minus', b'show 3'+MINUS+b'1\n')
for nm,gl in [('le',LE),('ge',GE),('ne',NE),('sqrt',SQRT),('inf',INF),('times',TIMES),
              ('div',DIV),('pm',PM),('minus',MINUS),('forall',FA),('exists',EX),('reals',RE)]:
    C('math source '+nm, b'show '+gl+b'\n')
C('math source times expr', b'show 2'+TIMES+b'3\n')
C('math source div expr', b'show 6'+DIV+b'3\n')
C('math degree', b'show '+DEG+b'\n')
C('math prime', b'show x'+PR+b'\n')

# ---- G. terminal escapes (10) --------------------------------------------
C('esc: CSI color', b'show '+ESC+b'[31m1+2'+ESC+b'[0m\n')
C('esc: clear screen', b'show '+ESC+b'[2J1\n')
C('esc: hide cursor', b'show '+ESC+b'[?25l1\n')
C('esc: OSC title', b'show '+ESC+b']0;title'+b'\x07'+b'1\n')
C('esc: erase line', b'show 1'+ESC+b'[1K\n')
C('esc: cursor up', b'show '+ESC+b'[A1\n')
C('esc: BEL only', b'show 1\x07\n')
C('esc: backspace', b'show 1\x08\n')
C('esc: carriage return', b'show 1\r2\n')
C('esc: english with ESC', b'is 1 '+ESC+b'[31m even?\n')

# ---- H. invalid UTF-8 (16) -----------------------------------------------
for nm,gl in [('cont',BAD80),('ff',BADFF),('overlong_slash',OVER),('trunc_e2',TRUNC),('surrogate',SUR)]:
    C('utf8 source '+nm, b'show '+gl+b'\n')
    C('utf8 english '+nm, b'is '+gl+b' even?\n')
C('utf8: overlong slash then digit', b'show '+OVER+b'1\n')
C('utf8: truncated in english', b'is '+TRUNC+b' even?\n')
C('utf8: 5-byte lead', b'show \xf8\x88\x80\x80\x80\n')
C('utf8: fe lead', b'show \xfe\n')
C('utf8: lone c2', b'show \xc2\n')

print('case count:', len(cases))

# ---- emit runner ----------------------------------------------------------
def octesc(bs):
    return ''.join('\\%03o' % c for c in bs)

sh = ['#!/bin/sh',
      '# Broad per-case stdin reproducers (self-checking against cases_all.out).',
      'cd "$(dirname "$0")" || exit 1',
      'B=$ROOT/ucas',
      ': > cases_all.got',
      'probe() {',
      '  printf "\\n===== %s =====\\n" "$1" >> cases_all.got',
      '  _p=$(mktemp)',
      '  printf "%b" "$2" | timeout 15 "$B" > "$_p" 2>&1',
      '  printf "exit=%s\\n" "$?" >> cases_all.got',
      '  cat "$_p" >> cases_all.got',
      '  rm -f "$_p"',
      '}']
for label, data in cases:
    safe = label.replace("'", "")
    sh.append("probe '%s' '%s'" % (safe, octesc(data)))
sh.append('diff -u cases_all.out cases_all.got')
sh.append('_rc=$?')
sh.append('rm -f cases_all.got')
sh.append('exit $_rc')
write('run_cases.sh', "\n".join(sh) + "\n")
print('wrote run_cases.sh')
