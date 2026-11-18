/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * ecisog.c - isogenies: classical modular polynomials Phi_l (mod p by
 * linear algebra on q-expansions of j, over Z by CRT on several primes,
 * verified mod an extra prime), Velu's formulas from a kernel point,
 * Kohel's from a kernel polynomial, distinct-degree factorisation (the
 * field of definition of torsion), and l-isogeny graphs.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ucas.h"
#include "ring.h"
#include "ecff.h"

#define PCO(F, a, i) ((a)->c + (size_t)(i) * (size_t)(F)->n)

/* ---- q-series mod p ---- */

/* J1 = q j(q) = E4^3 / prod (1 - q^n)^24, T coefficients (stride n) */
static void
jseries(const struct mf *F, u64 *J, int T)
{
	int n = F->n, i, k;
	u64 *E4 = xcalloc((size_t)T * n, sizeof(u64));
	u64 *eta = xcalloc((size_t)T * n, sizeof(u64));
	u64 *a = xcalloc((size_t)T * n, sizeof(u64));
	u64 *b = xcalloc((size_t)T * n, sizeof(u64));
	u64 t[FW], inv0[FW];

#define S(v, i) ((v) + (size_t)(i) * n)
	/* E4 = 1 + 240 sum sigma3(m) q^m */
	mf_one(F, S(E4, 0));
	for (i = 1; i < T; i++) {
		u64 s3 = 0;
		for (k = 1; k <= i; k++)
			if (i % k == 0)
				s3 += (u64)k * k * k;
		mf_from_u64(F, S(E4, i), s3);
		mf_mul_u64(F, S(E4, i), S(E4, i), 240);
	}
	/* eta = prod (1 - q^m) by Euler's pentagonal numbers */
	for (k = 0;; k++) {
		int e1 = k * (3 * k - 1) / 2, e2 = k * (3 * k + 1) / 2, done = 1;
		if (e1 < T) {
			mf_from_i64(F, S(eta, e1), (k & 1) ? -1 : 1);
			done = 0;
		}
		if (k > 0 && e2 < T) {
			mf_from_i64(F, S(eta, e2), (k & 1) ? -1 : 1);
			done = 0;
		}
		if (done)
			break;
	}
	/* series product helper: r = x * y mod q^T */
#define SMUL(r, x, y) do { \
	memset(b, 0, sizeof(u64) * (size_t)T * n); \
	for (int ii = 0; ii < T; ii++) { \
		if (mf_is_zero(F, S(x, ii))) continue; \
		for (int jj = 0; ii + jj < T; jj++) { \
			mf_mul(F, t, S(x, ii), S(y, jj)); \
			mf_add(F, S(b, ii + jj), S(b, ii + jj), t); \
		} \
	} \
	memcpy(r, b, sizeof(u64) * (size_t)T * n); \
} while (0)
	/* eta^24 = ((eta^2)^2 (eta^2))... : eta^8 = ((eta^2)^2)^2, eta^24 =
	 * eta^8 eta^16 */
	memcpy(a, eta, sizeof(u64) * (size_t)T * n);
	SMUL(a, a, a);           /* 2 */
	SMUL(a, a, a);           /* 4 */
	SMUL(a, a, a);           /* 8 */
	memcpy(eta, a, sizeof(u64) * (size_t)T * n);
	SMUL(a, a, a);           /* 16 */
	SMUL(a, a, eta);         /* 24 */
	/* inverse of a (a[0] = 1) */
	memset(eta, 0, sizeof(u64) * (size_t)T * n);
	mf_inv(F, inv0, S(a, 0), NULL);
	mf_copy(F, S(eta, 0), inv0);
	for (i = 1; i < T; i++) {
		u64 acc[FW];
		mf_zero(F, acc);
		for (k = 1; k <= i; k++) {
			mf_mul(F, t, S(a, k), S(eta, i - k));
			mf_add(F, acc, acc, t);
		}
		mf_mul(F, acc, acc, inv0);
		mf_neg(F, S(eta, i), acc);
	}
	/* E4^3 / eta^24 */
	SMUL(E4, E4, E4);
	{
		u64 *e3 = xcalloc((size_t)T * n, sizeof(u64));
		memcpy(e3, E4, sizeof(u64) * (size_t)T * n);
		/* E4 now E4^2; need E4^3: recompute E4 */
		memset(a, 0, sizeof(u64) * (size_t)T * n);
		mf_one(F, S(a, 0));
		for (i = 1; i < T; i++) {
			u64 s3 = 0;
			for (k = 1; k <= i; k++)
				if (i % k == 0)
					s3 += (u64)k * k * k;
			mf_from_u64(F, S(a, i), s3);
			mf_mul_u64(F, S(a, i), S(a, i), 240);
		}
		SMUL(e3, e3, a);
		SMUL(J, e3, eta);
		free(e3);
	}
#undef SMUL
#undef S
	free(E4);
	free(eta);
	free(a);
	free(b);
}

/*
 * Phi_l mod p: c[i * (l + 2) + j] the coefficient of X^i Y^j (0 <= i, j
 * <= l + 1).  Returns 1, or 0 when the linear system is singular.
 */
int
modpoly_mod(const struct mf *F, int l, u64 *c)
{
	int n = F->n, T, U = 0, i, k, nr, col, row, emin, E, L2 = l + 2;
	int *ui, *uk;
	u64 *J, **Jp, **Jl, *A, t[FW];

#define S(v, i) ((v) + (size_t)(i) * n)
	emin = -(l * l + l);
	E = 2 * l + 8;
	T = E - emin + 2;
	nr = E - emin + 1;
	ui = xmalloc(sizeof(int) * (size_t)(L2 * L2));
	uk = xmalloc(sizeof(int) * (size_t)(L2 * L2));
	for (i = 0; i <= l; i++)
		for (k = i; k <= l; k++)
			if (!(i == l && k == l)) {
				ui[U] = i;
				uk[U] = k;
				U++;
			}
	J = xcalloc((size_t)T * n, sizeof(u64));
	jseries(F, J, T);
	/* powers J1(q)^i and J1(q^l)^k, i, k <= l + 1 */
	Jp = xmalloc(sizeof(u64 *) * (size_t)(l + 2));
	Jl = xmalloc(sizeof(u64 *) * (size_t)(l + 2));
	for (i = 0; i <= l + 1; i++) {
		Jp[i] = xcalloc((size_t)T * n, sizeof(u64));
		Jl[i] = xcalloc((size_t)T * n, sizeof(u64));
		if (i == 0) {
			mf_one(F, S(Jp[0], 0));
			mf_one(F, S(Jl[0], 0));
			continue;
		}
		for (int a = 0; a < T; a++) {
			if (mf_is_zero(F, S(Jp[i - 1], a)))
				continue;
			for (int b = 0; a + b < T; b++) {
				mf_mul(F, t, S(Jp[i - 1], a), S(J, b));
				mf_add(F, S(Jp[i], a + b), S(Jp[i], a + b), t);
			}
		}
		/* J1(q^l)^i: substitute q -> q^l in J1^i */
		for (int a = 0; a * l < T; a++)
			mf_copy(F, S(Jl[i], a * l), S(Jp[i], a));
	}
	/* rows: q^e, e = emin .. E; columns: the unknowns, then the constant
	 * (the known terms X^(l+1) + Y^(l+1) - X^l Y^l) */
	A = xcalloc((size_t)nr * (U + 1) * n, sizeof(u64));
#define AE(r, c) (A + ((size_t)(r) * (U + 1) + (c)) * n)
	for (col = 0; col <= U; col++) {
		/* the series of the monomial(s) of this column */
		int nm = 0, mi[3], mk[3], sg[3], m;
		if (col < U) {
			mi[nm] = ui[col];
			mk[nm] = uk[col];
			sg[nm++] = 1;
			if (ui[col] != uk[col]) {
				mi[nm] = uk[col];
				mk[nm] = ui[col];
				sg[nm++] = 1;
			}
		} else {
			mi[nm] = l + 1;
			mk[nm] = 0;
			sg[nm++] = 1;
			mi[nm] = 0;
			mk[nm] = l + 1;
			sg[nm++] = 1;
			mi[nm] = l;
			mk[nm] = l;
			sg[nm++] = -1;
		}
		for (m = 0; m < nm; m++) {
			int off = -(mi[m] + l * mk[m]);   /* q-exponent of term 0 */
			u64 *X = Jp[mi[m]], *Y = Jl[mk[m]];
			for (int a = 0; a < T; a++) {
				if (mf_is_zero(F, S(X, a)))
					continue;
				for (int b = 0; a + b < T; b += l) {
					int ex = off + a + b;
					if (ex > E)
						break;
					if (mf_is_zero(F, S(Y, b)))
						continue;
					mf_mul(F, t, S(X, a), S(Y, b));
					if (sg[m] < 0)
						mf_neg(F, t, t);
					mf_add(F, AE(ex - emin, col), AE(ex - emin, col), t);
				}
			}
		}
	}
	/* solve A[:, :U] x = -A[:, U] by Gauss-Jordan */
	row = 0;
	{
		int *piv = xmalloc(sizeof(int) * (size_t)U);
		for (col = 0; col < U; col++) {
			int r2, pr = -1;
			u64 inv[FW];
			for (r2 = row; r2 < nr; r2++)
				if (!mf_is_zero(F, AE(r2, col))) {
					pr = r2;
					break;
				}
			if (pr < 0) {
				free(piv);
				goto bad;
			}
			if (pr != row)
				for (int cc = 0; cc <= U; cc++) {
					u64 s[FW];
					mf_copy(F, s, AE(pr, cc));
					mf_copy(F, AE(pr, cc), AE(row, cc));
					mf_copy(F, AE(row, cc), s);
				}
			mf_inv(F, inv, AE(row, col), NULL);
			for (int cc = col; cc <= U; cc++)
				mf_mul(F, AE(row, cc), AE(row, cc), inv);
			for (r2 = 0; r2 < nr; r2++) {
				u64 f[FW];
				if (r2 == row || mf_is_zero(F, AE(r2, col)))
					continue;
				mf_copy(F, f, AE(r2, col));
				for (int cc = col; cc <= U; cc++) {
					mf_mul(F, t, f, AE(row, cc));
					mf_sub(F, AE(r2, cc), AE(r2, cc), t);
				}
			}
			piv[col] = row++;
		}
		/* consistency: the remaining rows must be 0 = 0 */
		for (int r2 = row; r2 < nr; r2++)
			if (!mf_is_zero(F, AE(r2, U))) {
				free(piv);
				goto bad;
			}
		memset(c, 0, sizeof(u64) * (size_t)(L2 * L2) * FW);
		for (col = 0; col < U; col++) {
			u64 v[FW];
			mf_neg(F, v, AE(piv[col], U));
			mf_copy(F, c + (size_t)(ui[col] * L2 + uk[col]) * FW, v);
			mf_copy(F, c + (size_t)(uk[col] * L2 + ui[col]) * FW, v);
		}
		mf_one(F, c + (size_t)((l + 1) * L2) * FW);
		mf_one(F, c + (size_t)(l + 1) * FW);
		mf_one(F, t);
		mf_neg(F, c + (size_t)(l * L2 + l) * FW, t);
		free(piv);
	}
	free(A);
	for (i = 0; i <= l + 1; i++) {
		free(Jp[i]);
		free(Jl[i]);
	}
	free(Jp);
	free(Jl);
	free(J);
	free(ui);
	free(uk);
	return 1;
bad:
	free(A);
	for (i = 0; i <= l + 1; i++) {
		free(Jp[i]);
		free(Jl[i]);
	}
	free(Jp);
	free(Jl);
	free(J);
	free(ui);
	free(uk);
	return 0;
#undef AE
#undef S
}

/* Phi_l over Z by CRT on 62-bit primes; c[i (l+2) + j]; *nprimes used;
 * verified mod one more prime.  0: coefficients too large */
int
modpoly_z(int l, zz *c, int *nprimes, int *verified)
{
	int L2 = l + 2, np = 0, i, stable = 0;
	nn M, p, half;
	u64 *cp = xmalloc(sizeof(u64) * (size_t)(L2 * L2) * FW);
	zz *prev = xcalloc((size_t)(L2 * L2), sizeof(zz));
	nn *res = xcalloc((size_t)(L2 * L2), sizeof(nn));

	nn_set(&M, 1);
	nn_set(&p, (1ULL << 62) - 57);
	*verified = 0;
	for (np = 0; np < 18 && stable < 1; np++) {
		struct mf F;
		nn_nextprime(&p, &p);
		mf_init(&F, &p);
		if (!modpoly_mod(&F, l, cp)) {
			nn_add_u64(&p, &p, 2);
			continue;
		}
		/* CRT: res mod M, new residue mod p */
		for (i = 0; i < L2 * L2; i++) {
			nn r, rm, inv, u, t;
			mf_to_nn(&F, &r, cp + (size_t)i * FW);
			if (np == 0) {
				res[i] = r;
				continue;
			}
			nn_mod(&rm, &res[i], &p);
			nn_mod(&t, &M, &p);
			nn_invmod(&inv, &t, &p);
			nn_submod(&u, &r, &rm, &p);
			nn_mulmod(&u, &u, &inv, &p);
			if (!nn_mul(&t, &u, &M))
				goto big;
			nn_add(&res[i], &res[i], &t);
		}
		if (!nn_mul(&M, &M, &p))
			goto big;
		/* symmetric representatives; stable when unchanged */
		nn_shr(&half, &M, 1);
		stable = np > 0;
		for (i = 0; i < L2 * L2; i++) {
			zz z;
			if (nn_cmp(&res[i], &half) > 0) {
				nn t;
				nn_sub(&t, &M, &res[i]);
				zz_from_nn(&z, &t, 1);
			} else
				zz_from_nn(&z, &res[i], 0);
			if (zz_cmp(&z, &prev[i]))
				stable = 0;
			prev[i] = z;
		}
		nn_add_u64(&p, &p, 2);
	}
	*nprimes = np;
	for (i = 0; i < L2 * L2; i++)
		c[i] = prev[i];
	/* verify mod an independent prime */
	{
		struct mf F;
		nn q;
		nn_set(&q, (1ULL << 61) - 1);
		mf_init(&F, &q);
		if (modpoly_mod(&F, l, cp)) {
			*verified = 1;
			for (i = 0; i < L2 * L2; i++) {
				u64 v[FW];
				mf_from_zz(&F, v, &c[i]);
				if (!mf_eq(&F, v, cp + (size_t)i * FW))
					*verified = 0;
			}
		}
	}
	free(cp);
	free(prev);
	free(res);
	return stable;
big:
	free(cp);
	free(prev);
	free(res);
	return 0;
}

/* Phi_l(X, j) as a polynomial in X mod p */
void
modpoly_at(const struct mf *F, int l, const u64 *c, const u64 *j,
    struct px *r)
{
	int L2 = l + 2, i, k;

	px_reserve(F, r, l + 1);
	for (i = 0; i <= l + 1; i++) {
		u64 acc[FW], t[FW];
		mf_zero(F, acc);
		for (k = l + 1; k >= 0; k--) {
			mf_mul(F, acc, acc, j);
			mf_add(F, acc, acc, c + (size_t)(i * L2 + k) * FW);
		}
		mf_copy(F, px_coef(F, r, i), acc);
		(void)t;
	}
	r->d = l + 1;
	px_norm(F, r);
}

/* ---- Velu and Kohel ---- */

/* the codomain from the kernel generated by P of order l (computed);
 * sums v, w over half the kernel; also the kernel polynomial h */
int
velu(const struct ecp_curve *E, const struct ecp_pt *P, int l,
    struct ecp_curve *E2, struct px *h, u64 *v, u64 *w)
{
	const struct mf *F = E->K;
	struct ecp_pt Q;
	u64 a[FW], b[FW], gx[FW], t[FW], u[FW];
	int i, half = l == 2 ? 1 : (l - 1) / 2;

	mf_zero(F, v);
	mf_zero(F, w);
	px_set_u64(F, h, 1);
	Q = *P;
	for (i = 1; i <= half; i++) {
		struct px lin;
		if (Q.inf)
			return 0;         /* the order is smaller than l */
		/* gx = 3 x^2 + a; v_Q = 2 gx (gx for 2-torsion), u_Q = 4 y^2 */
		mf_sqr(F, gx, Q.x);
		mf_mul_u64(F, gx, gx, 3);
		mf_add(F, gx, gx, E->a);
		if (mf_is_zero(F, Q.y))
			mf_copy(F, t, gx);
		else
			mf_dbl(F, t, gx);
		mf_add(F, v, v, t);
		mf_sqr(F, u, Q.y);
		mf_mul_u64(F, u, u, 4);
		/* w += u_Q + x_Q v_Q */
		mf_mul(F, t, t, Q.x);
		mf_add(F, t, t, u);
		mf_add(F, w, w, t);
		px_init(&lin);
		px_set_x(F, &lin);
		mf_neg(F, px_coef(F, &lin, 0), Q.x);
		px_mul(F, h, h, &lin);
		px_free(&lin);
		ecp_add(E, &Q, &Q, P);
	}
	/* l P = O */
	if (l > 2) {
		struct ecp_pt T;
		ecp_mul_u64(E, &T, P, (u64)l);
		if (!T.inf)
			return 0;
	} else if (!mf_is_zero(F, P->y))
		return 0;
	mf_mul_u64(F, t, v, 5);
	mf_sub(F, a, E->a, t);
	mf_mul_u64(F, t, w, 7);
	mf_sub(F, b, E->b, t);
	ecp_set(E2, F, a, b);
	return 1;
}

/* Velu's map on a point R not in the kernel: (X, Y) */
void
velu_map(const struct ecp_curve *E, const struct ecp_pt *P, int l,
    const struct ecp_pt *R, struct ecp_pt *out)
{
	const struct mf *F = E->K;
	struct ecp_pt Q;
	u64 X[FW], Y[FW], gx[FW], gy[FW], vq[FW], uq[FW], d[FW], di[FW],
	    d2[FW], d3[FW], t[FW], s[FW];
	int i, half = l == 2 ? 1 : (l - 1) / 2;

	if (R->inf) {
		*out = *R;
		return;
	}
	mf_copy(F, X, R->x);
	mf_copy(F, Y, R->y);
	Q = *P;
	for (i = 1; i <= half; i++) {
		mf_sqr(F, gx, Q.x);
		mf_mul_u64(F, gx, gx, 3);
		mf_add(F, gx, gx, E->a);
		mf_dbl(F, gy, Q.y);
		mf_neg(F, gy, gy);
		if (mf_is_zero(F, Q.y))
			mf_copy(F, vq, gx);
		else
			mf_dbl(F, vq, gx);
		mf_sqr(F, uq, gy);
		mf_sub(F, d, R->x, Q.x);
		if (!mf_inv(F, di, d, NULL)) {
			ecp_set_inf(E, out);
			return;
		}
		mf_sqr(F, d2, di);
		mf_mul(F, d3, d2, di);
		/* X += v/(x - xq) + u/(x - xq)^2 */
		mf_mul(F, t, vq, di);
		mf_add(F, X, X, t);
		mf_mul(F, t, uq, d2);
		mf_add(F, X, X, t);
		/* Y -= u 2y/(x - xq)^3 + v (y - yq)/(x - xq)^2 - gx gy /
		 * (x - xq)^2 */
		mf_dbl(F, s, R->y);
		mf_mul(F, s, s, uq);
		mf_mul(F, s, s, d3);
		mf_sub(F, t, R->y, Q.y);
		mf_mul(F, t, t, vq);
		mf_mul(F, t, t, d2);
		mf_add(F, s, s, t);
		mf_mul(F, t, gx, gy);
		mf_mul(F, t, t, d2);
		mf_sub(F, s, s, t);
		mf_sub(F, Y, Y, s);
		ecp_add(E, &Q, &Q, P);
	}
	mf_copy(F, out->x, X);
	mf_copy(F, out->y, Y);
	out->inf = 0;
}

/* Kohel: the codomain from a kernel polynomial h of degree d (odd l = 2d
 * + 1): with power sums s1 = sum x_Q, s2 = sum x_Q^2, s3 = sum x_Q^3:
 * v = 6 s2 + 2 a d, w = 10 s3 + 6 a s1 + 4 b d */
void
kohel(const struct ecp_curve *E, const struct px *h0, struct ecp_curve *E2)
{
	const struct mf *F = E->K;
	struct px h;
	u64 e1[FW], e2[FW], e3[FW], p1[FW], p2[FW], p3[FW], v[FW], w[FW],
	    t[FW], u[FW], a[FW], b[FW];
	int d;

	px_init(&h);
	px_copy(F, &h, h0);
	px_monic(F, &h);
	d = h.d;
	/* elementary symmetric e1, e2, e3 from h = x^d - e1 x^(d-1) + e2 ... */
	mf_zero(F, e1);
	mf_zero(F, e2);
	mf_zero(F, e3);
	if (d >= 1)
		mf_neg(F, e1, px_coef(F, &h, d - 1));
	if (d >= 2)
		mf_copy(F, e2, px_coef(F, &h, d - 2));
	if (d >= 3)
		mf_neg(F, e3, px_coef(F, &h, d - 3));
	/* Newton: p1 = e1, p2 = e1^2 - 2 e2, p3 = e1^3 - 3 e1 e2 + 3 e3 */
	mf_copy(F, p1, e1);
	mf_sqr(F, p2, e1);
	mf_dbl(F, t, e2);
	mf_sub(F, p2, p2, t);
	mf_sqr(F, p3, e1);
	mf_mul(F, p3, p3, e1);
	mf_mul(F, t, e1, e2);
	mf_mul_u64(F, t, t, 3);
	mf_sub(F, p3, p3, t);
	mf_mul_u64(F, t, e3, 3);
	mf_add(F, p3, p3, t);
	mf_mul_u64(F, v, p2, 6);
	mf_mul_u64(F, t, E->a, 2 * (u64)d);
	mf_add(F, v, v, t);
	mf_mul_u64(F, w, p3, 10);
	mf_mul(F, t, E->a, p1);
	mf_mul_u64(F, t, t, 6);
	mf_add(F, w, w, t);
	mf_mul_u64(F, t, E->b, 4 * (u64)d);
	mf_add(F, w, w, t);
	mf_mul_u64(F, u, v, 5);
	mf_sub(F, a, E->a, u);
	mf_mul_u64(F, u, w, 7);
	mf_sub(F, b, E->b, u);
	ecp_set(E2, F, a, b);
	px_free(&h);
}

/* ---- fast small-field polynomial multiplication ----
 * px_mul()'s generic NTT spends 3-4 primes on coefficients that, for a small
 * base field, all fit in one 62-bit prime.  Distinct-degree factorisation
 * multiplies degree-D polynomials thousands of times, so use a single-prime
 * NTT when the convolution coefficients are guaranteed to fit.  Fall back to
 * the generic routines for large fields or long products. */
#define NQP 4611686017554972673ULL     /* = c * 2^26 + 1, prime */
#define NQZ 4151654384686787924ULL     /* primitive 2^13-th root of unity */
#define NQLOGK 13

static inline u64
nq_add(u64 a, u64 b)
{
	u64 s = a + b;
	return s >= NQP ? s - NQP : s;   /* a, b < 2^62, so no wrap */
}

static inline u64
nq_sub(u64 a, u64 b)
{
	return a >= b ? a - b : a + NQP - b;
}

static inline u64
nq_mul(u64 a, u64 b)
{
	return (u128)a * b % NQP;
}

static u64
nq_pow(u64 a, u64 e)
{
	u64 r = 1;
	while (e) {
		if (e & 1)
			r = nq_mul(r, a);
		a = nq_mul(a, a);
		e >>= 1;
	}
	return r;
}

static void
nq_ntt(u64 *a, int logn, int inv)
{
	int n = 1 << logn, i, j, len;

	for (i = 1, j = 0; i < n; i++) {
		int bit = n >> 1;
		for (; j & bit; bit >>= 1)
			j ^= bit;
		j ^= bit;
		if (i < j) {
			u64 t = a[i];
			a[i] = a[j];
			a[j] = t;
		}
	}
	for (len = 2; len <= n; len <<= 1) {
		int klen = NQLOGK - __builtin_ctz((unsigned)len);
		u64 wlen = nq_pow(NQZ, 1ULL << klen), w;
		if (inv)
			wlen = nq_pow(wlen, NQP - 2);
		for (i = 0; i < n; i += len) {
			w = 1;
			for (j = 0; j < len / 2; j++) {
				u64 u = a[i + j], v = nq_mul(a[i + j + len / 2], w);
				a[i + j] = nq_add(u, v);
				a[i + j + len / 2] = nq_sub(u, v);
				w = nq_mul(w, wlen);
			}
		}
	}
	if (inv) {
		u64 ni = nq_pow((u64)n, NQP - 2);
		for (i = 0; i < n; i++)
			a[i] = nq_mul(a[i], ni);
	}
}

static u64
modpow64(u64 a, u64 e, u64 p)
{
	u64 r = 1 % p;
	while (e) {
		if (e & 1)
			r = (u128)r * a % p;
		a = (u128)a * a % p;
		e >>= 1;
	}
	return r;
}

/* r = a * b over F_p, using the one-prime NTT when safe.  Returns 1 on
 * success, 0 if the caller should use px_mul(). */
static int
px_mul_fast(const struct mf *F, struct px *r, const struct px *a,
    const struct px *b)
{
	int na = a->d + 1, nb = b->d + 1, need = na + nb - 1, logn = 0, L, i;
	u64 p0, rmod, invr, *A, *B;

	if (F->n != 1)
		return 0;
	p0 = F->p[0];
	if ((u128)(na < nb ? na : nb) * (p0 - 1) * (p0 - 1) >= NQP)
		return 0;
	while ((1 << logn) < need)
		logn++;
	if (logn > NQLOGK)
		return 0;
	L = 1 << logn;
	rmod = ((u128)1 << 64) % p0;
	invr = modpow64(rmod, p0 - 2, p0);
	A = xcalloc((size_t)L, sizeof(u64));
	B = xcalloc((size_t)L, sizeof(u64));
	for (i = 0; i < na; i++)          /* Montgomery -> plain */
		A[i] = (u128)a->c[i] * invr % p0;
	for (i = 0; i < nb; i++)
		B[i] = (u128)b->c[i] * invr % p0;
	nq_ntt(A, logn, 0);
	nq_ntt(B, logn, 0);
	for (i = 0; i < L; i++)
		A[i] = nq_mul(A[i], B[i]);
	nq_ntt(A, logn, 1);
	px_reserve(F, r, need - 1);
	r->d = need - 1;
	for (i = 0; i < need; i++) {      /* plain -> Montgomery */
		u64 v = A[i] % p0;
		r->c[i] = (u128)v * rmod % p0;
	}
	px_norm(F, r);
	free(A);
	free(B);
	return 1;
}

static void
nq_reverse(const struct mf *F, struct px *r, const struct px *a, int d)
{
	struct px t;
	int i;

	px_init(&t);
	px_reserve(F, &t, d < 0 ? 0 : d);
	for (i = 0; i <= d; i++) {
		if (d - i <= a->d)
			mf_copy(F, PCO(F, &t, i), PCO(F, a, d - i));
		else
			mf_zero(F, PCO(F, &t, i));
	}
	t.d = d;
	px_norm(F, &t);
	px_copy(F, r, &t);
	px_free(&t);
}

/* Newton reduction mod M->m using the fast multiplication; mirrors
 * px_reduce() in ecpoly.c.  Falls back to px_rem() when the fast path is
 * not applicable. */
static void
px_reduce_fast(const struct mf *F, const struct pxmod *M, struct px *r,
    const struct px *a)
{
	struct px ar, q, t;
	int d = M->m.d, k;

	if (a->d < d) {
		px_copy(F, r, a);
		return;
	}
	if (d < 1 || a->d > 2 * d - 2 || d < 48) {
		px_rem(F, r, a, &M->m);
		return;
	}
	k = a->d - d + 1;
	px_init(&ar);
	px_init(&q);
	px_init(&t);
	nq_reverse(F, &ar, a, a->d);
	if (ar.d >= k)
		ar.d = k - 1;
	if (!px_mul_fast(F, &q, &ar, &M->inv))
		goto slow;
	if (q.d >= k)
		q.d = k - 1;
	nq_reverse(F, &q, &q, k - 1);
	if (!px_mul_fast(F, &t, &q, &M->m))
		goto slow;
	px_sub(F, r, a, &t);
	px_free(&ar);
	px_free(&q);
	px_free(&t);
	if (r->d >= d)
		px_rem(F, r, r, &M->m);
	return;
slow:
	px_free(&ar);
	px_free(&q);
	px_free(&t);
	px_rem(F, r, a, &M->m);
}

static void
px_mulmod_fast(const struct mf *F, const struct pxmod *M, struct px *r,
    const struct px *a, const struct px *b)
{
	struct px t;

	px_init(&t);
	if (!px_mul_fast(F, &t, a, b))
		px_mul(F, &t, a, b);
	px_reduce_fast(F, M, r, &t);
	px_free(&t);
}

/* Frobenius in F_p[x]/(m), used by distinct-degree factorisation.  In
 * characteristic p, (sum a_i x^i)^p = sum a_i (x^p)^i because a_i^p = a_i
 * for a_i in F_p.  Precomputing qpow[i] = x^(i p) mod m makes one Frobenius
 * application a linear combination (O(D^2) field operations), far cheaper
 * than a fresh modular exponentiation by p at every degree.  The modulus m
 * is fixed for the lifetime of a struct px_frob. */
struct px_frob {
	struct pxmod M;
	struct px *qpow;   /* qpow[i] = x^(i p) mod m, i = 0 .. D-1 */
	int D;
};

static void
px_frob_init(const struct mf *F, struct px_frob *fr, const struct px *m)
{
	struct px xp;
	int i;

	fr->D = m->d;
	pxmod_init(F, &fr->M, m);
	fr->qpow = xcalloc((size_t)(fr->D > 0 ? fr->D : 1), sizeof(struct px));
	if (fr->D <= 0)
		return;
	px_init(&xp);
	px_set_x(F, &xp);
	px_powmod(F, &fr->M, &xp, &xp, &F->P);   /* xp = x^p mod m */
	px_init(&fr->qpow[0]);
	px_set_u64(F, &fr->qpow[0], 1);
	for (i = 1; i < fr->D; i++) {
		px_init(&fr->qpow[i]);
		px_mulmod_fast(F, &fr->M, &fr->qpow[i], &fr->qpow[i - 1], &xp);
	}
	px_free(&xp);
}

static void
px_frob_free(struct px_frob *fr)
{
	int i;
	for (i = 0; i < fr->D; i++)
		px_free(&fr->qpow[i]);
	free(fr->qpow);
	pxmod_free(&fr->M);
}

/* r = a^p mod m; a must have degree < fr->D (and reduced mod m) */
static void
px_frob_apply(const struct mf *F, const struct px_frob *fr, struct px *r,
    const struct px *a)
{
	struct px ac;
	int n = F->n, D = fr->D, i, j;

	/* r may alias a, so snapshot the input before touching r's storage */
	px_init(&ac);
	px_copy(F, &ac, a);
	px_reserve(F, r, D > 0 ? D - 1 : 0);
	r->d = D - 1;
	if (D <= 0) {
		r->d = -1;
		px_free(&ac);
		return;
	}
	memset(r->c, 0, sizeof(u64) * (size_t)n * (size_t)D);
	if (n == 1) {
		const u64 p0 = F->p[0], pinv = F->pinv;
		for (i = 0; i <= ac.d && i < D; i++) {
			u64 ai = ac.c[i], *qi;
			if (!ai)
				continue;
			qi = fr->qpow[i].c;
			for (j = 0; j <= fr->qpow[i].d; j++) {
				u128 s = (u128)ai * qi[j];
				u64 lo = (u64)s, hi = (u64)(s >> 64);
				u64 mm = lo * pinv;
				u128 t = (u128)mm * p0 + lo;
				u128 v = (u128)hi + (u64)(t >> 64);
				u64 old, rr;
				if (v >= p0)
					v -= p0;
				old = r->c[j];
				rr = old + (u64)v;
				/* rr < old means 2^64 wrapped; then rr is already < p0 */
				if (rr >= p0 && rr >= old)
					rr -= p0;
				r->c[j] = rr;
			}
		}
	} else {
		u64 prod[FW];
		for (i = 0; i <= ac.d && i < D; i++) {
			if (mf_is_zero(F, PCO(F, &ac, i)))
				continue;
			for (j = 0; j <= fr->qpow[i].d; j++) {
				mf_mul(F, prod, PCO(F, &ac, i), PCO(F, &fr->qpow[i], j));
				mf_add(F, PCO(F, r, j), PCO(F, r, j), prod);
			}
		}
	}
	px_norm(F, r);
	px_free(&ac);
}

/* Distinct-degree factorisation of a squarefree f: counts[d] = the number
 * of irreducible factors of degree d (0 <= d <= maxd); returns the largest
 * d with counts[d] > 0, or 0 when f is constant.  Every irreducible factor
 * degree is determined: the loop stops only once the unfactored part is
 * irreducible, and its degree is then recorded.  The caller must pass
 * maxd >= f0->d so counts[] has room for the largest possible degree.
 *
 * The scan works in batches of DDF_BLOCK degrees: in one batch we build the
 * single product P = prod (x^(p^i) - x) mod f and test gcd(P, f) once.  Only
 * when that gcd is nontrivial do we do per-degree gcds, and then against the
 * (small) product of the factors already isolated in the batch.  This keeps
 * the linear scan -- and its expensive gcds -- off the common path where no
 * small factors exist (e.g. a division polynomial with one large factor). */
#define DDF_BLOCK 32

int
px_ddf(const struct mf *F, const struct px *f0, int *counts, int maxd)
{
	struct px f, h, hstart, x, g, t, P, gg, hh, gi;
	struct px_frob fr;
	struct pxmod Mg;
	int d, hi, i, top = 0, have_fr = 0;

	px_init(&f);
	px_init(&h);
	px_init(&hstart);
	px_init(&x);
	px_init(&g);
	px_init(&t);
	px_init(&P);
	px_init(&gg);
	px_init(&hh);
	px_init(&gi);
	px_copy(F, &f, f0);
	px_monic(F, &f);
	memset(counts, 0, sizeof(int) * (size_t)(maxd + 1));
	if (f.d <= 0)
		goto done;
	px_set_x(F, &x);
	px_copy(F, &h, &x);          /* h = x^(p^(d-1)) mod f, for d = 1 */

	d = 1;
	while (d <= maxd && f.d >= 2 * d) {
		if (!have_fr) {
			px_frob_init(F, &fr, &f);
			have_fr = 1;
		}
		if (h.d >= fr.D)         /* h may be from a previous, larger modulus */
			px_rem(F, &h, &h, &f);
		px_copy(F, &hstart, &h);

		hi = d + DDF_BLOCK - 1;
		if (hi > maxd)
			hi = maxd;
		if (hi > f.d / 2)        /* past this point f is irreducible */
			hi = f.d / 2;
		if (hi < d)
			hi = d;

		/* P = prod_{i=d..hi} (x^(p^i) - x) mod f */
		px_set_u64(F, &P, 1);
		for (i = d; i <= hi; i++) {
			px_frob_apply(F, &fr, &h, &h);
			px_sub(F, &t, &h, &x);
			px_mulmod_fast(F, &fr.M, &P, &P, &t);
		}
		px_gcd(F, &g, &P, &f);
		if (g.d <= 0) {          /* no factors of degree in [d, hi] */
			d = hi + 1;
			continue;
		}

		/* Factors exist in [d, hi].  Isolate each exact degree with a
		 * per-degree pass on g (which is small here). */
		px_copy(F, &gg, &g);
		px_monic(F, &gg);
		pxmod_init(F, &Mg, &gg);
		px_rem(F, &hh, &hstart, &gg);   /* x^(p^(d-1)) mod gg */
		for (i = d; i <= hi && gg.d > 0; i++) {
			px_powmod(F, &Mg, &hh, &hh, &F->P);
			px_sub(F, &t, &hh, &x);
			px_gcd(F, &gi, &t, &gg);
			if (gi.d > 0) {
				counts[i] += gi.d / i;
				if (i > top)
					top = i;
				px_divmod(F, &gg, NULL, &gg, &gi);
				px_monic(F, &gg);
				pxmod_free(&Mg);
				pxmod_init(F, &Mg, &gg);
				px_rem(F, &hh, &hh, &gg);
			}
		}
		pxmod_free(&Mg);

		px_divmod(F, &f, NULL, &f, &g);
		px_monic(F, &f);
		px_frob_free(&fr);       /* modulus changed */
		have_fr = 0;
		px_rem(F, &h, &h, &f);   /* x^(p^hi) mod the new f */
		d = hi + 1;
	}
	/* the remaining f is a single irreducible of degree f.d */
	if (f.d > 0) {
		counts[f.d]++;
		if (f.d > top)
			top = f.d;
	}
done:
	if (have_fr)
		px_frob_free(&fr);
	px_free(&f);
	px_free(&h);
	px_free(&hstart);
	px_free(&x);
	px_free(&g);
	px_free(&t);
	px_free(&P);
	px_free(&gg);
	px_free(&hh);
	px_free(&gi);
	return top;
}
