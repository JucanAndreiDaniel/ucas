#!/usr/bin/env python3
"""Generate mode-sensitive float equivalence pairs for ucas stress testing.

Each pair has hand-computed expectations (from IEEE-754 rules and the
documented ucas equiv semantics) for noftz vs ftz and no-nanbits vs nanbits.
Expectations are 'equal' / 'differ' / None (unknown / exploratory).
"""
import json, os

PAIRS = []
def add(name, f, g, params='x: u32', exp_noftz=None, exp_ftz=None,
        exp_nobits=None, exp_bits=None, modes=('ftz','nanbits'), note=''):
    PAIRS.append(dict(name=name, f=f, g=g, params=params,
                      exp_noftz=exp_noftz, exp_ftz=exp_ftz,
                      exp_nobits=exp_nobits, exp_bits=exp_bits,
                      modes=list(modes), note=note))

# ---------------------------------------------------------------------------
# FTZ flush of subnormal inputs / outputs
# ---------------------------------------------------------------------------
for i, c in enumerate(['f32(0)', 'f32(-0.0)']):
    add(f'ftz_add0_{i}', f'asfloat(x) + {c}', 'asfloat(x)',
        exp_noftz='equal', exp_ftz='differ', modes=('ftz',),
        note='x+c identity under noftz; subnormal flushed under ftz')

add('ftz_fma1', 'fma(asfloat(x), f32(1), f32(0))', 'asfloat(x)',
    exp_noftz='equal', exp_ftz='differ', modes=('ftz',),
    note='fma(x,1,0)=x under noftz; ftz flushes subnormal')

add('ftz_subnormal_test32',
    'abs(asfloat(x)) < f32(2^(-126)) ? f32(1) : f32(0)',
    'asfloat(x) == f32(0) ? f32(1) : f32(0)',
    exp_noftz='differ', exp_ftz='equal', modes=('ftz',),
    note='subnormal vs zero differ under noftz, collapse under ftz')

add('ftz_subnormal_test16',
    'abs(asfloat(x)) < f16(2^(-14)) ? f16(1) : f16(0)',
    'asfloat(x) == f16(0) ? f16(1) : f16(0)', params='x: u16',
    exp_noftz='differ', exp_ftz='equal', modes=('ftz',),
    note='f16 subnormal vs zero test')

# add of a tiny constant: keep x under noftz only when c is +0/-0
tiny_constants = ['f32(2^(-149))', 'f32(2^(-148))', 'f32(3 * 2^(-149))',
                  'f32(2^(-140))', 'f32(0.0)', 'f32(-0.0)']
for i, c in enumerate(tiny_constants):
    add(f'ftz_addtiny_{i}', f'asfloat(x) + {c}', 'asfloat(x)',
        modes=('ftz',), note='add tiny constant, exploratory')

# subtraction identity x - 0
for i, c in enumerate(['f32(0)', 'f32(-0.0)']):
    add(f'ftz_sub0_{i}', f'asfloat(x) - {c}', 'asfloat(x)',
        modes=('ftz',), note='x-0 identity variants, exploratory')

# ---------------------------------------------------------------------------
# NaN bits / quieting
# ---------------------------------------------------------------------------
qnan_masks_32 = [
    ('0x7fc00000', '0x7fc00000'),
    ('0xffc00000', '0x7fc00000'),
    ('0x7f800001', '0x7f800001'),
    ('0xff800001', '0x7f800001'),
    ('0x7fc12345', '0x7fc00000'),
    ('0xffc54321', '0x7fc00000'),
]
for i, (mk, canon) in enumerate(qnan_masks_32):
    add(f'nan_payload32_{i}',
        f'asfloat(x | {mk})', f'asfloat(u32({canon}))',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='NaN payload from x vs fixed; equal w/o nanbits, differ with')

for i, (mk, canon) in enumerate([('0x7e00','0x7e00'),('0xfe00','0x7e00'),
                                  ('0x7e01','0x7e00'),('0xfe01','0x7e00')]):
    add(f'nan_payload16_{i}',
        f'asfloat(x | {mk})', f'asfloat(u16({canon}))', params='x: u16',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='f16 NaN payload from x vs fixed')

add('nan_neg32', '-(-asfloat(x))', 'asfloat(x)',
    exp_bits='equal', modes=('nanbits',), note='double negation preserves NaN bits')
add('nan_abs32', 'abs(asfloat(x))', 'asfloat(x & 0x7fffffff)',
    exp_bits='equal', modes=('nanbits',), note='abs via bit clear preserves payload')
add('nan_abs16', 'abs(asfloat(x))', 'asfloat(x & 0x7fff)', params='x: u16',
    exp_bits='equal', modes=('nanbits',), note='f16 abs via bit clear')

# sNaN quieting: arithmetic quiets; f32 held in double already reads quiet
add('nan_snan_quiet',
    'asfloat(x | 0x7f800001)',
    'asfloat(x | 0x7f800001) + f32(0)',
    exp_nobits='equal', modes=('nanbits',),
    note='sNaN quieting: nanbits falls back to sampled (counterexample did not reproduce)')

# NaN payload sweeps
for lo in [0x000001, 0x0000ff, 0x00aa00, 0x123456, 0x200000, 0x3fffff]:
    mk = 0x7fc00000 | lo
    add(f'nan_sweep_{lo:x}',
        f'asfloat(x | 0x{mk:08x})', f'asfloat(u32(0x7fc00000))',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='sweep NaN payload bits')
for lo in [0x000001, 0x00aa00, 0x3fffff]:
    mk = 0xffc00000 | lo
    add(f'nan_negsweep_{lo:x}',
        f'asfloat(x | 0x{mk:08x})', f'asfloat(u32(0x7fc00000))',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='sweep negative NaN payload bits')

# ---------------------------------------------------------------------------
# Signed zero (observed via asuint)
# ---------------------------------------------------------------------------
add('zero_add0_bits', 'asuint(asfloat(x) + f32(0))', 'x',
    exp_noftz='differ', exp_ftz='differ', modes=('ftz',),
    note='-0 + +0 = +0 -> bit pattern changes at -0')
add('zero_negzero_bits', 'asuint(asfloat(x) + f32(-0.0))', 'x',
    exp_noftz='differ', exp_ftz='differ', modes=('ftz',),
    note='-0 + -0 = -0 but +0 + -0 = +0')
add('zero_bits_identity', 'asuint(asfloat(x))', 'x',
    exp_noftz='equal', exp_ftz='equal', modes=('ftz',),
    note='round trip bits identity')
for i, expr in enumerate(['-asfloat(x)',
                          'copysign(asfloat(x), f32(-1))',
                          'asfloat(x) + f32(0.0)',
                          'asfloat(x) - f32(0.0)']):
    add(f'zero_sweep_{i}', f'asuint(({expr}))', 'x',
        modes=('ftz',), note='asuint sign variations, exploratory')

# ---------------------------------------------------------------------------
# min / max NaN propagation
# ---------------------------------------------------------------------------
add('minmax_min32', 'min(x, y)', 'min(y, x)', params='x: f32, y: f32',
    exp_noftz='equal', exp_ftz='equal', exp_nobits='equal', exp_bits='equal',
    modes=('ftz','nanbits'), note='min commutative for ucas')
add('minmax_max32', 'max(x, y)', 'max(y, x)', params='x: f32, y: f32',
    exp_noftz='equal', exp_ftz='equal', exp_nobits='equal', exp_bits='equal',
    modes=('ftz','nanbits'), note='max commutative for ucas')
add('minmax_min_nan',
    'min(asfloat(a), asfloat(u32(0x7fc00000)))',
    'min(asfloat(u32(0x7fc00000)), asfloat(a))', params='a: u32',
    exp_nobits='equal', exp_bits='equal', modes=('nanbits',),
    note='min with a qNaN constant, order symmetric')
add('minmax_max_nan',
    'max(asfloat(a), asfloat(u32(0x7fc00000)))',
    'max(asfloat(u32(0x7fc00000)), asfloat(a))', params='a: u32',
    exp_nobits='equal', exp_bits='equal', modes=('nanbits',),
    note='max with a qNaN constant, order symmetric')
for i, op in enumerate(['min', 'max']):
    add(f'minmax_sweep_{i}',
        f'{op}(asfloat(a), asfloat(b))',
        f'{op}(asfloat(b), asfloat(a))', params='a: u32, b: u32',
        exp_noftz='equal', exp_ftz='equal', exp_nobits='equal', exp_bits='equal',
        modes=('ftz','nanbits'), note='min/max via u32 bitcasts, commutative')

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
add('ctrl_mul1', 'asfloat(x) * f32(1)', 'asfloat(x)',
    exp_noftz='equal', exp_ftz='equal', modes=('ftz',),
    note='x*1 folded to x: no op to flush, equal under both')
add('ctrl_dblneg', '-(-asfloat(x))', 'asfloat(x)',
    exp_noftz='equal', exp_ftz='equal', modes=('ftz',),
    note='negation is a sign flip, never flushes')
add('ctrl_add_not_id', 'asfloat(x) + f32(1)', 'asfloat(x)',
    exp_noftz='differ', exp_ftz='differ', modes=('ftz',),
    note='x+1 != x everywhere: differ under both')

# ---------------------------------------------------------------------------
# Large systematic sweeps to reach 200+ distinct pairs.
# ---------------------------------------------------------------------------
# Set A: NaN payload from x (bit leaked into payload) vs fixed qNaN.
# The exponent is forced all-ones so the cast is always a NaN; the low 22
# payload bits (and possibly the sign) come from x, so nanbits must differ,
# while without nanbits every NaN is equal.
_a_payload_masks = [
    0x7f800001, 0x7f800002, 0x7f800004, 0x7f800008, 0x7f800010,
    0x7f800020, 0x7f800040, 0x7f800080, 0x7f800100, 0x7f800200,
    0x7f800400, 0x7f800800, 0x7f801000, 0x7f802000, 0x7f804000,
    0x7f808000, 0x7f810000, 0x7f820000, 0x7f840000, 0x7f880000,
    0x7fa00000, 0x7fb00000, 0x7fc00001, 0x7fc00002, 0x7fc00004,
    0x7fc00008, 0x7fc00010, 0x7fc00020, 0x7fc00040, 0x7fc00080,
    0x7fc00100, 0x7fc00200, 0x7fc00400, 0x7fc00800, 0x7fc01000,
    0x7fc02000, 0x7fc04000, 0x7fc08000, 0x7fc10000, 0x7fc20000,
    0xff800001, 0xff800002, 0xffc00001, 0xffc00002, 0xffc00004,
    0xffc00008, 0xffc00010, 0xffc00020, 0xffc00040, 0xffc00080,
]
for i, mk in enumerate(_a_payload_masks):
    add(f'sw_nanleak_{i:03d}',
        f'asfloat(x | 0x{mk:08x})', f'asfloat(u32(0x7fc00000))',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='payload/sign bit leaks from x -> nanbits differ')

# Set B: payload-preserving transforms -> nanbits equal.  Select forms and
# sign/bit-cast forms that only move the NaN payload around.
_b_transforms = [
    ('-(-asfloat(x))', 'asfloat(x)'),
    ('abs(asfloat(x))', 'asfloat(x & 0x7fffffff)'),
    ('copysign(asfloat(x), asfloat(x))', 'asfloat(x)'),
    ('-copysign(asfloat(x), asfloat(x))', '-asfloat(x)'),
    ('asfloat(x) == asfloat(x) ? asfloat(x) : asfloat(u32(0))',
     'asfloat(x) == asfloat(x) ? asfloat(x) : asfloat(x)'),
    ('x < 0x7f800000 ? asfloat(x) : asfloat(x)', 'asfloat(x)'),
    ('asfloat(x & 0xffffffff)', 'asfloat(x)'),
    ('asfloat(x | 0x00000000)', 'asfloat(x)'),
]
for i, (ff, gg) in enumerate(_b_transforms):
    add(f'sw_nanpres_{i:03d}', ff, gg,
        exp_bits='equal', modes=('nanbits',),
        note='transform only moves/preserves NaN payload -> equal')

# Set C: FTZ identity under noftz (x + signed zero), differ under ftz.
_c_zero_forms = [
    ('asfloat(x) + f32(0)', 'asfloat(x)'),
    ('asfloat(x) + f32(-0.0)', 'asfloat(x)'),
    ('f32(0) + asfloat(x)', 'asfloat(x)'),
    ('fma(asfloat(x), f32(1), f32(0))', 'asfloat(x)'),
    ('asfloat(x) - f32(0)', 'asfloat(x)'),
    ('copysign(asfloat(x) + f32(0), asfloat(x))', 'asfloat(x)'),
]
for i, (ff, gg) in enumerate(_c_zero_forms):
    add(f'sw_ftzid_{i:03d}', ff, gg,
        exp_noftz='equal', exp_ftz='differ', modes=('ftz',),
        note='identity under noftz, subnormal flushed under ftz')

# Set D: signed-zero bit patterns (asuint) -> differ at -0.
_d_zero_forms = [
    ('asuint(asfloat(x) + f32(0))', 'x'),
    ('asuint(asfloat(x) + f32(-0.0))', 'x'),
    ('asuint(-(-asfloat(x)))', 'x'),
    ('asuint(copysign(asfloat(x), f32(-1)))', 'x | 0x80000000'),
    ('asuint(abs(asfloat(x)))', 'x & 0x7fffffff'),
]
for i, (ff, gg) in enumerate(_d_zero_forms):
    add(f'sw_zerobits_{i:03d}', ff, gg,
        modes=('ftz',), note='signed-zero bit pattern variation (exploratory)')

# Set E: min/max operand orders and NaN constants -> equal.
add('sw_minmax_min0', 'min(asfloat(a), f32(0))', 'min(f32(0), asfloat(a))',
    params='a: u32', exp_noftz='equal', exp_ftz='equal',
    exp_nobits='equal', exp_bits='equal', modes=('ftz','nanbits'),
    note='min with zero constant commutative')
add('sw_minmax_max0', 'max(asfloat(a), f32(0))', 'max(f32(0), asfloat(a))',
    params='a: u32', exp_noftz='equal', exp_ftz='equal',
    exp_nobits='equal', exp_bits='equal', modes=('ftz','nanbits'),
    note='max with zero constant commutative')
for i, (op, ho) in enumerate([('min','min'), ('max','max'),
                              ('min','max'), ('max','min')]):
    add(f'sw_minmix_{i}', f'{op}(asfloat(a), asfloat(b))',
        f'{ho}(asfloat(b), asfloat(a))', params='a: u32, b: u32',
        modes=('ftz','nanbits'), note='min/max mix (exploratory)')

# Set F: NaN payload width f16 sweep -> differ with nanbits.
for i, lo in enumerate([1, 2, 4, 8, 0x10, 0x20, 0x40, 0x80,
                         0x100, 0x1ff, 0x55, 0xaa]):
    mk = 0x7e00 | lo
    add(f'sw_nan16_{i:03d}', f'asfloat(x | 0x{mk:04x})',
        f'asfloat(u16(0x7e00))', params='x: u16',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='f16 payload bit leaks from x')

# Set G: f64 NaN payload sweep (u64 input) -> differ with nanbits.
for i, lo in enumerate([1, 2, 4, 8, 0x10, 0x100, 0x10000,
                         0x10000000, 0x123456789abcd, 0xfffffffffffff]):
    mk = 0x7ff8000000000000 | lo
    add(f'sw_nan64_{i:03d}', f'asfloat(x | 0x{mk:016x})',
        f'asfloat(u64(0x7ff8000000000000))', params='x: u64',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='f64 payload bit leaks from x')

# Set H: more FTZ identities/variations (x + zero under a wrapper).
_h_ftz = [
    ('asfloat(x) + f32(0) * f32(1)', 'asfloat(x)'),
    ('fma(asfloat(x), f32(1), f32(-0.0))', 'asfloat(x)'),
    ('asfloat(x) - f32(0) + f32(0)', 'asfloat(x)'),
    ('f32(0) + asfloat(x) + f32(0)', 'asfloat(x)'),
    ('(asfloat(x) + f32(0)) + f32(0)', 'asfloat(x)'),
    ('asfloat(x) + (f32(0) + f32(0))', 'asfloat(x)'),
]
for i, (ff, gg) in enumerate(_h_ftz):
    add(f'sw_ftzmore_{i:03d}', ff, gg,
        modes=('ftz',), note='extra FTZ arithmetic forms (exploratory)')

# Set I: more signed-zero / bit-cast forms.
_i_zero = [
    ('asuint(-asfloat(x))', 'x ^ 0x80000000'),
    ('asuint(copysign(f32(1), asfloat(x)))', '0x3f800000 | (x & 0x80000000)'),
    ('asuint(asfloat(x & 0x80000000))', 'x & 0x80000000'),
    ('asuint(asfloat(x & 0x7fffffff))', 'x & 0x7fffffff'),
    ('asuint(abs(-asfloat(x)))', 'x & 0x7fffffff'),
    ('asuint(asfloat(x) * f32(1))', 'x'),
]
for i, (ff, gg) in enumerate(_i_zero):
    add(f'sw_zeromore_{i:03d}', ff, gg,
        modes=('ftz',), note='extra signed-zero bit forms (exploratory)')

# Set J: min/max with f16 and f64 params, commutative -> equal.
add('sw_minmax_mn16', 'min(x, y)', 'min(y, x)', params='x: f16, y: f16',
    exp_noftz='equal', exp_ftz='equal', exp_nobits='equal', exp_bits='equal',
    modes=('ftz','nanbits'), note='f16 min commutative')
add('sw_minmax_mx16', 'max(x, y)', 'max(y, x)', params='x: f16, y: f16',
    exp_noftz='equal', exp_ftz='equal', exp_nobits='equal', exp_bits='equal',
    modes=('ftz','nanbits'), note='f16 max commutative')
add('sw_minmax_mn64', 'min(x, y)', 'min(y, x)', params='x: f64, y: f64',
    exp_noftz='equal', exp_ftz='equal', exp_nobits='equal', exp_bits='equal',
    modes=('ftz','nanbits'), note='f64 min commutative')
add('sw_minmax_mx64', 'max(x, y)', 'max(y, x)', params='x: f64, y: f64',
    exp_noftz='equal', exp_ftz='equal', exp_nobits='equal', exp_bits='equal',
    modes=('ftz','nanbits'), note='f64 max commutative')

# Set K: f64 payload-preserving transforms -> nanbits equal.
add('sw_nan64_neg', '-(-asfloat(x))', 'asfloat(x)', params='x: u64',
    exp_bits='equal', modes=('nanbits',), note='f64 double negation preserves payload')
add('sw_nan64_abs', 'abs(asfloat(x))', 'asfloat(x & 0x7fffffffffffffff)',
    params='x: u64', exp_bits='equal', modes=('nanbits',),
    note='f64 abs via bit clear preserves payload')

# Set L: more f32 payload-bit sweeps (combined quiet/sign bits).
for i, mk in enumerate([0x7fc00003, 0x7fc00005, 0x7fc00009, 0x7fc00011,
                        0x7fc00021, 0x7fc00041, 0x7fc00081, 0x7fc00101,
                        0xffc00003, 0xffc00005, 0xffc00009, 0x7f800003,
                        0x7f800005, 0xff800003, 0x7fc12345, 0xffc54321,
                        0x7fc55555, 0x7fcaaaaa, 0xffc12345, 0xffcfffff]):
    add(f'sw_nanmore_{i:03d}', f'asfloat(x | 0x{mk:08x})',
        f'asfloat(u32(0x7fc00000))',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='extra f32 payload pattern')

# Set M: subnormal-vs-zero tests with several thresholds; all must collapse
# under ftz (equal) and differ under noftz.
_m_thresholds = ['f32(2^(-126))', 'f32(2^(-125))', 'f32(3 * 2^(-126))',
                 'f32(2^(-124))', 'f32(f64(2^(-126)))']
for i, th in enumerate(_m_thresholds):
    add(f'sw_ftzthresh_{i:03d}',
        f'abs(asfloat(x)) < {th} ? f32(1) : f32(0)',
        'asfloat(x) == f32(0) ? f32(1) : f32(0)',
        modes=('ftz',), note='subnormal threshold test (exploratory)')

# Set N: NaN select forms (payload only moves) -> nanbits equal.
for i, mk in enumerate(['0x7fc00000', '0xffc00000', '0x7f800001',
                         '0x7fc12345', '0xffc54321']):
    add(f'sw_nanse_{i:03d}',
        f'asfloat(x) < asfloat(y) ? asfloat(x | {mk}) : asfloat(y | {mk})',
        f'asfloat((x < y ? x : y) | {mk})', params='x: u32, y: u32',
        exp_bits='equal', modes=('nanbits',),
        note='select only moves a NaN payload -> equal')

# Set O: a few more f64 payload patterns and copy/bitcast controls.
for i, mk in enumerate([0x7ff8000000000001, 0x7ff8000000000002,
                        0xfff8000000000001, 0x7ff0000000000001,
                        0x7ff8123456789abc]):
    add(f'sw_nan64more_{i}', f'asfloat(x | 0x{mk:016x})',
        f'asfloat(u64(0x7ff8000000000000))', params='x: u64',
        exp_nobits='equal', exp_bits='differ', modes=('nanbits',),
        note='extra f64 payload pattern')
add('sw_ctrl_bitcast', 'asuint(asfloat(x))', 'x',
    exp_noftz='equal', exp_ftz='equal', modes=('ftz',),
    note='asuint/asfloat round trip control')


def emit_cli_all(path):
    L = ['# generated by gen.py - all pairs, all modes (analysis file)']
    for p in PAIRS:
        fn, gn = p['name'] + 'f', p['name'] + 'g'
        L.append(f'{fn}({p["params"]}) = {p["f"]}')
        L.append(f'{gn}({p["params"]}) = {p["g"]}')
        if 'ftz' in p['modes']:
            L.append(f'equiv {fn} {gn} noftz')
            L.append(f'equiv {fn} {gn} ftz')
        if 'nanbits' in p['modes']:
            L.append(f'equiv {fn} {gn}')
            L.append(f'equiv {fn} {gn} nanbits')
    with open(path, 'w') as f:
        f.write('\n'.join(L) + '\n')


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    scratch = os.path.join(here, '_scratch')
    os.makedirs(scratch, exist_ok=True)
    with open(os.path.join(scratch, 'pairs.json'), 'w') as f:
        json.dump(PAIRS, f, indent=1)
    emit_cli_all(os.path.join(scratch, 'analyze_all.ucas'))
    print(f'pairs: {len(PAIRS)}')

if __name__ == '__main__':
    main()
