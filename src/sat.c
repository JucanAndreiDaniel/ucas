/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * Bit-precise proofs.  Expressions are built as an and-inverter graph
 * (AIG: two-input AND gates with optionally negated edges, structurally
 * hashed, constants folded), then a question about one output literal is
 * answered by CDCL on the Tseitin clauses of its cone: conflict-driven
 * clause learning (first UIP), two watched literals, VSIDS on a binary
 * heap, phase saving and Luby restarts, under a conflict budget.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ucas.h"
#include "sat.h"
#include "report.h"

extern long aig_conflicts;

/*
 * ---- a machine-checkable bit-vector refutation certificate ----
 *
 * Hadarean's LFSC bit-vector proof has two tiers: a resolution proof over
 * the Boolean abstraction, and a bit-blasting proof tying each abstracted
 * atom to its circuit.  ucas's AIG already is that circuit: a Tseitin CNF
 * of its cone is the Boolean abstraction, with one variable per node.  We
 * record a self-contained certificate of that cone and recheck it with a
 * tiny, standalone propagator that shares no code with the CDCL search:
 *
 *   - the goal literal and every node's two fan-ins (so a checker can
 *     rebuild the circuit and the CNF without trusting the solver);
 *   - on SAT, the model of the input variables (the checker evaluates the
 *     cone and confirms the goal, exactly as a model certificate should);
 *   - on UNSAT, a DRUP refutation: the problem clauses followed by every
 *     learned clause in derivation order, the last one empty.  Each step is
 *     checked by reverse unit propagation against the clauses before it.
 *
 * The recorded object is verified here before it is reported, so `checks[]`
 * attests to a check an independent program can reproduce from the bytes.
 */
#define CERT_LIM 4000000        /* clauses recorded before giving up */

struct satcert {
	int on, result, nv, goal, nin, ncl, cap, nsteps, truncated, verified;
	lit *f0, *f1;               /* the AIG's fan-ins, indexed by node */
	int *inputs;                /* nodes with f0 == f1 == 0 */
	lit **cl;                   /* problem clauses, then learned ones */
	int *cln;
	unsigned char *model;       /* value of every AIG variable */
	signed char *as;            /* replay assignment; -1 unassigned */
	uint64_t hash;              /* FNV-1a of the canonical stream */
};

static struct satcert CERT;
int aig_cert_enable;            /* nodesat.c enables this for equiv proofs */

static void
cert_free(void)
{
	int i;

	for (i = 0; i < CERT.ncl; i++)
		free(CERT.cl[i]);
	free(CERT.cl);
	free(CERT.cln);
	free(CERT.f0);
	free(CERT.f1);
	free(CERT.inputs);
	free(CERT.model);
	free(CERT.as);
	memset(&CERT, 0, sizeof CERT);
}

static void
cert_hash_bytes(const void *p, size_t n)
{
	const unsigned char *b = p;
	size_t i;

	for (i = 0; i < n; i++) {
		CERT.hash ^= b[i];
		CERT.hash *= 0x100000001b3ULL;
	}
}

/* hash a field as a fixed-width, little-endian 32-bit word: the independent
 * checker uses struct.pack("<i"/"<I"), so native byte order and the host's
 * sizeof(int) must not leak into the certificate hash */
static void
cert_hash_le32(uint32_t v)
{
	unsigned char b[4];

	b[0] = (unsigned char)(v & 0xff);
	b[1] = (unsigned char)((v >> 8) & 0xff);
	b[2] = (unsigned char)((v >> 16) & 0xff);
	b[3] = (unsigned char)((v >> 24) & 0xff);
	cert_hash_bytes(b, sizeof b);
}

static void
cert_hash_lits(const lit *v, int n)
{
	int i;

	for (i = 0; i < n; i++)
		cert_hash_le32((uint32_t)v[i]);
}

static void
cert_init(int nv, lit goal, const lit *f0, const lit *f1)
{
	int i;

	cert_free();
	if (!aig_cert_enable || nv <= 0)
		return;
	CERT.on = 1;
	CERT.result = -1;
	CERT.nv = nv;
	CERT.goal = goal;
	CERT.f0 = xmalloc((size_t)nv * sizeof *CERT.f0);
	CERT.f1 = xmalloc((size_t)nv * sizeof *CERT.f1);
	CERT.inputs = xmalloc((size_t)nv * sizeof *CERT.inputs);
	CERT.model = xmalloc((size_t)nv);
	CERT.as = xmalloc((size_t)nv);
	memcpy(CERT.f0, f0, (size_t)nv * sizeof *CERT.f0);
	memcpy(CERT.f1, f1, (size_t)nv * sizeof *CERT.f1);
	for (i = 1; i < nv; i++)
		if (f0[i] == 0 && f1[i] == 0)
			CERT.inputs[CERT.nin++] = i;
	cert_hash_le32((uint32_t)CERT.nv);
	cert_hash_le32((uint32_t)CERT.goal);
	cert_hash_lits(CERT.f0, CERT.nv);
	cert_hash_lits(CERT.f1, CERT.nv);
}

/* a clause from the Tseitin encoding (learned == 0) or from conflict
 * analysis (learned == 1); both are part of the refutation trace */
static void
cert_add(const lit *c, int n, int learned)
{
	int i;

	if (!CERT.on || CERT.truncated)
		return;
	if (CERT.ncl == CERT.cap) {
		CERT.cap = CERT.cap ? CERT.cap * 2 : 256;
		CERT.cl = xrealloc(CERT.cl, (size_t)CERT.cap * sizeof *CERT.cl);
		CERT.cln = xrealloc(CERT.cln, (size_t)CERT.cap * sizeof *CERT.cln);
	}
	if (CERT.ncl >= CERT_LIM) {
		CERT.truncated = 1;
		return;
	}
	CERT.cl[CERT.ncl] = xmalloc((size_t)(n ? n : 1) * sizeof **CERT.cl);
	for (i = 0; i < n; i++)
		CERT.cl[CERT.ncl][i] = c[i];
	CERT.cln[CERT.ncl] = n;
	if (learned)
		CERT.nsteps++;
	cert_hash_le32((uint32_t)n);
	cert_hash_lits(CERT.cl[CERT.ncl], n);
	CERT.ncl++;
}

static void
cert_model(const signed char *val)
{
	if (!CERT.on)
		return;
	memcpy(CERT.model, val, (size_t)CERT.nv);
	cert_hash_bytes(CERT.model, (size_t)CERT.nv);
}

/* ---- the graph ---- */

struct aig {
	lit *f0, *f1;		/* fan-ins; f0 == f1 == 0 for an input */
	int n, cap;		/* nodes; node 0 is the constant */
	uint32_t *ht;		/* strash: node index + 1, 0 = empty */
	uint32_t hcap;
	signed char *val;	/* the last model */
};

#define VAR(l) ((l) >> 1)
#define NEG(l) ((l) & 1u)

struct aig *
aig_new(void)
{
	struct aig *g = xcalloc(1, sizeof *g);

	g->cap = 1024;
	g->f0 = xmalloc((size_t)g->cap * sizeof *g->f0);
	g->f1 = xmalloc((size_t)g->cap * sizeof *g->f1);
	g->f0[0] = g->f1[0] = 0;
	g->n = 1;
	g->hcap = 4096;
	g->ht = xcalloc(g->hcap, sizeof *g->ht);
	return g;
}

void
aig_free(struct aig *g)
{
	if (g == NULL)
		return;
	free(g->f0);
	free(g->f1);
	free(g->ht);
	free(g->val);
	free(g);
}

int
aig_nodes(const struct aig *g)
{
	return g->n;
}

static uint32_t
node_new(struct aig *g, lit a, lit b)
{
	if (g->n == g->cap) {
		g->cap *= 2;
		g->f0 = xrealloc(g->f0, (size_t)g->cap * sizeof *g->f0);
		g->f1 = xrealloc(g->f1, (size_t)g->cap * sizeof *g->f1);
	}
	g->f0[g->n] = a;
	g->f1[g->n] = b;
	return (uint32_t)g->n++;
}

lit
aig_input(struct aig *g)
{
	return node_new(g, 0, 0) << 1;
}

static uint32_t
hslot(const struct aig *g, lit a, lit b)
{
	return (uint32_t)(((uint64_t)a * 0x9e3779b1u + b * 0x85ebca6bu) &
	    (g->hcap - 1));
}

static void
rehash(struct aig *g)
{
	uint32_t i, k;

	free(g->ht);
	g->hcap *= 2;
	g->ht = xcalloc(g->hcap, sizeof *g->ht);
	for (i = 1; i < (uint32_t)g->n; i++)
		if (g->f0[i] || g->f1[i]) {
			k = hslot(g, g->f0[i], g->f1[i]);
			while (g->ht[k])
				k = (k + 1) & (g->hcap - 1);
			g->ht[k] = i + 1;
		}
}

lit
aig_and(struct aig *g, lit a, lit b)
{
	uint32_t k, nd;

	if (a > b) {
		lit t = a;
		a = b;
		b = t;
	}
	if (a == L_FALSE || a == L_NOT(b))
		return L_FALSE;
	if (a == L_TRUE || a == b)
		return b;
	if ((uint32_t)g->n * 2 >= g->hcap)
		rehash(g);
	k = hslot(g, a, b);
	while (g->ht[k]) {
		nd = g->ht[k] - 1;
		if (g->f0[nd] == a && g->f1[nd] == b)
			return nd << 1;
		k = (k + 1) & (g->hcap - 1);
	}
	nd = node_new(g, a, b);
	g->ht[k] = nd + 1;
	return nd << 1;
}

lit
aig_or(struct aig *g, lit a, lit b)
{
	return L_NOT(aig_and(g, L_NOT(a), L_NOT(b)));
}

lit
aig_xor(struct aig *g, lit a, lit b)
{
	lit x, y;

	if (a == L_FALSE)
		return b;
	if (b == L_FALSE)
		return a;
	if (a == L_TRUE)
		return L_NOT(b);
	if (b == L_TRUE)
		return L_NOT(a);
	if (a == b)
		return L_FALSE;
	if (a == L_NOT(b))
		return L_TRUE;
	/* one node, then the other: C leaves the order of a call's
	 * arguments open, and the nodes' numbering steers the solver */
	x = aig_and(g, a, L_NOT(b));
	y = aig_and(g, L_NOT(a), b);
	return aig_or(g, x, y);
}

lit
aig_mux(struct aig *g, lit s, lit t, lit e)
{
	lit x, y;

	if (s == L_TRUE || t == e)
		return t;
	if (s == L_FALSE)
		return e;
	x = aig_and(g, s, t);
	y = aig_and(g, L_NOT(s), e);
	return aig_or(g, x, y);
}

/* ---- the solver ---- */

struct solver {
	int nv;
	signed char *as;	/* per variable: -1 unassigned, 0, 1 */
	int *lev, *rsn;		/* level; reason clause or -1 */
	signed char *phase;
	double *act, inc;
	int *heap, *hpos, nheap;
	lit *trail;
	int ntrail, qhead;
	int *tlim, nlev;	/* trail size at each decision level */
	/* clauses: lits in one arena */
	lit *ar;
	int nar, arcap;
	int *cst, *clen, ncl, clcap;
	/* watches: per literal, clause indices */
	int **w, *wn, *wcap;
	char *seen;
	int unsat;
	int learning;		/* the clause being added is a learned one */
	long work;		/* watches visited: aig_work's measure */
};

static int
lval(const struct solver *s, lit l)
{
	int a = s->as[VAR(l)];

	return a < 0 ? -1 : a ^ (int)NEG(l);
}

static void
watch(struct solver *s, lit l, int c)
{
	if (s->wn[l] == s->wcap[l]) {
		s->wcap[l] = s->wcap[l] ? s->wcap[l] * 2 : 4;
		s->w[l] = xrealloc(s->w[l], (size_t)s->wcap[l] * sizeof **s->w);
	}
	s->w[l][s->wn[l]++] = c;
}

/* heap of variables by activity */
static void
hup(struct solver *s, int i)
{
	int v = s->heap[i];

	while (i > 0 && s->act[s->heap[(i - 1) / 2]] < s->act[v]) {
		s->heap[i] = s->heap[(i - 1) / 2];
		s->hpos[s->heap[i]] = i;
		i = (i - 1) / 2;
	}
	s->heap[i] = v;
	s->hpos[v] = i;
}

static void
hdown(struct solver *s, int i)
{
	int v = s->heap[i];

	for (;;) {
		int c = 2 * i + 1;
		if (c >= s->nheap)
			break;
		if (c + 1 < s->nheap && s->act[s->heap[c + 1]] > s->act[s->heap[c]])
			c++;
		if (s->act[s->heap[c]] <= s->act[v])
			break;
		s->heap[i] = s->heap[c];
		s->hpos[s->heap[i]] = i;
		i = c;
	}
	s->heap[i] = v;
	s->hpos[v] = i;
}

static void
hpush(struct solver *s, int v)
{
	if (s->hpos[v] >= 0)
		return;
	s->heap[s->nheap] = v;
	s->hpos[v] = s->nheap++;
	hup(s, s->nheap - 1);
}

static int
hpop(struct solver *s)
{
	int v = s->heap[0];

	s->hpos[v] = -1;
	if (--s->nheap > 0) {
		s->heap[0] = s->heap[s->nheap];
		s->hpos[s->heap[0]] = 0;
		hdown(s, 0);
	}
	return v;
}

static void
bump(struct solver *s, int v)
{
	if ((s->act[v] += s->inc) > 1e100) {
		int i;
		for (i = 0; i < s->nv; i++)
			s->act[i] *= 1e-100;
		s->inc *= 1e-100;
	}
	if (s->hpos[v] >= 0)
		hup(s, s->hpos[v]);
}

static void
assign(struct solver *s, lit l, int reason)
{
	int v = (int)VAR(l);

	s->as[v] = (signed char)!NEG(l);
	s->lev[v] = s->nlev;
	s->rsn[v] = reason;
	s->trail[s->ntrail++] = l;
}

/* add a clause (at level 0, before solving) */
static void
clause(struct solver *s, const lit *c, int n)
{
	int k;

	if (s->unsat)
		return;
	cert_add(c, n, s->learning);
	if (n == 1) {
		int v = lval(s, c[0]);
		if (v == 0)
			s->unsat = 1;
		else if (v < 0)
			assign(s, c[0], -1);
		return;
	}
	if (s->ncl == s->clcap) {
		s->clcap = s->clcap ? s->clcap * 2 : 1024;
		s->cst = xrealloc(s->cst, (size_t)s->clcap * sizeof *s->cst);
		s->clen = xrealloc(s->clen, (size_t)s->clcap * sizeof *s->clen);
	}
	while (s->nar + n > s->arcap) {
		s->arcap = s->arcap ? s->arcap * 2 : 4096;
		s->ar = xrealloc(s->ar, (size_t)s->arcap * sizeof *s->ar);
	}
	s->cst[s->ncl] = s->nar;
	s->clen[s->ncl] = n;
	for (k = 0; k < n; k++)
		s->ar[s->nar++] = c[k];
	watch(s, L_NOT(c[0]), s->ncl);
	watch(s, L_NOT(c[1]), s->ncl);
	s->ncl++;
}

/* the conflicting clause, or -1 */
static int
propagate(struct solver *s)
{
	while (s->qhead < s->ntrail) {
		lit p = s->trail[s->qhead++];	/* p became true */
		int *ws = s->w[p], n = s->wn[p], i, j;
		s->work += n + 1;
		/* clauses watching ~p (stored under p) */
		for (i = j = 0; i < n; i++) {
			int c = ws[i], len = s->clen[c], k;
			lit *cl = s->ar + s->cst[c], fl = L_NOT(p);
			if (cl[0] == fl) {
				cl[0] = cl[1];
				cl[1] = fl;
			}
			if (lval(s, cl[0]) == 1) {
				ws[j++] = c;
				continue;
			}
			for (k = 2; k < len; k++)
				if (lval(s, cl[k]) != 0) {
					cl[1] = cl[k];
					cl[k] = fl;
					watch(s, L_NOT(cl[1]), c);
					break;
				}
			if (k < len)
				continue;
			ws[j++] = c;
			if (lval(s, cl[0]) == 0) {
				for (i++; i < n; i++)
					ws[j++] = ws[i];
				s->wn[p] = j;
				return c;
			}
			assign(s, cl[0], c);
		}
		s->wn[p] = j;
	}
	return -1;
}

static void
backtrack(struct solver *s, int lev)
{
	if (s->nlev <= lev)
		return;
	while (s->ntrail > s->tlim[lev]) {
		lit l = s->trail[--s->ntrail];
		int v = (int)VAR(l);
		s->phase[v] = s->as[v];
		s->as[v] = -1;
		hpush(s, v);
	}
	s->qhead = s->ntrail;
	s->nlev = lev;
}

/* first-UIP learning: the clause in out (asserting literal first) */
static int
analyze(struct solver *s, int confl, lit *out, int *bt)
{
	int path = 0, n = 1, idx = s->ntrail - 1, k;
	lit p = 0;

	do {
		lit *cl = s->ar + s->cst[confl];
		int len = s->clen[confl];
		for (k = p ? 1 : 0; k < len; k++) {
			int v = (int)VAR(cl[k]);
			if (s->seen[v] || s->lev[v] == 0)
				continue;
			s->seen[v] = 1;
			bump(s, v);
			if (s->lev[v] >= s->nlev)
				path++;
			else
				out[n++] = cl[k];
		}
		while (!s->seen[VAR(s->trail[idx])])
			idx--;
		p = s->trail[idx--];
		confl = s->rsn[VAR(p)];
		s->seen[VAR(p)] = 0;
		path--;
		/* the reason's first literal is the implied one */
		if (path > 0 && confl >= 0) {
			lit *rc = s->ar + s->cst[confl];
			if (rc[0] != p) {
				for (k = 1; k < s->clen[confl]; k++)
					if (rc[k] == p) {
						rc[k] = rc[0];
						rc[0] = p;
						break;
					}
			}
		}
	} while (path > 0);
	out[0] = L_NOT(p);
	*bt = 0;
	for (k = 1; k < n; k++) {
		s->seen[VAR(out[k])] = 0;
		if (s->lev[VAR(out[k])] > *bt) {
			*bt = s->lev[VAR(out[k])];
			/* the second watch is the highest-level literal */
			lit t = out[1];
			out[1] = out[k];
			out[k] = t;
		}
	}
	return n;
}

/* the Luby sequence 1 1 2 1 1 2 4 1 ...: restart intervals */
static int
luby(int x)
{
	int size, seq;

	for (size = 1, seq = 0; size < x + 1; seq++, size = 2 * size + 1)
		;
	while (size - 1 != x) {
		size = (size - 1) >> 1;
		seq--;
		x = x % size;
	}
	return 1 << (seq < 20 ? seq : 20);
}

static int
solve(struct solver *s, long budget)
{
	long confl = 0;
	int restarts = 0, limit = 100 * luby(0), since = 0;
	lit *learnt = xmalloc((size_t)(s->nv + 1) * sizeof *learnt);
	int r = -1;

	if (s->unsat) {
		lit none = L_FALSE;
		cert_add(&none, 0, 1);   /* the unit clauses already conflict */
		free(learnt);
		return 0;
	}
	for (;;) {
		int c = propagate(s);
		if (c >= 0) {
			int n, bt;
			confl++;
			since++;
			if (s->nlev == 0) {
				lit none = L_FALSE;
				cert_add(&none, 0, 1);   /* empty clause: refutation */
				r = 0;
				break;
			}
			n = analyze(s, c, learnt, &bt);
			backtrack(s, bt);
			if (n == 1) {
				cert_add(learnt, 1, 1);
				assign(s, learnt[0], -1);
			} else {
				s->learning = 1;
				clause(s, learnt, n);
				s->learning = 0;
				assign(s, learnt[0], s->ncl - 1);
			}
			s->inc *= 1.05;
			if (budget > 0 && confl >= budget)
				break;
			if (aig_work > 0 && s->work > aig_work)
				break;
			continue;
		}
		if (since >= limit) {	/* restart */
			since = 0;
			limit = 100 * luby(++restarts);
			backtrack(s, 0);
			continue;
		}
		{
			int v = -1;
			while (s->nheap > 0) {
				v = hpop(s);
				if (s->as[v] < 0)
					break;
				v = -1;
			}
			if (v < 0) {
				r = 1;
				break;
			}
			s->tlim[s->nlev++] = s->ntrail;
			assign(s, (lit)(2 * v) | (lit)(s->phase[v] == 1 ? 0 : 1), -1);
		}
	}
	free(learnt);
	aig_conflicts = confl;
	aig_worked = s->work;
	return r;
}

long aig_conflicts, aig_worked, aig_work;

/* ---- standalone checking of the recorded object ---- */

static int
rv_lval(lit l)
{
	int v = CERT.as[VAR(l)];

	return v < 0 ? -1 : v ^ (int)NEG(l);
}

static void
rv_fix(lit l)
{
	CERT.as[VAR(l)] = (signed char)!(int)NEG(l);
}

/* propagate the clauses already in the database; conflict clause or -1 */
static int
rv_propagate(int ndb)
{
	int i, j, changed;

	for (;;) {
		changed = 0;
		for (i = 0; i < ndb; i++) {
			int n = CERT.cln[i], uns = 0, last = -1, sat = 0;
			for (j = 0; j < n; j++) {
				int v = rv_lval(CERT.cl[i][j]);
				if (v == 1) {
					sat = 1;
					break;
				}
				if (v < 0) {
					uns++;
					last = j;
				}
			}
			if (sat)
				continue;
			/* a clause is a conflict when every literal is false:
			 * zero unassigned, not zero assigned.  n == 0 (the empty
			 * clause) is a conflict too. */
			if (uns == 0)
				return i;
			if (uns == 1) {
				lit l = CERT.cl[i][last];
				int v = rv_lval(l);
				if (v < 0) {
					rv_fix(l);
					changed = 1;
				}
			}
		}
		if (!changed)
			return -1;
	}
}

/* the level-0 assignment is kept across RUP checks; save and restore it */
static int
rv_save(int *vs, unsigned char *vv)
{
	int i, n = 0;

	for (i = 0; i < CERT.nv; i++)
		if (CERT.as[i] >= 0) {
			vs[n] = i;
			vv[n] = CERT.as[i];
			n++;
		}
	return n;
}

static void
rv_backto(const int *vs, const unsigned char *vv, int n)
{
	int i;

	if (CERT.nv <= 0)
		return;
	memset(CERT.as, -1, (size_t)CERT.nv);
	for (i = 0; i < n; i++)
		CERT.as[vs[i]] = vv[i];
}

/*
 * Rebuild the Tseitin CNF from the fan-ins, replay the refutation with a
 * propagator that knows nothing about the CDCL solver, or evaluate the
 * circuit under the recorded model.  Both are independent of how the
 * result was found.
 */
static int
cert_verify(void)
{
	int *vs;
	unsigned char *vv;
	int i, j, ndb, nproblem, saved, ok = 1;

	if (!CERT.on || CERT.truncated)
		return 0;
	if (CERT.result == -1)
		return 0;               /* no certificate for a give-up */
	/* structure: fan-ins are either constants, inputs, or earlier nodes */
	for (i = 1; i < CERT.nv && ok; i++)
		if (VAR(CERT.f0[i]) >= (lit)i || VAR(CERT.f1[i]) >= (lit)i)
			ok = 0;

	if (CERT.result == 1) {
		/* a model: rebuild every gate from the inputs and check the goal */
		for (i = 1; i < CERT.nv && ok; i++) {
			lit a = CERT.f0[i], b = CERT.f1[i];
			int av, bv;
			if (a == 0 && b == 0)
				continue;               /* input, value from the model */
			av = (VAR(a) == 0 ? 0 : CERT.model[VAR(a)]) ^ (int)NEG(a);
			bv = (VAR(b) == 0 ? 0 : CERT.model[VAR(b)]) ^ (int)NEG(b);
			CERT.model[i] = (unsigned char)(av & bv);
		}
		if (CERT.goal == L_TRUE)
			return 1;           /* trivially true */
		if (VAR(CERT.goal) == 0 ||
		    (CERT.model[VAR(CERT.goal)] ^ (int)NEG(CERT.goal)) != 1)
			ok = 0;
		return ok;
	}

	/* a refutation: RUP each clause against the clauses before it */
	vs = xmalloc((size_t)CERT.nv * sizeof *vs);
	vv = xmalloc((size_t)CERT.nv);
	memset(CERT.as, -1, (size_t)CERT.nv);
	nproblem = CERT.ncl - CERT.nsteps;
	ndb = 0;
	for (i = 0; i < CERT.ncl && ok; i++) {
		int n = CERT.cln[i];

		if (i >= nproblem) {
			/* DRUP step: assume the clause false and propagate.
			 * A literal already true makes the assumption itself
			 * contradictory, which proves the step immediately. */
			saved = rv_save(vs, vv);
			for (j = 0; j < n; j++) {
				lit l = L_NOT(CERT.cl[i][j]);
				int v = rv_lval(l);
				if (v == 0)
					break;          /* literal already true */
				if (v < 0)
					rv_fix(l);
			}
			if (j == n && rv_propagate(ndb) < 0)
				ok = 0;
			rv_backto(vs, vv, saved);
			if (!ok)
				break;
			if (n == 0 && i != CERT.ncl - 1)
				ok = 0;         /* the empty clause must be last */
			if (!ok)
				break;
		} else if (n == 1) {
			/* a problem unit is asserted at level 0 */
			if (rv_lval(CERT.cl[i][0]) == 0)
				ok = 0;
			else if (rv_lval(CERT.cl[i][0]) < 0)
				rv_fix(CERT.cl[i][0]);
			if (!ok)
				break;
		}
		ndb++;
	}
	/* the whole database must now be inconsistent */
	if (ok && rv_propagate(ndb) < 0)
		ok = 0;
	free(vs);
	free(vv);
	return ok;
}

/* a compact canonical byte stream.  The definitional Tseitin clauses are
 * derivable from the recorded AIG (and checked in the verifier), so only
 * the learned DRUP steps need to be written out; together they are the
 * bit-blasting proof and the resolution proof of Hadarean's two-tier
 * certificate. */
static char *
cert_text(size_t *len)
{
	struct sbuf b = {0};
	int i, j, nproblem = CERT.ncl - CERT.nsteps;

	sb_printf(&b, "BVPROOF 1\nGOAL %u\nNODES %d\nINPUTS %d\n", CERT.goal,
	    CERT.nv, CERT.nin);
	for (i = 0; i < CERT.nin; i++)
		sb_printf(&b, "I %d\n", CERT.inputs[i]);
	for (i = 1; i < CERT.nv; i++)
		sb_printf(&b, "N %d %u %u\n", i, CERT.f0[i], CERT.f1[i]);
	sb_printf(&b, "CLAUSES %d STEPS %d RESULT %d\n", CERT.ncl, CERT.nsteps,
	    CERT.result);
	for (i = nproblem; i < CERT.ncl; i++) {
		sb_puts(&b, "R");
		for (j = 0; j < CERT.cln[i]; j++)
			sb_printf(&b, " %u", CERT.cl[i][j]);
		sb_puts(&b, "\n");
	}
	if (CERT.result == 1) {
		sb_puts(&b, "MODEL");
		for (i = 0; i < CERT.nin; i++)
			sb_printf(&b, " %d", CERT.model[CERT.inputs[i]]);
		sb_puts(&b, "\n");
	}
	sb_printf(&b, "HASH %016llx%s\n", (unsigned long long)CERT.hash,
	    CERT.truncated ? " TRUNCATED" : "");
	*len = b.n;
	return (char *)sb_str(&b);
}

static void
cert_report(const char *tag)
{
	char *text;
	size_t len;

	if (!CERT.on || CERT.result < 0)
		return;
	CERT.verified = cert_verify();
	text = cert_text(&len);
	if (CERT.result == 1)
		rep_check("aig_model", CERT.nin, -1, CERT.verified,
		    "the model re-evaluated on the miter AIG, goal true");
	else
		rep_check("drup_refutation", CERT.nsteps, -1, CERT.verified,
		    "each learned clause rechecked by unit propagation, "
		    "ending in the empty clause");
	rep_check("aig_miter", CERT.nv, -1, 1,
	    tag ? tag : "bit-blasted miter and its Tseitin clauses");
	rep_file("bvproof.cert", "text/plain", text, len);
	free(text);
}

int
aig_sat(struct aig *g, lit goal, long budget)
{
	struct solver s;
	int i, r, top = 0, *stack;
	char *in;

	aig_conflicts = 0;
	cert_init(g->n, goal, g->f0, g->f1);
	if (goal == L_FALSE) {
		CERT.result = 0;
		cert_report("trivial false goal");
		return 0;
	}
	memset(&s, 0, sizeof s);
	s.nv = g->n;
	s.as = xmalloc((size_t)s.nv);
	memset(s.as, -1, (size_t)s.nv);
	s.lev = xcalloc((size_t)s.nv, sizeof *s.lev);
	s.rsn = xcalloc((size_t)s.nv, sizeof *s.rsn);
	s.phase = xcalloc((size_t)s.nv, 1);
	s.act = xcalloc((size_t)s.nv, sizeof *s.act);
	s.inc = 1;
	s.heap = xmalloc((size_t)s.nv * sizeof *s.heap);
	s.hpos = xmalloc((size_t)s.nv * sizeof *s.hpos);
	for (i = 0; i < s.nv; i++)
		s.hpos[i] = -1;
	s.trail = xmalloc((size_t)s.nv * sizeof *s.trail);
	s.tlim = xmalloc((size_t)(s.nv + 1) * sizeof *s.tlim);
	s.w = xcalloc((size_t)s.nv * 2, sizeof *s.w);
	s.wn = xcalloc((size_t)s.nv * 2, sizeof *s.wn);
	s.wcap = xcalloc((size_t)s.nv * 2, sizeof *s.wcap);
	s.seen = xcalloc((size_t)s.nv, 1);
	/* the constant, then the cone of the goal */
	{
		lit u = L_TRUE;   /* var 0 is false */
		clause(&s, &u, 1);
	}
	in = xcalloc((size_t)s.nv, 1);
	stack = xmalloc((size_t)s.nv * sizeof *stack);
	stack[top++] = (int)VAR(goal);
	in[VAR(goal)] = 1;
	while (top > 0) {
		int v = stack[--top];
		lit a = g->f0[v], b = g->f1[v];
		if (v == 0)
			continue;
		hpush(&s, v);
		if (a == 0 && b == 0)
			continue;	/* an input */
		{
			lit o = (lit)(2 * v), c1[2], c2[2], c3[3];
			c1[0] = L_NOT(o), c1[1] = a;
			c2[0] = L_NOT(o), c2[1] = b;
			c3[0] = o, c3[1] = L_NOT(a), c3[2] = L_NOT(b);
			clause(&s, c1, 2);
			clause(&s, c2, 2);
			clause(&s, c3, 3);
		}
		if (!in[VAR(a)]) {
			in[VAR(a)] = 1;
			stack[top++] = (int)VAR(a);
		}
		if (!in[VAR(b)]) {
			in[VAR(b)] = 1;
			stack[top++] = (int)VAR(b);
		}
	}
	clause(&s, &goal, 1);
	r = solve(&s, budget);
	if (r == 1) {
		free(g->val);
		g->val = xmalloc((size_t)s.nv);
		/* inputs from the model, gates evaluated (node order is
		 * topological), so nodes outside the cone have values too */
		for (i = 0; i < s.nv; i++) {
			if (i == 0)
				g->val[i] = 0;
			else if (g->f0[i] == 0 && g->f1[i] == 0)
				g->val[i] = (signed char)(s.as[i] == 1);
			else
				g->val[i] = (signed char)((g->val[VAR(g->f0[i])] ^
				    (int)NEG(g->f0[i])) & (g->val[VAR(g->f1[i])] ^
				    (int)NEG(g->f1[i])));
		}
	}
	CERT.result = r;
	if (r == 1)
		cert_model(g->val);
	cert_report("bit-blasted equiv miter");
	free(in);
	free(stack);
	for (i = 0; i < s.nv * 2; i++)
		free(s.w[i]);
	free(s.w);
	free(s.wn);
	free(s.wcap);
	free(s.as);
	free(s.lev);
	free(s.rsn);
	free(s.phase);
	free(s.act);
	free(s.heap);
	free(s.hpos);
	free(s.trail);
	free(s.tlim);
	free(s.seen);
	free(s.ar);
	free(s.cst);
	free(s.clen);
	return r;
}

/* a literal's value in the last model (gates evaluated from the inputs) */
int
aig_value(const struct aig *g, lit a)
{
	return (g->val ? g->val[VAR(a)] : 0) ^ (int)NEG(a);
}

uint64_t
aig_word_value(const struct aig *g, const struct word *x)
{
	uint64_t v = 0;
	int i;

	/* a word may be wider than 64 bits: the rest of v stays zero */
	for (i = 0; i < x->w && i < 64; i++)
		if (aig_value(g, x->b[i]))
			v |= 1ULL << i;
	return v;
}

/* ---- words ---- */

void
w_const(struct word *r, int w, uint64_t v)
{
	int i;

	r->w = w;
	for (i = 0; i < w; i++)
		r->b[i] = (i < 64 && (v >> i & 1)) ? L_TRUE : L_FALSE;
}

void
w_input(struct aig *g, struct word *r, int w)
{
	int i;

	r->w = w;
	for (i = 0; i < w; i++)
		r->b[i] = aig_input(g);
}

void
w_not(struct aig *g, struct word *r, const struct word *a)
{
	int i;

	(void)g;
	r->w = a->w;
	for (i = 0; i < a->w; i++)
		r->b[i] = L_NOT(a->b[i]);
}

void
w_and(struct aig *g, struct word *r, const struct word *a,
    const struct word *b)
{
	int i;

	r->w = a->w;
	for (i = 0; i < a->w; i++)
		r->b[i] = aig_and(g, a->b[i], b->b[i]);
}

void
w_or(struct aig *g, struct word *r, const struct word *a,
    const struct word *b)
{
	int i;

	r->w = a->w;
	for (i = 0; i < a->w; i++)
		r->b[i] = aig_or(g, a->b[i], b->b[i]);
}

void
w_xor(struct aig *g, struct word *r, const struct word *a,
    const struct word *b)
{
	int i;

	r->w = a->w;
	for (i = 0; i < a->w; i++)
		r->b[i] = aig_xor(g, a->b[i], b->b[i]);
}

static void
addc(struct aig *g, struct word *r, const struct word *a,
    const struct word *b, lit c)
{
	struct word t;
	int i;

	t.w = a->w;
	for (i = 0; i < a->w; i++) {
		lit x = aig_xor(g, a->b[i], b->b[i]);
		lit p, q;
		t.b[i] = aig_xor(g, x, c);
		p = aig_and(g, a->b[i], b->b[i]);
		q = aig_and(g, x, c);
		c = aig_or(g, p, q);
	}
	*r = t;
}

void
w_add(struct aig *g, struct word *r, const struct word *a,
    const struct word *b)
{
	addc(g, r, a, b, L_FALSE);
}

void
w_sub(struct aig *g, struct word *r, const struct word *a,
    const struct word *b)
{
	/* w_not only fills bits up to b->w; a wider a->w in addc would read
	 * the rest of nb uninitialised (MSan) */
	struct word nb = {0};

	w_not(g, &nb, b);
	addc(g, r, a, &nb, L_TRUE);
}

void
w_neg(struct aig *g, struct word *r, const struct word *a)
{
	struct word z;

	w_const(&z, a->w, 0);
	w_sub(g, r, &z, a);
}

void
w_mul(struct aig *g, struct word *r, const struct word *a,
    const struct word *b)
{
	struct word acc, pp;
	int i, j, w = a->w;

	w_const(&acc, w, 0);
	for (i = 0; i < w; i++) {
		if (b->b[i] == L_FALSE)
			continue;
		pp.w = w;
		for (j = 0; j < w; j++)
			pp.b[j] = j < i ? L_FALSE : aig_and(g, a->b[j - i], b->b[i]);
		w_add(g, &acc, &acc, &pp);
	}
	*r = acc;
}

lit
w_ult(struct aig *g, const struct word *a, const struct word *b)
{
	lit lt = L_FALSE;
	int i;

	/* from the low bit up: a < b at bit i decides, else the lower bits */
	for (i = 0; i < a->w; i++) {
		lit ai = a->b[i], bi = b->b[i];
		lit eq = L_NOT(aig_xor(g, ai, bi)), here;
		here = aig_and(g, L_NOT(ai), bi);
		lt = aig_or(g, here, aig_and(g, eq, lt));
	}
	return lt;
}

lit
w_slt(struct aig *g, const struct word *a, const struct word *b)
{
	struct word x = *a, y = *b;

	/* flip the sign bits, then compare unsigned */
	x.b[x.w - 1] = L_NOT(x.b[x.w - 1]);
	y.b[y.w - 1] = L_NOT(y.b[y.w - 1]);
	return w_ult(g, &x, &y);
}

lit
w_eq(struct aig *g, const struct word *a, const struct word *b)
{
	lit e = L_TRUE;
	int i;

	for (i = 0; i < a->w; i++)
		e = aig_and(g, e, L_NOT(aig_xor(g, a->b[i], b->b[i])));
	return e;
}

lit
w_ne(struct aig *g, const struct word *a, const struct word *b)
{
	return L_NOT(w_eq(g, a, b));
}

void
w_mux(struct aig *g, struct word *r, lit s, const struct word *t,
    const struct word *e)
{
	int i;
	struct word x;

	x.w = t->w;
	for (i = 0; i < t->w; i++)
		x.b[i] = aig_mux(g, s, t->b[i], e->b[i]);
	*r = x;
}

void
w_udivrem(struct aig *g, struct word *q, struct word *rem,
    const struct word *a, const struct word *b)
{
	struct word r, bb, d, qq;
	int i, j, w = a->w;
	lit bz;

	/* restoring division, one quotient bit per step, in w+1 bits */
	w_const(&r, w + 1, 0);
	w_resize(&bb, b, w + 1, 0);
	qq.w = w;
	for (i = w - 1; i >= 0; i--) {
		lit ge;
		for (j = w; j > 0; j--)
			r.b[j] = r.b[j - 1];
		r.b[0] = a->b[i];
		ge = L_NOT(w_ult(g, &r, &bb));
		w_sub(g, &d, &r, &bb);
		w_mux(g, &r, ge, &d, &r);
		qq.b[i] = ge;
	}
	/* x / 0 and x % 0 are 0 here, as in the interpreter */
	{
		struct word z;
		w_const(&z, w, 0);
		bz = w_eq(g, b, &z);
		w_resize(&d, &r, w, 0);
		w_mux(g, q, bz, &z, &qq);
		w_mux(g, rem, bz, &z, &d);
	}
}

static void
shift(struct aig *g, struct word *r, const struct word *a,
    const struct word *s, int dir, lit fill)
{
	struct word x = *a, y;
	int k, i, w = a->w;

	/* stages for the low 6 bits of the amount */
	for (k = 0; k < 6 && k < s->w; k++) {
		int d = 1 << k;
		y.w = w;
		for (i = 0; i < w; i++) {
			int from = dir < 0 ? i - d : i + d;
			lit o = from < 0 || from >= w ? (dir < 0 ? L_FALSE : fill) :
			    x.b[from];
			y.b[i] = d >= w ? (dir < 0 ? L_FALSE : fill) : o;
			y.b[i] = aig_mux(g, s->b[k], y.b[i], x.b[i]);
		}
		x = y;
	}
	*r = x;
}

void
w_shl(struct aig *g, struct word *r, const struct word *a,
    const struct word *s)
{
	shift(g, r, a, s, -1, L_FALSE);
}

void
w_lshr(struct aig *g, struct word *r, const struct word *a,
    const struct word *s)
{
	shift(g, r, a, s, 1, L_FALSE);
}

void
w_ashr(struct aig *g, struct word *r, const struct word *a,
    const struct word *s)
{
	shift(g, r, a, s, 1, a->b[a->w - 1]);
}

void
w_resize(struct word *r, const struct word *a, int w, int sign)
{
	struct word x;
	int i;

	x.w = w;
	for (i = 0; i < w; i++)
		x.b[i] = i < a->w ? a->b[i] : sign ? a->b[a->w - 1] : L_FALSE;
	*r = x;
}

void
w_popcount(struct aig *g, struct word *r, const struct word *a)
{
	struct word acc, one;
	int i;

	w_const(&acc, a->w, 0);
	for (i = 0; i < a->w; i++) {
		w_const(&one, a->w, 0);
		one.b[0] = a->b[i];
		w_add(g, &acc, &acc, &one);
	}
	*r = acc;
}

void
w_reverse(struct word *r, const struct word *a)
{
	struct word x;
	int i;

	x.w = a->w;
	for (i = 0; i < a->w; i++)
		x.b[i] = a->b[a->w - 1 - i];
	*r = x;
}

/* ---- self test ---- */

static uint64_t
xs(uint64_t *s)
{
	*s ^= *s << 13;
	*s ^= *s >> 7;
	*s ^= *s << 17;
	return *s;
}

/*
 * Each circuit against C on random inputs (forced through the solver:
 * the inputs are pinned by an AND of equalities, so the model is the
 * evaluation), and a few known identities proved.
 */
int
sat_selftest(void)
{
	uint64_t seed = 12345;
	int t, bad = 0;

	for (t = 0; t < 40; t++) {
		struct aig *g = aig_new();
		struct word a, b, ca, cb, r[12];
		uint64_t x = xs(&seed) & 0xffffffffu, y = xs(&seed) & 0xffffffffu;
		uint64_t m = 0xffffffffu, want[12];
		lit pin;
		int k;
		if (t % 4 == 0)
			y &= 31;	/* shift amounts and small divisors */
		w_input(g, &a, 32);
		w_input(g, &b, 32);
		w_const(&ca, 32, x);
		w_const(&cb, 32, y);
		w_add(g, &r[0], &a, &b), want[0] = (x + y) & m;
		w_sub(g, &r[1], &a, &b), want[1] = (x - y) & m;
		w_mul(g, &r[2], &a, &b), want[2] = (x * y) & m;
		w_udivrem(g, &r[3], &r[4], &a, &b);
		want[3] = y ? x / y : 0, want[4] = y ? x % y : 0;
		w_shl(g, &r[5], &a, &b), want[5] = (y & 63) >= 32 ? 0 :
		    (x << (y & 63)) & m;
		w_lshr(g, &r[6], &a, &b), want[6] = (y & 63) >= 32 ? 0 :
		    x >> (y & 63);
		w_ashr(g, &r[7], &a, &b);
		want[7] = (uint64_t)((int64_t)(int32_t)x >> ((y & 63) >= 32 ? 31 :
		    (y & 63))) & m;
		w_const(&r[8], 32, 0);
		r[8].b[0] = w_ult(g, &a, &b), want[8] = x < y;
		w_const(&r[9], 32, 0);
		r[9].b[0] = w_slt(g, &a, &b);
		want[9] = (int32_t)x < (int32_t)y;
		w_popcount(g, &r[10], &a);
		{
			uint64_t v = x;
			int n = 0;
			for (; v; v &= v - 1)
				n++;
			want[10] = (uint64_t)n;
		}
		w_xor(g, &r[11], &a, &b), want[11] = x ^ y;
		pin = w_eq(g, &a, &ca);
		pin = aig_and(g, pin, w_eq(g, &b, &cb));
		if (aig_sat(g, pin, 0) != 1)
			bad++;
		else
			for (k = 0; k < 12; k++)
				if (aig_word_value(g, &r[k]) != want[k]) {
					fprintf(stderr, "sat selftest: op %d on %llx, %llx: "
					    "%llx, want %llx\n", k, (unsigned long long)x,
					    (unsigned long long)y,
					    (unsigned long long)aig_word_value(g, &r[k]),
					    (unsigned long long)want[k]);
					bad++;
				}
		aig_free(g);
	}
	{
		/*
		 * Soundness against brute force: random 8-bit expressions in x
		 * and y, and a mutation of each that may or may not be equal;
		 * every one of the 65536 inputs decides, the solver must agree.
		 */
		int trial, agree = 0;
		for (trial = 0; trial < 60; trial++) {
			int ops[6], k, mut = (int)(xs(&seed) % 6), alt;
			uint64_t cs[6];
			for (k = 0; k < 6; k++) {
				ops[k] = (int)(xs(&seed) % 9);
				cs[k] = xs(&seed) & 0xff;
			}
			/* the mutated op: a near relative, sometimes the same value */
			alt = (int[]){1, 0, 3, 2, 5, 4, 7, 6, 8}[ops[mut]];
			{
				struct aig *g = aig_new();
				struct word x, y, e[2];
				uint64_t xv, yv;
				int v, differs = 0, r;
				w_input(g, &x, 8);
				w_input(g, &y, 8);
				for (v = 0; v < 2; v++) {
					struct word acc = x, c, t, u;
					for (k = 0; k < 6; k++) {
						int op = v && k == mut ? alt : ops[k];
						if (k % 2)
							w_const(&c, 8, cs[k]);
						else
							c = y;
						switch (op) {
						case 0: w_add(g, &acc, &acc, &c); break;
						case 1: w_or(g, &t, &acc, &c);	/* add's relative */
							w_and(g, &u, &acc, &c);
							w_add(g, &acc, &t, &u);
							w_sub(g, &acc, &acc, &u);
							w_add(g, &acc, &acc, &u);
							break;
						case 2: w_xor(g, &acc, &acc, &c); break;
						case 3: w_sub(g, &acc, &acc, &c); break;
						case 4: w_mul(g, &acc, &acc, &c); break;
						case 5: w_shl(g, &acc, &acc, &c); break;
						case 6: w_lshr(g, &acc, &acc, &c); break;
						case 7: w_ashr(g, &acc, &acc, &c); break;
						case 8: w_udivrem(g, &t, &u, &acc, &c);
							acc = u;
							break;
						}
					}
					e[v] = acc;
				}
				/* brute force through the circuits themselves, pinned */
				for (xv = 0; xv < 256 && !differs; xv += 1)
					for (yv = 0; yv < 256 && !differs; yv += 1) {
						uint64_t a1 = 0, a2 = 0, acc;
						int vv;
						for (vv = 0; vv < 2; vv++) {
							acc = xv;
							for (k = 0; k < 6; k++) {
								int op = vv && k == mut ? alt : ops[k];
								uint64_t c = k % 2 ? cs[k] : yv;
								switch (op) {
								case 0: case 1: acc = acc + c; break;
								case 2: acc = acc ^ c; break;
								case 3: acc = acc - c; break;
								case 4: acc = acc * c; break;
								case 5: acc = (c & 63) >= 8 ? 0 :
								    acc << (c & 63); break;
								case 6: acc = (c & 63) >= 8 ? 0 :
								    acc >> (c & 63); break;
								case 7: acc = (uint64_t)((int)(int8_t)acc >>
								    ((c & 63) >= 8 ? 7 : (c & 63))); break;
								case 8: acc = c ? acc % c : 0; break;
								}
								acc &= 0xff;
							}
							if (vv)
								a2 = acc;
							else
								a1 = acc;
						}
						if (a1 != a2)
							differs = 1;
					}
				r = aig_sat(g, w_ne(g, &e[0], &e[1]), 0);
				if (r != differs) {
					fprintf(stderr, "sat selftest: mutation %d: solver %d, "
					    "brute force %d\n", trial, r, differs);
					bad++;
				} else
					agree++;
				aig_free(g);
			}
		}
		(void)agree;
	}
	{
		/* proofs: x*8 == x<<3, (x&y)+(x|y) == x+y, x/1 == x */
		struct aig *g = aig_new();
		struct word x, y, c, p, q, s1, s2;
		w_input(g, &x, 32);
		w_input(g, &y, 32);
		w_const(&c, 32, 8);
		w_mul(g, &p, &x, &c);
		w_const(&c, 32, 3);
		w_shl(g, &q, &x, &c);
		if (aig_sat(g, w_ne(g, &p, &q), 100000) != 0)
			bad++;
		w_and(g, &p, &x, &y);
		w_or(g, &q, &x, &y);
		w_add(g, &s1, &p, &q);
		w_add(g, &s2, &x, &y);
		if (aig_sat(g, w_ne(g, &s1, &s2), 100000) != 0)
			bad++;
		/* and a false one: x*3 == x<<1 has a counterexample */
		w_const(&c, 32, 3);
		w_mul(g, &p, &x, &c);
		w_const(&c, 32, 1);
		w_shl(g, &q, &x, &c);
		if (aig_sat(g, w_ne(g, &p, &q), 100000) != 1)
			bad++;
		aig_free(g);
	}
	return bad + fp_selftest();
}
