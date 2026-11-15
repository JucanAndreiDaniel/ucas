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
 * Ozaki's slicing (a factor of more bits than a lane split into lanes,
 * several partial dots added) is not done: a factor must fit a lane.
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

struct fterm {
	nid x, y;		/* the factors (y 1 for a lone term) */
	int sign;
	int gx, gy;
	double kx, ky;
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

int
fdot_find(const struct func *f)
{
	struct fterm t[FD_MAXT];
	struct func g;
	struct dotres r;
	struct sbuf why = {0}, pf = {0};
	const struct model *m = model_active();
	const char *mn = sym_str(m->name);
	int n, i, G = 1 << 20, gb, prods = 0, said = 0;
	double kb, bound = 0, before, after;
	nid isum = 0, fb, one;
	ty_t I32 = TY(K_SINT, 32);

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
	 * up to the common grid */
	for (i = 0; i < n; i++) {
		nid kx = memk_fixform(t[i].x, t[i].gx);
		nid ky = memk_fixform(t[i].y, t[i].gy);
		nid term;
		int s = t[i].gx + t[i].gy - G;
		if (!kx || !ky)
			return 0;
		term = mk_bin(O_MUL, mk_cast(I32, kx), mk_cast(I32, ky));
		if (s)
			term = mk_bin(O_SHL, term, mk_const_i(I32, s));
		isum = !isum ? (t[i].sign < 0 ? mk_un(O_NEG, term) : term) :
		    mk_bin(t[i].sign < 0 ? O_SUB : O_ADD, isum, term);
	}
	g = *f;
	g.body = isum;
	g.anon = 1;
	dot_search(&g, 7, &r);
	before = fuse_expr_cost(m, f->body);
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

