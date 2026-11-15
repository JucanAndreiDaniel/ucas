/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * tcdot.c: a tensor core's block FMA as an operation of the language,
 * tc_dot(A, B, c): A and B tables of n f16 (n from 1 to 16; 8 is the
 * f16 block of the parts below), c an f32, the result an f32:
 *
 *   1. each product a_i b_i exact: its significand the product of the
 *      two (subnormals without the hidden bit, exponent -14), its
 *      exponent the sum, not renormalised (significand in [0, 4));
 *   2. E = the largest exponent among the nonzero products and c (a
 *      zero takes no part), at least -132;
 *   3. every term (the products and c) as a fixed-point number of 24
 *      fractional bits relative to 2^E (23 and one extra alignment bit),
 *      its magnitude truncated (bits shifted out are dropped: toward
 *      zero, term by term), its sign applied after;
 *   4. the exact integer sum of those (it fits 30 bits: 2 integer bits, 24
 *      fractional, and the carries of up to 17 terms);
 *   5. normalised once and truncated to an f32 (round toward zero),
 *      subnormal results kept (truncated), an exponent past 127 infinite.
 *
 * That is the model Khattak and Mikaitis (arXiv 2512.07004) give for
 * Ampere (A100, A2, A30: their Table 3 and section 4.1.2; the parameters
 * of models/A100TC.m in github.com/north-numerical-computing/
 * MATLAB-tensor-core: fma 8, neab 1, rz, global alignment, products not
 * renormalised, -132 as the exponent's floor), which Valpey et al.
 * (arXiv 2502.15999, an sm_86 A6000) describe the same way: eight-term
 * blocks, one normalisation, truncation to f32.  Not verified here (no
 * GPU): the fourth carry bit (2512.07004 confirmed three), the sign of a
 * zero sum (taken +0), an f16 result's rounding (round to nearest even:
 * not written), and the hardware at all.  m16n8k16 is two blocks
 * chained: tc_dot(A[8..15], B[8..15], tc_dot(A[0..7], B[0..7], c)).
 *
 * The operation is written as its definition over integer operations on
 * the bits (asuint of each input, fields, an integer multiply, max,
 * variable shifts, clz, selects), so the evaluator, the intervals and
 * the SAT bit-blast (nodesat.c) work on it as on any expression: `equiv`
 * and `show` compare an emulation against it.  Infinities and NaNs among
 * the inputs are outside its domain.
 *
 * Its error (derived in tcdot_bound): with T = the n products and c, E as
 * above, each term's truncation loses less than 2^(E-24) (one unit of the
 * window), so the window's sum S is within n_t 2^(E-24) of sum T, n_t the
 * terms not on the window's grid (at most n + 1); the final truncation
 * loses less than 2^-23 |S|.  Since max|T| >= 2^E where the largest term
 * has a normal significand (products of normal f16, a normal c):
 *
 *   |tc_dot - sum T| < (n + 1) 2^-24 max|T| + 2^-23 |sum T| (1 + ...),
 *
 * relative to the largest term, not to sum |T|: a sum that cancels keeps
 * the absolute error of its largest term, and a small term next to a
 * large one may lose every bit.
 */
#include "calc.h"
#include "report.h"
#include "tcdot.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

static const ty_t U32 = TY(K_UINT, 32), I32 = TY(K_SINT, 32);

static nid
k32(int64_t v)
{
	return mk_const_i(U32, v);
}

static nid
sel(nid c, nid a, nid b)
{
	return mk_sel(c, a, b);
}

/* a >> min(s, 31) of a u32 (a below 2^31: past 31 it is 0) */
static nid
shr_sat(nid a, nid s)
{
	return mk_bin(O_SHR, a, mk_bin(O_MIN, s, k32(31)));
}

/* the n entries of table t, or 0 */
static int
entries(nid t, nid *e, int max)
{
	uint32_t j;

	if (N.op[t] != O_TABLE || N.b[t] < 1 || N.b[t] > (uint32_t)max)
		return 0;
	for (j = 0; j < N.b[t]; j++)
		e[j] = N.lst[N.a[t] + j];
	return (int)N.b[t];
}

/*
 * The block FMA over the n pairs (a[i], b[i]) (f16) and c (f32), with
 * `frac` fractional bits in the window (24: 23 and one extra) and the
 * exponent's floor `floor` (-132): an f32.
 */
nid
tc_dot_expr(const nid *a, const nid *b, int n, nid c, int frac, int floor_e)
{
	nid mag[TC_MAXN + 1], ex[TC_MAXN + 1], sg[TC_MAXN + 1], nz[TC_MAXN + 1];
	nid E, S, A, msb, neg, Er, mant, nrm, sub, bits, kk;
	int i, off = 200;	/* exponents + off: positive */

	for (i = 0; i < n; i++) {
		nid ha = mk_cast(U32, mk_un(O_ASUINT, mk_cast(TY_F16, a[i])));
		nid hb = mk_cast(U32, mk_un(O_ASUINT, mk_cast(TY_F16, b[i])));
		nid Ea = mk_bin(O_AND, mk_bin(O_SHR, ha, k32(10)), k32(31));
		nid Eb = mk_bin(O_AND, mk_bin(O_SHR, hb, k32(10)), k32(31));
		nid sa = sel(mk_bin(O_EQ, Ea, k32(0)), mk_bin(O_AND, ha, k32(1023)),
		    mk_bin(O_OR, mk_bin(O_AND, ha, k32(1023)), k32(1024)));
		nid sb = sel(mk_bin(O_EQ, Eb, k32(0)), mk_bin(O_AND, hb, k32(1023)),
		    mk_bin(O_OR, mk_bin(O_AND, hb, k32(1023)), k32(1024)));
		/* sig in [0, 2^22): 20 fractional bits; exponent (Ea - 15) +
		 * (Eb - 15), subnormals at -14 */
		mag[i] = mk_bin(O_MUL, sa, sb);
		ex[i] = mk_bin(O_ADD, mk_bin(O_ADD, mk_bin(O_MAX, Ea, k32(1)),
		    mk_bin(O_MAX, Eb, k32(1))), k32(off - 30));
		sg[i] = mk_bin(O_AND, mk_bin(O_XOR, ha, hb), k32(0x8000));
		nz[i] = mk_bin(O_NE, mag[i], k32(0));
	}
	{
		nid hc = mk_un(O_ASUINT, mk_cast(TY_F32, c));
		nid Ec = mk_bin(O_AND, mk_bin(O_SHR, hc, k32(23)), k32(255));
		nid Mc = mk_bin(O_AND, hc, k32(0x7fffff));
		hc = mk_cast(U32, hc);
		mag[n] = sel(mk_bin(O_EQ, Ec, k32(0)), Mc, mk_bin(O_OR, Mc,
		    k32(0x800000)));
		ex[n] = mk_bin(O_ADD, mk_bin(O_MAX, Ec, k32(1)), k32(off - 127));
		sg[n] = mk_bin(O_AND, hc, k32(0x80000000LL));
		nz[n] = mk_bin(O_NE, mag[n], k32(0));
	}
	E = k32(off + floor_e);
	for (i = 0; i <= n; i++)
		E = mk_bin(O_MAX, E, sel(nz[i], ex[i], k32(0)));
	/* the window: a product's significand has 20 fractional bits, c's 23 */
	S = mk_const_i(I32, 0);
	for (i = 0; i <= n; i++) {
		int up = i < n ? frac - 20 : frac - 23;
		nid t = shr_sat(mk_bin(O_SHL, mag[i], k32(up)), mk_bin(O_SUB, E,
		    ex[i]));
		t = mk_cast(I32, t);
		S = mk_bin(O_ADD, S, sel(mk_bin(O_NE, sg[i], k32(0)), mk_un(O_NEG,
		    t), t));
	}
	neg = mk_bin(O_LT, S, mk_const_i(I32, 0));
	A = mk_cast(U32, sel(neg, mk_un(O_NEG, S), S));
	msb = mk_bin(O_SUB, k32(31), mk_cast(U32, mk_un(O_CLZ, A)));
	/* the result's biased exponent: E - off - frac + msb + 127 */
	Er = mk_bin(O_SUB, mk_cast(I32, mk_bin(O_ADD, E, msb)),
	    mk_const_i(I32, off + frac - 127));
	mant = sel(mk_bin(O_GE, msb, k32(23)), mk_bin(O_SHR, A, mk_bin(O_SUB,
	    msb, k32(23))), mk_bin(O_SHL, A, mk_bin(O_SUB, k32(23), msb)));
	nrm = mk_bin(O_OR, mk_bin(O_SHL, mk_cast(U32, Er), k32(23)),
	    mk_bin(O_AND, mant, k32(0x7fffff)));
	/* a subnormal result: A 2^(E - off - frac) in units of 2^-149 */
	kk = mk_cast(I32, E);
	sub = sel(mk_bin(O_GE, kk, mk_const_i(I32, off + frac - 149)),
	    mk_bin(O_SHL, A, mk_cast(U32, mk_bin(O_SUB, kk, mk_const_i(I32,
	    off + frac - 149)))), mk_bin(O_SHR, A, mk_cast(U32,
	    mk_bin(O_SUB, mk_const_i(I32, off + frac - 149), kk))));
	bits = sel(mk_bin(O_GE, Er, mk_const_i(I32, 255)), k32(0x7f800000),
	    sel(mk_bin(O_GE, Er, mk_const_i(I32, 1)), nrm, sub));
	bits = sel(mk_bin(O_EQ, A, k32(0)), k32(0), mk_bin(O_OR, bits,
	    sel(neg, k32(0x80000000LL), k32(0))));
	return mk_un(O_ASFLOAT, bits);
}

/* tc_dot(A, B, c) as parsed: the tables' entries */
nid
tc_dot_call(nid ta, nid tb, nid c)
{
	nid a[TC_MAXN], b[TC_MAXN];
	int n = entries(ta, a, TC_MAXN), m = entries(tb, b, TC_MAXN), i;

	if (!n || n != m)
		fail("tc_dot(A, B, c): A and B are tables of the same length, 1 "
		    "to %d f16 ([a0, a1, ...]), c an f32", TC_MAXN);
	for (i = 0; i < n; i++)
		if (TY_ISINT(N.ty[a[i]]) && !is_const(a[i]))
			fail("tc_dot: %s is an integer; the entries are f16 values",
			    node_str(a[i]));
	return tc_dot_expr(a, b, n, mk_cast(TY_F32, c), 24, -132);
}

/* ---- the bound, and a sampled check of it ---- */

static uint64_t rs;

static uint32_t
rnd(void)
{
	rs ^= rs << 13;
	rs ^= rs >> 7;
	rs ^= rs << 17;
	return (uint32_t)(rs >> 11);
}

/* an f16 value with bits h (finite) */
static double
f16v(uint32_t h)
{
	int e = (int)(h >> 10 & 31), m = (int)(h & 1023);
	double v = e ? ldexp(1024 + m, e - 25) : ldexp(m, -24);

	return h & 0x8000 ? -v : v;
}

/* the block's value by the same steps, in doubles (an independent
 * transcription, for the check) */
static double
block(const double *pa, const double *pb, int n, double c, int frac,
    int *Eo)
{
	int i, E = -132, e;
	double s = 0, t, r;

	for (i = 0; i < n; i++)
		if (pa[i] * pb[i] != 0) {
			/* the product's exponent: the sum of the inputs' (at
			 * least -14 each), its significand not renormalised */
			int ea = pa[i] == 0 ? 0 : ilogb(pa[i]), eb = ilogb(pb[i]);
			if (ea < -14)
				ea = -14;
			if (eb < -14)
				eb = -14;
			if (ea + eb > E)
				E = ea + eb;
		}
	if (c != 0) {
		e = ilogb(c);
		if (e < -126)
			e = -126;
		if (e > E)
			E = e;
	}
	for (i = 0; i <= n; i++) {
		t = i < n ? pa[i] * pb[i] : c;	/* exact in double */
		t = ldexp(t, frac - E);
		t = t < 0 ? -floor(-t) : floor(t);
		s += t;				/* integers below 2^31: exact */
	}
	*Eo = E;
	if (s == 0)
		return 0;
	/* truncated to 24 significant bits, or to the subnormal grid */
	e = ilogb(s) + E - frac;
	r = ldexp(s, E - frac);
	if (e < -126)
		t = ldexp(trunc(ldexp(r, 149)), -149);
	else
		t = ldexp(trunc(ldexp(r, 23 - e)), e - 23);
	return t;
}

void
tcdot_report(int n, int samples, uint64_t seed, int cancel)
{
	double worst_rel_max = 0, worst_rel_sum = 0, worst_frac = 0;
	int s, i, bad = 0, mism = 0, E;

	rs = seed * 0x9E3779B97F4A7C15ULL + 1;
	if (!rs)
		rs = 1;
	printf("tc_dot: a block FMA of %d f16 products and an f32 c (Ampere's "
	    "f16 HMMA with f32 accumulate, as modelled by arXiv 2512.07004)\n",
	    n);
	printf("  semantics: products exact; aligned to E, the largest exponent "
	    "among the products and c (at least -132), in a window of 24 "
	    "fractional bits, each term truncated toward zero; one exact "
	    "integer sum; normalised once and truncated to f32\n");
	printf("  bound (derived): |tc_dot - sum T| < %d 2^(E-24) + 2^-23 |S| "
	    "<= %d 2^-24 max|T| + 2^-23 |sum T| + ..., T the %d products and "
	    "c, S the window's sum\n", n + 1, n + 1, n + 1);
	printf("    each term loses less than one unit of the window, 2^(E-24), "
	    "by its truncation (none for a term on the window's grid); the "
	    "final truncation to 24 bits loses less than 2^-23 |S|; and 2^E <= "
	    "max|T| where the largest term's significand is at least 1 (normal "
	    "inputs)\n");
	printf("    relative to the largest term, not to sum |T|: with "
	    "cancellation the result's own relative error is unbounded\n");
	rep_begin("tcdot");
	rep_int("terms", n + 1);
	rep_str("bound", "(n+1) 2^(E-24) + 2^-23 |S|");
	for (s = 0; s < samples; s++) {
		double pa[TC_MAXN], pb[TC_MAXN], c, exact = 0, got, b, mx = 0;
		nid an[TC_MAXN], bn[TC_MAXN], e;
		for (i = 0; i < n; i++) {
			uint32_t ha, hb;
			do {
				ha = rnd() & 0xffff;
			} while ((ha & 0x7c00) == 0x7c00 || (ha & 0x7c00) < 0x1400);
			do {
				hb = rnd() & 0xffff;
			} while ((hb & 0x7c00) == 0x7c00 || (hb & 0x7c00) < 0x1400);
			pa[i] = f16v(ha);
			pb[i] = f16v(hb);
		}
		c = ldexp((double)(rnd() & 0xffffff), (int)(rnd() % 40) - 40);
		if (cancel && n >= 2) {
			/* a sum that cancels: the last product undoes the first */
			pa[n - 1] = -pa[0];
			pb[n - 1] = pb[0];
		}
		for (i = 0; i < n; i++) {
			exact += pa[i] * pb[i];
			if (fabs(pa[i] * pb[i]) > mx)
				mx = fabs(pa[i] * pb[i]);
		}
		c = (double)(float)c;
		exact += c;
		if (fabs(c) > mx)
			mx = fabs(c);
		got = block(pa, pb, n, c, 24, &E);
		/* the operation as written, evaluated */
		for (i = 0; i < n; i++) {
			an[i] = mk_cast(TY_F16, mk_const_r(pa[i]));
			bn[i] = mk_cast(TY_F16, mk_const_r(pb[i]));
		}
		e = tc_dot_expr(an, bn, n, mk_cast(TY_F32, mk_const_r(c)), 24, -132);
		if (!is_const(e) || N.kr[e] != got)
			mism++;
		b = (n + 1) * ldexp(1.0, E - 24) + ldexp(fabs(got), -23) * 1.0000001;
		if (fabs(got - exact) >= b)
			bad++;
		if (fabs(got - exact) / b > worst_frac)
			worst_frac = fabs(got - exact) / b;
		if (fabs(got - exact) / mx > worst_rel_max)
			worst_rel_max = fabs(got - exact) / mx;
		if (exact != 0 && fabs(got - exact) / fabs(exact) > worst_rel_sum)
			worst_rel_sum = fabs(got - exact) / fabs(exact);
	}
	printf("  checked on %d random blocks (sampled, seed %llu%s): the "
	    "operation as written and an independent transcription agree on "
	    "%d; the bound holds on %d, the error at most %.3g of it\n",
	    samples, (unsigned long long)seed, cancel ? ", the first product "
	    "cancelled by the last" : "", samples - mism, samples - bad,
	    worst_frac);
	printf("  largest error relative to max|T|: %.3g (2^-24 = %.3g); "
	    "relative to |sum T|: %.3g\n", worst_rel_max, ldexp(1.0, -24),
	    worst_rel_sum);
	rep_check("sampled", samples, worst_frac, bad == 0 && mism == 0,
	    "the bound on random blocks, and the operation against an "
	    "independent transcription");
	rep_num("max_error_over_max_term", worst_rel_max);
	rep_num("max_error_over_sum", worst_rel_sum);
	rep_end();
}

int
tcdot_command(struct P *p)
{
	char w[48];
	uint32_t at = cmdp_pos(p);
	int64_t v;
	int n = 8, samples = 256, cancel = 0;
	uint64_t seed = 1;

	if (!cmdp_word(p, w, sizeof w))
		return 0;
	if (strcmp(w, "tcdot") != 0 || func_find(sym_cstr(w))) {
		cmdp_seek(p, at);
		return 0;
	}
	while (!cmdp_eos(p)) {
		if (cmdp_kw(p, "n")) {
			if (!cmdp_int(p, &v) || v < 1 || v > TC_MAXN)
				fail("tcdot: n from 1 to %d", TC_MAXN);
			n = (int)v;
		} else if (cmdp_kw(p, "samples")) {
			if (!cmdp_int(p, &v) || v < 1 || v > 100000)
				fail("tcdot: samples from 1 to 100000");
			samples = (int)v;
		} else if (cmdp_kw(p, "seed")) {
			if (!cmdp_int(p, &v) || v < 0)
				fail("tcdot: seed N, a whole number");
			seed = (uint64_t)v;
		} else if (cmdp_kw(p, "cancel"))
			cancel = 1;
		else {
			cmdp_fail_here(p);
			fail("tcdot [n N] [samples N] [seed N] [cancel]");
		}
	}
	notes_flush();
	tcdot_report(n, samples, seed, cancel);
	return 1;
}

const char *
tcdot_nlp_raw(const char *sent)
{
	static char out[96];
	char buf[300];
	size_t n = strlen(sent), i;
	const char *q;
	int k = 8;

	if (n >= sizeof buf)
		return NULL;
	for (i = 0; i <= n; i++)
		buf[i] = (char)(sent[i] >= 'A' && sent[i] <= 'Z' ? sent[i] + 32 :
		    sent[i]);
	if (!strncmp(buf, "tcdot", 5) || strchr(buf, '=') || strchr(buf, '('))
		return NULL;
	if (!strstr(buf, "block fma") && !strstr(buf, "tensor core dot") &&
	    !strstr(buf, "tensor-core dot") && !strstr(buf, "block fused "
	    "multiply"))
		return NULL;
	if ((q = strstr(buf, " of ")) != NULL && q[4] >= '1' && q[4] <= '9')
		k = atoi(q + 4);
	if (k < 1 || k > TC_MAXN)
		k = 8;
	snprintf(out, sizeof out, "tcdot n %d%s", k, strstr(buf, "cancel") ?
	    " cancel" : "");
	return out;
}
