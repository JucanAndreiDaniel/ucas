/* SPDX-License-Identifier: GPL-3.0-or-later */
/* winograd.c: Winograd's inner product, priced for a block of outputs
 * that share their rows' and columns' corrections */
#ifndef UCAS_WINOGRAD_H
#define UCAS_WINOGRAD_H

#include "ucas.h"

struct P;
int winograd_command(struct P *p);	/* `winograd F [rows R] [cols C] [tol T]` */
void winograd_run(const struct func *f, long rows, long cols, double tol);
const char *winograd_nlp_raw(const char *sent);	/* nlp.c */

#endif
