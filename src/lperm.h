/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * lperm.c: a lane map of a subgroup, l -> map[l] (lane l reads the value
 * of lane map[l]), realised as the cheapest proved sequence of exchanges
 * the active cost model prices.
 *
 * A map that is F2-affine on the lanes' bits, map[l] = A l ^ c, is a
 * composition of conditional xor exchanges: stage i is
 *
 *	s_i(l) = p_i(l) ? s_(i-1)(l ^ k_i) : s_(i-1)(l),
 *	p_i(l) = parity(l & m_i) ^ e_i
 *
 * a shuffle by lane xor k_i (sg_shuffle_xor, or sg_quad where k_i < 4),
 * then a select on a parity of the lane's bits (none where m_i = 0 and
 * e_i = 1: every lane takes the exchange).  The stages compose to
 * map[l] = g_1(g_2(... g_n(l))), g_i(l) = l ^ k_i p_i(l), whose linear
 * part is the product of the elementary maps I ^ k_i m_i^T.  Each stage
 * changes the linear part by a matrix of rank one, so rank(I ^ A) stages
 * are needed and the search, which takes a stage only where it lowers
 * the rank of what is left by one, finds a sequence of that length (the
 * fewest; among those, the cheapest it finds by a beam of the stages'
 * prices, not an exhaustive minimum).  The constant c is reached by the
 * stages' e_i or one unconditional exchange.  Recursive doubling and
 * butterflies are the case A = I (unconditional exchanges only); a
 * broadcast within groups of 2^j lanes is a singular A.
 *
 * A map that is not affine but takes each lane's value to at most one
 * lane (a permutation, or a part of one: an unread lane's source is any
 * the others leave) goes through a Benes network over the lane bits, in
 * an order searched: 2 n - 1 stages of exchanges by lane xor 2^b, the
 * outer bit first and last, each lane pair swapping or not by the
 * looping algorithm (two subnetworks, the pairs of sources and of
 * destinations given different ones, recursively).  A stage's lanes are
 * then a table (taken where (T >> lane) & 1); a table that is a parity
 * of the lane's bits is written as one, an empty one is dropped and a
 * full one is an exchange in every lane.  A map that copies a lane to
 * two has no such route, and stays one shuffle.
 *
 * Besides the stages: no data movement where the map is the identity; a
 * quad's broadcast (map[l] = (l & ~3) | i), one sg_quad; and one
 * shuffle by an index, the price given or (for an affine map) that of
 * the index written as shifts, masks and xors.  The cheapest under the
 * model is chosen, and with a model where the stages are not cheaper,
 * they are not.
 *
 * Proof: the stages are composed lane by lane, every one of the W lanes
 * (every point of a finite domain); lane l's value after the stages is
 * lane g_1(...g_n(l))'s by the definitions of the shuffle and the select.
 */
#ifndef UCAS_LPERM_H
#define UCAS_LPERM_H

#include "ucas.h"

#define LPERM_MAXST 14	/* stages: at most 2 log2(W) + 1 */

enum { LPH_NONE, LPH_IDENTITY, LPH_STAGES, LPH_QUADBCAST, LPH_SHUFFLE };
/* how a stage's exchange is done */
enum { LPX_XOR, LPX_QUAD, LPX_SHUF };

struct lperm_stage {
	uint8_t k;	/* exchange with lane xor k */
	uint8_t m, e;	/* taken where parity(lane & m) ^ e; m 0, e 1: always */
	uint8_t istab;	/* taken where (tab >> lane) & 1 instead */
	uint8_t how;	/* LPX_*: the class its exchange is priced by */
	uint64_t tab;
	double price;	/* the exchange, and the select and predicate */
};
/* a stage every lane takes: the exchange alone, no select */
#define LPERM_ALWAYS(s) (!(s)->m && !(s)->istab)

struct lperm_plan {
	int w, bits;		/* lanes (a power of two), log2 */
	int kind;		/* LPH_*: the cheapest */
	int affine;		/* the map is affine on its defined lanes */
	int benes;		/* the stages are a Benes network's (not affine) */
	uint8_t col[6], c;	/* map[l] = A l ^ c, col[j] = A e_j */
	int rank;		/* rank(I ^ A): the fewest conditional stages */
	int nst;
	struct lperm_stage st[LPERM_MAXST];
	int qbi;		/* the quad's lane of a broadcast, -1 */
	double price;		/* the chosen realisation's */
	double stages_price;	/* the stages' (INFINITY: none) */
	double shuffle_price;	/* one shuffle by an index (INFINITY: none) */
	int proved;		/* the stages give map on every defined lane */
};

/*
 * The cheapest proved realisation of map (w lanes, w a power of two up
 * to 64; map[l] -1 where lane l's result is not read) under m, filled
 * into *p.  idx_price is what an index for one shuffle costs (< 0: the
 * affine index's price, as shifts, masks and xors; INFINITY: no
 * shuffle).  Returns p->kind, LPH_NONE where nothing realises the map
 * (no exchange the model lists; a map out of the lanes).
 */
int lperm_plan(const struct model *m, const int16_t *map, int w,
    double idx_price, struct lperm_plan *p);
/*
 * The price of the cheapest proved realisation of a 32-lane map under m,
 * INFINITY where none; *stages (may be NULL) gets the number of exchange
 * stages it uses (0 for the identity, 1 for one shuffle or quad op).
 */
double lperm_price(const struct model *m, const int16_t map[32], int *stages);
/* map fitted as A l ^ c on its defined lanes; 0 when it is not affine */
int lperm_affine(const int16_t *map, int w, uint8_t *col, uint8_t *c);
/*
 * The plan as an expression: v a value per lane (the bound lane in it),
 * read in lane at, W lanes.  LPH_SHUFFLE gives sg_shuffle(v, idx), idx
 * the affine index of `at` (affine maps only), else 0.
 */
nid lperm_expr(const struct lperm_plan *p, nid v, nid at);
/* "2 stages: xor 1 where lane & 2, ..." */
void lperm_text(struct sbuf *b, const struct lperm_plan *p);
/* `lperm INDEX [lanes N] [model M]` (parse.c) */
struct P;
int lperm_command(struct P *p);
/* English for it (nlp.c): "the lane map ... as xor stages under rdna2" */
const char *lperm_nlp_raw(const char *sent);

#endif
