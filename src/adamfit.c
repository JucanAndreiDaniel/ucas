/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * adamfit.c - cheap approximations by a search over expression shapes,
 * each shape's constants fitted by Adam (adamfit.h).
 *
 *   adamfit F [in a..b] [as f32|f64|real] [ops + - * / fma sqrt exp log sin
 *       cos abs] [count N] [size N] [steps N] [lr R] [restarts N] [wcost W]
 *       [werr W] [error e | ulp u] [relative | absolute] [auto] [list N]
 *       [seed K] [seconds S] [name P] [nocert]
 *
 * The shapes: every polynomial in Horner form up to the constants' limit
 * (plain, odd x*P(x*x), even P(x*x)), small rationals, forms with sqrt when
 * it is enabled, then random expressions of the grammar up to `size` nodes,
 * each kept once (commutative operands in a canonical order, no operation
 * on constants alone, no x - x or x / x).
 *
 * The fit: a tiny network per shape, its weights the constants.  Forward
 * over the training sample, then one reverse sweep gives the gradient of
 * the loss (1/p) log sum |r|^p, r the weighted residual (relative to F by
 * default), p = 2 first and 8 after: a smooth path to the largest error.
 * Adam (b1 0.9, b2 0.999, the step decaying linearly to a tenth) from a few
 * starts; stage 2 trains the best 64 shapes ten times longer, p up to 32.
 * The sample's points are spread with + - * / only, and the default
 * operations use + - * / and sqrt only: a seed gives the same run on every
 * libm.
 *
 * Every shape is priced as ucas prices any expression (approx's rules, the
 * active model); the stage-2 shapes are defined as functions in the target
 * format, measured with the IEEE evaluator against a long double reference
 * on a dense sample, and the listed ones get a bound that holds on the
 * whole interval (acert.c), which their final score uses.
 */
#include "ucas.h"
#include "approx.h"
#include "numsearch.h"
#include "report.h"
#include "stoch.h"
#include "adamfit.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <time.h>

#define AF_MAXN 32	/* nodes of a shape */
#define AF_MAXK 8	/* trainable constants */
#define AF_T 264	/* training points at most */
#define AF_T1 66	/* stage 1's */
#define AF_T2 257	/* stage 2's */
#define AF_STAGE2 96	/* shapes trained longer */
#define AF_PERCOST 3	/* of them, the best at each cost */
#define AF_NV 8192	/* measuring sample */

enum {
	Q_X, Q_C, Q_ADD, Q_SUB, Q_MUL, Q_DIV, Q_FMA, Q_SQRT, Q_EXP, Q_LOG,
	Q_SIN, Q_COS, Q_ABS, Q_NOPS
};
static const char *const qname[Q_NOPS] = {"x", "c", "+", "-", "*", "/",
	"fma", "sqrt", "exp", "log", "sin", "cos", "abs"};
static const int qarity[Q_NOPS] = {0, 0, 2, 2, 2, 2, 3, 1, 1, 1, 1, 1, 1};

struct shape {
	uint8_t op[AF_MAXN], a[AF_MAXN], b[AF_MAXN], c[AF_MAXN], k[AF_MAXN];
	int n, nk;		/* root: n - 1; node 0 is x */
	char kind[12];		/* poly, odd, even, rational, sqrt, random */
	/* the fit */
	double th[AF_MAXK];
	double terr;		/* the largest weighted residual on the sample */
	double cost;
	double score1;
	int ok;
	/* stage 2 */
	double merr;		/* measured in the metric, machine arithmetic */
	double bound;		/* certified, or -1 */
	char why[160];		/* not certified: why */
	double score;
	int bad;		/* points where it is undefined */
	int pick;		/* chosen for stage 2 */
};

static struct {
	struct func f;
	char fname[200];
	struct lref ref;
	int w, prec, emin, rel;
	double lo, hi;
	unsigned ops;		/* 1 << Q_* */
	int count, size, steps, restarts, list, autom, cert;
	double lr, wcost, werr, tol, secs;
	char tolname[24];
	uint64_t seed;
	char name[24];
	/* the training sample */
	double tx[AF_T], ty[AF_T], tw[AF_T];
	int nt;
	/* the measuring sample */
	double *mx;
	ld *my;
	int nm;
	double c0;		/* the target's cost */
	struct shape *sh;
	int nsh, capsh;
	uint64_t *seen;		/* hash set of the shapes' keys */
	uint32_t capseen;
	struct nsrng rng;
	struct timespec t0;
} F;

/* ---- small helpers ---- */

static double
rnd(int w, double v)
{
	return w == 32 ? (double)(float)v : v;
}

static ld
ulp_of(ld y)
{
	int e;

	y = fabsl(y);
	if (y == 0)
		return ldexpl(1, F.emin - (F.prec - 1));
	e = ilogbl(y);
	if (e < F.emin)
		e = F.emin;
	return ldexpl(1, e - (F.prec - 1));
}

static void
kfmt(char *buf, size_t n, double v)
{
	snprintf(buf, n, F.w == 64 || F.w == 0 ? "%.17g" : "%.9g", v);
	if (!strpbrk(buf, ".eni"))
		strncat(buf, ".0", n - strlen(buf) - 1);
}

static double
elapsed(void)
{
	struct timespec t;

	clock_gettime(CLOCK_MONOTONIC, &t);
	return (double)(t.tv_sec - F.t0.tv_sec) +
	    (t.tv_nsec - F.t0.tv_nsec) / 1e9;
}

/* the error in its unit (ulp, relative or absolute), as the metric prints */
static void
efmt(char *buf, size_t n, double e)
{
	if (!isfinite(e))
		snprintf(buf, n, "inf");
	else if (F.w && F.rel)
		snprintf(buf, n, "%.3g ulp", e);
	else
		snprintf(buf, n, "%.3g%s", e, F.rel ? " rel" : "");
}

/* live feedback: stdout, and stderr too inside a JSON request, where
 * stdout is captured until the answer (a client shows those lines live) */
static void
say(const char *fmt, ...)
{
	char line[600];
	va_list ap;

	va_start(ap, fmt);
	vsnprintf(line, sizeof line, fmt, ap);
	va_end(ap);
	fputs(line, stdout);
	fputc('\n', stdout);
	fflush(stdout);
	if (rep_on) {
		fprintf(stderr, "ucas: adamfit: %s\n", line);
		fflush(stderr);
	}
}

/* ---- shapes ---- */

static int
sh_add(struct shape *s, int op, int a, int b, int c)
{
	int i = s->n;

	if (i >= AF_MAXN)
		return -1;
	s->op[i] = (uint8_t)op;
	s->a[i] = (uint8_t)a;
	s->b[i] = (uint8_t)b;
	s->c[i] = (uint8_t)c;
	s->k[i] = 0;
	s->n++;
	return i;
}

static int
sh_const(struct shape *s)
{
	int i;

	if (s->nk >= AF_MAXK)
		return -1;
	if ((i = sh_add(s, Q_C, 0, 0, 0)) < 0)
		return -1;
	s->k[i] = (uint8_t)s->nk++;
	return i;
}

static void
sh_init(struct shape *s, const char *kind)
{
	memset(s, 0, sizeof *s);
	s->n = 1;		/* node 0: x */
	s->op[0] = Q_X;
	snprintf(s->kind, sizeof s->kind, "%s", kind);
}

/* does node i depend on x */
static int
has_x(const struct shape *s, int i)
{
	int j, ar;

	if (s->op[i] == Q_X)
		return 1;
	if (s->op[i] == Q_C)
		return 0;
	ar = qarity[s->op[i]];
	for (j = 0; j < ar; j++)
		if (has_x(s, j == 0 ? s->a[i] : j == 1 ? s->b[i] : s->c[i]))
			return 1;
	return 0;
}

/*
 * The canonical text of node i, constants as c, the operands of + and *
 * (and fma's first two) in order: two shapes are the same when their
 * texts are.  0 when too long.
 */
static int
canon(const struct shape *s, int i, char *out, size_t n)
{
	char x[2][512], y[512];
	int op = s->op[i];

	if (op == Q_X)
		return snprintf(out, n, "x") < (int)n;
	if (op == Q_C)
		return snprintf(out, n, "c") < (int)n;
	if (qarity[op] == 1) {
		if (!canon(s, s->a[i], x[0], sizeof x[0]))
			return 0;
		return snprintf(out, n, "%s(%s)", qname[op], x[0]) < (int)n;
	}
	if (!canon(s, s->a[i], x[0], sizeof x[0]) ||
	    !canon(s, s->b[i], x[1], sizeof x[1]))
		return 0;
	if ((op == Q_ADD || op == Q_MUL || op == Q_FMA) &&
	    strcmp(x[0], x[1]) > 0) {
		memcpy(y, x[0], sizeof y);
		memcpy(x[0], x[1], sizeof y);
		memcpy(x[1], y, sizeof y);
	}
	if (op == Q_FMA) {
		if (!canon(s, s->c[i], y, sizeof y))
			return 0;
		return snprintf(out, n, "fma(%s,%s,%s)", x[0], x[1], y) <
		    (int)n;
	}
	return snprintf(out, n, "(%s%s%s)", x[0], qname[op], x[1]) < (int)n;
}

static uint64_t
hash_str(const char *s)
{
	uint64_t h = 1469598103934665603ull;

	while (*s)
		h = (h ^ (uint8_t)*s++) * 1099511628211ull;
	return h | 1;
}

/* the shape is new: remember it */
static int
seen_add(uint64_t h)
{
	uint32_t i, m;

	if ((uint32_t)F.nsh * 2 + 2 > F.capseen) {
		uint64_t *old = F.seen;
		uint32_t oc = F.capseen, j;
		F.capseen = F.capseen ? F.capseen * 2 : 8192;
		F.seen = xcalloc(F.capseen, sizeof *F.seen);
		for (j = 0; j < oc; j++)
			if (old[j]) {
				m = F.capseen - 1;
				for (i = (uint32_t)old[j] & m; F.seen[i];
				    i = (i + 1) & m)
					;
				F.seen[i] = old[j];
			}
		free(old);
	}
	m = F.capseen - 1;
	for (i = (uint32_t)h & m; F.seen[i]; i = (i + 1) & m)
		if (F.seen[i] == h)
			return 0;
	F.seen[i] = h;
	return 1;
}

/* a shape worth training: x in it, no operation on constants alone, no
 * x - x, x / x; new */
static int
sh_keep(const struct shape *s)
{
	char key[2048];
	int i;

	if (s->n < 2 || !has_x(s, s->n - 1))
		return 0;
	for (i = 1; i < s->n; i++) {
		int op = s->op[i];
		if (op == Q_C || op == Q_X)
			continue;
		if (!has_x(s, i))
			return 0;	/* constants folded: one constant does */
		if ((op == Q_SUB || op == Q_DIV) && s->a[i] == s->b[i])
			return 0;
		if (!(F.ops & (1u << op)))
			return 0;
	}
	if (!canon(s, s->n - 1, key, sizeof key))
		return 0;
	return seen_add(hash_str(key));
}

static struct shape *
sh_push(const struct shape *s)
{
	if (!sh_keep(s))
		return NULL;
	if (F.nsh == F.capsh) {
		F.capsh = F.capsh ? F.capsh * 2 : 1024;
		F.sh = xrealloc(F.sh, (size_t)F.capsh * sizeof *F.sh);
	}
	F.sh[F.nsh] = *s;
	return &F.sh[F.nsh++];
}

/* Horner in v (a node) with nk constants: c0 + v*(c1 + v*(...)) */
static int
horner(struct shape *s, int v, int nk)
{
	int acc = sh_const(s), j;

	for (j = 1; j < nk && acc >= 0; j++) {
		int m = sh_add(s, Q_MUL, acc, v, 0), c = sh_const(s);
		if (m < 0 || c < 0)
			return -1;
		acc = sh_add(s, Q_ADD, m, c, 0);
	}
	return acc;
}

static void
seeds(void)
{
	struct shape s;
	int d, e, r, sq;

	for (d = 1; d <= AF_MAXK; d++) {
		/* c0 + x*(...) of d constants */
		sh_init(&s, "poly");
		if (horner(&s, 0, d) >= 0)
			sh_push(&s);
		/* odd: x*P(x*x); even: P(x*x) */
		sh_init(&s, "odd");
		sq = sh_add(&s, Q_MUL, 0, 0, 0);
		if ((r = horner(&s, sq, d)) >= 0 && sh_add(&s, Q_MUL, r, 0, 0) >= 0)
			sh_push(&s);
		if (d > 1) {
			sh_init(&s, "even");
			sq = sh_add(&s, Q_MUL, 0, 0, 0);
			if (horner(&s, sq, d) >= 0)
				sh_push(&s);
		}
	}
	/* rationals P/Q, Q's Horner starting at x (its constant term is the
	 * scale P already has): (a0 + x a1 ...) / (1-ish) */
	for (d = 1; d <= 5; d++)
		for (e = 1; e <= 4 && d + e <= AF_MAXK; e++) {
			int p, q;
			sh_init(&s, "rational");
			p = horner(&s, 0, d);
			q = horner(&s, 0, e + 1);
			if (p >= 0 && q >= 0 && s.nk <= AF_MAXK &&
			    sh_add(&s, Q_DIV, p, q, 0) >= 0)
				sh_push(&s);
		}
	if (F.ops & (1u << Q_SQRT))
		for (d = 1; d <= 4; d++) {
			int t, p;
			/* P(x) * sqrt(x), P(sqrt(x)) */
			sh_init(&s, "sqrt");
			t = sh_add(&s, Q_SQRT, 0, 0, 0);
			p = horner(&s, 0, d);
			if (t >= 0 && p >= 0 && sh_add(&s, Q_MUL, p, t, 0) >= 0)
				sh_push(&s);
			sh_init(&s, "sqrt");
			t = sh_add(&s, Q_SQRT, 0, 0, 0);
			if (horner(&s, t, d + 1) >= 0)
				sh_push(&s);
		}
}

/* a random expression of about `size` nodes from the enabled operations */
static int
gen(struct shape *s, int size)
{
	int ops[Q_NOPS], nops = 0, op, i, a, b, c, left;
	double u;

	if (size <= 1 || s->n >= AF_MAXN - 2) {
		u = ns_unif(&F.rng);
		if (u < 0.55 || s->nk >= AF_MAXK)
			return 0;		/* x */
		return sh_const(s);
	}
	for (i = Q_ADD; i < Q_NOPS; i++)
		if ((F.ops & (1u << i)) && qarity[i] < size)
			ops[nops++] = i;
	if (nops == 0)
		return 0;
	op = ops[(int)(ns_unif(&F.rng) * nops) % nops];
	left = size - 1;
	if (qarity[op] == 1) {
		a = gen(s, left);
		return a < 0 ? -1 : sh_add(s, op, a, 0, 0);
	}
	if (qarity[op] == 2) {
		int la = 1 + (int)(ns_unif(&F.rng) * (left - 1));
		a = gen(s, la);
		b = gen(s, left - la);
		return a < 0 || b < 0 ? -1 : sh_add(s, op, a, b, 0);
	}
	{
		int la = 1 + (int)(ns_unif(&F.rng) * (left - 2));
		int lb = 1 + (int)(ns_unif(&F.rng) * (left - la - 1));
		a = gen(s, la);
		b = gen(s, lb);
		c = gen(s, left - la - lb);
		return a < 0 || b < 0 || c < 0 ? -1 : sh_add(s, op, a, b, c);
	}
}

static void
randoms(void)
{
	struct shape s;
	long tries;

	for (tries = 0; F.nsh < F.count && tries < (long)F.count * 60;
	    tries++) {
		int size = 2 + (int)(ns_unif(&F.rng) * (F.size - 1));
		sh_init(&s, "random");
		if (gen(&s, size) < 0)
			continue;
		sh_push(&s);
	}
}

/* ---- the fit: forward, one reverse sweep, Adam ---- */

static double vv[AF_MAXN][AF_T], gg[AF_MAXN][AF_T];

/* forward on the training sample; 0 where something is not finite */
static int
forward(const struct shape *s, const double *th)
{
	int i, t;

	for (t = 0; t < F.nt; t++)
		vv[0][t] = F.tx[t];
	for (i = 1; i < s->n; i++) {
		const double *a = vv[s->a[i]], *b = vv[s->b[i]], *c = vv[s->c[i]];
		double *v = vv[i];
		switch (s->op[i]) {
		case Q_C:
			for (t = 0; t < F.nt; t++)
				v[t] = th[s->k[i]];
			break;
		case Q_ADD: for (t = 0; t < F.nt; t++) v[t] = a[t] + b[t]; break;
		case Q_SUB: for (t = 0; t < F.nt; t++) v[t] = a[t] - b[t]; break;
		case Q_MUL: for (t = 0; t < F.nt; t++) v[t] = a[t] * b[t]; break;
		case Q_DIV: for (t = 0; t < F.nt; t++) v[t] = a[t] / b[t]; break;
		case Q_FMA:
			for (t = 0; t < F.nt; t++)
				v[t] = a[t] * b[t] + c[t];
			break;
		case Q_SQRT:
			for (t = 0; t < F.nt; t++)
				v[t] = a[t] >= 0 ? sqrt(a[t]) : NAN;
			break;
		case Q_EXP: for (t = 0; t < F.nt; t++) v[t] = exp(a[t]); break;
		case Q_LOG:
			for (t = 0; t < F.nt; t++)
				v[t] = a[t] > 0 ? log(a[t]) : NAN;
			break;
		case Q_SIN: for (t = 0; t < F.nt; t++) v[t] = sin(a[t]); break;
		case Q_COS: for (t = 0; t < F.nt; t++) v[t] = cos(a[t]); break;
		case Q_ABS: for (t = 0; t < F.nt; t++) v[t] = fabs(a[t]); break;
		}
	}
	for (t = 0; t < F.nt; t++)
		if (!isfinite(vv[s->n - 1][t]))
			return 0;
	return 1;
}

/*
 * The loss (1/p) log sum |r_t|^p, r_t = (R(x_t) - y_t) w_t, and its
 * gradient over the constants in g; returns max |r_t| (inf: not finite).
 */
static double
loss_grad(const struct shape *s, const double *th, double p, double *g)
{
	int i, t, root = s->n - 1;
	double M = 0, sum = 0, r[AF_T];

	if (!forward(s, th))
		return INFINITY;
	for (t = 0; t < F.nt; t++) {
		r[t] = (vv[root][t] - F.ty[t]) * F.tw[t];
		if (fabs(r[t]) > M)
			M = fabs(r[t]);
	}
	for (i = 0; i < s->nk; i++)
		g[i] = 0;
	if (M == 0)
		return 0;
	for (t = 0; t < F.nt; t++)
		sum += pow(fabs(r[t]) / M, p);
	for (i = 0; i < s->n; i++)
		memset(gg[i], 0, sizeof(double) * (size_t)F.nt);
	for (t = 0; t < F.nt; t++) {
		double q = r[t] / M;
		/* d/dr (1/p) log sum |r|^p = |r|^(p-1) sign(r) / sum |r|^p */
		gg[root][t] = pow(fabs(q), p - 1) * (q < 0 ? -1 : 1) / (sum * M) *
		    F.tw[t];
	}
	for (i = root; i >= 1; i--) {
		double *gi = gg[i], *ga = gg[s->a[i]], *gb = gg[s->b[i]],
		    *gc = gg[s->c[i]];
		const double *va = vv[s->a[i]], *vb = vv[s->b[i]], *v = vv[i];
		switch (s->op[i]) {
		case Q_C:
			for (t = 0; t < F.nt; t++)
				g[s->k[i]] += gi[t];
			break;
		case Q_ADD:
			for (t = 0; t < F.nt; t++)
				ga[t] += gi[t], gb[t] += gi[t];
			break;
		case Q_SUB:
			for (t = 0; t < F.nt; t++)
				ga[t] += gi[t], gb[t] -= gi[t];
			break;
		case Q_MUL:
			for (t = 0; t < F.nt; t++) {
				ga[t] += gi[t] * vb[t];
				gb[t] += gi[t] * va[t];
			}
			break;
		case Q_DIV:
			for (t = 0; t < F.nt; t++) {
				ga[t] += gi[t] / vb[t];
				gb[t] -= gi[t] * v[t] / vb[t];
			}
			break;
		case Q_FMA:
			for (t = 0; t < F.nt; t++) {
				ga[t] += gi[t] * vb[t];
				gb[t] += gi[t] * va[t];
				gc[t] += gi[t];
			}
			break;
		case Q_SQRT:
			for (t = 0; t < F.nt; t++)
				ga[t] += v[t] > 0 ? gi[t] * 0.5 / v[t] : 0;
			break;
		case Q_EXP:
			for (t = 0; t < F.nt; t++)
				ga[t] += gi[t] * v[t];
			break;
		case Q_LOG:
			for (t = 0; t < F.nt; t++)
				ga[t] += gi[t] / va[t];
			break;
		case Q_SIN:
			for (t = 0; t < F.nt; t++)
				ga[t] += gi[t] * cos(va[t]);
			break;
		case Q_COS:
			for (t = 0; t < F.nt; t++)
				ga[t] -= gi[t] * sin(va[t]);
			break;
		case Q_ABS:
			for (t = 0; t < F.nt; t++)
				ga[t] += va[t] < 0 ? -gi[t] : gi[t];
			break;
		}
	}
	for (i = 0; i < s->nk; i++)
		if (!isfinite(g[i]))
			return INFINITY;
	return M;
}

/* a normal deviate from twelve uniforms (no libm in the loop) */
static double
gauss(void)
{
	double z = -6;
	int i;

	for (i = 0; i < 12; i++)
		z += ns_unif(&F.rng);
	return z;
}

/*
 * Adam over the constants from th: steps steps, the step lr decaying to a
 * tenth, p from p0 to p1 halfway.  th ends at the best point seen (by the
 * largest residual); returns that residual.
 */
static double
adam(const struct shape *s, double *th, int steps, double lr, double p0,
    double p1)
{
	double m[AF_MAXK] = {0}, v[AF_MAXK] = {0}, g[AF_MAXK], best[AF_MAXK];
	double be = INFINITY, b1t = 1, b2t = 1;
	const double b1 = 0.9, b2 = 0.999;
	int st, i;

	memcpy(best, th, sizeof best);
	for (st = 0; st <= steps; st++) {
		double p = st < steps * 4 / 10 ? p0 : p1;
		double e = loss_grad(s, th, p, g), a;
		if (!isfinite(e)) {
			if (st == 0)
				return INFINITY;
			break;	/* left the domain: keep the best so far */
		}
		if (e < be) {
			be = e;
			memcpy(best, th, sizeof best);
		}
		if (st == steps || e == 0)
			break;
		b1t *= b1;
		b2t *= b2;
		a = lr * (1 - 0.9 * st / steps);
		for (i = 0; i < s->nk; i++) {
			double mh, vh;
			m[i] = b1 * m[i] + (1 - b1) * g[i];
			v[i] = b2 * v[i] + (1 - b2) * g[i] * g[i];
			mh = m[i] / (1 - b1t);
			vh = v[i] / (1 - b2t);
			th[i] -= a * mh / (sqrt(vh) + 1e-300);
		}
	}
	memcpy(th, best, sizeof best);
	return be;
}

/* stage 1: a few starts, the best kept */
static void
train(struct shape *s)
{
	double th[AF_MAXK], e;
	int r, i;

	s->terr = INFINITY;
	for (r = 0; r < F.restarts; r++) {
		for (i = 0; i < AF_MAXK; i++)
			th[i] = r == 0 ? 0.5 : gauss();
		e = adam(s, th, F.steps, F.lr, 2, 8);
		if (e < s->terr) {
			s->terr = e;
			memcpy(s->th, th, sizeof th);
		}
	}
	s->ok = isfinite(s->terr);
}

/* the training residual in the metric's unit: ulps of f's format when
 * relative (one ulp of a relative 2^(1 - prec) at most) */
static double
tunit(double r)
{
	return F.w && F.rel ? r * ldexp(1, F.prec - 1) : r;
}

/* ---- ucas expressions: text, definition, price ---- */

static void
text(const struct shape *s, int i, const double *th, int round, struct sbuf *b)
{
	char k[48];
	int op = s->op[i];

	switch (op) {
	case Q_X:
		sb_puts(b, "x");
		return;
	case Q_C:
		if (th == NULL)
			snprintf(k, sizeof k, "c%d", s->k[i]);
		else
			kfmt(k, sizeof k, round ? rnd(F.w, th[s->k[i]]) : th[s->k[i]]);
		sb_puts(b, k[0] == '-' ? "(" : "");
		sb_puts(b, k);
		sb_puts(b, k[0] == '-' ? ")" : "");
		return;
	}
	if (qarity[op] == 1) {
		sb_printf(b, "%s(", qname[op]);
		text(s, s->a[i], th, round, b);
		sb_puts(b, ")");
		return;
	}
	if (op == Q_FMA) {
		sb_puts(b, "fma(");
		text(s, s->a[i], th, round, b);
		sb_puts(b, ", ");
		text(s, s->b[i], th, round, b);
		sb_puts(b, ", ");
		text(s, s->c[i], th, round, b);
		sb_puts(b, ")");
		return;
	}
	{
		/* parentheses only where precedence needs them */
		int pr = op == Q_ADD || op == Q_SUB ? 1 : 2;
		int la = s->op[s->a[i]], lb = s->op[s->b[i]];
		int pa = la == Q_ADD || la == Q_SUB ? 1 : la == Q_MUL || la == Q_DIV ? 2 : 3;
		int pb = lb == Q_ADD || lb == Q_SUB ? 1 : lb == Q_MUL || lb == Q_DIV ? 2 : 3;
		int qa = pa < pr, qb = pb < pr || (pb == pr && (op == Q_SUB ||
		    op == Q_DIV));
		sb_puts(b, qa ? "(" : "");
		text(s, s->a[i], th, round, b);
		sb_printf(b, "%s %s ", qa ? ")" : "", qname[op]);
		sb_puts(b, qb ? "(" : "");
		text(s, s->b[i], th, round, b);
		sb_puts(b, qb ? ")" : "");
	}
}

/* a shape's text with its constants (th) or as c0, c1 ... (NULL) */
static char *
shape_text(const struct shape *s, const double *th)
{
	struct sbuf b = {0};

	text(s, s->n - 1, th, th != NULL && F.w != 0, &b);
	return b.p;
}

static struct func *
define(const char *name, const char *body)
{
	jmp_buf saved;
	struct toks *st = diag_toks;
	const char *sf = diag_file;
	uint32_t stok = diag_tok;
	struct sbuf b = {0};
	char lo[48], hi[48];
	struct func *f;
	uint32_t sym = sym_cstr(name);

	kfmt(lo, sizeof lo, F.lo);
	kfmt(hi, sizeof hi, F.hi);
	sb_printf(&b, "%s(x: %s in %s..%s) = %s\n", name, F.w == 32 ? "f32" :
	    F.w == 64 ? "f64" : "real", lo, hi, body);
	if ((f = func_find(sym)) != NULL)
		f->body = 0;
	note_mute++;
	memcpy(saved, fail_jmp, sizeof saved);
	run_source(b.p, "<adamfit>", 0);
	memcpy(fail_jmp, saved, sizeof saved);
	note_mute--;
	diag_toks = st;
	diag_file = sf;
	diag_tok = stok;
	free(b.p);
	f = func_find(sym);
	if (f == NULL || f->body == 0)
		return NULL;
	return f;
}

/* drop a function this command made for its own use */
static void
forget(const char *name)
{
	uint32_t sym = sym_cstr(name);
	int i;

	for (i = 0; i < nfuncs; i++)
		if (funcs[i].name == sym) {
			memmove(&funcs[i], &funcs[i + 1],
			    (size_t)(nfuncs - i - 1) * sizeof *funcs);
			nfuncs--;
			return;
		}
}

#define TMP "_adamfit_"

static double
shape_cost(const struct shape *s)
{
	double th[AF_MAXK], c;
	struct func *f;
	char *t;
	int i;

	for (i = 0; i < AF_MAXK; i++)
		th[i] = 0.75 + i;	/* any constants: the price is the shape's */
	t = shape_text(s, th);
	f = define(TMP, t);
	free(t);
	c = f ? approx_price(f->body) : INFINITY;
	return c;
}

/* ---- measuring ---- */

static void
measure(struct shape *s, nid body)
{
	struct plan p;
	nid roots[1];
	int64_t *in_i = xcalloc((size_t)MAXP * CH, sizeof *in_i);
	double *in_r = xcalloc((size_t)MAXP * CH, sizeof *in_r);
	uint32_t base, i, np, loc;
	double e = 0;

	roots[0] = body;
	plan_build(&p, roots, 1, 0);
	loc = p.root[0];
	s->bad = 0;
	for (base = 0; base < (uint32_t)F.nm; base += CH) {
		np = (uint32_t)F.nm - base < CH ? (uint32_t)F.nm - base : CH;
		for (i = 0; i < np; i++)
			in_r[i] = F.mx[base + i];
		plan_run(&p, np, in_i, in_r);
		for (i = 0; i < np; i++) {
			ld y = F.my[base + i], v, ae, d;
			if (!isfinite(y))
				continue;
			v = COLR(&p, loc)[i];
			if ((COLF(&p, loc)[i] & F_UNDEF) || !isfinite(v)) {
				s->bad++;
				continue;
			}
			ae = fabsl(v - y);
			if (F.w && F.rel)
				d = ae / ulp_of(y);
			else if (F.rel)
				d = y != 0 ? ae / fabsl(y) : (ae == 0 ? 0 : INFINITY);
			else
				d = ae;
			if (d > e)
				e = (double)d;
		}
	}
	plan_free(&p);
	free(in_i);
	free(in_r);
	s->merr = s->bad ? INFINITY : e;
}

/* n training points, denser near the ends (smoothstep), in the format;
 * returns how many are usable */
static int
sample(int n)
{
	int i;

	F.nt = 0;
	for (i = 0; i < n; i++) {
		double t = (double)i / (n - 1), u = t * t * (3 - 2 * t);
		double x = rnd(F.w, F.lo + (F.hi - F.lo) * u), y;
		y = (double)lref_eval(&F.ref, x);
		if (!isfinite(y))
			continue;
		if (F.rel && y == 0)
			continue;	/* exact there or not: measured below */
		F.tx[F.nt] = x;
		F.ty[F.nt] = y;
		F.tw[F.nt] = F.rel ? 1 / fabs(y) : 1;
		F.nt++;
	}
	return F.nt;
}

/* ---- the polish: Levenberg-Marquardt, then Lawson's reweighting ----
 *
 * Adam explores (every shape, from random starts); for the shapes kept for
 * stage 2 the local optimum is then found precisely: Levenberg-Marquardt on
 * the weighted squares, the Jacobian by forward-mode derivatives, and
 * Lawson's iteration (each point's weight times its error, again) towards
 * the smallest largest error. */

static double dv[AF_MAXK][AF_MAXN][AF_T];

/* the residuals e_t = (R - y) w_t and their Jacobian J[k][t]; 0 when not
 * finite */
static int
jacobian(const struct shape *s, const double *th, double *e, double J[][AF_T])
{
	int i, k, t, root = s->n - 1;

	if (!forward(s, th))
		return 0;
	for (k = 0; k < s->nk; k++) {
		double (*d)[AF_T] = dv[k];
		for (t = 0; t < F.nt; t++)
			d[0][t] = 0;
		for (i = 1; i < s->n; i++) {
			const double *a = vv[s->a[i]], *b = vv[s->b[i]], *v = vv[i];
			const double *da = d[s->a[i]], *db = d[s->b[i]], *dc = d[s->c[i]];
			double *o = d[i];
			switch (s->op[i]) {
			case Q_C:
				for (t = 0; t < F.nt; t++)
					o[t] = s->k[i] == k;
				break;
			case Q_ADD: for (t = 0; t < F.nt; t++) o[t] = da[t] + db[t]; break;
			case Q_SUB: for (t = 0; t < F.nt; t++) o[t] = da[t] - db[t]; break;
			case Q_MUL:
				for (t = 0; t < F.nt; t++)
					o[t] = da[t] * b[t] + a[t] * db[t];
				break;
			case Q_DIV:
				for (t = 0; t < F.nt; t++)
					o[t] = (da[t] - v[t] * db[t]) / b[t];
				break;
			case Q_FMA:
				for (t = 0; t < F.nt; t++)
					o[t] = da[t] * b[t] + a[t] * db[t] + dc[t];
				break;
			case Q_SQRT:
				for (t = 0; t < F.nt; t++)
					o[t] = v[t] > 0 ? da[t] * 0.5 / v[t] : 0;
				break;
			case Q_EXP: for (t = 0; t < F.nt; t++) o[t] = da[t] * v[t]; break;
			case Q_LOG: for (t = 0; t < F.nt; t++) o[t] = da[t] / a[t]; break;
			case Q_SIN:
				for (t = 0; t < F.nt; t++)
					o[t] = da[t] * cos(a[t]);
				break;
			case Q_COS:
				for (t = 0; t < F.nt; t++)
					o[t] = -da[t] * sin(a[t]);
				break;
			case Q_ABS:
				for (t = 0; t < F.nt; t++)
					o[t] = a[t] < 0 ? -da[t] : da[t];
				break;
			}
		}
		for (t = 0; t < F.nt; t++) {
			J[k][t] = d[root][t] * F.tw[t];
			if (!isfinite(J[k][t]))
				return 0;
		}
	}
	for (t = 0; t < F.nt; t++)
		e[t] = (vv[root][t] - F.ty[t]) * F.tw[t];
	return 1;
}

/* solve A x = b (n <= AF_MAXK) by elimination with partial pivoting */
static int
solve(int n, double A[][AF_MAXK], double *b, double *x)
{
	int i, j, k;

	for (k = 0; k < n; k++) {
		int pv = k;
		for (i = k + 1; i < n; i++)
			if (fabs(A[i][k]) > fabs(A[pv][k]))
				pv = i;
		if (!(fabs(A[pv][k]) > 0))
			return 0;
		if (pv != k) {
			for (j = 0; j < n; j++) {
				double t = A[k][j];
				A[k][j] = A[pv][j];
				A[pv][j] = t;
			}
			{
				double t = b[k];
				b[k] = b[pv];
				b[pv] = t;
			}
		}
		for (i = k + 1; i < n; i++) {
			double f = A[i][k] / A[k][k];
			for (j = k; j < n; j++)
				A[i][j] -= f * A[k][j];
			b[i] -= f * b[k];
		}
	}
	for (i = n - 1; i >= 0; i--) {
		double v = b[i];
		for (j = i + 1; j < n; j++)
			v -= A[i][j] * x[j];
		x[i] = v / A[i][i];
	}
	for (i = 0; i < n; i++)
		if (!isfinite(x[i]))
			return 0;
	return 1;
}

/* weighted squares sum u_t e_t^2 */
static double
wsse(const double *e, const double *u)
{
	double s2 = 0;
	int t;

	for (t = 0; t < F.nt; t++)
		s2 += u[t] * e[t] * e[t];
	return s2;
}

/* Levenberg-Marquardt on sum u_t e_t^2 from th, iters steps at most */
static void
lm(const struct shape *s, double *th, const double *u, int iters)
{
	static double J[AF_MAXK][AF_T];
	double e[AF_T], lam = 1e-3, cur;
	int it, i, j, t, n = s->nk;

	if (!jacobian(s, th, e, J))
		return;
	cur = wsse(e, u);
	for (it = 0; it < iters; it++) {
		double A[AF_MAXK][AF_MAXK], g[AF_MAXK], d[AF_MAXK], tr[AF_MAXK];
		double ne[AF_T];
		static double NJ[AF_MAXK][AF_T];
		for (i = 0; i < n; i++) {
			g[i] = 0;
			for (t = 0; t < F.nt; t++)
				g[i] -= u[t] * J[i][t] * e[t];
			for (j = 0; j < n; j++) {
				double a = 0;
				for (t = 0; t < F.nt; t++)
					a += u[t] * J[i][t] * J[j][t];
				A[i][j] = a;
			}
		}
		for (;;) {
			double B[AF_MAXK][AF_MAXK], c[AF_MAXK];
			for (i = 0; i < n; i++) {
				for (j = 0; j < n; j++)
					B[i][j] = A[i][j];
				B[i][i] += lam * (A[i][i] > 0 ? A[i][i] : 1);
				c[i] = g[i];
			}
			if (solve(n, B, c, d)) {
				for (i = 0; i < n; i++)
					tr[i] = th[i] + d[i];
				if (jacobian(s, tr, ne, NJ) && wsse(ne, u) < cur) {
					memcpy(th, tr, sizeof(double) * (size_t)n);
					memcpy(e, ne, sizeof(double) * (size_t)F.nt);
					memcpy(J, NJ, sizeof J);
					cur = wsse(e, u);
					lam = lam / 3 < 1e-12 ? 1e-12 : lam / 3;
					break;
				}
			}
			lam *= 4;
			if (lam > 1e12)
				return;	/* no step helps: a minimum */
		}
	}
}

/* LM, then Lawson's reweighting towards minimax; th ends at the best (by
 * the largest |e_t|), which is returned */
static double
polish(const struct shape *s, double *th)
{
	static double J[AF_MAXK][AF_T];
	double u[AF_T], e[AF_T], best[AF_MAXK], be = INFINITY, sum;
	int r, t;

	for (t = 0; t < F.nt; t++)
		u[t] = 1.0 / F.nt;
	memcpy(best, th, sizeof best);
	for (r = 0; r < 24; r++) {
		double m = 0;
		lm(s, th, u, r == 0 ? 60 : 12);
		if (!jacobian(s, th, e, J))
			break;
		for (t = 0; t < F.nt; t++)
			if (fabs(e[t]) > m)
				m = fabs(e[t]);
		if (m < be) {
			be = m;
			memcpy(best, th, sizeof best);
		}
		if (m == 0)
			break;
		/* Lawson: weights times |e|, normalised */
		sum = 0;
		for (t = 0; t < F.nt; t++)
			sum += u[t] *= fabs(e[t]) / m + 1e-300;
		if (!(sum > 0))
			break;
		for (t = 0; t < F.nt; t++)
			u[t] /= sum;
	}
	memcpy(th, best, sizeof best);
	return be;
}

static double
score_of(double cost, double err)
{
	if (!isfinite(err) || !isfinite(cost))
		return INFINITY;
	return F.wcost * cost / F.c0 + F.werr * log2(1 + err / F.tol);
}

/* ---- the run ---- */

static int
by_score1(const void *a, const void *b)
{
	const struct shape *x = a, *y = b;

	return (x->score1 > y->score1) - (x->score1 < y->score1);
}

/* stage 2's choice first, then by score1 */
static int
by_pick(const void *a, const void *b)
{
	const struct shape *x = a, *y = b;

	if (x->pick != y->pick)
		return y->pick - x->pick;
	return (x->score1 > y->score1) - (x->score1 < y->score1);
}

static int
by_cost_err(const void *a, const void *b)
{
	const struct shape *x = a, *y = b;

	if (x->cost != y->cost)
		return (x->cost > y->cost) - (x->cost < y->cost);
	return (x->terr > y->terr) - (x->terr < y->terr);
}

static int
by_score(const void *a, const void *b)
{
	const struct shape *x = a, *y = b;

	return (x->score > y->score) - (x->score < y->score);
}

/* the candidates no other beats in both cost and error, as a line */
static int
by_pair(const void *a, const void *b)
{
	const double *x = a, *y = b;

	return (x[0] > y[0]) - (x[0] < y[0]);
}

static void
front_text(struct sbuf *b, struct shape *s, int n, int stage2)
{
	int i, j, k = 0, np = 0;
	char e[32];
	double (*pr)[2] = xmalloc((size_t)(n + 1) * sizeof *pr);

	for (i = 0; i < n; i++) {
		double ci = s[i].cost, ei = stage2 ? s[i].merr :
		    tunit(s[i].terr);
		int dom = !isfinite(ei) || !s[i].ok;
		for (j = 0; j < n && !dom; j++) {
			double cj = s[j].cost, ej = stage2 ? s[j].merr :
			    tunit(s[j].terr);
			if (j != i && s[j].ok && cj <= ci && ej <= ei &&
			    (cj < ci || ej < ei || j < i))
				dom = 1;
		}
		if (dom)
			continue;
		pr[np][0] = ci;
		pr[np][1] = ei;
		np++;
	}
	/* cheapest first */
	qsort(pr, (size_t)np, sizeof *pr, by_pair);
	for (i = 0; i < np; i++) {
		efmt(e, sizeof e, pr[i][1]);
		sb_printf(b, "%s%g/%s", k++ ? ", " : "", pr[i][0], e);
		if (k >= 9 && i + 1 < np) {
			sb_puts(b, " ...");
			break;
		}
	}
	if (np == 0)
		sb_puts(b, "-");
	free(pr);
}

static void
run(void)
{
	int i, done = 0, nt = 0, n2, m2;
	double best = INFINITY, best2 = INFINITY, next_report;
	char e2[32];
	struct shape *s;
	char e[32];
	nid tbody = F.f.body;
	struct sbuf b = {0};

	clock_gettime(CLOCK_MONOTONIC, &F.t0);
	ns_seed(&F.rng, F.seed);
	/* the samples: training points denser near the ends (smoothstep), the
	 * measuring points evenly spaced, both in the format */
	if (sample(AF_T1) < 8)
		fail("adamfit: %s is undefined (or 0, for a relative error) at most "
		    "points of [%g, %g]", F.fname, F.lo, F.hi);
	F.nm = AF_NV;
	F.mx = xmalloc((size_t)F.nm * sizeof *F.mx);
	F.my = xmalloc((size_t)F.nm * sizeof *F.my);
	for (i = 0; i < F.nm; i++) {
		F.mx[i] = rnd(F.w, F.lo + (F.hi - F.lo) * i / (F.nm - 1));
		F.my[i] = lref_eval(&F.ref, F.mx[i]);
	}
	F.c0 = approx_price(tbody);
	if (!(F.c0 > 0))
		F.c0 = 1;

	seeds();
	randoms();
	printf("adamfit %s on [%.9g, %.9g] as %s: %d shapes of up to %d nodes, "
	    "ops", F.fname, F.lo, F.hi, F.w == 32 ? "f32" : F.w == 64 ? "f64" :
	    "real", F.nsh, F.size);
	for (i = Q_ADD; i < Q_NOPS; i++)
		if (F.ops & (1u << i))
			printf(" %s", qname[i]);
	printf("\n");
	printf("  fit: Adam (b1 0.9, b2 0.999, step %g decaying to a tenth), %d "
	    "steps from %d starts, p-norm 2 then 8 of the %s residual on %d "
	    "points; the best %d again on %d points, p up to 32, then polished "
	    "(Levenberg-Marquardt, Lawson)\n", F.lr, F.steps, F.restarts,
	    F.rel ? "relative" : "absolute", F.nt, F.count / 4 < 8 ? 8 :
	    F.count / 4 > AF_STAGE2 ? AF_STAGE2 : F.count / 4, AF_T2);
	printf("  score = %g * cost / %g (%s's cost under %s) + %g * log2(1 + "
	    "error / %s)\n", F.wcost, F.c0, F.fname, model_active() ?
	    sym_str(model_active()->name) : "-", F.werr, F.tolname);
	fflush(stdout);
	rep_begin("adamfit");
	rep_str("target", F.fname);
	rep_num("lo", F.lo);
	rep_num("hi", F.hi);
	rep_str("format", F.w == 32 ? "f32" : F.w == 64 ? "f64" : "real");
	rep_int("shapes", F.nsh);
	rep_num("wcost", F.wcost);
	rep_num("werr", F.werr);
	rep_num("cost_reference", F.c0);
	rep_num("tolerance", F.tol);

	/* stage 1 */
	next_report = F.nsh / 10.0;
	for (i = 0; i < F.nsh; i++) {
		s = &F.sh[i];
		s->cost = shape_cost(s);
		train(s);
		done++;
		s->score1 = s->ok ? score_of(s->cost, tunit(s->terr)) : INFINITY;
		if (s->ok)
			nt++;
		if (!F.autom && s->score1 < best) {
			char *t = shape_text(s, s->th);
			efmt(e, sizeof e, tunit(s->terr));
			say("  [%5d/%d] score %.3f  cost %g  error ~%s  %s  (%s)", done,
			    F.nsh, s->score1, s->cost, e, t, s->kind);
			free(t);
		}
		if (s->score1 < best)
			best = s->score1;
		if (!F.autom && done >= next_report && done < F.nsh) {
			sb_clear(&b);
			front_text(&b, F.sh, done, 0);
			say("  ... %d/%d shapes, %d fitted, best score %.3f, front "
			    "(cost/error): %s", done, F.nsh, nt, best, b.p ? b.p : "");
			next_report += F.nsh / 10.0;
		}
		if (F.secs > 0 && elapsed() > F.secs) {
			say("  stopped after %.1f s: %d of %d shapes fitted", F.secs,
			    done, F.nsh);
			break;
		}
	}
	F.nsh = done;
	rep_int("fitted", nt);

	/*
	 * stage 2: the best at every cost (Adam alone leaves shapes with many
	 * constants far from their optimum: a cost level is judged by its
	 * best), then the best scores, trained again and polished
	 */
	qsort(F.sh, (size_t)F.nsh, sizeof *F.sh, by_cost_err);
	/* a quarter of the shapes asked for, 8 to AF_STAGE2 */
	m2 = F.count / 4 < 8 ? 8 : F.count / 4 > AF_STAGE2 ? AF_STAGE2 : F.count / 4;
	n2 = 0;
	for (i = 0; i < F.nsh && n2 < m2 * 2 / 3; i++) {
		int j = i, k = 0;
		while (j < F.nsh && F.sh[j].cost == F.sh[i].cost) {
			if (F.sh[j].ok && k < AF_PERCOST && n2 < m2 * 2 / 3) {
				F.sh[j].pick = 1;
				k++;
				n2++;
			}
			j++;
		}
		i = j - 1;
	}
	qsort(F.sh, (size_t)F.nsh, sizeof *F.sh, by_score1);
	for (i = 0; i < F.nsh && n2 < m2; i++)
		if (F.sh[i].ok && !F.sh[i].pick) {
			F.sh[i].pick = 1;
			n2++;
		}
	qsort(F.sh, (size_t)F.nsh, sizeof *F.sh, by_pick);
	sample(AF_T2);
	if (!F.autom)
		say("  stage 2: the best %d shapes on %d points: Adam %d more steps, "
		    "then Levenberg-Marquardt and Lawson's reweighting", n2, F.nt,
		    F.steps * 10);
	for (i = 0; i < n2; i++) {
		struct func *f;
		char *t;
		double th[AF_MAXK], e;
		s = &F.sh[i];
		/* Adam on, nearer the largest error, then the polish from where
		 * it ends; the better of the two */
		s->terr = adam(s, s->th, F.steps * 10, F.lr * 0.2, 8, 32);
		memcpy(th, s->th, sizeof th);
		e = polish(s, th);
		if (e < s->terr) {
			s->terr = e;
			memcpy(s->th, th, sizeof th);
		}
		t = shape_text(s, s->th);
		f = define(TMP, t);
		free(t);
		if (f == NULL) {
			s->merr = INFINITY;
		} else {
			s->cost = approx_price(f->body);
			measure(s, f->body);
		}
		s->bound = -1;
		s->score = score_of(s->cost, s->merr);
		if (!F.autom && s->score < best2) {
			char *t = shape_text(s, s->th);
			efmt(e2, sizeof e2, s->merr);
			say("  [stage 2 %2d/%d] score %.3f  cost %g  error %s  %s  (%s)",
			    i + 1, n2, s->score, s->cost, e2, t, s->kind);
			free(t);
		}
		if (s->score < best2)
			best2 = s->score;
	}
	forget(TMP);
	qsort(F.sh, (size_t)n2, sizeof *F.sh, by_score);
	while (n2 > 0 && !isfinite(F.sh[n2 - 1].score))
		n2--;
	if (n2 == 0) {
		free(b.p);
		fail("adamfit: no shape could be fitted on [%g, %g]", F.lo, F.hi);
	}
	sb_clear(&b);
	front_text(&b, F.sh, n2, 1);
	printf("  measured on %d points: front (cost/error) %s\n", F.nm, b.p);

	/* the closest candidates: certified, ranked by the certified error */
	{
		int nl = n2 < F.list ? n2 : F.list;
		for (i = 0; i < nl; i++) {
			char nm[40], *t;
			struct func *f;
			struct acert ac;
			s = &F.sh[i];
			snprintf(nm, sizeof nm, "%s%d", F.name, i + 1);
			t = shape_text(s, s->th);
			f = define(nm, t);
			free(t);
			s->bound = -1;
			s->why[0] = 0;
			if (f && F.cert) {
				memset(&ac, 0, sizeof ac);
				acert_run(tbody, f->body, F.lo, F.hi, F.w, F.rel, 0, 0,
				    &ac);
				if (ac.ok)
					s->bound = ac.bound;
				else
					snprintf(s->why, sizeof s->why, "%s", ac.why);
			}
			s->score = score_of(s->cost, s->bound >= 0 ? s->bound :
			    s->merr);
		}
		/* certified bounds can reorder them; names follow the order */
		qsort(F.sh, (size_t)nl, sizeof *F.sh, by_score);
		printf("  %s candidates%s (defined as %s1 ...):\n", F.autom ?
		    "closest" : "best", F.cert ? ", their error certified on the "
		    "whole interval" : "", F.name);
		printf("  #   score   cost  measured      certified          shape\n");
		rep_list("candidates");
		for (i = 0; i < nl; i++) {
			char nm[40], me[32], ce[48], *t, *k;
			s = &F.sh[i];
			snprintf(nm, sizeof nm, "%s%d", F.name, i + 1);
			t = shape_text(s, s->th);
			k = shape_text(s, NULL);
			define(nm, t);
			efmt(me, sizeof me, s->merr);
			if (s->bound >= 0) {
				char bb[32];
				efmt(bb, sizeof bb, s->bound);
				snprintf(ce, sizeof ce, "<= %s", bb);
			} else
				snprintf(ce, sizeof ce, F.cert ? "not certified" :
				    "-");
			printf("  %-3d %-7.3f %-5g %-13s %-18s %s (%s)\n", i + 1,
			    s->score, s->cost, me, ce, k, s->kind);
			printf("      %s(x) = %s\n", nm, t);
			if (s->bound < 0 && s->why[0])
				printf("      not certified: %s\n", s->why);
			rep_obj(NULL);
			rep_str("name", nm);
			rep_str("expr", t);
			rep_str("shape", k);
			rep_str("kind", s->kind);
			rep_num("cost", s->cost);
			rep_num("error", s->merr);
			rep_bool("certified", s->bound >= 0);
			if (s->bound >= 0)
				rep_num("bound", s->bound);
			else if (s->why[0])
				rep_str("why", s->why);
			rep_num("score", s->score);
			rep_end();
			free(t);
			free(k);
		}
		rep_end();
		if (nl && F.sh[0].bound >= 0)
			rep_proof("symbolic", "the best candidate's error bound is "
			    "derived on the whole interval (acert)");
	}
	if (getenv("UCAS_NO_TIMES") == NULL)
		printf("  %.2f s\n", elapsed());
	free(b.p);
}

static void
reset(void)
{
	free(F.sh);
	free(F.seen);
	free(F.mx);
	free(F.my);
	if (F.ref.n)
		lref_free(&F.ref);
	memset(&F, 0, sizeof F);
}

static const char *const optwords[] = {"in", "as", "ops", "count", "size",
	"steps", "lr", "restarts", "wcost", "werr", "error", "ulp", "relative",
	"absolute", "auto", "list", "seed", "seconds", "name", "nocert", NULL};

static unsigned
op_bit(const char *w)
{
	int i;

	if (!strcmp(w, "add") || !strcmp(w, "+"))
		return 1u << Q_ADD;
	if (!strcmp(w, "sub") || !strcmp(w, "-"))
		return 1u << Q_SUB;
	if (!strcmp(w, "mul") || !strcmp(w, "*"))
		return 1u << Q_MUL;
	if (!strcmp(w, "div") || !strcmp(w, "/"))
		return 1u << Q_DIV;
	for (i = Q_FMA; i < Q_NOPS; i++)
		if (!strcmp(w, qname[i]))
			return 1u << i;
	return 0;
}

int
adamfit_command(struct P *p)
{
	struct func *f;
	uint32_t at = cmdp_pos(p);
	char w[32];
	int haverange = 0, metric = -1, fmt = -1;
	double lo = 0, hi = 0, tol_err = 0, tol_ulp = 0;

	if (!cmdp_word(p, w, sizeof w))
		return 0;
	if (strcmp(w, "adamfit") != 0 || func_find(sym_cstr(w))) {
		cmdp_seek(p, at);
		return 0;
	}
	reset();
	F.ops = 1u << Q_ADD | 1u << Q_SUB | 1u << Q_MUL | 1u << Q_DIV |
	    1u << Q_FMA | 1u << Q_SQRT;
	F.count = 2000;
	F.size = 9;
	F.steps = 200;
	F.restarts = 3;
	F.lr = 0.05;
	F.wcost = 0.8;
	F.werr = 0.5;
	F.list = 6;
	F.cert = 1;
	F.seed = stoch_seed();
	snprintf(F.name, sizeof F.name, "af");
	f = cmdp_func(p, optwords);
	F.f = *f;
	if (F.f.np != 1)
		fail("adamfit needs a function of one variable (%s has %d)",
		    F.f.anon ? "the expression" : sym_str(F.f.name), F.f.np);
	snprintf(F.fname, sizeof F.fname, "%s", F.f.anon ? node_str(F.f.body) :
	    sym_str(F.f.name));
	if (cmdp_kw(p, "in")) {
		lo = cmdp_number(p, optwords);
		if (!cmdp_tok(p, T_DOTDOT))
			fail("expected '..' in the interval");
		hi = cmdp_number(p, optwords);
		haverange = 1;
	}
	while (!cmdp_eos(p)) {
		cmdp_fail_here(p);
		if (cmdp_kw(p, "as")) {
			if (cmdp_kw(p, "f32") || cmdp_kw(p, "float"))
				fmt = 32;
			else if (cmdp_kw(p, "f64") || cmdp_kw(p, "double"))
				fmt = 64;
			else if (cmdp_kw(p, "real"))
				fmt = 0;
			else
				fail("as f32, f64 or real");
		} else if (cmdp_kw(p, "ops")) {
			/* + - * / are tokens, the rest words */
			F.ops = 0;
			for (;;) {
				unsigned bit = 0;
				if (cmdp_tok(p, T_PLUS))
					bit = 1u << Q_ADD;
				else if (cmdp_tok(p, T_MINUS))
					bit = 1u << Q_SUB;
				else if (cmdp_tok(p, T_STAR))
					bit = 1u << Q_MUL;
				else if (cmdp_tok(p, T_SLASH))
					bit = 1u << Q_DIV;
				else {
					uint32_t q = cmdp_pos(p);
					char ow[16];
					if (!cmdp_word(p, ow, sizeof ow))
						break;
					if ((bit = op_bit(ow)) == 0) {
						cmdp_seek(p, q);
						break;
					}
				}
				F.ops |= bit;
				(void)cmdp_tok(p, T_COMMA);
			}
			if (!(F.ops & (1u << Q_ADD | 1u << Q_MUL | 1u << Q_FMA)))
				fail("ops: at least + or * (or fma) among + - * / fma "
				    "sqrt exp log sin cos abs");
		} else if (cmdp_kw(p, "count")) {
			double v = cmdp_number(p, optwords);
			if (!(v >= 1) || v > 1e6)
				fail("count: shapes from 1 to 1000000, not %g", v);
			F.count = (int)v;
		} else if (cmdp_kw(p, "size")) {
			double v = cmdp_number(p, optwords);
			if (!(v >= 2) || v > 20)
				fail("size: nodes of a random shape, 2 to 20, not %g", v);
			F.size = (int)v;
		} else if (cmdp_kw(p, "steps")) {
			double v = cmdp_number(p, optwords);
			if (!(v >= 10) || v > 100000)
				fail("steps: Adam's steps per start, 10 to 100000, not %g",
				    v);
			F.steps = (int)v;
		} else if (cmdp_kw(p, "lr")) {
			F.lr = cmdp_number(p, optwords);
			if (!(F.lr > 0) || F.lr > 10)
				fail("lr: Adam's step, above 0 and at most 10");
		} else if (cmdp_kw(p, "restarts")) {
			double v = cmdp_number(p, optwords);
			if (!(v >= 1) || v > 64)
				fail("restarts: starts per shape, 1 to 64, not %g", v);
			F.restarts = (int)v;
		} else if (cmdp_kw(p, "wcost")) {
			F.wcost = cmdp_number(p, optwords);
			if (!(F.wcost >= 0))
				fail("wcost: a weight, 0 or more");
		} else if (cmdp_kw(p, "werr")) {
			F.werr = cmdp_number(p, optwords);
			if (!(F.werr >= 0))
				fail("werr: a weight, 0 or more");
		} else if (cmdp_kw(p, "error"))
			tol_err = cmdp_number(p, optwords);
		else if (cmdp_kw(p, "ulp"))
			tol_ulp = cmdp_number(p, optwords);
		else if (cmdp_kw(p, "relative"))
			metric = 1;
		else if (cmdp_kw(p, "absolute"))
			metric = 0;
		else if (cmdp_kw(p, "auto"))
			F.autom = 1;
		else if (cmdp_kw(p, "nocert"))
			F.cert = 0;
		else if (cmdp_kw(p, "list")) {
			double v = cmdp_number(p, optwords);
			if (!(v >= 1) || v > 64)
				fail("list: 1 to 64 candidates, not %g", v);
			F.list = (int)v;
		} else if (cmdp_kw(p, "seed")) {
			double v = cmdp_number(p, optwords);
			if (!(v >= 0) || v > 9e15)
				fail("seed: a whole number, not %g", v);
			F.seed = (uint64_t)v;
		} else if (cmdp_kw(p, "seconds")) {
			F.secs = cmdp_number(p, optwords);
			if (!(F.secs > 0))
				fail("seconds: a time limit above 0");
		} else if (cmdp_kw(p, "name")) {
			if (!cmdp_word(p, F.name, sizeof F.name))
				fail("name needs an identifier");
		} else
			fail("unknown adamfit option (see help)");
	}
	notes_flush();
	if (!haverange) {
		if (!F.f.p[0].ranged)
			fail("give an interval: adamfit F in a..b");
		lo = F.f.p[0].rlo;
		hi = F.f.p[0].rhi;
	}
	if (!(lo < hi) || !isfinite(lo) || !isfinite(hi))
		fail("the interval must be finite and non-empty");
	if (fmt < 0)
		fmt = TYK(F.f.p[0].ty) == K_FLOAT && TYW(F.f.p[0].ty) != 16 ?
		    TYW(F.f.p[0].ty) : 32;
	F.w = fmt;
	F.prec = F.w == 32 ? 24 : 53;
	F.emin = F.w == 32 ? -126 : -1022;
	F.lo = rnd(F.w, lo);
	F.hi = rnd(F.w, hi);
	lref_init(&F.ref, F.f.body, 0);
	/* relative unless F is 0 somewhere in the interval (or asked) */
	if (metric < 0) {
		int i, zero = 0;
		for (i = 0; i <= 256 && !zero; i++) {
			ld y = lref_eval(&F.ref, F.lo + (F.hi - F.lo) * i / 256);
			if (y == 0)
				zero = 1;
		}
		metric = !zero;
	}
	F.rel = metric;
	if (tol_ulp > 0 && F.w && F.rel) {
		F.tol = tol_ulp;
		snprintf(F.tolname, sizeof F.tolname, "%g ulp", tol_ulp);
	} else if (tol_err > 0) {
		F.tol = F.w && F.rel ? tol_err * ldexp(1, F.prec - 1) : tol_err;
		snprintf(F.tolname, sizeof F.tolname, "%g", tol_err);
	} else if (F.w && F.rel) {
		F.tol = 1;
		snprintf(F.tolname, sizeof F.tolname, "1 ulp");
	} else {
		F.tol = F.w == 32 ? 1e-7 : 1e-15;
		snprintf(F.tolname, sizeof F.tolname, "%g", F.tol);
	}
	run();
	return 1;
}

static char *
ci_find(char *s, const char *w)
{
	size_t n = strlen(w);

	for (; *s; s++)
		if (!strncasecmp(s, w, n))
			return s;
	return NULL;
}

/*
 * English: "fit sin(x) with adam on 0..1", "adam fit exp(x) in 0..1",
 * "search for cheap approximations of sin(x) in 0..1 by gradient descent",
 * "train expressions for log(x) in 1..2" ... becomes adamfit; "and just
 * report the closest" / "automatically" adds auto.
 */
const char *
adamfit_nlp_raw(const char *sent)
{
	static char out[1200];
	char buf[1000], tail[80] = "", *s, *q;
	size_t n;
	static const char *const pre[] = {"adam fit ", "adamfit ", "fit with adam ",
		"neural fit ", "train expressions for ", "train an expression for ",
		"evolve expressions for ", "search expressions for ",
		"search for cheap expressions for ", "search for cheap approximations of ",
		"find cheap expressions for ", "find cheap approximations of ", NULL};
	static const char *const post[] = {" with adam", " using adam", " by adam",
		" with gradient descent", " by gradient descent",
		" using gradient descent", " with a neural fitter", NULL};
	static const char *const autos[] = {" and just report the closest",
		" and report the closest", " automatically", " in auto mode",
		" quietly", NULL};
	int i, adam = 0;

	while (*sent == ' ' || *sent == '\t')
		sent++;
	if (strlen(sent) >= sizeof buf)
		return NULL;
	strcpy(buf, sent);
	n = strlen(buf);
	while (n && (buf[n - 1] == ' ' || buf[n - 1] == '?' || buf[n - 1] == '.' ||
	    buf[n - 1] == '\n'))
		buf[--n] = 0;
	s = buf;
	if (!strncasecmp(s, "please ", 7))
		s += 7;
	for (i = 0; autos[i]; i++)
		if ((q = ci_find(s, autos[i])) != NULL) {
			memmove(q, q + strlen(autos[i]), strlen(q + strlen(autos[i])) +
			    1);
			snprintf(tail, sizeof tail, " auto");
		}
	for (i = 0; post[i]; i++)
		if ((q = ci_find(s, post[i])) != NULL) {
			memmove(q, q + strlen(post[i]), strlen(q + strlen(post[i])) + 1);
			adam = 1;
		}
	for (i = 0; pre[i]; i++)
		if (!strncasecmp(s, pre[i], strlen(pre[i]))) {
			s += strlen(pre[i]);
			adam = 1;
			break;
		}
	if (!adam && !strncasecmp(s, "fit ", 4) && strstr(sent, "adam")) {
		s += 4;
		adam = 1;
	}
	{
		/* "fit F with adam": the verb before F */
		static const char *const verbs[] = {"fit ", "approximate ",
			"approximations of ", "search for ", "search ", "train ",
			"find ", NULL};
		for (i = 0; adam && verbs[i]; i++)
			if (!strncasecmp(s, verbs[i], strlen(verbs[i]))) {
				s += strlen(verbs[i]);
				break;
			}
	}
	if (!adam || !*s)
		return NULL;
	/* "on 0..1", "from 0 to 1", "over [0, 1]" as in a..b */
	if ((q = strstr(s, " from ")) != NULL && strstr(q, " to ")) {
		char *t = strstr(q, " to ");
		*q = 0;
		*t = 0;
		snprintf(out, sizeof out, "adamfit %s in %s..%s%s", s, q + 6, t + 4,
		    tail);
		return out;
	}
	if ((q = strstr(s, " on ")) != NULL && strstr(q, ".."))
		memcpy(q, " in ", 4);
	if ((q = strstr(s, " over ")) != NULL && strstr(q, "..")) {
		memmove(q + 4, q + 6, strlen(q + 6) + 1);
		memcpy(q, " in ", 4);
	}
	snprintf(out, sizeof out, "adamfit %s%s", s, tail);
	return out;
}
