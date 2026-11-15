/* SPDX-License-Identifier: GPL-3.0-or-later */
/* tcdot.c: a tensor core's block FMA (f16 products, f32 accumulate) as
 * an operation written over the bits; its derived error bound */
#ifndef UCAS_TCDOT_H
#define UCAS_TCDOT_H

#include "ucas.h"

#define TC_MAXN 16

/* the block over n pairs of f16 and an f32 c: frac fractional bits in
 * the window (24), the exponent's floor (-132) */
nid tc_dot_expr(const nid *a, const nid *b, int n, nid c, int frac,
    int floor_e);
/* tc_dot(A, B, c), A and B tables of f16 (parse.c) */
nid tc_dot_call(nid ta, nid tb, nid c);
/* `tcdot [n N] [samples N] [seed N] [cancel]`: the semantics, the bound
 * and a sampled check */
struct P;
int tcdot_command(struct P *p);
void tcdot_report(int n, int samples, uint64_t seed, int cancel);
const char *tcdot_nlp_raw(const char *sent);

#endif
