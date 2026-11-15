/* SPDX-License-Identifier: GPL-3.0-or-later */
/* fdot.c: an exact float sum of products on a binary grid as an integer
 * dot product (dot.c), scaled once */
#ifndef UCAS_FDOT_H
#define UCAS_FDOT_H

#include "ucas.h"

/* find's section for f (an f32 body): 1 when it said something */
int fdot_find(const struct func *f);

#endif
