/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * mma.c: a warp's matrix product (an MMA of a tensor core: PTX's
 * mma.sync m16n8k16 and m16n8k8 with f16 A and B) on a GPU that has no
 * matrix unit, as subgroup exchanges and dot products: the dataflows
 * searched, priced under the active model, the cheapest proved over the
 * 32 lanes and written as GLSL.
 *
 *   mma [m16n8k16 | m16n8k8] [f32 | f16] [model M] [all] [validate]
 *       [nofile] [seed N]
 */
#ifndef MMA_H
#define MMA_H

struct P;
int mma_command(struct P *p);			/* parse.c */
const char *mma_nlp_raw(const char *sent);	/* nlp.c */

#endif
