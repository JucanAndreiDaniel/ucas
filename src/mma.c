/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * mma.c: a warp's matrix product, D = A B + C on fragments spread over
 * the 32 lanes as PTX's mma.sync.aligned.m16n8k16 (and m16n8k8) .row.col
 * lays them out, with f16 A and B and f32 or f16 C and D, for a GPU with
 * subgroups and no matrix unit.
 *
 *   mma [m16n8k16 | m16n8k8] [f32 | f16] [model M] [all] [validate]
 *       [nofile] [seed N]
 *
 * Nothing here names a strategy.  A dataflow is a choice of where each
 * product is formed and how its operands get there:
 *
 *   - output-stationary: a lane forms the products of its own elements
 *     of D, fetching the words of A's rows and B's columns it needs; the
 *     order of the k words in each lane is a search variable (a xor of
 *     the lane's bits), which lets two lanes that need the same words
 *     fetch half each and swap the rest;
 *   - A- or B-stationary: a lane forms every product its own words of A
 *     (or B) take part in, fetching the other operand's words, and the
 *     partial sums meet at D's owners by a butterfly over the lane bits
 *     that tell the partial sums apart; which partial sum sits in which
 *     register is a search variable (a xor of the lane's bits), as a
 *     butterfly needs the same registers sent from every lane;
 *
 * and for each operand fetched: by subgroup exchanges, the words packed
 * or unpacked to f32 first, or through a slot of shared memory (two
 * layouts).  Every fetch looks for a word already at hand in another
 * lane that a xor shuffle reaches, and each exchange is classified by
 * the lane map it is (a xor of a constant, a broadcast within the quad,
 * anything else as a shuffle by an index computed from the lane's bits).
 * The model's prices decide: sg_shuffle, sg_shuffle_xor and sg_quad
 * (both a shuffle where the model does not list them), load_shared,
 * store_shared and bank_conflict over its banks, sg_barrier (barrier
 * where it is absent), conv for an unpack or a pack of f16, fmul for a
 * product or a multiply-add, fdot2 (two f16 products added into an f32,
 * absent unless listed) and fadd.
 *
 * The chosen dataflow is run on symbols over all 32 lanes: each element
 * of D must come out as the sum of exactly its K products and its C,
 * each once; that, the exactness of a product of two f16 in f32, and the
 * longest chain of roundings an element's terms go through (h) give the
 * bound |D - (A B + C)| <= gamma_h (sum_k |A_ik B_kj| + |C_ij|).  It is
 * then run on random fragments in f32 against the exact sums, and the
 * bound checked (a secondary check, sampled).
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

#include "ucas.h"
#include "memk.h"
#include "mma.h"
#include "report.h"

void deliver_file(const char *name, const char *type, const char *data,
    size_t n, int nofile);	/* anim.c */

#define ML 32		/* the lanes of a warp */
#define MAXI 1024	/* a plan's instructions */
#define MAXT 384	/* its lane maps and address maps */
#define MAXF 512	/* the values it knows the lanes' contents of */
#define MAXS 64		/* partial sums a lane, in the stationary flows */
#define NTERM (16 * 16 * 8 + 16 * 8)	/* products and C's elements */
#define NWD ((NTERM + 63) / 64)

/* ---- the fragments ---- */

struct pos {
	int8_t lane, reg, half;
};

struct shape {
	char name[16];
	int M, N, K, f32;
	int na, nb, nc;			/* registers of A, B, C (and D) */
	int8_t ar[ML][4][2], ak[ML][4][2];	/* A: row, column (k) */
	int8_t bk[ML][2][2], bc[ML][2][2];	/* B: row (k), column */
	int8_t cr[ML][4][2], cc[ML][4][2];	/* C, D: row, column */
	struct pos aown[16][16], bown[16][8], cown[16][8];
};

/*
 * PTX's layouts with g = lane / 4, t = lane % 4: A's register j holds row
 * g + 8 (j & 1), columns 2t + 8 (j >> 1) and the next; B's register j
 * column g, rows 2t + 8j and the next; an f32 C's register j row
 * g + 8 (j >> 1), column 2t + (j & 1); an f16 C's register j row g + 8j,
 * columns 2t and 2t + 1.
 */
static void
shape_build(struct shape *s, int k16, int f32)
{
	int l, r, h;

	memset(s, 0, sizeof *s);
	s->M = 16;
	s->N = 8;
	s->K = k16 ? 16 : 8;
	s->f32 = f32;
	s->na = k16 ? 4 : 2;
	s->nb = k16 ? 2 : 1;
	s->nc = f32 ? 4 : 2;
	snprintf(s->name, sizeof s->name, "m16n8k%d", s->K);
	for (l = 0; l < ML; l++) {
		int g = l >> 2, t = l & 3;
		for (r = 0; r < s->na; r++)
			for (h = 0; h < 2; h++) {
				struct pos p = {(int8_t)l, (int8_t)r, (int8_t)h};
				s->ar[l][r][h] = (int8_t)(g + 8 * (r & 1));
				s->ak[l][r][h] = (int8_t)(2 * t + h + 8 * (r >> 1));
				s->aown[s->ar[l][r][h]][s->ak[l][r][h]] = p;
			}
		for (r = 0; r < s->nb; r++)
			for (h = 0; h < 2; h++) {
				struct pos p = {(int8_t)l, (int8_t)r, (int8_t)h};
				s->bk[l][r][h] = (int8_t)(2 * t + h + 8 * r);
				s->bc[l][r][h] = (int8_t)g;
				s->bown[s->bk[l][r][h]][s->bc[l][r][h]] = p;
			}
		for (r = 0; r < s->nc; r++)
			for (h = 0; h < (f32 ? 1 : 2); h++) {
				struct pos p = {(int8_t)l, (int8_t)r, (int8_t)h};
				s->cr[l][r][h] = (int8_t)(f32 ? g + 8 * (r >> 1) :
				    g + 8 * r);
				s->cc[l][r][h] = (int8_t)(f32 ? 2 * t + (r & 1) :
				    2 * t + h);
				s->cown[s->cr[l][r][h]][s->cc[l][r][h]] = p;
			}
	}
}

/* ---- plans ---- */

enum { I_IN, I_XCH, I_STS, I_BAR, I_LDS, I_UNPK, I_MUL, I_FMA, I_DOT2,
	I_FADD, I_OUT, I_SEL };
enum { VW, VH, VF, VNONE };	/* a word of two f16, one as f32, an f32 */
enum { XK_XOR, XK_QUAD, XK_SHUF };
enum { OA, OB, OC };		/* operands */
enum { WA, WB, WP };		/* what an exchange carries: A, B, a partial sum */
enum { T_SHUF, T_SHUFU, T_STAGE0, T_STAGE1, T_N };
enum { F_OUT, F_ASTAT, F_BSTAT };

struct ins {
	uint8_t op, vt, opnd, reg, half, xk, what;
	int16_t a, b, c, tab, xm;
};

struct mplan {
	int n, nt;
	struct ins in[MAXI];
	int16_t tab[MAXT][ML];
	/* what it is */
	int fam, trans[2], perm[5], order[5], nord;
	int bad;
	double cost;
	/* the tally */
	int nx[3][3], nlds, nsts, nbar, nunpk, nfma, ndot2, nfadd, npack, nsel;
	int nidx, idxops, maxdeg;
	/* from the proof */
	int depth, proved;
};

struct bld {
	struct mplan *p;
	const struct shape *s;
	const struct model *m;
	int fdot2;
	int own[3][4];
	int nf;
	int16_t fv[MAXF];
	int32_t fid[MAXF][ML];
	int staged[2];
	int noreuse;	/* the reference: each word fetched from its owner */
};

static int unp[MAXI][2];	/* a word's unpacked halves, -1 */

static double
price(const struct model *m, int k)
{
	return (double)model_cost(m, k);
}

static int
avail(const struct model *m, int k)
{
	return cclass_available(m, k);
}

/* an exchange's price: a xor within the quad is a quad swap too */
static double
xch_price(const struct model *m, int xk, int xm)
{
	double best = price(m, C_SG_SHUF);

	if (xk == XK_XOR && avail(m, C_SG_SHUFXOR) &&
	    price(m, C_SG_SHUFXOR) < best)
		best = price(m, C_SG_SHUFXOR);
	if ((xk == XK_QUAD || (xk == XK_XOR && xm < 4)) && avail(m, C_SG_QUAD)
	    && price(m, C_SG_QUAD) < best)
		best = price(m, C_SG_QUAD);
	return best;
}

static int
barrier_class(const struct model *m)
{
	return avail(m, C_SG_BARRIER) ? C_SG_BARRIER : C_BARRIER;
}

/* t[l] = t[0] ^ (the xor of t[1 << i] ^ t[0] over l's bits i) */
static int
affine(const int16_t *t)
{
	int l, i, v;

	for (l = 0; l < ML; l++) {
		v = t[0];
		for (i = 0; i < 5; i++)
			if (l >> i & 1)
				v ^= t[0] ^ t[1 << i];
		if (v != t[l])
			return 0;
	}
	return 1;
}

/* a lane map's kind: -1 the lane itself, -2 not affine */
static int
classify(const int16_t *t, int *xm)
{
	int l, m = t[0], q = t[0] & 3, isx = 1, isq = 1;

	for (l = 0; l < ML; l++) {
		if ((t[l] ^ l) != m)
			isx = 0;
		if ((t[l] & ~3) != (l & ~3) || (t[l] & 3) != q)
			isq = 0;
	}
	if (isx) {
		*xm = m;
		return m ? XK_XOR : -1;
	}
	if (isq) {
		*xm = q;
		return XK_QUAD;
	}
	*xm = 0;
	return affine(t) ? XK_SHUF : -2;
}

/* the terms of an affine map as an expression of the lane: for each
 * shift d, the lane bits that land d places up; *ops: its operations */
struct aff {
	int c, nt, mask[24], sh[24];
};

static void
aff_terms(const int16_t *t, struct aff *a)
{
	int i, j, d, mask[32];

	memset(mask, 0, sizeof mask);
	a->c = t[0];
	a->nt = 0;
	for (i = 0; i < 5; i++) {
		int col = t[1 << i] ^ t[0];
		for (j = 0; j < 16; j++)
			if (col >> j & 1)
				mask[j - i + 8] |= 1 << i;
	}
	for (d = 0; d < 32; d++)
		if (mask[d]) {
			a->mask[a->nt] = mask[d];
			a->sh[a->nt++] = d - 8;
		}
}

static void
aff_text(struct sbuf *b, const int16_t *t)
{
	struct aff a;
	int k, l;

	aff_terms(t, &a);
	/* the expression as written gives the map, in every lane */
	for (l = 0; l < ML; l++) {
		int v = a.c;
		for (k = 0; k < a.nt; k++)
			v ^= a.sh[k] >= 0 ? (l & a.mask[k]) << a.sh[k] :
			    (l & a.mask[k]) >> -a.sh[k];
		if (v != t[l])
			fail("mma: internal error, lane %d's index is %d, not %d", l,
			    v, t[l]);
	}
	for (k = 0; k < a.nt; k++) {
		const char *x = k ? " ^ " : "";
		int paren = a.nt > 1 || a.c;
		if (a.mask[k] == 31 && a.sh[k] == 0)
			sb_printf(b, "%slane", x);
		else if (a.sh[k] == 0)
			sb_printf(b, "%s(lane & %du)", x, a.mask[k]);
		else if (a.mask[k] == 31 && !paren)
			sb_printf(b, "%slane %s %du", x, a.sh[k] > 0 ? "<<" : ">>",
			    abs(a.sh[k]));
		else
			sb_printf(b, "%s((lane & %du) %s %du)", x, a.mask[k],
			    a.sh[k] > 0 ? "<<" : ">>", abs(a.sh[k]));
	}
	if (a.nt == 0)
		sb_printf(b, "%du", a.c);
	else if (a.c)
		sb_printf(b, " ^ %du", a.c);
}

/* its price: the ands, shifts and xors */
static double
aff_price(const struct model *m, const int16_t *t, int *ops)
{
	struct aff a;
	int k, nl = 0, ns = 0;

	aff_terms(t, &a);
	for (k = 0; k < a.nt; k++) {
		nl += a.mask[k] != 31;
		ns += a.sh[k] != 0;
	}
	nl += a.nt > 1 ? a.nt - 1 : 0;
	nl += a.nt && a.c;
	*ops = nl + ns;
	return nl * price(m, C_LOGIC) + ns * price(m, C_SHIFT);
}

static int
tab_add(struct mplan *p, const int16_t *t)
{
	int k;

	for (k = 0; k < p->nt; k++)
		if (!memcmp(p->tab[k], t, sizeof p->tab[k]))
			return k;
	if (p->nt == MAXT) {
		p->bad = 1;
		return 0;
	}
	memcpy(p->tab[p->nt], t, sizeof p->tab[0]);
	return p->nt++;
}

static int
emit(struct bld *b, int op, int vt, int a, int bb, int c)
{
	struct mplan *p = b->p;
	struct ins *x;

	if (p->n == MAXI) {
		p->bad = 1;
		return 0;
	}
	x = &p->in[p->n];
	memset(x, 0, sizeof *x);
	x->op = (uint8_t)op;
	x->vt = (uint8_t)vt;
	x->a = (int16_t)a;
	x->b = (int16_t)bb;
	x->c = (int16_t)c;
	x->tab = -1;
	unp[p->n][0] = unp[p->n][1] = -1;
	return p->n++;
}

/* a value's contents in every lane: operand, lane, register, half + 1 */
static int32_t
mkid(int opnd, int lane, int reg, int hs)
{
	return opnd << 12 | lane << 6 | reg << 2 | hs;
}

static void
know(struct bld *b, int v, const int32_t *id)
{
	if (b->nf == MAXF) {
		b->p->bad = 1;
		return;
	}
	b->fv[b->nf] = (int16_t)v;
	memcpy(b->fid[b->nf++], id, sizeof b->fid[0]);
}

static const int32_t *
known(const struct bld *b, int v)
{
	int k;

	for (k = 0; k < b->nf; k++)
		if (b->fv[k] == v)
			return b->fid[k];
	return NULL;
}

static int
own(struct bld *b, int opnd, int reg)
{
	int v, l;
	int32_t id[ML];

	if (b->own[opnd][reg] >= 0)
		return b->own[opnd][reg];
	v = emit(b, I_IN, opnd == OC && b->s->f32 ? VF : VW, -1, -1, -1);
	b->p->in[v].opnd = (uint8_t)opnd;
	b->p->in[v].reg = (uint8_t)reg;
	b->own[opnd][reg] = v;
	if (opnd != OC) {
		for (l = 0; l < ML; l++)
			id[l] = mkid(opnd, l, reg, 0);
		know(b, v, id);
	}
	return v;
}

static int
unpack(struct bld *b, int w, int h)
{
	const int32_t *wid;
	int32_t id[ML];
	int v, l;

	if (unp[w][h] >= 0)
		return unp[w][h];
	/* an f16 C's half is a sum (of one term) */
	v = emit(b, I_UNPK, b->p->in[w].op == I_IN && b->p->in[w].opnd == OC ?
	    VF : VH, w, -1, -1);
	b->p->in[v].half = (uint8_t)h;
	b->p->nunpk++;
	unp[w][h] = v;
	if ((wid = known(b, w)) != NULL) {
		for (l = 0; l < ML; l++)
			id[l] = wid[l] | (h + 1);
		know(b, v, id);
	}
	return v;
}

/* the address of an operand's register of a lane in a warp's slot */
static int
stage_addr(const struct bld *b, int opnd, int lane, int reg)
{
	const struct shape *s = b->s;
	int base = opnd == OA ? 0 : ML * s->na, nr = opnd == OA ? s->na : s->nb;

	return b->p->trans[opnd] == T_STAGE0 ? base + reg * ML + lane :
	    base + lane * nr + reg;
}

static int
stage_words(const struct shape *s)
{
	return ML * (s->na + s->nb);
}

/* the most distinct words the lanes put on one bank */
static int
degree(const struct model *m, const int16_t *a)
{
	int banks = (int)m->par[MP_BANKS], bb = (int)m->par[MP_BANK_BYTES];
	int l, j, d, best = 1;

	if (banks <= 0 || bb <= 0)
		return 1;
	for (l = 0; l < ML; l++) {
		int bank = a[l] * 4 / bb % banks;
		d = 0;
		for (j = 0; j < ML; j++) {
			int k;
			if (a[j] * 4 / bb % banks != bank)
				continue;
			for (k = 0; k < j; k++)
				if (a[k] == a[j])
					break;
			if (k == j)
				d++;
		}
		if (d > best)
			best = d;
	}
	return best;
}

static double
lds_price(const struct model *m, int deg)
{
	return price(m, C_LOAD_SHARED) + (deg - 1) * price(m, C_BANK_CONFLICT);
}

/* the stores of the staged operands, between two barriers */
static void
stage_setup(struct bld *b)
{
	const struct shape *s = b->s;
	int o, r, l, v;

	if (!b->staged[OA] && !b->staged[OB])
		return;
	emit(b, I_BAR, VNONE, -1, -1, -1);
	for (o = OA; o <= OB; o++) {
		if (!b->staged[o])
			continue;
		for (r = 0; r < (o == OA ? s->na : s->nb); r++) {
			int16_t t[ML];
			int w = own(b, o, r);
			for (l = 0; l < ML; l++)
				t[l] = (int16_t)stage_addr(b, o, l, r);
			v = emit(b, I_STS, VNONE, w, -1, -1);
			b->p->in[v].tab = (int16_t)tab_add(b->p, t);
			b->p->in[v].opnd = (uint8_t)o;
		}
	}
	emit(b, I_BAR, VNONE, -1, -1, -1);
}

/* a way to get the wanted words into the lanes of a mask */
struct piece {
	double cost;
	int kind;	/* -1 at hand in the lane, XK_*, 99 a load */
	int xm, from, deg;	/* from: a value at hand (else the register) */
};

/*
 * The cheapest piece for the lanes of mask: the register itself (read
 * from lane sl[l] by a xor or a quad's broadcast, or over the whole warp
 * by a shuffle or a load), or a value at hand read from lane l ^ q.
 */
static void
piece_best(struct bld *b, int opnd, const int8_t *sl, const int8_t *rg,
    int hs, const int32_t *id, uint32_t mask, struct piece *pc)
{
	int l, k, q, l0 = __builtin_ctz(mask), uni = 1, isx = 1, isq = 1;
	int xm = sl[l0] ^ l0, qi = sl[l0] & 3, full = mask == 0xffffffffu;
	double pr;

	pc->cost = INFINITY;
	pc->from = -1;
	for (l = 0; l < ML; l++) {
		if (!(mask >> l & 1))
			continue;
		uni &= rg[l] == rg[l0];
		isx &= (sl[l] ^ l) == xm;
		isq &= (sl[l] & ~3) == (l & ~3) && (sl[l] & 3) == qi;
	}
	if (uni && isx && xm == 0) {
		pc->cost = 0;
		pc->kind = -1;
		return;
	}
	if (uni && b->staged[opnd] && full) {
		int16_t t[ML];
		for (l = 0; l < ML; l++)
			t[l] = (int16_t)stage_addr(b, opnd, sl[l], rg[0]);
		pc->deg = degree(b->m, t);
		pc->cost = lds_price(b->m, pc->deg) + (hs ? price(b->m, C_CONV) : 0);
		pc->kind = 99;
	} else if (uni && !b->staged[opnd]) {
		int16_t t[ML];
		for (l = 0; l < ML; l++)
			t[l] = sl[l];
		if (isx) {
			pc->cost = xch_price(b->m, XK_XOR, xm);
			pc->kind = XK_XOR;
			pc->xm = xm;
		} else if (isq) {
			pc->cost = xch_price(b->m, XK_QUAD, qi);
			pc->kind = XK_QUAD;
			pc->xm = qi;
		} else if (full && affine(t)) {
			pc->cost = xch_price(b->m, XK_SHUF, 0);
			pc->kind = XK_SHUF;
			pc->xm = 0;
		}
	}
	if (b->noreuse)
		return;
	for (k = 0; k < b->nf; k++) {
		const int32_t *f = b->fid[k];
		for (q = 0; q < ML; q++) {
			if (f[l0 ^ q] != id[l0])
				continue;
			for (l = l0 + 1; l < ML; l++)
				if ((mask >> l & 1) && f[l ^ q] != id[l])
					break;
			if (l < ML)
				continue;
			pr = q ? xch_price(b->m, XK_XOR, q) : 0;
			if (pr < pc->cost) {
				pc->cost = pr;
				pc->kind = q ? XK_XOR : -1;
				pc->xm = q;
				pc->from = b->fv[k];
			}
		}
	}
}

/* the piece's value (its lanes outside the mask hold anything) */
static int
piece_make(struct bld *b, int opnd, const int8_t *sl, const int8_t *rg,
    int hs, const struct piece *pc)
{
	struct mplan *p = b->p;
	int16_t t[ML];
	int l, v, from = pc->from;

	if (pc->kind == 99) {
		int32_t wid[ML];
		for (l = 0; l < ML; l++) {
			t[l] = (int16_t)stage_addr(b, opnd, sl[l], rg[0]);
			wid[l] = mkid(opnd, sl[l], rg[0], 0);
		}
		v = emit(b, I_LDS, VW, -1, -1, -1);
		p->in[v].tab = (int16_t)tab_add(p, t);
		p->in[v].opnd = (uint8_t)opnd;
		p->nlds++;
		if (pc->deg > p->maxdeg)
			p->maxdeg = pc->deg;
		know(b, v, wid);
		return hs ? unpack(b, v, hs - 1) : v;
	}
	if (from < 0) {
		from = own(b, opnd, rg[0]);	/* the same in every lane here */
		if (hs)
			from = unpack(b, from, hs - 1);
		if (pc->kind == -1)
			return from;
		for (l = 0; l < ML; l++)
			t[l] = (int16_t)(pc->kind == XK_XOR ? l ^ pc->xm : pc->kind ==
			    XK_QUAD ? (l & ~3) | pc->xm : sl[l]);
	} else {
		if (pc->kind == -1)
			return from;
		for (l = 0; l < ML; l++)
			t[l] = (int16_t)(l ^ pc->xm);
	}
	v = emit(b, I_XCH, p->in[from].vt, from, -1, -1);
	p->in[v].xk = (uint8_t)pc->kind;
	p->in[v].xm = (int16_t)pc->xm;
	p->in[v].tab = (int16_t)tab_add(p, t);
	p->in[v].what = (uint8_t)(opnd == OA ? WA : WB);
	p->nx[pc->kind][opnd == OA ? WA : WB]++;
	return v;
}

/*
 * The value whose lane l holds operand opnd's register rg[l] of lane
 * sl[l] (half hs - 1, or the word for hs 0): one at hand, the cheapest
 * piece for the whole warp, or two pieces for the lanes either side of a
 * lane bit and a select between them.
 */
static int
fetch(struct bld *b, int opnd, const int8_t *sl, const int8_t *rg, int hs)
{
	struct mplan *p = b->p;
	struct piece whole, half[2], bh[2];
	int32_t id[ML];
	int l, k, bit, bb = -1, v;
	double best, sel = price(b->m, C_SELECT);

	for (l = 0; l < ML; l++)
		id[l] = mkid(opnd, sl[l], rg[l], hs);
	for (k = 0; k < b->nf; k++)
		if (!memcmp(b->fid[k], id, sizeof id))
			return b->fv[k];
	piece_best(b, opnd, sl, rg, hs, id, 0xffffffffu, &whole);
	best = whole.cost;
	for (bit = 0; bit < 5 && !b->noreuse; bit++) {
		uint32_t m1 = 0;
		for (l = 0; l < ML; l++)
			if (l >> bit & 1)
				m1 |= 1u << l;
		piece_best(b, opnd, sl, rg, hs, id, ~m1, &half[0]);
		piece_best(b, opnd, sl, rg, hs, id, m1, &half[1]);
		if (half[0].cost + half[1].cost + sel < best) {
			best = half[0].cost + half[1].cost + sel;
			bb = bit;
			bh[0] = half[0];
			bh[1] = half[1];
		}
	}
	if (!isfinite(best)) {
		p->bad = 1;
		return 0;
	}
	if (bb < 0)
		v = piece_make(b, opnd, sl, rg, hs, &whole);
	else {
		int8_t s2[2][ML], r2[2][ML];
		int v0, v1, h;
		/* each piece built from the lanes it covers */
		for (h = 0; h < 2; h++)
			for (l = 0; l < ML; l++) {
				int src = (l >> bb & 1) == h ? l : (l ^ 1 << bb);
				s2[h][l] = sl[src];
				r2[h][l] = rg[src];
			}
		v0 = piece_make(b, opnd, s2[0], r2[0], hs, &bh[0]);
		v1 = piece_make(b, opnd, s2[1], r2[1], hs, &bh[1]);
		v = emit(b, I_SEL, p->in[v0].vt, v0, v1, -1);
		p->in[v].xm = (int16_t)bb;
		p->nsel++;
	}
	if (p->bad)
		return 0;
	know(b, v, id);
	return v;
}

/* acc + x y, x and y one f16 each (acc < 0: none) */
static int
fma1(struct bld *b, int acc, int x, int y)
{
	b->p->nfma++;
	return acc < 0 ? emit(b, I_MUL, VF, x, y, -1) :
	    emit(b, I_FMA, VF, x, y, acc);
}

/* acc + the dot product of words x and y */
static int
dotw(struct bld *b, int acc, int x, int y)
{
	int h;

	if (b->fdot2 && b->p->in[x].vt == VW && b->p->in[y].vt == VW) {
		b->p->ndot2++;
		return emit(b, I_DOT2, VF, x, y, acc);
	}
	for (h = 0; h < 2; h++)
		acc = fma1(b, acc, b->p->in[x].vt == VW ? unpack(b, x, h) : x,
		    b->p->in[y].vt == VW ? unpack(b, y, h) : y);
	return acc;
}

/* half h of an operand's word: x (the lane's own), else fetched, as a
 * word (u 0) or as the half itself (u 1) */
static int
term(struct bld *b, int opnd, int x, const int8_t *sl, const int8_t *rg,
    int u, int h)
{
	if (x >= 0)
		return unpack(b, x, h);
	return u ? fetch(b, opnd, sl, rg, h + 1) :
	    unpack(b, fetch(b, opnd, sl, rg, 0), h);
}

/* acc + the dot product of a word of A and a word of B, each the lane's
 * own (xa, xb) or fetched */
static int
dot_fetch(struct bld *b, int acc, int xa, const int8_t *sla,
    const int8_t *rga, int ua, int xb, const int8_t *slb, const int8_t *rgb,
    int ub)
{
	int h;

	if (!ua && !ub) {
		int wa = xa >= 0 ? xa : fetch(b, OA, sla, rga, 0);
		int wb = xb >= 0 ? xb : fetch(b, OB, slb, rgb, 0);
		if (b->p->bad)
			return 0;
		return dotw(b, acc, wa, wb);
	}
	for (h = 0; h < 2 && !b->p->bad; h++) {
		int ha = term(b, OA, xa, sla, rga, ua, h);
		int hb = term(b, OB, xb, slb, rgb, ub, h);
		acc = fma1(b, acc, ha, hb);
	}
	return acc;
}

/* the lane's C as f32, for output element o */
static int
c_value(struct bld *b, int o)
{
	if (b->s->f32)
		return own(b, OC, o);
	return unpack(b, own(b, OC, o >> 1), o & 1);
}

/* D's register (and half) of output element o */
static void
d_out(struct bld *b, const int *val)
{
	int o, v;

	if (b->s->f32)
		for (o = 0; o < 4; o++) {
			v = emit(b, I_OUT, VNONE, val[o], -1, -1);
			b->p->in[v].reg = (uint8_t)o;
		}
	else
		for (o = 0; o < 2; o++) {
			v = emit(b, I_OUT, VNONE, val[2 * o], val[2 * o + 1], -1);
			b->p->in[v].reg = (uint8_t)o;
			b->p->npack++;
		}
}

static void
out_elem(const struct shape *s, int o, int l, int *r, int *c)
{
	int reg = s->f32 ? o : o >> 1, h = s->f32 ? 0 : o & 1;

	*r = s->cr[l][reg][h];
	*c = s->cc[l][reg][h];
}

static int
xperm(const int *P, int l)
{
	int i, v = 0;

	for (i = 0; i < 5; i++)
		if (l >> i & 1)
			v ^= P[i];
	return v;
}

static void
bld_init(struct bld *b, struct mplan *p, const struct shape *s,
    const struct model *m)
{
	memset(b, 0, sizeof *b);
	memset(p, 0, sizeof *p);
	b->p = p;
	b->s = s;
	b->m = m;
	b->fdot2 = avail(m, C_FDOT2);
	memset(b->own, -1, sizeof b->own);
}

/*
 * Output-stationary: lane l sums the products of its own elements of D,
 * its k words taken in the order kw ^ perm(l).
 */
static void
gen_out(struct bld *b)
{
	const struct shape *s = b->s;
	struct mplan *p = b->p;
	int o, l, kw, nk = s->K / 2, acc[4];
	int ua = p->trans[OA] == T_SHUFU, ub = p->trans[OB] == T_SHUFU;

	b->staged[OA] = p->trans[OA] >= T_STAGE0;
	b->staged[OB] = p->trans[OB] >= T_STAGE0;
	stage_setup(b);
	for (o = 0; o < 4; o++)
		acc[o] = c_value(b, o);
	for (kw = 0; kw < nk; kw++)
		for (o = 0; o < 4; o++) {
			int8_t sla[ML], rga[ML], slb[ML], rgb[ML];
			for (l = 0; l < ML; l++) {
				int r, c, k = 2 * (kw ^ xperm(p->perm, l));
				struct pos pa, pb;
				if (k >= s->K) {
					p->bad = 1;
					return;
				}
				out_elem(s, o, l, &r, &c);
				pa = s->aown[r][k];
				pb = s->bown[k][c];
				sla[l] = pa.lane;
				rga[l] = pa.reg;
				slb[l] = pb.lane;
				rgb[l] = pb.reg;
			}
			acc[o] = dot_fetch(b, acc[o], -1, sla, rga, ua, -1, slb, rgb, ub);
			if (p->bad)
				return;
		}
	d_out(b, acc);
}

/* ---- the stationary flows' partial sums and their butterfly ---- */

struct red {
	int ns, nst, bit[5], nsend[5];
	int8_t from[5][MAXS], to[5][MAXS];
	int8_t oslot[4];
	int16_t ohold[4][ML];
	int16_t key[MAXS][ML];	/* r * N + c of each partial sum */
};

/*
 * The partial sums' keys under the stationary operand X's words, the
 * other index of slot j being j ^ perm(L, l): slot (group, j).
 */
static int
stat_keys(const struct shape *s, int X, const int *L, struct red *R,
    int *grp, int *ng, int *gof)
{
	int nx = X == OA ? s->na : s->nb, ny = X == OA ? s->N : s->M;
	int r, g, l, j;

	*ng = 0;
	for (r = 0; r < nx; r++) {
		for (g = 0; g < *ng; g++) {
			int r0 = grp[g * 4];
			for (l = 0; l < ML; l++)
				if ((X == OA ? s->ar[l][r][0] != s->ar[l][r0][0] :
				    s->bc[l][r][0] != s->bc[l][r0][0]))
					break;
			if (l == ML)
				break;
		}
		if (g == *ng) {
			gof[g] = 0;
			(*ng)++;
		}
		grp[g * 4 + gof[g]++] = r;
	}
	R->ns = *ng * ny;
	if (R->ns > MAXS)
		return 0;
	for (g = 0; g < *ng; g++)
		for (j = 0; j < ny; j++)
			for (l = 0; l < ML; l++) {
				int y = j ^ xperm(L, l), x, rr, cc;
				if (y >= ny)
					return 0;
				x = X == OA ? s->ar[l][grp[g * 4]][0] :
				    s->bc[l][grp[g * 4]][0];
				rr = X == OA ? x : y;
				cc = X == OA ? y : x;
				R->key[g * ny + j][l] = (int16_t)(rr * s->N + cc);
			}
	return 1;
}

static int
popc(unsigned v)
{
	int n = 0;

	for (; v; v &= v - 1)
		n++;
	return n;
}

/*
 * The butterfly: the lanes that hold a key differ in the bits of bm; a
 * key is summed at red(key), the holder whose bit b of those is D's
 * owner's (Q[b] < 0) or the key's bit Q[b] (r * N + c), the bits taken
 * in the order given; each step must send the same slots from every lane
 * into the same slots.  Then each of D's elements is read from its
 * holder's slot, the same slot in every lane (an exchange when the
 * holder is another lane).
 */
static int
red_plan(const struct shape *s, struct red *R, const int *order, int nord,
    const int *Q, int *bmp)
{
	static uint32_t hold[256];
	static int16_t redl[256];
	int nkey = s->M * s->N, k, l, sl, st, i, live[MAXS];
	int bm = -1;

	memset(hold, 0, sizeof hold);
	for (sl = 0; sl < R->ns; sl++)
		for (l = 0; l < ML; l++) {
			k = R->key[sl][l];
			if (hold[k] >> l & 1)
				return 0;
			hold[k] |= 1u << l;
		}
	for (k = 0; k < nkey; k++) {
		int h0 = __builtin_ctz(hold[k] | 0x80000000u), m = 0;
		struct pos d;
		if (!hold[k])
			return 0;
		for (l = 0; l < ML; l++)
			if (hold[k] >> l & 1)
				m |= l ^ h0;
		if (popc(hold[k]) != 1 << popc((unsigned)m))
			return 0;
		for (l = 0; l < ML; l++)
			if ((hold[k] >> l & 1) && ((l ^ h0) & ~m))
				return 0;
		if (bm < 0)
			bm = m;
		else if (bm != m)
			return 0;
		d = s->cown[k / s->N][k % s->N];
		{
			int b, q = 0;
			for (b = 0; b < 5; b++)
				if (m >> b & 1)
					q |= (Q == NULL || Q[b] < 0 ? d.lane >> b : k >> Q[b]) & 1
					    ? 1 << b : 0;
			redl[k] = (int16_t)((h0 & ~m) | q);
		}
	}
	*bmp = bm;
	if (nord != popc((unsigned)bm))
		return -1;
	for (i = 0; i < nord; i++)
		if (!(bm >> order[i] & 1))
			return -1;
	for (sl = 0; sl < R->ns; sl++)
		live[sl] = 1;
	R->nst = nord;
	for (st = 0; st < nord; st++) {
		int b = order[st], send[MAXS];
		R->bit[st] = b;
		R->nsend[st] = 0;
		for (sl = 0; sl < R->ns; sl++) {
			send[sl] = 0;
			if (!live[sl])
				continue;
			send[sl] = redl[R->key[sl][0]] >> b & 1;
			for (l = 1; l < ML; l++)
				if (((redl[R->key[sl][l]] ^ l) >> b & 1) != send[sl])
					return 0;
		}
		for (sl = 0; sl < R->ns; sl++) {
			int to = -1, s2;
			if (!live[sl] || !send[sl])
				continue;
			for (l = 0; l < ML; l++) {
				int kk = R->key[sl][l ^ 1 << b];
				for (s2 = 0; s2 < R->ns; s2++)
					if (live[s2] && !send[s2] && R->key[s2][l] == kk)
						break;
				if (s2 == R->ns || (to >= 0 && s2 != to))
					return 0;
				to = s2;
			}
			R->from[st][R->nsend[st]] = (int8_t)sl;
			R->to[st][R->nsend[st]++] = (int8_t)to;
		}
		for (sl = 0; sl < R->ns; sl++)
			if (send[sl])
				live[sl] = 0;
	}
	/* D's elements: the slot of each, the same in every lane */
	for (i = 0; i < 4; i++) {
		int slot = -1;
		for (l = 0; l < ML; l++) {
			int r, c, h;
			out_elem(s, i, l, &r, &c);
			k = r * s->N + c;
			h = redl[k];
			for (sl = 0; sl < R->ns; sl++)
				if (live[sl] && R->key[sl][h] == k)
					break;
			if (sl == R->ns || (slot >= 0 && sl != slot))
				return 0;
			slot = sl;
			R->ohold[i][l] = (int16_t)h;
		}
		R->oslot[i] = (int8_t)slot;
	}
	return 1;
}

/*
 * X-stationary: lane l forms the products of its own words of X with
 * the other operand's, the partial sums of one group of X's registers
 * (one row of A, one column of B) in slots j, then the butterfly.
 */
static void
gen_stat(struct bld *b, const struct red *R, int X)
{
	const struct shape *s = b->s;
	struct mplan *p = b->p;
	int Y = 1 - X, grp[16], ng, gof[4], g, j, l, q, val[MAXS], st, i;
	int ny = X == OA ? s->N : s->M, uy = p->trans[Y] == T_SHUFU;
	struct red R2;

	b->staged[Y] = p->trans[Y] >= T_STAGE0;
	stat_keys(s, X, p->perm, &R2, grp, &ng, gof);
	stage_setup(b);
	for (g = 0; g < ng; g++)
		for (j = 0; j < ny; j++) {
			int acc = -1;
			for (q = 0; q < gof[g]; q++) {
				int rho = grp[g * 4 + q], xw = own(b, X, rho);
				int8_t sy[ML], ry[ML];
				for (l = 0; l < ML; l++) {
					int y = j ^ xperm(p->perm, l), k;
					struct pos py;
					k = X == OA ? s->ak[l][rho][0] : s->bk[l][rho][0];
					py = X == OA ? s->bown[k][y] : s->aown[y][k];
					sy[l] = py.lane;
					ry[l] = py.reg;
				}
				if (X == OA)
					acc = dot_fetch(b, acc, xw, NULL, NULL, 0, -1, sy, ry,
					    uy);
				else
					acc = dot_fetch(b, acc, -1, sy, ry, uy, xw, NULL, NULL,
					    0);
				if (p->bad)
					return;
			}
			val[g * ny + j] = acc;
		}
	for (st = 0; st < R->nst; st++)
		for (i = 0; i < R->nsend[st]; i++) {
			int16_t t[ML];
			int x;
			for (l = 0; l < ML; l++)
				t[l] = (int16_t)(l ^ 1 << R->bit[st]);
			x = emit(b, I_XCH, VF, val[R->from[st][i]], -1, -1);
			p->in[x].xk = XK_XOR;
			p->in[x].xm = (int16_t)(1 << R->bit[st]);
			p->in[x].tab = (int16_t)tab_add(p, t);
			p->in[x].what = WP;
			p->nx[XK_XOR][WP]++;
			val[R->to[st][i]] = emit(b, I_FADD, VF, val[R->to[st][i]], x, -1);
			p->nfadd++;
		}
	{
		int out[4];
		for (i = 0; i < 4; i++) {
			int v = val[R->oslot[i]], xm, k;
			k = classify(R->ohold[i], &xm);
			if (k == -2) {
				p->bad = 1;
				return;
			}
			if (k >= 0) {
				int x = emit(b, I_XCH, VF, v, -1, -1);
				p->in[x].xk = (uint8_t)k;
				p->in[x].xm = (int16_t)xm;
				p->in[x].tab = (int16_t)tab_add(p, R->ohold[i]);
				p->in[x].what = WP;
				p->nx[k][WP]++;
				v = x;
			}
			out[i] = emit(b, I_FADD, VF, v, c_value(b, i), -1);
			p->nfadd++;
		}
		d_out(b, out);
	}
}

/* ---- prices ---- */

enum { FM_XOR, FM_QSWAP, FM_QBCAST, FM_SHUF };

/* how an exchange is written: the cheapest form its lane map allows */
static int
xch_form(const struct model *m, int xk, int xm, double *pr)
{
	int f = FM_SHUF;
	double best = price(m, C_SG_SHUF);

	if (xk == XK_XOR) {
		f = FM_XOR;	/* a shuffle's price where the model lists none */
		if (avail(m, C_SG_SHUFXOR) && price(m, C_SG_SHUFXOR) < best)
			best = price(m, C_SG_SHUFXOR);
		if (xm < 4 && avail(m, C_SG_QUAD) && price(m, C_SG_QUAD) < best) {
			best = price(m, C_SG_QUAD);
			f = FM_QSWAP;
		}
	} else if (xk == XK_QUAD && avail(m, C_SG_QUAD) &&
	    price(m, C_SG_QUAD) <= best) {
		best = price(m, C_SG_QUAD);
		f = FM_QBCAST;
	}
	*pr = best;
	return f;
}

/* a shuffle index already written that this one is a xor of a constant
 * from (one operation), or -1; seen[t] 1 for the index tables written */
static int
idx_parent(const struct mplan *p, int tab, const uint8_t *seen)
{
	int t, l;

	for (t = 0; t < p->nt; t++) {
		int c;
		if (seen[t] != 1 || t == tab)
			continue;
		c = p->tab[t][0] ^ p->tab[tab][0];
		for (l = 1; l < ML && (p->tab[t][l] ^ p->tab[tab][l]) == c; l++)
			;
		if (l == ML)
			return t;
	}
	return -1;
}

static void
plan_price(struct mplan *p, const struct shape *s, const struct model *m)
{
	static uint8_t seen[MAXT];
	double c = 0, pr;
	int i, ops, lane = 0, selbits = 0;

	memset(seen, 0, sizeof seen);
	p->nidx = p->idxops = p->nsts = p->nbar = 0;
	for (i = 0; i < p->n; i++) {
		const struct ins *x = &p->in[i];
		switch (x->op) {
		case I_XCH:
			if (xch_form(m, x->xk, x->xm, &pr) == FM_SHUF) {
				lane = 1;
				if (!seen[x->tab]) {
					if (idx_parent(p, x->tab, seen) >= 0) {
						c += price(m, C_LOGIC);
						p->idxops++;
					} else {
						c += aff_price(m, p->tab[x->tab], &ops) +
						    price(m, C_LOGIC);
						p->idxops += ops + 1;
					}
					seen[x->tab] = 1;
					p->nidx++;
				}
			}
			c += pr;
			break;
		case I_STS:
		case I_LDS:
			lane = 1;
			if (!seen[x->tab]) {
				seen[x->tab] = 2;	/* an address: no shuffle index */
				c += aff_price(m, p->tab[x->tab], &ops) + price(m, C_IADD);
				p->idxops += ops + 1;
			}
			if (x->op == I_STS) {
				c += price(m, C_STORE_SHARED) + (degree(m, p->tab[x->tab]) -
				    1) * price(m, C_BANK_CONFLICT);
				p->nsts++;
			} else
				c += lds_price(m, degree(m, p->tab[x->tab]));
			break;
		case I_BAR:
			c += price(m, barrier_class(m));
			p->nbar++;
			break;
		case I_SEL:
			c += price(m, C_SELECT);
			if (!(selbits >> x->xm & 1))	/* (lane & 1 << b) != 0 */
				c += price(m, C_LOGIC) + price(m, C_CMP);
			selbits |= 1 << x->xm;
			lane = 1;
			break;
		case I_UNPK:
			c += price(m, C_CONV);
			break;
		case I_MUL:
		case I_FMA:
			c += price(m, C_FMUL);
			break;
		case I_DOT2:
			c += price(m, C_FDOT2);
			break;
		case I_FADD:
			c += price(m, C_FADD);
			break;
		case I_OUT:
			if (!s->f32)
				c += 2 * price(m, C_CONV);
			break;
		}
	}
	if (lane)
		c += price(m, C_LOGIC);		/* the lane in its 32 */
	if (p->nsts)
		c += price(m, C_SHIFT) + price(m, C_IMUL);	/* the warp's slot */
	p->cost = c;
}

/* ---- the proof: the plan run on symbols over the 32 lanes ---- */

struct sv {
	uint16_t t[2];
	int16_t d;
};
static struct sv SV[MAXI][ML];
static uint64_t (*SB)[ML][NWD];

static uint16_t
tag(int opnd, int r, int c)
{
	return (uint16_t)(opnd << 8 | r << 4 | c);
}

static int
prod_term(const struct shape *s, int ta, int tb)
{
	if (ta >> 8 == OB) {
		int t = ta;
		ta = tb;
		tb = t;
	}
	if (ta >> 8 != OA || tb >> 8 != OB || (ta & 15) != (tb >> 4 & 15))
		return -1;
	return ((ta >> 4 & 15) * s->K + (ta & 15)) * s->N + (tb & 15);
}

static int
c_term(const struct shape *s, int r, int c)
{
	return s->M * s->K * s->N + r * s->N + c;
}

static int
bit_add(uint64_t *b, int k)
{
	if (k < 0 || b[k >> 6] >> (k & 63) & 1)
		return 0;
	b[k >> 6] |= 1ULL << (k & 63);
	return 1;
}

/*
 * 1 when every element of D comes out as exactly its K products and its
 * C, each once; *depth the most roundings any term goes through.  why:
 * the first thing wrong.
 */
static int
prove(struct mplan *p, const struct shape *s, struct sbuf *why)
{
	static struct sv mem[256];
	static int8_t memw[256];
	int i, l, k, j, depth = 0;

	if (SB == NULL && (SB = calloc(MAXI, sizeof *SB)) == NULL)
		fail("mma: out of memory");
	memset(memw, 0, sizeof memw);
	for (i = 0; i < p->n; i++) {
		const struct ins *x = &p->in[i];
		for (l = 0; l < ML; l++) {
			struct sv *v = &SV[i][l];
			uint64_t *b = SB[i][l];
			if (x->vt == VF)
				memset(b, 0, sizeof SB[0][0]);
			switch (x->op) {
			case I_IN:
				for (j = 0; j < 2; j++)
					v->t[j] = x->opnd == OA ? tag(OA, s->ar[l][x->reg][j],
					    s->ak[l][x->reg][j]) : x->opnd == OB ? tag(OB,
					    s->bk[l][x->reg][j], s->bc[l][x->reg][j]) : tag(OC,
					    s->cr[l][x->reg][j], s->cc[l][x->reg][j]);
				if (x->vt == VF) {
					bit_add(b, c_term(s, s->cr[l][x->reg][0],
					    s->cc[l][x->reg][0]));
					v->d = 0;
				}
				break;
			case I_XCH:
				*v = SV[x->a][p->tab[x->tab][l]];
				if (x->vt == VF)
					memcpy(b, SB[x->a][p->tab[x->tab][l]], sizeof SB[0][0]);
				break;
			case I_STS:
				k = p->tab[x->tab][l];
				if (memw[k]) {
					sb_printf(why, "two lanes store to word %d of the slot", k);
					return 0;
				}
				memw[k] = 1;
				mem[k] = SV[x->a][l];
				break;
			case I_LDS:
				k = p->tab[x->tab][l];
				if (!memw[k]) {
					sb_printf(why, "lane %d loads word %d, never stored", l,
					    k);
					return 0;
				}
				*v = mem[k];
				break;
			case I_UNPK:
				v->t[0] = SV[x->a][l].t[x->half];
				if (x->vt == VF) {
					bit_add(b, c_term(s, v->t[0] >> 4 & 15, v->t[0] & 15));
					v->d = 0;
				}
				break;
			case I_SEL:
				k = l >> x->xm & 1 ? x->b : x->a;
				*v = SV[k][l];
				if (x->vt == VF)
					memcpy(b, SB[k][l], sizeof SB[0][0]);
				break;
			case I_MUL:
			case I_FMA:
			case I_DOT2:
				if (x->c >= 0)
					memcpy(b, SB[x->c][l], sizeof SB[0][0]);
				if (x->op == I_DOT2) {
					for (j = 0; j < 2; j++)
						if (!bit_add(b, prod_term(s, SV[x->a][l].t[j],
						    SV[x->b][l].t[j])))
							goto bad;
					v->d = (int16_t)(x->c >= 0 ? SV[x->c][l].d + 2 : 1);
				} else {
					if (!bit_add(b, prod_term(s, SV[x->a][l].t[0],
					    SV[x->b][l].t[0])))
						goto bad;
					v->d = (int16_t)(x->c >= 0 ? SV[x->c][l].d + 1 : 0);
				}
				break;
			case I_FADD:
				for (k = 0; k < NWD; k++) {
					if (SB[x->a][l][k] & SB[x->b][l][k])
						goto bad;
					b[k] = SB[x->a][l][k] | SB[x->b][l][k];
				}
				v->d = (int16_t)((SV[x->a][l].d > SV[x->b][l].d ?
				    SV[x->a][l].d : SV[x->b][l].d) + 1);
				break;
			case I_OUT:
				for (j = 0; j < (s->f32 ? 1 : 2); j++) {
					uint64_t want[NWD];
					int r = s->cr[l][x->reg][j], c = s->cc[l][x->reg][j];
					int src = j ? x->b : x->a, kk;
					memset(want, 0, sizeof want);
					for (kk = 0; kk < s->K; kk++)
						bit_add(want, (r * s->K + kk) * s->N + c);
					bit_add(want, c_term(s, r, c));
					if (memcmp(want, SB[src][l], sizeof want)) {
						sb_printf(why, "lane %d's D[%d][%d] is not the sum "
						    "of its %d products and C", l, r, c, s->K);
						return 0;
					}
					if (SV[src][l].d > depth)
						depth = SV[src][l].d;
				}
				break;
			}
			continue;
bad:
			sb_printf(why, "instruction %d in lane %d: a product of "
			    "elements that do not meet, or a term counted twice", i, l);
			return 0;
		}
	}
	p->depth = depth;
	p->proved = 1;
	return 1;
}

/* ---- the plan run on numbers ---- */

static float
h2f(uint32_t h)
{
	int e = (int)(h >> 10 & 31), mt = (int)(h & 1023);
	float v;

	if (e == 0)
		v = ldexpf((float)mt, -24);
	else if (e == 31)
		v = mt ? NAN : INFINITY;
	else
		v = ldexpf((float)(mt + 1024), e - 25);
	return h >> 15 & 1 ? -v : v;
}

/* f32 to f16, to nearest even */
static uint32_t
f2h(float f)
{
	uint32_t sg = signbit(f) ? 0x8000u : 0;
	float a = fabsf(f), q;
	int e;

	if (isnan(f))
		return sg | 0x7e00u;
	if (a < 0x1p-14f)
		return sg | (uint32_t)rintf(a * 0x1p24f);
	frexpf(a, &e);
	q = rintf(ldexpf(a, 11 - e));
	if (q == 2048.0f) {
		q = 1024.0f;
		e++;
	}
	if (e + 14 > 30)
		return sg | 0x7c00u;
	return sg | (uint32_t)(e + 14) << 10 | ((uint32_t)q - 1024u);
}

struct nv {
	uint32_t w;
	float f;
};
static struct nv NV[MAXI][ML];

static void
run(const struct mplan *p, const struct shape *s, uint32_t A[ML][4],
    uint32_t B[ML][2], uint32_t C[ML][4], uint32_t D[ML][4])
{
	static uint32_t mem[256];
	int i, l;

	for (i = 0; i < p->n; i++) {
		const struct ins *x = &p->in[i];
		for (l = 0; l < ML; l++) {
			struct nv *v = &NV[i][l];
			const struct nv *a = x->a >= 0 ? &NV[x->a][l] : NULL;
			const struct nv *b = x->b >= 0 ? &NV[x->b][l] : NULL;
			float acc = x->c >= 0 ? NV[x->c][l].f : 0.0f;
			switch (x->op) {
			case I_IN:
				v->w = x->opnd == OA ? A[l][x->reg] : x->opnd == OB ?
				    B[l][x->reg] : C[l][x->reg];
				memcpy(&v->f, &v->w, 4);
				break;
			case I_XCH:
				*v = NV[x->a][p->tab[x->tab][l]];
				break;
			case I_STS:
				mem[p->tab[x->tab][l]] = a->w;
				break;
			case I_LDS:
				v->w = mem[p->tab[x->tab][l]];
				break;
			case I_UNPK:
				v->f = h2f(a->w >> (16 * x->half) & 0xffff);
				break;
			case I_SEL:
				*v = l >> x->xm & 1 ? *b : *a;
				break;
			case I_MUL:
				v->f = a->f * b->f;
				break;
			case I_FMA:
				v->f = fmaf(a->f, b->f, acc);
				break;
			case I_DOT2:
				v->f = fmaf(h2f(a->w >> 16), h2f(b->w >> 16),
				    fmaf(h2f(a->w & 0xffff), h2f(b->w & 0xffff), acc));
				break;
			case I_FADD:
				v->f = a->f + b->f;
				break;
			case I_OUT:
				if (s->f32)
					memcpy(&D[l][x->reg], &a->f, 4);
				else
					D[l][x->reg] = f2h(a->f) | f2h(b->f) << 16;
				break;
			}
		}
	}
}

static uint64_t
rnd(uint64_t *st)
{
	*st ^= *st << 13;
	*st ^= *st >> 7;
	*st ^= *st << 17;
	return *st;
}

/* a random f16, normal, its exponent in -e..e */
static uint32_t
rnd_half(uint64_t *st, int e)
{
	uint64_t r = rnd(st);

	return (uint32_t)((r & 1) << 15 | (15 - e + r % (2 * e + 1)) << 10 |
	    (r >> 8 & 1023));
}

static double
gamma_n(int h)
{
	double u = 0x1p-24;

	return h * u / (1 - h * u);
}

/*
 * The plan on n random fragments against the exact sums: the largest
 * error as a fraction of the bound; *bad, the count over it.
 */
static double
check(const struct mplan *p, const struct shape *s, int n, uint64_t seed,
    int *bad)
{
	static uint32_t A[ML][4], B[ML][2], C[ML][4], D[ML][4];
	uint64_t st = seed * 0x9e3779b97f4a7c15ULL + 1;
	double worst = 0;
	int it, l, r, c, k, e = s->f32 ? 8 : 3;

	*bad = 0;
	for (it = 0; it < n; it++) {
		for (l = 0; l < ML; l++) {
			for (r = 0; r < s->na; r++)
				A[l][r] = rnd_half(&st, e) | rnd_half(&st, e) << 16;
			for (r = 0; r < s->nb; r++)
				B[l][r] = rnd_half(&st, e) | rnd_half(&st, e) << 16;
			for (r = 0; r < s->nc; r++)
				if (s->f32) {
					float f = h2f(rnd_half(&st, e)) * 4.0f;
					memcpy(&C[l][r], &f, 4);
				} else
					C[l][r] = rnd_half(&st, e) | rnd_half(&st, e) << 16;
		}
		run(p, s, A, B, C, D);
		for (r = 0; r < s->M; r++)
			for (c = 0; c < s->N; c++) {
				long double sum = 0, mag = 0, e;
				struct pos pc = s->cown[r][c];
				float got, cv;
				double bound;
				for (k = 0; k < s->K; k++) {
					struct pos pa = s->aown[r][k], pb = s->bown[k][c];
					long double t = (long double)h2f(A[pa.lane][pa.reg] >>
					    (16 * pa.half) & 0xffff) *
					    h2f(B[pb.lane][pb.reg] >> (16 * pb.half) & 0xffff);
					sum += t;
					mag += fabsl(t);
				}
				if (s->f32) {
					memcpy(&cv, &C[pc.lane][pc.reg], 4);
					memcpy(&got, &D[pc.lane][pc.reg], 4);
				} else {
					cv = h2f(C[pc.lane][pc.reg] >> (16 * pc.half) & 0xffff);
					got = h2f(D[pc.lane][pc.reg] >> (16 * pc.half) & 0xffff);
				}
				sum += cv;
				mag += fabsl((long double)cv);
				bound = gamma_n(p->depth) * (double)mag;
				if (!s->f32)	/* the f16 rounding of the f32 sum */
					bound = 0x1p-11 * fabs((double)sum) + (1 + 0x1p-11) *
					    bound + 0x1p-25;
				e = fabsl((long double)got - sum);
				if ((double)e > bound)
					(*bad)++;
				if (bound > 0 && (double)e / bound > worst)
					worst = (double)e / bound;
			}
	}
	return worst;
}

/* ---- the search ---- */

/* the best plan of each family and fetch: [family][trans A][trans B] */
static struct mplan *best[3][T_N][T_N];
static struct mplan cur, ref;
static long tried;
static int feasible[3], shaped[3];	/* priced; a butterfly that fits */

static int
better(const struct mplan *a, const struct mplan *b)
{
	if (b == NULL)
		return 1;
	if (a->cost != b->cost)
		return a->cost < b->cost;
	return a->n < b->n;
}

static void
keep(const struct mplan *p)
{
	struct mplan **slot;

	tried++;
	if (p->bad || !isfinite(p->cost))
		return;
	{
		/* an operand staged and never loaded: the plan without it */
		int i, o, ld[2] = {0, 0};
		for (i = 0; i < p->n; i++)
			if (p->in[i].op == I_LDS)
				ld[p->in[i].opnd] = 1;
		for (o = 0; o < 2; o++)
			if (p->trans[o] >= T_STAGE0 && !ld[o])
				return;
	}
	feasible[p->fam] = 1;
	slot = &best[p->fam][p->trans[0]][p->trans[1]];
	if (!better(p, *slot))
		return;
	if (*slot == NULL && (*slot = malloc(sizeof **slot)) == NULL)
		fail("mma: out of memory");
	**slot = *p;
}

/* the masks of a xor of lane bits into n values, at most k bits nonzero */
static int
next_perm(int *P, int n, int k)
{
	int i, nz;

	for (;;) {
		for (i = 0; i < 5; i++) {
			if (++P[i] < n)
				break;
			P[i] = 0;
		}
		if (i == 5)
			return 0;
		for (nz = 0, i = 0; i < 5; i++)
			nz += P[i] != 0;
		if (nz <= k)
			return 1;
	}
}

/* the next choice of each reduce bit's source: -1 (D's owner), 0..nk-1 */
static int
next_q(int *Q, int bm, int nk)
{
	int b;

	for (b = 0; b < 5; b++) {
		if (!(bm >> b & 1))
			continue;
		if (++Q[b] < nk)
			return 1;
		Q[b] = -1;
	}
	return 0;
}

static int
next_order(int *ord, int n)
{
	/* the next permutation, lexicographically */
	int i = n - 2, j, t;

	while (i >= 0 && ord[i] >= ord[i + 1])
		i--;
	if (i < 0)
		return 0;
	for (j = n - 1; ord[j] <= ord[i]; j--)
		;
	t = ord[i];
	ord[i] = ord[j];
	ord[j] = t;
	for (i++, j = n - 1; i < j; i++, j--) {
		t = ord[i];
		ord[i] = ord[j];
		ord[j] = t;
	}
	return 1;
}

static void
search(const struct shape *s, const struct model *m)
{
	struct bld b;
	int P[5], ta, tb, X, i;
	struct red R;

	tried = 0;
	memset(feasible, 0, sizeof feasible);
	memset(shaped, 0, sizeof shaped);
	for (X = 0; X < 3; X++)
		for (ta = 0; ta < T_N; ta++)
			for (tb = 0; tb < T_N; tb++)
				if (best[X][ta][tb]) {
					free(best[X][ta][tb]);
					best[X][ta][tb] = NULL;
				}
	/* the reference: output-stationary, each word from its owner, packed */
	memset(P, 0, sizeof P);
	bld_init(&b, &ref, s, m);
	b.noreuse = 1;
	ref.fam = F_OUT;
	gen_out(&b);
	if (!ref.bad)
		plan_price(&ref, s, m);
	/* output-stationary, the k words in the order kw ^ perm(l) */
	do
		for (ta = 0; ta < T_N; ta++)
			for (tb = 0; tb < T_N; tb++) {
				bld_init(&b, &cur, s, m);
				cur.fam = F_OUT;
				cur.trans[OA] = ta;
				cur.trans[OB] = tb;
				memcpy(cur.perm, P, sizeof P);
				gen_out(&b);
				if (!cur.bad)
					plan_price(&cur, s, m);
				keep(&cur);
			}
	while (next_perm(P, s->K / 2, 2));
	/* X-stationary, slot j's other index j ^ perm(l) */
	for (X = OA; X <= OB; X++) {
		int ny = X == OA ? s->N : s->M, grp[16], ng, gof[4], Q[5];
		int nkb = 7;	/* r * N + c: 3 bits of c, 4 of r */
		memset(P, 0, sizeof P);
		do {
			int bm, ord[5], nord = 0, r;
			if (!stat_keys(s, X, P, &R, grp, &ng, gof))
				continue;
			r = red_plan(s, &R, ord, -1, NULL, &bm);
			if (r == 0)
				continue;
			for (i = 0; i < 5; i++)
				if (bm >> i & 1)
					ord[nord++] = i;
			/* the reduce target's bits: D's owner's, or a key bit each */
			memset(Q, -1, sizeof Q);
			do {
			do {
				if (red_plan(s, &R, ord, nord, Q, &bm) != 1)
					continue;
				shaped[X == OA ? F_ASTAT : F_BSTAT] = 1;
				for (ta = 0; ta < T_N; ta++) {
					bld_init(&b, &cur, s, m);
					cur.fam = X == OA ? F_ASTAT : F_BSTAT;
					cur.trans[1 - X] = ta;
					cur.trans[X] = 0;
					memcpy(cur.perm, P, sizeof P);
					memcpy(cur.order, ord, sizeof ord);
					cur.nord = nord;
					gen_stat(&b, &R, X);
					if (!cur.bad)
						plan_price(&cur, s, m);
					keep(&cur);
				}
			} while (next_order(ord, nord));
			} while (next_q(Q, bm, nkb));
		} while (next_perm(P, ny, ny > 8 ? 2 : 3));
	}
}

/* ---- words ---- */

static const char *const famname[3] = {"output-stationary",
	"A-stationary", "B-stationary"};

static void
plan_text(struct sbuf *b, const struct mplan *p, const struct model *m)
{
	static const char *const what[3] = {"A", "B", "partial sums"};
	int w, k, i, nl[2] = {0, 0}, any;

	for (i = 0; i < p->n; i++)
		if (p->in[i].op == I_LDS)
			nl[p->in[i].opnd]++;
	sb_printf(b, "%s", famname[p->fam]);
	for (w = 0; w < 3; w++) {
		int n[4] = {0, 0, 0, 0};
		double pr;
		for (i = 0; i < p->n; i++)
			if (p->in[i].op == I_XCH && p->in[i].what == w)
				n[xch_form(m, p->in[i].xk, p->in[i].xm, &pr)]++;
		if (w < 2 && !nl[w] && !n[0] && !n[1] && !n[2] && !n[3])
			continue;
		if (w == 2 && !n[0] && !n[1] && !n[2] && !n[3])
			continue;
		sb_printf(b, "; %s:", what[w]);
		any = 0;
		if (w < 2 && nl[w]) {
			sb_printf(b, " %d loads from shared memory (%s)", nl[w],
			    p->trans[w] == T_STAGE0 ? "register-major" : "lane-major");
			any = 1;
		}
		{
			static const char *const fn[4] = {"xor shuffles", "quad swaps",
				"quad broadcasts", "shuffles"};
			for (k = 0; k < 4; k++)
				if (n[k]) {
					sb_printf(b, "%s %d %s", any ? "," : "", n[k], fn[k]);
					any = 1;
				}
		}
		if (w < 2 && p->trans[w] == T_SHUFU)
			sb_printf(b, " (unpacked)");
	}
	if (p->nsel)
		sb_printf(b, "; %d selects", p->nsel);
	if (p->ndot2)
		sb_printf(b, "; %d fdot2", p->ndot2);
	if (p->fam == F_OUT && xperm(p->perm, 31))
		sb_printf(b, "; k order by lane");
}

/* ---- GLSL ---- */

static const char *
vtype(int vt)
{
	return vt == VW ? "uint" : "float";
}

static void
glsl(struct sbuf *o, const struct mplan *p, const struct shape *s,
    const struct model *m, const char *fname, const char *head)
{
	static uint8_t idx[MAXT];
	int i, quad = 0, shuf = 0, dot2 = 0, stage = 0, sw = stage_words(s);
	int sgbar;
	double pr;

	for (i = 0; i < p->n; i++) {
		const struct ins *x = &p->in[i];
		if (x->op == I_XCH) {
			int f = xch_form(m, x->xk, x->xm, &pr);
			quad |= f == FM_QSWAP || f == FM_QBCAST;
			shuf = 1;
		}
		dot2 |= x->op == I_DOT2;
		stage |= x->op == I_STS;
	}
	/* a subgroup barrier where the warp is within one subgroup (it
	 * exchanges, or the model has one), else the workgroup's */
	sgbar = shuf || avail(m, C_SG_BARRIER);
	if (head)
		sb_puts(o, head);
	if (shuf || sgbar)
		sb_printf(o, "#extension GL_KHR_shader_subgroup_basic : require\n");
	if (shuf)
		sb_printf(o, "#extension GL_KHR_shader_subgroup_shuffle : require\n");
	if (quad)
		sb_printf(o, "#extension GL_KHR_shader_subgroup_quad : require\n");
	if (dot2)
		sb_printf(o, "#extension GL_EXT_spirv_intrinsics : require\n"
		    "#extension GL_EXT_shader_explicit_arithmetic_types_float16 : "
		    "require\n"
		    "// OpFDot2MixAcc32VALVE: a.x * b.x + a.y * b.y + c in f32\n"
		    "spirv_instruction(extensions = "
		    "[\"SPV_VALVE_mixed_float_dot_product\"], capabilities = [6912], "
		    "id = 6916)\n"
		    "float mma_fdot2(f16vec2 a, f16vec2 b, float c);\n");
	if (stage)
		sb_printf(o, "#ifndef MMA_WARPS\n#define MMA_WARPS 1  "
		    "// the workgroup's warps of 32\n#endif\n"
		    "shared uint mma_slot[MMA_WARPS * %du];\n", sw);
	if (s->f32)
		sb_printf(o, "void %s(uint a[%d], uint b[%d], float c[4], "
		    "out float d[4])\n{\n", fname, s->na, s->nb);
	else
		sb_printf(o, "void %s(uint a[%d], uint b[%d], uint c[2], "
		    "out uint d[2])\n{\n", fname, s->na, s->nb);
	sb_printf(o, "\tuint lane = %s & 31u;\n", sgbar ?
	    "gl_SubgroupInvocationID" : "gl_LocalInvocationIndex");
	if (shuf)
		sb_printf(o, "\tuint base = gl_SubgroupInvocationID & ~31u;\n");
	if (stage)
		sb_printf(o, "\tuint slot = (gl_LocalInvocationIndex >> 5) * %du;\n",
		    sw);
	memset(idx, 0, sizeof idx);
	for (i = 0; i < p->n; i++) {
		const struct ins *x = &p->in[i];
		int f;
		switch (x->op) {
		case I_IN:
			sb_printf(o, "\t%s v%d = %c[%d];\n", vtype(x->vt), i,
			    "abc"[x->opnd], x->reg);
			break;
		case I_XCH:
			f = xch_form(m, x->xk, x->xm, &pr);
			if (f == FM_SHUF && !idx[x->tab]) {
				int par = idx_parent(p, x->tab, idx);
				if (par >= 0)
					sb_printf(o, "\tuint i%d = i%d ^ %du;\n", x->tab, par,
					    p->tab[par][0] ^ p->tab[x->tab][0]);
				else {
					sb_printf(o, "\tuint i%d = base | (", x->tab);
					aff_text(o, p->tab[x->tab]);
					sb_printf(o, ");\n");
				}
				idx[x->tab] = 1;
			}
			sb_printf(o, "\t%s v%d = ", vtype(x->vt), i);
			if (f == FM_XOR)
				sb_printf(o, "subgroupShuffleXor(v%d, %du);\n", x->a, x->xm);
			else if (f == FM_QSWAP)
				sb_printf(o, "subgroupQuadSwap%s(v%d);\n", x->xm == 1 ?
				    "Horizontal" : x->xm == 2 ? "Vertical" : "Diagonal",
				    x->a);
			else if (f == FM_QBCAST)
				sb_printf(o, "subgroupQuadBroadcast(v%d, %du);\n", x->a,
				    x->xm);
			else
				sb_printf(o, "subgroupShuffle(v%d, i%d);\n", x->a, x->tab);
			break;
		case I_STS:
			sb_printf(o, "\tmma_slot[slot + (");
			aff_text(o, p->tab[x->tab]);
			sb_printf(o, ")] = v%d;\n", x->a);
			break;
		case I_LDS:
			sb_printf(o, "\tuint v%d = mma_slot[slot + (", i);
			aff_text(o, p->tab[x->tab]);
			sb_printf(o, ")];\n");
			break;
		case I_BAR:
			sb_printf(o, "\t%s();\n", sgbar ? "subgroupBarrier" : "barrier");
			break;
		case I_UNPK:
			sb_printf(o, "\tfloat v%d = unpackHalf2x16(v%d).%c;\n", i, x->a,
			    "xy"[x->half]);
			break;
		case I_SEL:
			sb_printf(o, "\t%s v%d = (lane & %du) != 0u ? v%d : v%d;\n",
			    vtype(x->vt), i, 1 << x->xm, x->b, x->a);
			break;
		case I_MUL:
			sb_printf(o, "\tfloat v%d = v%d * v%d;\n", i, x->a, x->b);
			break;
		case I_FMA:
			sb_printf(o, "\tfloat v%d = fma(v%d, v%d, v%d);\n", i, x->a, x->b,
			    x->c);
			break;
		case I_DOT2:
			sb_printf(o, "\tfloat v%d = mma_fdot2(unpackFloat2x16(v%d), "
			    "unpackFloat2x16(v%d), ", i, x->a, x->b);
			if (x->c >= 0)
				sb_printf(o, "v%d);\n", x->c);
			else
				sb_printf(o, "0.0);\n");
			break;
		case I_FADD:
			sb_printf(o, "\tfloat v%d = v%d + v%d;\n", i, x->a, x->b);
			break;
		case I_OUT:
			if (s->f32)
				sb_printf(o, "\td[%d] = v%d;\n", x->reg, x->a);
			else
				sb_printf(o, "\td[%d] = packHalf2x16(vec2(v%d, v%d));\n",
				    x->reg, x->a, x->b);
			break;
		}
	}
	sb_printf(o, "}\n");
}

/* glslangValidator and spirv-val on a compute shader that calls it: 1
 * accepted, 0 refused (why), -1 no tools */
static int
validate(const char *fn, const char *src, const struct shape *s,
    struct sbuf *why)
{
	char dir[] = "/tmp/ucas-mma.XXXXXX", path[256], cmd[1024];
	struct sbuf w = {0};
	FILE *fp;
	int rc;

	if (system("command -v glslangValidator >/dev/null 2>&1 && "
	    "command -v spirv-val >/dev/null 2>&1") != 0)
		return -1;
	if (mkdtemp(dir) == NULL)
		return -1;
	sb_printf(&w, "#version 450\n%s"
	    "layout(local_size_x = 32) in;\n"
	    "layout(std430, binding = 0) buffer IO { uint ab[]; } io;\n"
	    "void main()\n{\n\tuint i = gl_LocalInvocationIndex;\n"
	    "\tuint a[%d], b[%d];\n", src, s->na, s->nb);
	sb_printf(&w, "\tfor (int k = 0; k < %d; k++) a[k] = io.ab[i * 16u + "
	    "uint(k)];\n", s->na);
	sb_printf(&w, "\tfor (int k = 0; k < %d; k++) b[k] = io.ab[i * 16u + 4u "
	    "+ uint(k)];\n", s->nb);
	if (s->f32)
		sb_printf(&w, "\tfloat c[4], d[4];\n\tfor (int k = 0; k < 4; k++) "
		    "c[k] = uintBitsToFloat(io.ab[i * 16u + 8u + uint(k)]);\n"
		    "\t%s(a, b, c, d);\n\tfor (int k = 0; k < 4; k++) "
		    "io.ab[i * 16u + 12u + uint(k)] = floatBitsToUint(d[k]);\n}\n",
		    fn);
	else
		sb_printf(&w, "\tuint c[2], d[2];\n\tfor (int k = 0; k < 2; k++) "
		    "c[k] = io.ab[i * 16u + 8u + uint(k)];\n"
		    "\t%s(a, b, c, d);\n\tfor (int k = 0; k < 2; k++) "
		    "io.ab[i * 16u + 12u + uint(k)] = d[k];\n}\n", fn);
	/* the extensions go first */
	{
		struct sbuf v = {0};
		const char *t = sb_str(&w), *e;
		sb_printf(&v, "#version 450\n");
		t = strchr(t, '\n') + 1;
		while (!strncmp(t, "#extension", 10)) {
			e = strchr(t, '\n') + 1;
			sb_printf(&v, "%.*s", (int)(e - t), t);
			t = e;
		}
		sb_printf(&v, "%s", t);
		snprintf(path, sizeof path, "%s/mma.comp", dir);
		if ((fp = fopen(path, "w")) == NULL)
			return -1;
		fputs(sb_str(&v), fp);
		fclose(fp);
		free(v.p);
	}
	free(w.p);
	snprintf(cmd, sizeof cmd, "glslangValidator -V --target-env vulkan1.1 "
	    "-o %s/mma.spv %s > %s/log 2>&1 && spirv-val --target-env "
	    "vulkan1.1 %s/mma.spv >> %s/log 2>&1", dir, path, dir, dir, dir);
	rc = system(cmd);
	if (rc != 0) {
		char line[300];
		snprintf(path, sizeof path, "%s/log", dir);
		if ((fp = fopen(path, "r")) != NULL) {
			while (fgets(line, sizeof line, fp))
				if (strstr(line, "ERROR") || strstr(line, "error")) {
					line[strcspn(line, "\n")] = 0;
					sb_printf(why, "%s", line);
					break;
				}
			fclose(fp);
		}
	}
	snprintf(cmd, sizeof cmd, "rm -rf %s", dir);
	if (system(cmd) != 0)
		;
	return rc == 0;
}

/* ---- the command ---- */

static int
cmp_plan(const void *a, const void *b)
{
	const struct mplan *p = *(const struct mplan *const *)a;
	const struct mplan *q = *(const struct mplan *const *)b;

	return better(p, q) ? -1 : better(q, p) ? 1 : 0;
}

static void
mma_run(int k16, int f32, const struct model *m, int all, int val,
    int nofile, uint64_t seed)
{
	static struct shape S;
	struct mplan *list[3 * T_N * T_N], *p;
	struct sbuf why = {0}, t = {0}, g = {0};
	int n = 0, i, ta, tb, f, shown, bad, nterm;
	char fname[48], file[64];
	double worst;

	shape_build(&S, k16, f32);
	if (!avail(m, C_SG_SHUF) && !(isfinite(price(m, C_LOAD_SHARED)) &&
	    isfinite(price(m, C_STORE_SHARED))))
		fail("mma: %s has neither subgroup shuffles (sg_shuffle) nor "
		    "shared memory to move the fragments with", sym_str(m->name));
	search(&S, m);
	for (f = 0; f < 3; f++)
		for (ta = 0; ta < T_N; ta++)
			for (tb = 0; tb < T_N; tb++)
				if (best[f][ta][tb])
					list[n++] = best[f][ta][tb];
	if (n == 0)
		fail("mma: no dataflow is possible under %s (its subgroup "
		    "operations or its shared memory are missing)",
		    sym_str(m->name));
	qsort(list, (size_t)n, sizeof list[0], cmp_plan);
	/* the proof of the cheapest that holds (each shown is proved) */
	for (i = 0; i < n; i++) {
		sb_clear(&why);
		if (!prove(list[i], &S, &why))
			fail("mma: internal error, a plan failed its proof: %s",
			    sb_str(&why));
	}
	p = list[0];
	nterm = S.K;
	snprintf(fname, sizeof fname, "mma_%s_%s", S.name, f32 ? "f32" : "f16");
	rep_begin("mma");
	printf("mma %s: D = A B + C on a warp's fragments as PTX's "
	    "mma.sync.aligned.%s.row.col lays them out, f16 A and B, %s C and "
	    "D, 32 lanes, under %s (%ld dataflows tried)\n", S.name, S.name,
	    f32 ? "f32" : "f16", sym_str(m->name), tried);
	rep_str("shape", S.name);
	rep_str("accumulator", f32 ? "f32" : "f16");
	rep_str("model", sym_str(m->name));
	rep_int("tried", tried);
	printf("  each of D's %d elements is a sum of %d products of f16 and its "
	    "C\n", S.M * S.N, nterm);
	rep_list("dataflows");
	shown = all ? n : n < 6 ? n : 6;
	for (i = 0; i < shown; i++) {
		sb_clear(&t);
		plan_text(&t, list[i], m);
		printf("  %2d. %-9g %s, depth %d\n", i + 1, list[i]->cost, sb_str(&t),
		    list[i]->depth);
		rep_obj(NULL);
		rep_num("cost", list[i]->cost);
		rep_str("dataflow", sb_str(&t));
		rep_int("depth", list[i]->depth);
		rep_end();
	}
	rep_end();
	if (shown < n)
		printf("  (%d more: mma ... all)\n", n - shown);
	for (f = 0; f < 3; f++)
		if (!feasible[f])
			printf("  %s: none possible: %s\n", famname[f], f == F_OUT ||
			    shaped[f] ? "its exchanges need subgroup shuffles, which "
			    "the model does not list (sg_shuffle)" : "no assignment of "
			    "the partial sums to registers (a xor of the lane's bits) "
			    "lets a butterfly send and read them from the same "
			    "registers in every lane");
	if (!ref.bad) {
		sb_clear(&why);
		if (!prove(&ref, &S, &why))
			fail("mma: internal error, the reference failed its proof: %s",
			    sb_str(&why));
		sb_clear(&t);
		plan_text(&t, &ref, m);
		printf("  reference, each word fetched from the lane that holds it: "
		    "%g (%s, depth %d)", ref.cost, sb_str(&t), ref.depth);
		if (ref.cost > list[0]->cost * 1.005)
			printf("; the chosen is %.2fx cheaper\n", ref.cost /
			    list[0]->cost);
		else
			printf("; nothing cheaper under %s\n", sym_str(m->name));
		rep_num("reference_cost", ref.cost);
	}
	sb_clear(&t);
	plan_text(&t, p, m);
	printf("  chosen: %s, cost %g\n", sb_str(&t), p->cost);
	rep_str("chosen", sb_str(&t));
	rep_num("cost", p->cost);
	{
		int nx = 0, w, k;
		for (w = 0; w < 3; w++)
			for (k = 0; k < 3; k++)
				nx += p->nx[k][w];
		printf("    %d exchanges, %d loads and %d stores of shared memory "
		    "(bank conflicts at most %d-way), %d barriers, %d unpacks, "
		    "%d %s, %d adds%s\n", nx, p->nlds, p->nsts, p->maxdeg ?
		    p->maxdeg : 1, p->nbar, p->nunpk, p->ndot2 ? p->ndot2 : p->nfma,
		    p->ndot2 ? "fdot2" : "multiply-adds", p->nfadd, f32 ? "" :
		    ", 2 packs");
		if (p->nidx)
			printf("    %d shuffle indices, %d integer operations\n",
			    p->nidx, p->idxops);
	}
	printf("  proof: the plan run on symbols in all 32 lanes gives every "
	    "element of D as exactly its %d products and its C, each once "
	    "(exhaustive over the lanes)\n", nterm);
	rep_proof("exhaustive", "the plan run on symbols in all 32 lanes: "
	    "every element of D is exactly its K products and its C, each once");
	printf("  bound: |D - (A B + C)| <= gamma_%d (sum_k |A_ik B_kj| + "
	    "|C_ij|), gamma_%d = %d u / (1 - %d u) = %.4g, u = 2^-24%s\n",
	    p->depth, p->depth, p->depth, p->depth, gamma_n(p->depth),
	    f32 ? "" : "; then D's f16 rounding, 2^-11 |D| (2^-25 below "
	    "the normals)");
	rep_strf("bound", "gamma_%d (sum_k |A_ik B_kj| + |C_ij|)%s", p->depth,
	    f32 ? "" : " + f16 rounding");
	rep_int("depth", p->depth);
	printf("    a product of two f16 is exact in f32 (22 significant bits, "
	    "exponents within f32's normals), so only the sums round: each "
	    "term through at most %d roundings%s\n", p->depth, p->ndot2 ?
	    " (an fdot2 counted as two)" : "");
	{
		int nx = 0, w, k;
		const char *c1, *c3 = NULL;
		for (w = 0; w < 3; w++)
			for (k = 0; k < 3; k++)
				nx += p->nx[k][w];
		c1 = nx ? "every lane of the warp active, the warp a subgroup of 32 "
		    "or 32 aligned lanes of a larger one" : avail(m, C_SG_BARRIER) ?
		    "the warp within one subgroup, every lane active" :
		    "every invocation of the workgroup calls it (a workgroup "
		    "barrier), each warp 32 consecutive invocations";
		if (p->ndot2)
			c3 = "an fdot2 rounds at most twice (SPV_VALVE_mixed_float_"
			    "dot_product leaves its rounding to the device)";
		printf("  holds when: %s; the f32 sums round to nearest%s%s\n", c1,
		    c3 ? "; " : "", c3 ? c3 : "");
		rep_cond("%s", c1);
		rep_cond("the f32 sums round to nearest");
		if (c3)
			rep_cond("%s", c3);
	}
	worst = check(p, &S, 64, seed, &bad);
	printf("  check: 64 random sets of fragments in f32 against the exact "
	    "sums: %s, the largest error %.3g of the bound (sampled, not a "
	    "proof)\n", bad ? "OVER THE BOUND" : "within the bound", worst);
	rep_check("random", 64L * S.M * S.N, worst, !bad, "random fragments "
	    "against the exact sums, as a fraction of the bound");
	sb_clear(&t);
	plan_text(&t, p, m);
	sb_clear(&why);
	sb_printf(&why, "// D = A B + C on a warp's fragments as PTX's "
	    "mma.sync.aligned.%s.row.col\n// lays them out (f16 A and B, %s C "
	    "and D), for a GPU without a matrix unit.\n// ucas mma %s %s under "
	    "%s: %s;\n// cost %g (each word fetched from its lane: %g).\n// "
	    "Proved over the 32 lanes: each element of D is its %d products "
	    "and C, each once;\n// |D - (A B + C)| <= gamma_%d (sum_k |A_ik "
	    "B_kj| + |C_ij|)%s, u = 2^-24.\n", S.name, f32 ? "f32" : "f16",
	    S.name, f32 ? "f32" : "f16", sym_str(m->name), sb_str(&t), p->cost,
	    ref.cost, S.K, p->depth, f32 ? "" : ", then D's f16 rounding");
	glsl(&g, p, &S, m, fname, sb_str(&why));
	if (val) {
		sb_clear(&why);
		i = validate(fname, sb_str(&g), &S, &why);
		if (i < 0)
			printf("  validate: glslangValidator or spirv-val is not on "
			    "PATH\n");
		else
			printf("  validate: a compute shader of 32 lanes calling it "
			    "%s glslangValidator and spirv-val%s%s\n", i ? "passes" :
			    "FAILS", i ? "" : ": ", i ? "" : sb_str(&why));
		if (i >= 0)
			rep_check("glslang", 1, 0, i, "glslangValidator and spirv-val");
	}
	snprintf(file, sizeof file, "%s.glsl", fname);
	printf("  GLSL (%s):\n", file);
	{
		const char *q = sb_str(&g), *e;
		for (; *q; q = e) {
			e = strchr(q, '\n');
			e = e ? e + 1 : q + strlen(q);
			printf("    %.*s", (int)(e - q), q);
		}
	}
	rep_str("glsl", sb_str(&g));
	deliver_file(file, "text/plain", sb_str(&g), g.n, nofile);
	free(why.p);
	free(t.p);
	free(g.p);
}

int
mma_command(struct P *p)
{
	char w[48];
	uint32_t at = cmdp_pos(p);
	struct model *m = model_active();
	int k16 = 1, f32 = 1, all = 0, val = 0, nofile = 0;
	int64_t v;
	uint64_t seed = 1;

	if (!cmdp_word(p, w, sizeof w))
		return 0;
	if ((strcmp(w, "mma") != 0 && strcmp(w, "hmma") != 0) ||
	    func_find(sym_cstr(w))) {
		cmdp_seek(p, at);
		return 0;
	}
	while (!cmdp_eos(p)) {
		if (cmdp_kw(p, "m16n8k16"))
			k16 = 1;
		else if (cmdp_kw(p, "m16n8k8"))
			k16 = 0;
		else if (cmdp_kw(p, "f32"))
			f32 = 1;
		else if (cmdp_kw(p, "f16"))
			f32 = 0;
		else if (cmdp_kw(p, "all"))
			all = 1;
		else if (cmdp_kw(p, "validate"))
			val = 1;
		else if (cmdp_kw(p, "nofile"))
			nofile = 1;
		else if (cmdp_kw(p, "seed")) {
			if (!cmdp_int(p, &v) || v < 0)
				fail("mma: seed N, a whole number");
			seed = (uint64_t)v;
		} else if (cmdp_kw(p, "model") || cmdp_kw(p, "under") ||
		    cmdp_kw(p, "on")) {
			if (!cmdp_word(p, w, sizeof w) ||
			    (m = model_find(sym_cstr(w))) == NULL)
				fail("mma: unknown model (see 'models')");
		} else {
			cmdp_fail_here(p);
			fail("mma [m16n8k16 | m16n8k8] [f32 | f16] [model M] [all] "
			    "[validate] [nofile] [seed N]");
		}
	}
	notes_flush();
	mma_run(k16, f32, m, all, val, nofile, seed);
	return 1;
}

/* ---- English ---- */

/*
 * "emulate hmma on rdna2", "a warp matrix multiply m16n8k8 with f16
 * accumulators under gt1030", "tensor core mma without cooperative
 * matrices", "mma.sync m16n8k16 f32"
 */
const char *
mma_nlp_raw(const char *sent)
{
	static char out[200];
	static const char *const keys[] = {"hmma", "mma", "tensor core",
		"tensor-core", "matrix multiply-accumulate", "matrix multiply "
		"accumulate", "warp matrix", "mma.sync", NULL};
	char buf[600], *s, *q, model[48] = "";
	int i, k16 = 1, f32 = 1, hit = 0;
	size_t n;

	n = strlen(sent);
	if (n >= sizeof buf)
		return NULL;
	for (i = 0; (size_t)i <= n; i++)
		buf[i] = (char)(sent[i] >= 'A' && sent[i] <= 'Z' ? sent[i] + 32 :
		    sent[i]);
	s = buf;
	for (i = 0; keys[i]; i++) {
		const char *h = strstr(s, keys[i]);
		size_t kn = strlen(keys[i]);
		if (h && (h == s || !(h[-1] >= 'a' && h[-1] <= 'z')) &&
		    !(h[kn] >= 'a' && h[kn] <= 'z'))
			hit = 1;
	}
	if (!hit)
		return NULL;
	/* not a definition or another command's statement */
	if (strchr(s, '=') || strchr(s, '('))
		return NULL;
	if (strstr(s, "k8") && !strstr(s, "k16"))
		k16 = 0;
	if (strstr(s, "f16 acc") || strstr(s, "half acc") ||
	    strstr(s, "f16 c") || strstr(s, "f16 output") ||
	    strstr(s, "f16 result") || (strstr(s, "f16") && !strstr(s, "f32") &&
	    strstr(s, "accum")))
		f32 = 0;
	for (q = s; (q = strpbrk(q, " ")) != NULL; q++) {
		const char *w = q + 1;
		size_t wn = strcspn(w, " ?.,");
		if (wn && wn < sizeof model && (q - s >= 3) &&
		    (!strncmp(q - 3, " on", 3) || !strncmp(q - 3, "der", 3) ||
		    !strncmp(q - 3, "for", 3) || !strncmp(q - 3, "del", 3)) &&
		    model_find(sym_intern(w, wn)) != NULL) {
			memcpy(model, w, wn);
			model[wn] = 0;
		}
	}
	snprintf(out, sizeof out, "mma %s %s%s%s%s%s%s", k16 ? "m16n8k16" :
	    "m16n8k8", f32 ? "f32" : "f16", model[0] ? " model " : "", model,
	    strstr(s, "validat") ? " validate" : "", strstr(s, "nofile") ?
	    " nofile" : "", strstr(s, "every dataflow") || strstr(s,
	    "all dataflows") ? " all" : "");
	return out;
}
