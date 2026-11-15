/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * f16x.c: the bits of a narrow float read in a wider format.  For the
 * bits h of a finite f16 (exponent field E in 0..30, mantissa M), the
 * word
 *
 *	b = ((h & 0x7fff) << 13) | ((h & 0x8000) << 16)
 *
 * has sign h's sign, exponent field E and mantissa M << 13, so as an f32
 * it is (-1)^s (1 + M 2^-10) 2^(E - 127) where E >= 1 and (-1)^s M 2^13
 * 2^-149 = (-1)^s M 2^-136 where E = 0, against the f16's (1 + M 2^-10)
 * 2^(E - 15) and M 2^-24: in both cases exactly 2^-112 times it, zeros
 * and their signs included.  So
 *
 *	f32(asfloat(h)) == asfloat(b) * 2^112
 *
 * for every h whose exponent field is not 31 (no infinity, no NaN), and a
 * later multiply by a constant c takes the scale: f32(asfloat(h)) * c ==
 * asfloat(b) * (c 2^112), the same exact product, so the same rounding,
 * while c 2^112 is an f32 (|c| < 2^16).  An f16 subnormal (E = 0, M not
 * 0) makes an f32 subnormal: exact in IEEE arithmetic, which ucas's
 * evaluator does; a device that flushes f32 denormals reads it as 0, so
 * that case is a condition said with the rewrite.  Where the sign is
 * proved 0 (h below 0x8000) b is h << 13 alone.
 *
 * The rewrite seeds find (through ifx_cands): an unpack of f16 by integer
 * operations where the model prices `conv` above them; nothing here
 * decides.  The range of h is the interval irw gives, and every value in
 * it is checked to have an exponent field below 31 (at most 2^16 values:
 * every point).  Packing an f32 into f16 bits the same way rounds (or
 * truncates) unless the value is on f16's grid: not offered.
 */
#include "calc.h"
#include "irw.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

static const ty_t U32 = TY(K_UINT, 32);

/* h, the 16-bit word whose f16 n converts (f32(asfloat(h))); 0 if not */
static nid
f16_bits_of(nid n)
{
	nid a;

	if (N.op[n] != O_CAST || N.ty[n] != TY_F32)
		return 0;
	a = N.a[n];
	if (N.op[a] != O_ASFLOAT || N.ty[a] != TY_F16)
		return 0;
	return N.a[a];
}

/* what the h in [lo, hi] are: finite (no exponent 31), and whether some
 * is negative or subnormal */
static int
scan_bits(int64_t lo, int64_t hi, int *neg, int *sub)
{
	int64_t v;

	*neg = *sub = 0;
	if (hi - lo > 0xffff || lo < -32768 || hi > 0xffff)
		return 0;
	for (v = lo; v <= hi; v++) {
		int64_t u = v & 0xffff;	/* an i16's bits as a u16's */
		if ((u & 0x7c00) == 0x7c00)
			return 0;
		if (u & 0x8000)
			*neg = 1;
		if (!(u & 0x7c00) && (u & 0x3ff))
			*sub = 1;
	}
	return 1;
}

static nid
f32k(double v)
{
	return mk_cast(TY_F32, mk_const_r(v));
}

/* the f32 bits b of h, plain (positive h) or with the sign moved */
static nid
widen_bits(nid h, int neg, int how)
{
	nid u = mk_cast(U32, h);

	if (!neg)
		return mk_bin(O_SHL, u, mk_const_i(U32, 13));
	if (how == 0)
		return mk_bin(O_OR, mk_bin(O_SHL, mk_bin(O_AND, u, mk_const_i(U32,
		    0x7fff)), mk_const_i(U32, 13)), mk_bin(O_SHL, mk_bin(O_AND, u,
		    mk_const_i(U32, 0x8000)), mk_const_i(U32, 16)));
	/* the sign copied by an arithmetic shift, the copies cleared */
	return mk_bin(O_AND, mk_cast(U32, mk_bin(O_SHR, mk_cast(TY(K_SINT, 32),
	    mk_bin(O_SHL, u, mk_const_i(U32, 16))), mk_const_i(TY(K_SINT, 32),
	    3))), mk_const_i(U32, 0x8fffffffLL));
}

static void
add_one(struct ivc *c, nid root, nid n, nid h, double scale, int64_t lo,
    int64_t hi, int neg, int sub, int how, struct irw **out, int *cnt,
    int *cap)
{
	char what[200], cond[400];
	struct sbuf pf = {0};
	nid b = widen_bits(h, neg, how), to;
	const char *hs = shared_str(h, 60);

	to = mk_bin(O_MUL, mk_un(O_ASFLOAT, b), f32k(scale));
	if (scale == 1)
		to = mk_un(O_ASFLOAT, b);
	snprintf(what, sizeof what, "the f16 %s unpacked by its bits%s%s",
	    hs, scale == ldexp(1.0, 112) ? "" : ", the scale 2^-112 taken by ",
	    scale == ldexp(1.0, 112) ? "" : "the multiply");
	snprintf(cond, sizeof cond, "%s in [%lld, %lld]: no exponent field 31 "
	    "(no infinity or NaN; every value checked)%s%s", hs, (long long)lo,
	    (long long)hi, neg ? "" : ", the sign bit 0",
	    sub ? "; it reaches f16 subnormals, which give f32 subnormals: "
	    "exact in IEEE arithmetic, 0 on a device that flushes f32 denormals"
	    : "");
	sb_printf(&pf, "h = %s is a finite f16's bits: sign s, exponent field "
	    "E in 0..30, mantissa M; its value is (-1)^s (1 + M 2^-10) 2^(E-15) "
	    "(E >= 1) or (-1)^s M 2^-24 (E = 0)\n", hs);
	if (!neg)
		sb_puts(&pf, "s = 0, so b = h << 13 puts E at bits 23..27 (the f32 "
		    "exponent field, value E) and M at bits 13..22\n");
	else if (how == 0)
		sb_puts(&pf, "b = ((h & 0x7fff) << 13) | ((h & 0x8000) << 16) "
		    "puts s at bit 31, E in the f32 exponent field and M at bits "
		    "13..22\n");
	else
		sb_puts(&pf, "(h << 16) as i32 shifted right by 3 copies s into "
		    "bits 28..31 and puts E and M at bits 23..27 and 13..22; & "
		    "0x8fffffff clears the copies: s at bit 31, E, M << 13\n");
	sb_puts(&pf, "as an f32 that is (-1)^s (1 + M 2^-10) 2^(E-127) or "
	    "(-1)^s M 2^13 2^-149 = (-1)^s M 2^-136: 2^-112 times the f16, "
	    "exactly, zeros and their signs included\n");
	if (scale == ldexp(1.0, 112))
		sb_puts(&pf, "times 2^112, an f32: the product is the f16's value, "
		    "exact (f32 holds every f16)");
	else
		sb_printf(&pf, "%s's other factor %.9g times 2^112 is %.9g, an f32 "
		    "(a power of two's scaling, below 2^128): both products have "
		    "the same exact value, so they round alike", shared_str(n, 60),
		    scale / ldexp(1.0, 112), scale);
	irw_add(out, cnt, cap, root, n, to, what, cond, sb_str(&pf), 1);
	free(pf.p);
	(void)c;
}

void
f16x_cands(struct ivc *c, nid root, nid n, struct irw **out, int *cnt,
    int *cap)
{
	nid h = 0, cv = 0, k = 0;
	double scale = ldexp(1.0, 112), kv;
	int64_t lo, hi;
	int neg, sub, j;
	char why[200];

	if (N.op[n] == O_CAST)
		h = f16_bits_of(n);
	else if (N.op[n] == O_MUL && N.ty[n] == TY_F32) {
		/* f32(asfloat(h)) * c: the scale goes into c */
		for (j = 0; j < 2 && !h; j++) {
			cv = j ? N.b[n] : N.a[n];
			k = j ? N.a[n] : N.b[n];
			if (is_const(k) && (h = f16_bits_of(cv)) != 0) {
				kv = N.kr[k];
				if (!isfinite(kv) || fabs(kv) >= 65536 || kv == 0)
					h = 0;
				else
					scale = kv * ldexp(1.0, 112);
			}
		}
	}
	if (!h || !TY_ISINT(N.ty[h]) || !TY_SIZED(N.ty[h]) || TYW(N.ty[h]) != 16)
		return;
	if (!irw_range(c, h, INT64_MIN, &lo, &hi, why, sizeof why)) {
		int64_t m = TYK(N.ty[h]) == K_SINT ? -32768 : 0;
		lo = m;
		hi = m + 65535;
	}
	if (!scan_bits(lo, hi, &neg, &sub))
		return;
	add_one(c, root, n, h, scale, lo, hi, neg, sub, 0, out, cnt, cap);
	if (neg)
		add_one(c, root, n, h, scale, lo, hi, neg, sub, 1, out, cnt, cap);
}
