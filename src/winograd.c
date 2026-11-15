/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * winograd.c: Winograd's 1968 inner product.  For a sum of products
 * sum_k x_k y_k, with the pairs taken two by two,
 *
 *	sum_k x_k y_k = sum_j (x_2j + y_2j+1)(x_2j+1 + y_2j) - xi - eta,
 *	xi = sum_j x_2j x_2j+1,  eta = sum_j y_2j y_2j+1
 *
 * (each product expands to x_2j x_2j+1 + x_2j y_2j + y_2j+1 x_2j+1 +
 * y_2j+1 y_2j; the two corrections take away the products within one
 * side).  It holds in any commutative ring: for integers modulo 2^W,
 * which poly_identity checks by expanding both sides.  It halves the
 * multiplies of each output when xi belongs to a row of a matrix
 * product and eta to a column, each computed once and shared by the
 * outputs of that row or column; for one output alone it costs more.
 *
 * `winograd F [rows R] [cols C] [tol T]` prices an R x C block of such
 * outputs (F one of them, its first factors the row's, its second the
 * column's) both ways under the active model, from the expressions' own
 * covers: R C (direct) against R C (pairs) + R (xi) + C (eta).  For
 * floats the rounding differs: with u the unit roundoff and n/2 pairs,
 * the computed result is within
 *
 *	gamma_(n/2+3) (sum_j |x_2j + y_2j+1| |x_2j+1 + y_2j| + sum |x x| +
 *	sum |y y|)
 *
 * of the exact sum (each pair: two adds and a multiply, three roundings;
 * the sum of n/2 + 2 terms in any order; the standard model fl(a op b) =
 * (a op b)(1 + d), |d| <= u), bounded over the parameters' ranges (|a +
 * b| <= |a| + |b|); it is offered only where that is within T.  The direct sum
 * has gamma_n sum |x y|: Winograd's is larger where x and y differ in
 * scale.
 */
#include "calc.h"
#include "fuse.h"
#include "report.h"
#include "stoch.h"
#include "winograd.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#define WG_MAXT 16

static int
gather(nid e, nid *x, nid *y, int n)
{
	if (n < 0 || n >= WG_MAXT)
		return -1;
	if (N.op[e] == O_ADD) {
		n = gather(N.a[e], x, y, n);
		return gather(N.b[e], x, y, n);
	}
	if (N.op[e] == O_MUL) {
		x[n] = N.a[e];
		y[n] = N.b[e];
		return n + 1;
	}
	return -1;
}

static nid
sum_of(const nid *t, int n)
{
	nid s = t[0];
	int i;

	for (i = 1; i < n; i++)
		s = mk_bin(O_ADD, s, t[i]);
	return s;
}

/* the largest |e| on f's domain (< 0: not known): a parameter's range,
 * a constant, and |a + b| <= |a| + |b|, |a b| = |a| |b| */
static double
amax(const struct func *f, nid e)
{
	double a, b;

	switch (N.op[e]) {
	case O_CONST:
		return fabs(TY_FP(N.ty[e]) ? N.kr[e] : (double)N.ki[e]);
	case O_VAR:
		if (N.ki[e] < 0 || N.ki[e] >= f->np || !f->p[N.ki[e]].ranged)
			return -1;
		if (TY_FP(f->p[N.ki[e]].ty))
			return fmax(fabs(f->p[N.ki[e]].rlo), fabs(f->p[N.ki[e]].rhi));
		return fmax(fabs((double)f->p[N.ki[e]].lo),
		    fabs((double)f->p[N.ki[e]].hi));
	case O_CAST: case O_NEG:
		return amax(f, N.a[e]);
	case O_ADD: case O_SUB: case O_MUL:
		a = amax(f, N.a[e]);
		b = amax(f, N.b[e]);
		if (a < 0 || b < 0)
			return -1;
		return N.op[e] == O_MUL ? a * b : a + b;
	}
	return -1;
}

void
winograd_run(const struct func *f, long rows, long cols, double tol)
{
	const struct model *m = model_active();
	const char *mn = sym_str(m->name);
	nid x[WG_MAXT], y[WG_MAXT], pr[WG_MAXT], xx[WG_MAXT], yy[WG_MAXT];
	nid per, xi, eta, full, XI, ETA;
	int n = gather(f->body, x, y, 0), h, j, fp = TY_FP(N.ty[f->body]);
	int ok = 1, deg;
	double cd, cp, cx, cy, tot_d, tot_w, bound = -1;
	struct sbuf how = {0};

	if (n < 2 || (n & 1))
		fail("winograd: %s is not a sum of an even number of products "
		    "(x0*y0 + x1*y1 + ...)", node_str(f->body));
	h = n / 2;
	for (j = 0; j < h; j++) {
		pr[j] = mk_bin(O_MUL, mk_bin(O_ADD, x[2 * j], y[2 * j + 1]),
		    mk_bin(O_ADD, x[2 * j + 1], y[2 * j]));
		xx[j] = mk_bin(O_MUL, x[2 * j], x[2 * j + 1]);
		yy[j] = mk_bin(O_MUL, y[2 * j], y[2 * j + 1]);
	}
	xi = sum_of(xx, h);
	eta = sum_of(yy, h);
	/* the corrections, computed once a row and once a column: free
	 * inputs to each output */
	XI = mk_var(MAXP + 1, sym_cstr("xi"), N.ty[xi]);
	ETA = mk_var(MAXP + 2, sym_cstr("eta"), N.ty[eta]);
	per = mk_bin(O_SUB, sum_of(pr, h), mk_bin(O_ADD, XI, ETA));
	full = mk_bin(O_SUB, sum_of(pr, h), mk_bin(O_ADD, xi, eta));
	cd = fuse_expr_cost(m, f->body);
	cp = fuse_expr_cost(m, per);
	cx = fuse_expr_cost(m, xi);
	cy = fuse_expr_cost(m, eta);
	tot_d = (double)rows * cols * cd;
	tot_w = (double)rows * cols * cp + rows * cx + cols * cy;
	rep_begin("winograd");
	printf("winograd %s: %d products as %d pair products and two "
	    "corrections, under %s\n", f->anon ? node_str(f->body) :
	    sym_str(f->name), n, h, mn);
	printf("  per output: %s - (xi + eta)\n", shared_str(sum_of(pr, h),
	    300));
	printf("  xi = %s (a row's), eta = %s (a column's)\n",
	    shared_str(xi, 200), shared_str(eta, 200));
	if (!fp) {
		/* a ring identity: modulo 2^W */
		ok = poly_identity(f->body, full, &deg, &how);
		printf("  identity: (x_2j + y_2j+1)(x_2j+1 + y_2j) = x_2j x_2j+1 + "
		    "x_2j y_2j + x_2j+1 y_2j+1 + y_2j y_2j+1, so the pairs less xi "
		    "and eta leave sum x_k y_k: %s\n", ok ? "both sides expanded "
		    "as polynomials agree modulo 2^W (exact, any operands)" :
		    "not proved by expansion");
		rep_bool("proved", ok);
		rep_str("proof", ok ? "algebra" : "none");
	} else {
		/* the derived bound over the domain */
		double s = 0, u = ldexp(1.0, TYW(N.ty[f->body]) == 64 ? -53 :
		    TYW(N.ty[f->body]) == 16 ? -11 : -24), g, a;
		int k = h + 3;
		for (j = 0; j < h && s >= 0; j++) {
			a = amax(f, mk_bin(O_ADD, x[2 * j], y[2 * j + 1]));
			g = amax(f, mk_bin(O_ADD, x[2 * j + 1], y[2 * j]));
			if (a < 0 || g < 0)
				s = -1;
			else
				s += a * g;
			a = amax(f, xx[j]);
			g = amax(f, yy[j]);
			if (s >= 0 && (a < 0 || g < 0))
				s = -1;
			else if (s >= 0)
				s += a + g;
		}
		if (s >= 0)
			bound = k * u / (1 - k * u) * s;
		printf("  floats: the same algebra, not the same roundings; "
		    "|computed - exact| <= gamma_%d (sum |x_2j + y_2j+1| |x_2j+1 + "
		    "y_2j| + sum |x x| + sum |y y|)%s", k, bound >= 0 ? "" :
		    ": the parameters' ranges do not bound it\n");
		if (bound >= 0)
			printf(" <= %.6g over the parameters' ranges\n", bound);
		ok = bound >= 0 && bound <= tol;
		if (!ok)
			printf("  not offered: %s\n", tol > 0 ? "the bound is past "
			    "the tolerance" : "floats need a tolerance (tol T)");
		rep_num("bound", bound);
		rep_bool("within_tol", ok);
	}
	printf("  per output %g against %g as written; xi %g, eta %g\n", cp, cd,
	    cx, cy);
	printf("  a %ld x %ld block: %g against %g as written: %s\n", rows,
	    cols, tot_w, tot_d, !ok ? "not offered" : tot_w < tot_d ?
	    "cheaper" : "not cheaper");
	rep_num("cost_output", cp);
	rep_num("cost_output_before", cd);
	rep_num("cost_block", tot_w);
	rep_num("cost_block_before", tot_d);
	rep_bool("cheaper", ok && tot_w < tot_d);
	rep_expr("output", per);
	rep_expr("xi", xi);
	rep_expr("eta", eta);
	rep_end();
	free(how.p);
}

int
winograd_command(struct P *p)
{
	static const char *const stop[] = {"rows", "cols", "tol", NULL};
	char w[48];
	uint32_t at = cmdp_pos(p);
	struct func *f;
	long rows = 1, cols = 1;
	double tol = 0;
	int64_t v;

	if (!cmdp_word(p, w, sizeof w))
		return 0;
	if (strcmp(w, "winograd") != 0 || func_find(sym_cstr(w))) {
		cmdp_seek(p, at);
		return 0;
	}
	f = cmdp_func(p, stop);
	while (!cmdp_eos(p)) {
		if (cmdp_kw(p, "rows")) {
			if (!cmdp_int(p, &v) || v < 1)
				fail("winograd: rows N, at least 1");
			rows = (long)v;
		} else if (cmdp_kw(p, "cols")) {
			if (!cmdp_int(p, &v) || v < 1)
				fail("winograd: cols N, at least 1");
			cols = (long)v;
		} else if (cmdp_kw(p, "tol")) {
			tol = cmdp_number(p, stop);
			if (!(tol > 0))
				fail("winograd: tol must be positive");
		} else {
			cmdp_fail_here(p);
			fail("winograd F [rows R] [cols C] [tol T]");
		}
	}
	notes_flush();
	winograd_run(f, rows, cols, tol);
	return 1;
}

/* "winograd's inner product of f for 64 rows and 64 columns" */
const char *
winograd_nlp_raw(const char *sent)
{
	static char out[200];
	char buf[300], name[64] = "";
	const char *q;
	size_t n = strlen(sent), i;
	long r = 1, c = 1;

	if (n >= sizeof buf)
		return NULL;
	for (i = 0; i <= n; i++)
		buf[i] = (char)(sent[i] >= 'A' && sent[i] <= 'Z' ? sent[i] + 32 :
		    sent[i]);
	if (!strncmp(buf, "winograd ", 9) || strchr(buf, '=') ||
	    !strstr(buf, "winograd"))
		return NULL;
	if ((q = strstr(buf, " of ")) != NULL) {
		size_t k = strcspn(q + 4, " ?.,");
		if (k && k < sizeof name) {
			memcpy(name, sent + (q + 4 - buf), k);
			name[k] = 0;
		}
	}
	if (!name[0] || !func_find(sym_cstr(name)))
		return NULL;
	if ((q = strstr(buf, " rows")) != NULL) {
		const char *d = q;
		while (d > buf && d[-1] >= '0' && d[-1] <= '9')
			d--;
		r = atol(d);
	}
	if ((q = strstr(buf, " col")) != NULL) {
		const char *d = q;
		while (d > buf && d[-1] >= '0' && d[-1] <= '9')
			d--;
		c = atol(d);
	}
	snprintf(out, sizeof out, "winograd %s rows %ld cols %ld", name,
	    r > 0 ? r : 1, c > 0 ? c : 1);
	return out;
}
