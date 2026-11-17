/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * fdot.c: an exact float dot product as an integer one.  Where the grid
 * analysis of memk.c (fix_grid) proves every factor of a float sum of
 * products k 2^g, k an integer (a converted integer, a binary constant,
 * their sums and products), and the whole sum exact in f32 (nothing on
 * the way reaches 24 bits of its grid), the sum is
 *
 *	sum_i x_i y_i = 2^G sum_i (k_xi k_yi) 2^(g_xi + g_yi - G),
 *	G = min_i (g_xi + g_yi),
 *
 * an integer sum of products scaled once.  That integer sum goes to dot.c's
 * search, which lays its factors into the lanes of the dot forms the
 * active model has (and keeps a layout only where it is cheaper, proving
 * it); the float form is then f32(the dot) * 2^G, exact while the
 * integer sum stays below 2^24 (the conversion) and 2^G times it is a
 * normal f32 or zero.  Kept only when the model prices the whole lower.
 * Nothing names a target: a model without dot forms gets nothing.
 *
 * A factor of more bits than a lane is sliced (Ozaki's splitting of the
 * mantissas): k = sum_j ((k >> wj) & (2^w - 1)) 2^(wj) for the low
 * slices and k >> w(s - 1) (arithmetic) for the top one, exactly, in
 * two's complement; a product of two sliced factors is the sum of the
 * slices' cross products moved up by w(i + j).  Those are integer sums of
 * products again, for dot.c to lay into lanes of w bits (a slice that is
 * a byte of the factor's word is that word's lane already).  i32 wraps
 * modulo 2^32 on the way, which changes no result that fits it, and the
 * whole stays below 2^24.  Each lane width the model has a form of is
 * tried, and none: the cheapest proved is kept.  The slicing of floats
 * that are on no grid (a scale from the ranges and a bound on what is
 * dropped) is `ozaki`, below.
 */
#include "calc.h"
#include "fuse.h"
#include "memk.h"
#include "report.h"
#include "fdot.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#define FD_MAXT 16
#define FD_MAXSL 4	/* slices of a factor */

struct fterm {
	nid x, y;		/* the factors (y 1 for a lone term) */
	int sign;
	int gx, gy;
	double kx, ky;
	nid nkx, nky;		/* the integers k themselves (ozaki), else 0 */
	double X, Y;		/* ozaki: the factors' bounds */
};

static int
gather(nid e, int sign, struct fterm *t, int n)
{
	if (n < 0 || n >= FD_MAXT)
		return -1;
	switch (N.op[e]) {
	case O_ADD:
		n = gather(N.a[e], sign, t, n);
		return gather(N.b[e], sign, t, n);
	case O_SUB:
		n = gather(N.a[e], sign, t, n);
		return gather(N.b[e], -sign, t, n);
	case O_NEG:
		return gather(N.a[e], -sign, t, n);
	case O_MUL:
		t[n].x = N.a[e];
		t[n].y = N.b[e];
		t[n].sign = sign;
		return n + 1;
	case O_FMA:
		t[n].x = N.a[e];
		t[n].y = N.b[e];
		t[n].sign = sign;
		return gather(N.c[e], sign, t, n + 1);
	}
	t[n].x = e;
	t[n].y = 0;
	t[n].sign = sign;
	return n + 1;
}

/* a float factor that is never negative, by its structure: a
 * conversion of an unsigned integer, a constant at least 0, or a
 * product or sum of such */
static int
nonneg(nid x)
{
	switch (N.op[x]) {
	case O_CONST:
		return TY_FP(N.ty[x]) ? N.kr[x] >= 0 : N.ki[x] >= 0;
	case O_CAST:
		return TYK(N.ty[N.a[x]]) == K_UINT || TY_ISINT(N.ty[N.a[x]]) == 0 ?
		    TYK(N.ty[N.a[x]]) == K_UINT || nonneg(N.a[x]) : 0;
	case O_MUL:
	case O_ADD:
		return nonneg(N.a[x]) && nonneg(N.b[x]);
	}
	return 0;
}

/* the slices of k (bound kb in magnitude; pos: never negative) in lanes
 * of w bits: n, and their nodes (low first); w 0, or k fitting a lane:
 * k itself */
static int
slices(nid k, double kb, int pos, int w, nid *sl)
{
	ty_t I32 = TY(K_SINT, 32);
	int s = 1, j;

	if (w <= 0 || kb < ldexp(1.0, pos ? w : w - 1)) {
		sl[0] = k;
		return 1;
	}
	while (s < FD_MAXSL && ldexp(1.0, w * s - 1) <= kb)
		s++;
	if (ldexp(1.0, w * s - 1) <= kb)
		return 0;
	for (j = 0; j < s - 1; j++) {
		nid v = j ? mk_bin(O_SHR, k, mk_const_i(I32, w * j)) : k;
		sl[j] = mk_bin(O_AND, v, mk_const_i(I32, (1 << w) - 1));
	}
	sl[s - 1] = mk_bin(O_SHR, k, mk_const_i(I32, w * (s - 1)));
	return s;
}

/* the integer sum on the grid 2^G, its factors sliced into lanes of w
 * bits (w 0: as they are); *nsl the slices made beyond one a factor */
static nid
build_isum(const struct fterm *t, int n, int G, int w, int *nsl)
{
	ty_t I32 = TY(K_SINT, 32);
	nid isum = 0;
	int lane = w == 7 || w == 15 || w == 3 ? w + 1 : w;
	int i, a, b;

	*nsl = 0;
	for (i = 0; i < n; i++) {
		nid kx = t[i].nkx ? t[i].nkx : memk_fixform(t[i].x, t[i].gx);
		nid ky = t[i].nky ? t[i].nky : memk_fixform(t[i].y, t[i].gy);
		nid sx[FD_MAXSL], sy[FD_MAXSL];
		int s = t[i].gx + t[i].gy - G, nx, ny;
		if (!kx || !ky)
			return 0;
		nx = slices(mk_cast(I32, kx), t[i].kx, !t[i].nkx && nonneg(t[i].x), w,
		    sx);
		ny = slices(mk_cast(I32, ky), t[i].ky, !t[i].nky && nonneg(t[i].y), w,
		    sy);
		if (!nx || !ny)
			return 0;
		*nsl += nx - 1 + ny - 1;
		for (a = 0; a < nx; a++)
			for (b = 0; b < ny; b++) {
				nid term = mk_bin(O_MUL, sx[a], sy[b]);
				int sh = s + w * (a + b);
				(void)lane;
				if (sh)
					term = mk_bin(O_SHL, term, mk_const_i(I32, sh));
				isum = !isum ? (t[i].sign < 0 ? mk_un(O_NEG, term) : term) :
				    mk_bin(t[i].sign < 0 ? O_SUB : O_ADD, isum, term);
			}
	}
	return isum;
}

int
fdot_find(const struct func *f)
{
	struct fterm t[FD_MAXT] = {0};
	struct func g;
	struct dotres r;
	struct sbuf why = {0}, pf = {0};
	const struct model *m = model_active();
	const char *mn = sym_str(m->name);
	int n, i, G = 1 << 20, gb, prods = 0, said = 0, sliced = 0, nslices = 0;
	double kb, bound = 0, before, after;
	nid isum = 0, fb, one;

	if (N.ty[f->body] != TY_F32 || (N.fl[f->body] & NF_SG))
		return 0;
	n = gather(f->body, 1, t, 0);
	if (n < 2)
		return 0;
	/* the whole sum exact on a grid: no step rounds */
	if (!fix_grid(f, f->body, &gb, &kb, &why)) {
		free(why.p);
		return 0;
	}
	for (i = 0; i < n; i++) {
		one = mk_cast(TY_F32, mk_const_i(TY_LIT, 1));
		if (!t[i].y)
			t[i].y = one;
		if (!fix_grid(f, t[i].x, &t[i].gx, &t[i].kx, NULL) ||
		    !fix_grid(f, t[i].y, &t[i].gy, &t[i].ky, NULL))
			return 0;
		if (t[i].gx + t[i].gy < G)
			G = t[i].gx + t[i].gy;
		prods += N.op[t[i].y] != O_CONST || N.op[t[i].x] != O_CONST;
	}
	for (i = 0; i < n; i++)
		bound += t[i].kx * t[i].ky * ldexp(1.0, t[i].gx + t[i].gy - G);
	if (prods < 2 || bound >= 16777216.0)
		return 0;
	/* the integer sum: each factor's k (memk_fixform), each term scaled
	 * up to the common grid; then the same with the factors sliced into
	 * lanes of each width the model has dot forms of (Ozaki), the
	 * cheapest proved kept */
	before = fuse_expr_cost(m, f->body);
	memset(&r, 0, sizeof r);
	r.status = DOT_NONE;
	{
		/* w bits a slice (the low ones unsigned), and w - 1 for forms
		 * whose lanes are signed only */
		static const int wd[7] = {0, 8, 16, 4, 7, 15, 3},
		    fm[7] = {7, 1, 2, 4, 1, 2, 4};
		double bc = INFINITY;
		int v, any = 0;
		for (v = 0; v < 7; v++) {
			struct dotres r2;
			int nsl;
			nid s2 = build_isum(t, n, G, wd[v], &nsl);
			if (!s2 || (v && !nsl))
				continue;	/* nothing sliced: the first's */
			g = *f;
			g.body = s2;
			g.anon = 1;
			dot_search(&g, fm[v], &r2);
			if (r2.status == DOT_UNAVAILABLE && v) {
				dotres_free(&r2);
				continue;
			}
			if (!any || (r2.status == DOT_PROVED && (r.status != DOT_PROVED
			    || r2.after < bc))) {
				if (any)
					dotres_free(&r);
				r = r2;
				isum = s2;
				sliced = wd[v] && nsl ? wd[v] : 0;
				nslices = nsl;
				bc = r2.status == DOT_PROVED ? r2.after : INFINITY;
				any = 1;
			} else
				dotres_free(&r2);
		}
		if (!any)
			return 0;
	}
	if (r.status == DOT_UNAVAILABLE) {
		printf("  float dot products: %s has no dot product forms (the "
		    "sum is exact on the grid 2^%d, an integer sum below %g)\n",
		    mn, G, bound);
		said = 1;
		goto out;
	}
	if (r.status != DOT_PROVED)
		goto out;
	fb = mk_cast(TY_F32, r.body);
	if (G)
		fb = mk_bin(O_MUL, fb, mk_cast(TY_F32, mk_const_r(ldexp(1.0, G))));
	after = fuse_expr_cost(m, fb);
	said = 1;
	sb_printf(&pf, "every factor is k 2^g, k an integer (fix_grid: converted "
	    "integers, binary constants, + - * keep a grid), and the f32 sum is "
	    "exact: no step reaches 24 bits of its grid\n");
	sb_printf(&pf, "so the sum is 2^%d times the integer sum %s, each term's "
	    "k's multiplied and moved up to the grid 2^%d; that sum is below "
	    "%g in magnitude: inside i32, and below 2^24, so f32 holds it and "
	    "the conversion is exact; times 2^%d, a power of two, exact\n",
	    G, shared_str(isum, 160), G, bound, G);
	if (sliced)
		sb_printf(&pf, "factors wider than a lane sliced into lanes of %d "
		    "bits (Ozaki): k = the sum of (k >> %dj) & %d times 2^(%dj), the "
		    "top slice k >> %d(s - 1) (arithmetic), exact in two's "
		    "complement; %d slice%s more than the factors; each product the "
		    "sum of its slices' products moved up by %d(i + j); i32 wraps "
		    "modulo 2^32 on the way, which changes no sum that fits\n",
		    sliced, sliced, (1 << sliced) - 1, sliced, sliced, nslices,
		    nslices == 1 ? "" : "s", sliced);
	sb_printf(&pf, "the integer sum as dot products (dot.c): %s",
	    sb_str(&r.desc));
	if (!(after < before)) {
		printf("  float dot products: derived, but not cheaper under %s "
		    "(cost %g, as written %g): %s\n", mn, after, before,
		    shared_str(fb, 200));
		rep_obj("float_dot_products");
		rep_str("model", mn);
		rep_num("cost_before", before);
		rep_num("cost", after);
		rep_expr("candidate", fb);
		rep_bool("cheaper", 0);
		rep_end();
		goto out;
	}
	{
		struct sbuf w = {0};
		struct eqproof pr;
		int bad = equiv_decide(f, f->body, fb, &w, &pr);
		const char *s = sb_str(&pf), *e;
		printf("  float dot products under %s (an exact float sum of "
		    "products as an integer dot, scaled once; cost %g as "
		    "written):\n", mn, before);
		printf("  cost %-3g %s\n", after, shared_str(fb, 300));
		for (; *s; s = *e ? e + 1 : e) {
			e = strchr(s, '\n');
			if (!e)
				e = s + strlen(s);
			printf("           %.*s\n", (int)(e - s), s);
		}
		printf("           integer sum %s; %s\n", sb_str(&r.proof),
		    bad ? "contradicted by the check" : pr.how == EQ_EXHAUSTIVE ?
		    "checked on every point of the domain" : pr.how == EQ_SAT ?
		    "checked by SAT" : "checked on a sample of the domain");
		rep_obj("float_dot_products");
		rep_str("model", mn);
		rep_int("grid", G);
		rep_num("cost_before", before);
		rep_num("cost", after);
		rep_expr("expr", fb);
		rep_str("derivation", sb_str(&pf));
		rep_str("check", bad ? "contradicted" : pr.how == EQ_EXHAUSTIVE ?
		    "exhaustive" : pr.how == EQ_SAT ? "sat" : "sampled");
		rep_end();
		free(w.p);
	}
out:
	dotres_free(&r);
	free(why.p);
	free(pf.p);
	return said;
}


/* ---- ozaki: floats on no grid, a fixed scale and a bound ---- */

/* a bound on |x| from the parameters' ranges: 0 when none is known */
static int
fbound(const struct func *f, nid x, double *X)
{
	double a, b;

	switch (N.op[x]) {
	case O_CONST:
		*X = fabs(TY_FP(N.ty[x]) ? N.kr[x] : (double)N.ki[x]);
		return 1;
	case O_VAR: {
		const struct param *q = &f->p[N.ki[x]];
		if (N.ki[x] < 0 || N.ki[x] >= f->np)
			return 0;
		if (q->ranged) {
			*X = TY_FP(q->ty) ? fmax(fabs(q->rlo), fabs(q->rhi)) :
			    fmax(fabs((double)q->lo), fabs((double)q->hi));
			return 1;
		}
		if (q->ty == TY_F16) {
			*X = 65504;
			return 1;
		}
		return 0;
	}
	case O_CAST:
	case O_NEG:
		return fbound(f, N.a[x], X);
	case O_MUL:
		if (!fbound(f, N.a[x], &a) || !fbound(f, N.b[x], &b))
			return 0;
		*X = a * b;
		return 1;
	}
	return 0;
}

/* the grid every value of x lies on: an f16's 2^-24, an integer's 1, a
 * constant's lowest bit; 0 where none smaller than any scale is known */
static double
quantum(const struct func *f, nid x)
{
	switch (N.op[x]) {
	case O_VAR:
		if (N.ki[x] < 0 || N.ki[x] >= f->np)
			return 0;
		return f->p[N.ki[x]].ty == TY_F16 ? 0x1p-24 :
		    TY_ISINT(f->p[N.ki[x]].ty) ? 1 : 0;
	case O_CAST:
	case O_NEG:
		return quantum(f, N.a[x]);
	case O_CONST: {
		double v = TY_FP(N.ty[x]) ? fabs(N.kr[x]) : fabs((double)N.ki[x]);
		int e;
		if (v == 0)
			return INFINITY;
		frexp(v, &e);
		while (ldexp(v, 53 - e) != floor(ldexp(v, 53 - e)))
			e++;
		{
			double q = ldexp(1.0, e - 53);
			while (fmod(v, 2 * q) == 0)
				q *= 2;
			return q;
		}
	}
	}
	return 0;
}

/* a value of type ty in [lo, hi], uniformly (f16 and f32 rounded) */
static double
rnd_in(uint64_t *st, ty_t ty, double lo, double hi)
{
	double u, v;
	int e;

	*st ^= *st << 13;
	*st ^= *st >> 7;
	*st ^= *st << 17;
	u = (double)(*st >> 11) * 0x1p-53;
	v = lo + (hi - lo) * u;
	if (ty == TY_F32)
		v = (double)(float)v;
	else if (ty == TY_F16 && v != 0) {
		frexp(v, &e);
		e = e < -13 ? -13 : e;
		v = ldexp(rint(ldexp(v, 11 - e)), e - 11);
	}
	return v;
}

/*
 * Ozaki's scheme on a float sum of products sum_i s_i x_i y_i whose
 * factors have bounds from the parameters' ranges: each factor scaled by
 * a power of two to an integer k = i32(x 2^-g) of at most p bits
 * (truncated: |x - k 2^g| < 2^g), the integers' sum laid into the
 * model's dot forms by slicing (fdot_find's), then converted and scaled
 * back.  Error, against the exact sum:
 *
 *	sum_i (2^gx Y + X 2^gy + 2^(gx + gy)) + 2^-24 2^G I
 *
 * (the truncations, and the conversion of the integer sum I to f32 where
 * it reaches 2^24).  p is the most bits that keep I inside i32.  Kept
 * where that is within tol and the model prices it below the sum.
 */
static void
ozaki_run(const struct func *f, int nsl, double tol, uint64_t seed)
{
	static const int wd[3] = {8, 16, 4}, fm[3] = {1, 2, 4};
	struct fterm t[FD_MAXT];
	const struct model *m = model_active();
	const char *mn = sym_str(m->name);
	ty_t I32 = TY(K_SINT, 32);
	int n, i, v, best = -1, G = 0;
	double before, bcost = INFINITY, bE = 0, asw = 0;
	nid bfb = 0;
	struct dotres br;
	struct sbuf d = {0};

	memset(&br, 0, sizeof br);
	if (!TY_FP(N.ty[f->body]))
		fail("ozaki: %s is not a float sum of products",
		    shared_str(f->body, 80));
	n = gather(f->body, 1, t, 0);
	if (n < 2)
		fail("ozaki: %s is not a sum of products", shared_str(f->body, 80));
	for (i = 0; i < n; i++) {
		if (!t[i].y)
			t[i].y = mk_cast(TY_F32, mk_const_i(TY_LIT, 1));
		if (!fbound(f, t[i].x, &t[i].X) || !fbound(f, t[i].y, &t[i].Y))
			fail("ozaki: no bound on %s from the parameters' ranges (give "
			    "them ranges: x: f32 in -1..1)", shared_str(t[i].X ?
			    t[i].y : t[i].x, 80));
		asw += t[i].X * t[i].Y;
	}
	before = fuse_expr_cost(m, f->body);
	rep_begin("ozaki");
	printf("ozaki %s under %s: a float sum of %d products as integer dot "
	    "products, each factor scaled to an integer by a power of two from "
	    "its range\n", f->anon ? shared_str(f->body, 120) : sym_str(f->name),
	    mn, n);
	rep_str("model", mn);
	rep_num("cost_before", before);
	for (v = 0; v < 3; v++) {
		int w = wd[v], S = nsl, pmax = S * w - 1 < 30 ? S * w - 1 : 30;
		int pp, Gv, d, ok = 1, nd = 2 * S - 1;
		double E, Bd[2 * FD_MAXSL], scaled = 0;
		struct dotres rd[2 * FD_MAXSL];
		nid fb = 0, map[2 * FD_MAXT];
		struct func g;
		double c;

		pp = pmax;
		memset(rd, 0, sizeof rd);
		/* each factor to an integer of pp bits; then each weight's sum
		 * bounded, pp lowered until every one fits i32 */
		for (;;) {
			double top = ldexp(1.0, pp - w * (S - 1)), low = ldexp(1.0, w) - 1;
			Gv = 1 << 20;
			for (i = 0; i < n; i++) {
				int ex = 0, ey = 0;
				frexp(t[i].X, &ex);
				frexp(t[i].Y, &ey);
				t[i].gx = ex - pp;
				t[i].gy = ey - pp;
				if (t[i].gx + t[i].gy < Gv)
					Gv = t[i].gx + t[i].gy;
			}
			ok = 1;
			for (d = 0; d < nd; d++) {
				int a2;
				Bd[d] = 0;
				for (i = 0; i < n; i++)
					for (a2 = 0; a2 < S; a2++) {
						int b2 = d - a2;
						double ma, mb;
						if (b2 < 0 || b2 >= S)
							continue;
						ma = a2 == S - 1 ? top : low;
						mb = b2 == S - 1 ? top : low;
						Bd[d] += ma * mb * ldexp(1.0, t[i].gx + t[i].gy - Gv);
					}
				if (Bd[d] >= 2147483648.0)
					ok = 0;
			}
			if (ok || pp <= w * (S - 1) + 1)
				break;
			pp--;
		}
		if (!ok)
			continue;
		/* the scaled factors as free i32s, |k| <= 2^pp: each weight's sum
		 * of slice products laid into dots and proved for any of them */
		memset(&g, 0, sizeof g);
		g.anon = 1;
		g.np = 2 * n;
		for (i = 0; i < 2 * n; i++) {
			char nm[16];
			snprintf(nm, sizeof nm, "k%d", i);
			g.p[i].name = sym_cstr(nm);
			g.p[i].ty = I32;
			g.p[i].ranged = 1;
			g.p[i].hi = (int64_t)1 << pp;
			g.p[i].lo = -g.p[i].hi;
			g.p[i].rlo = (double)g.p[i].lo;
			g.p[i].rhi = (double)g.p[i].hi;
			map[i] = mk_cast(I32, mk_bin(O_MUL, mk_cast(TY_F32, i & 1 ?
			    t[i / 2].y : t[i / 2].x), mk_cast(TY_F32, mk_const_r(ldexp(1.0,
			    -(i & 1 ? t[i / 2].gy : t[i / 2].gx))))));
		}
		for (d = 0; d < nd && ok; d++) {
			nid sum = 0;
			for (i = 0; i < n; i++) {
				nid sx[FD_MAXSL], sy[FD_MAXSL];
				int a2, sh = t[i].gx + t[i].gy - Gv;
				nid kx = mk_var(2 * i, g.p[2 * i].name, I32);
				nid ky = mk_var(2 * i + 1, g.p[2 * i + 1].name, I32);
				for (a2 = 0; a2 < S; a2++) {
					sx[a2] = a2 < S - 1 ? mk_bin(O_AND, a2 ? mk_bin(O_SHR, kx,
					    mk_const_i(I32, w * a2)) : kx, mk_const_i(I32, (1 << w) -
					    1)) : mk_bin(O_SHR, kx, mk_const_i(I32, w * a2));
					sy[a2] = a2 < S - 1 ? mk_bin(O_AND, a2 ? mk_bin(O_SHR, ky,
					    mk_const_i(I32, w * a2)) : ky, mk_const_i(I32, (1 << w) -
					    1)) : mk_bin(O_SHR, ky, mk_const_i(I32, w * a2));
					if (S == 1)
						sx[0] = kx, sy[0] = ky;
				}
				for (a2 = 0; a2 < S; a2++) {
					int b2 = d - a2;
					nid term;
					if (b2 < 0 || b2 >= S)
						continue;
					term = mk_bin(O_MUL, sx[a2], sy[b2]);
					if (sh)
						term = mk_bin(O_SHL, term, mk_const_i(I32, sh));
					sum = !sum ? (t[i].sign < 0 ? mk_un(O_NEG, term) : term) :
					    mk_bin(t[i].sign < 0 ? O_SUB : O_ADD, sum, term);
				}
			}
			g.body = sum;
			dot_search(&g, fm[v], &rd[d]);
			if (rd[d].status == DOT_NONE || rd[d].status == DOT_UNAVAILABLE) {
				dotres_free(&rd[d]);
				memset(&rd[d], 0, sizeof rd[d]);
				rd[d].status = DOT_PROVED;
				rd[d].body = sum;
				rd[d].kind = "identity";
			} else if (rd[d].status != DOT_PROVED)
				ok = 0;
			if (ok) {
				nid x = mk_cast(TY_F32, subst(rd[d].body, map, 2 * n));
				int e2 = Gv + w * d;
				if (e2)
					x = mk_bin(O_MUL, x, mk_cast(TY_F32, mk_const_r(ldexp(1.0,
					    e2))));
				fb = fb ? mk_bin(O_ADD, fb, x) : x;
				scaled += Bd[d] * ldexp(1.0, e2);
			}
		}
		if (!ok) {
			for (d = 0; d < nd; d++)
				dotres_free(&rd[d]);
			continue;
		}
		/* the error: each factor's truncation (none where its grid is
		 * the factor's own: an f16 on 2^-24, an integer on 1), each
		 * weight's conversion past 2^24, and the f32 adds of the weights */
		E = 0;
		for (i = 0; i < n; i++) {
			double dx = ldexp(1.0, t[i].gx), dy = ldexp(1.0, t[i].gy);
			if (quantum(f, t[i].x) >= dx)
				dx = 0;
			if (quantum(f, t[i].y) >= dy)
				dy = 0;
			E += dx * t[i].Y + t[i].X * dy + dx * dy;
		}
		for (d = 0; d < nd; d++)
			if (Bd[d] >= 16777216.0)
				E += 0x1p-24 * Bd[d] * ldexp(1.0, Gv + w * d);
		E += (nd - 1) * 0x1p-24 / (1 - (nd - 1) * 0x1p-24) * scaled;
		c = fuse_expr_cost(m, fb);
		printf("  lanes of %2d bits, %d slices: factors of %d bits (|k| <= "
		    "2^%d), %d weights each inside i32: cost %g, error %s%.4g\n", w,
		    S, pp + 1, pp, nd, c, E > 0 ? "at most " : "", E);
		if (c < bcost || (c == bcost && E < bE)) {
			if (best >= 0)
				dotres_free(&br);
			br = rd[0];
			rd[0].desc.p = NULL;
			for (d = 1; d < nd; d++)
				dotres_free(&rd[d]);
			bcost = c;
			bE = E;
			bfb = fb;
			best = v;
			G = Gv;
		} else
			for (d = 0; d < nd; d++)
				dotres_free(&rd[d]);
	}
	if (best < 0) {
		printf("  no form: a weight's integer sum would leave i32 at any "
		    "width\n");
		rep_bool("rewritten", 0);
		free(d.p);
		return;
	}
	printf("  as written: cost %g; its f32 sum within about %.4g of the "
	    "exact (gamma_%d sum |x y|)\n", before, n * 0x1p-24 / (1 - n *
	    0x1p-24) * asw, n);
	printf("  best: %s\n", shared_str(bfb, 300));
	{
		const char *q = sb_str(&br.desc), *e;
		printf("    the integer sum (dot.c):");
		for (; *q; q = *e ? e + 1 : e) {
			e = strchr(q, '\n');
			if (!e)
				e = q + strlen(q);
			printf(" %.*s\n%s", (int)(e - q), q, *e && e[1] ? "     " : "");
		}
	}
	printf("    proved: the integer sum's dots by %s; the rest is the "
	    "derivation above\n", br.kind ? br.kind : "dot.c");
	rep_num("cost", bcost);
	rep_num("bound", bE);
	rep_int("grid", G);
	rep_expr("expr", bfb);
	/* the bound checked on random points of the domain */
	{
		struct plan pl;
		nid roots[2 * FD_MAXT + 1];
		uint32_t loc[2 * FD_MAXT + 1];
		int64_t *in_i = xcalloc((size_t)MAXP * CH, sizeof *in_i);
		double *in_r = xcalloc((size_t)MAXP * CH, sizeof *in_r);
		uint64_t st = seed * 0x9e3779b97f4a7c15ULL + 7;
		double worst = 0;
		int nr = 0, c, k, over = 0;
		for (i = 0; i < n; i++) {
			roots[nr++] = t[i].x;
			roots[nr++] = t[i].y;
		}
		roots[nr++] = bfb;
		plan_build(&pl, roots, (uint32_t)nr, 0);
		for (k = 0; k < nr; k++)
			loc[k] = plan_loc(&pl, roots[k]);
		for (c = 0; c < 16; c++) {
			int pt;
			for (pt = 0; pt < CH; pt++)
				for (k = 0; k < f->np; k++) {
					const struct param *q = &f->p[k];
					double lo = q->ranged ? (TY_FP(q->ty) ? q->rlo :
					    (double)q->lo) : -65504, hi = q->ranged ? (TY_FP(q->ty) ?
					    q->rhi : (double)q->hi) : 65504;
					if (TY_FP(q->ty))
						in_r[(size_t)k * CH + pt] = rnd_in(&st, q->ty, lo, hi);
					else
						in_i[(size_t)k * CH + pt] = (int64_t)floor(rnd_in(&st,
						    TY_F64, lo, hi + 0.999));
				}
			plan_run(&pl, CH, in_i, in_r);
			for (pt = 0; pt < CH; pt++) {
				long double ex = 0, e;
				for (i = 0; i < n; i++)
					ex += (long double)t[i].sign * COLR(&pl, loc[2 * i])[pt] *
					    COLR(&pl, loc[2 * i + 1])[pt];
				e = fabsl((long double)COLR(&pl, loc[nr - 1])[pt] - ex);
				if ((double)e > bE)
					over++;
				if ((double)e > worst)
					worst = (double)e;
			}
		}
		printf("  check: %d random points, the largest error %.4g, %s the "
		    "bound %.4g (sampled, not a proof)\n", 16 * CH, worst, over ?
		    "OVER" : "within", bE);
		rep_check("random", 16L * CH, worst, !over, "the scheme against "
		    "the exact sum on random points");
		plan_free(&pl);
		free(in_i);
		free(in_r);
	}
	if (tol > 0 && bE > tol)
		printf("  -> not taken: its error bound %.4g is past tol %g%s\n", bE,
		    tol, nsl < FD_MAXSL ? " (more slices, more bits: slices N)" : "");
	else if (tol <= 0)
		printf("  -> an approximation: give tol T, the error allowed, to "
		    "take it\n");
	else if (!(bcost < before))
		printf("  -> within tol, but not cheaper under %s (%g against %g)\n",
		    mn, bcost, before);
	else
		printf("  -> taken: cost %g against %g, error at most %.4g <= tol "
		    "%g\n", bcost, before, bE, tol);
	rep_bool("rewritten", tol > 0 && bE <= tol && bcost < before);
	dotres_free(&br);
	free(d.p);
}

int
ozaki_command(struct P *p)
{
	static const char *const stop[] = {"slices", "tol", "seed", "model", NULL};
	char w[48];
	uint32_t at = cmdp_pos(p);
	struct func *f;
	struct model *was = model_active(), *m = NULL;
	double tol = 0;
	int64_t v;
	int nsl = 2;
	uint64_t seed = 1;

	if (!cmdp_word(p, w, sizeof w))
		return 0;
	if (strcmp(w, "ozaki") != 0 || func_find(sym_cstr(w))) {
		cmdp_seek(p, at);
		return 0;
	}
	f = cmdp_func(p, stop);
	while (!cmdp_eos(p)) {
		if (cmdp_kw(p, "slices")) {
			if (!cmdp_int(p, &v) || v < 1 || v > FD_MAXSL)
				fail("ozaki: slices N, 1 to %d", FD_MAXSL);
			nsl = (int)v;
		} else if (cmdp_kw(p, "tol")) {
			tol = cmdp_number(p, stop);
			if (!(tol > 0))
				fail("ozaki: tol must be positive");
		} else if (cmdp_kw(p, "seed")) {
			if (!cmdp_int(p, &v) || v < 0)
				fail("ozaki: seed N");
			seed = (uint64_t)v;
		} else if (cmdp_kw(p, "model")) {
			if (!cmdp_word(p, w, sizeof w) ||
			    (m = model_find(sym_cstr(w))) == NULL)
				fail("ozaki: unknown model (see 'models')");
		} else {
			cmdp_fail_here(p);
			fail("ozaki F [slices N] [tol T] [seed N] [model M]");
		}
	}
	notes_flush();
	if (m)
		model_set_active(m);
	ozaki_run(f, nsl, tol, seed);
	if (m)
		model_set_active(was);
	return 1;
}

/* "ozaki's scheme for f with 3 slices", "f as integer dot products by
 * ozaki within 1e-3" */
const char *
ozaki_nlp_raw(const char *sent)
{
	static char out[200];
	char buf[300], name[64] = "", tol[32] = "", sl[8] = "";
	const char *q;
	size_t n = strlen(sent), i;

	if (n >= sizeof buf)
		return NULL;
	for (i = 0; i <= n; i++)
		buf[i] = (char)(sent[i] >= 'A' && sent[i] <= 'Z' ? sent[i] + 32 :
		    sent[i]);
	if (!strncmp(buf, "ozaki ", 6) || strchr(buf, '=') || !strstr(buf, "ozaki"))
		return NULL;
	if ((q = strstr(buf, " for ")) != NULL || (q = strstr(buf, " of ")) !=
	    NULL) {
		const char *s = strchr(q + 1, ' ') + 1;
		size_t k = strcspn(s, " ?.,");
		if (k && k < sizeof name) {
			memcpy(name, s, k);
			name[k] = 0;
		}
	}
	if (!name[0] && (q = strchr(buf, ' ')) == NULL)
		return NULL;
	if (!name[0]) {
		size_t k = strcspn(buf, " ");
		if (k < sizeof name && strncmp(buf, "ozaki", 5)) {
			memcpy(name, buf, k);
			name[k] = 0;
		}
	}
	if (!name[0] || !func_find(sym_cstr(name)))
		return NULL;
	if ((q = strstr(buf, "within ")) != NULL || (q = strstr(buf, "tol ")) !=
	    NULL) {
		const char *s = strchr(q, ' ') + 1;
		size_t k = strcspn(s, " ?,");
		if (k && k < sizeof tol) {
			memcpy(tol, s, k);
			tol[k] = 0;
		}
	}
	if ((q = strstr(buf, " slices")) != NULL && q > buf) {
		const char *s = q - 1;
		while (s > buf && s[-1] >= '0' && s[-1] <= '9')
			s--;
		if (s[0] >= '0' && s[0] <= '9' && q - s < (long)sizeof sl) {
			memcpy(sl, s, (size_t)(q - s));
			sl[q - s] = 0;
		}
	}
	snprintf(out, sizeof out, "ozaki %s%s%s%s%s", name, sl[0] ? " slices " :
	    "", sl, tol[0] ? " tol " : "", tol);
	return out;
}
