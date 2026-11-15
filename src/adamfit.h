/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * adamfit: a structure search for cheap approximations.  Thousands of
 * expression shapes over x and trainable constants, each shape's constants
 * fitted by Adam (gradient descent with moment estimates, reverse-mode
 * gradients over a sample), ranked by
 *
 *     score = wcost * cost / C0 + werr * log2(1 + err / tol)
 *
 * (C0: the target's own cost under the active model; tol: the error unit,
 * 1 ulp by default), the finalists' error certified on the whole interval
 * (acert.c).  Streams each better candidate as it is found; `auto` reports
 * only the closest candidates at the end.
 */
#ifndef ADAMFIT_H
#define ADAMFIT_H

struct P;
int adamfit_command(struct P *p);		/* parse.c */
const char *adamfit_nlp_raw(const char *sent);	/* nlp.c */
/* the statement is adamfit on a code block: no SPIR-V note (nlp.c) */
int adamfit_wants_glsl(const char *stmt);

#endif
