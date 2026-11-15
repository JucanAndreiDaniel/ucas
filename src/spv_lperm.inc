/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * spv_lperm.inc (included by spirv.c): simplify writes an
 * OpGroupNonUniformShuffle whose index is an F2-affine function of
 * SubgroupLocalInvocationId alone as lperm.c's stages, each an
 * OpGroupNonUniformShuffleXor and an OpSelect on a parity of the lane's
 * bits, where the active model prices them below the shuffle and the
 * index's instructions (sg_shuffle_xor, sg_quad, select, logic, cmp).
 *
 * The map is read at the lanes 0 .. 2^b - 1, 2^b the smallest block the
 * map keeps every lane in, and SAT proves the index equal to that map
 * on the lane's low b bits with its other bits kept, for every 32-bit
 * lane: so the stages, which exchange within blocks of 2^b lanes, give
 * every lane the value the shuffle reads, in a subgroup of any size
 * that is a multiple of 2^b, with every lane active (a lane the stages
 * pass through must take part).  Written only where 2^b is at most 4
 * (a quad; Vulkan subgroups of quad operations have at least 4 lanes);
 * a larger block needs the pipeline's subgroup size and is said, not
 * written, as sg_proposals does.  The stages' proof is lperm.c's: they
 * are composed on every lane of the block.
 */

/* a load of SubgroupLocalInvocationId */
static int
lp_lane_load(int id)
{
	int k = SP.def[id];
	const struct sins *I;

	if (k < 0)
		return 0;
	I = &V.in[k];
	if (strcmp(I->op, "OpLoad") || I->nop < 2)
		return 0;
	return V.id[res_of(idx(I->opnd[1]))].builtin == B_SUBLANE;
}

/*
 * Instruction k runs with every lane that entered the entry point: it is
 * in an entry point's function, with no conditional branch, switch or
 * loop before it there (an exchange reads its partner lane, which must
 * be active; a shuffle by an index reads only the lane it names).
 */
static int
lp_uniform(int k)
{
	int j, f = -1, e;

	for (j = k; j >= 0; j--) {
		const char *op = V.in[j].op;
		if (!strcmp(op, "OpFunction")) {
			f = V.in[j].res;
			break;
		}
		if (!strcmp(op, "OpBranchConditional") || !strcmp(op, "OpSwitch") ||
		    !strcmp(op, "OpLoopMerge") || !strcmp(op, "OpKill") ||
		    !strcmp(op, "OpTerminateInvocation") ||
		    !strcmp(op, "OpDemoteToHelperInvocation"))
			return 0;
	}
	if (f < 0)
		return 0;
	for (e = 0; e < V.nin; e++)
		if (!strcmp(V.in[e].op, "OpEntryPoint") && V.in[e].nop >= 2 &&
		    res_of(idx(V.in[e].opnd[1])) == f)
			return 1;
	return 0;
}

/* the smallest block 2^b (b >= 1) an affine map keeps its lanes in */
static int
lp_block(const struct lperm_plan *p)
{
	int b = 1, j, h;

	for (j = 0; j < p->bits; j++)
		if (p->col[j] != (1 << j)) {
			for (h = p->bits - 1; h >= 0; h--)
				if ((p->col[j] ^ (1 << j)) >> h & 1)
					break;
			if (j + 1 > b)
				b = j + 1;
			if (h + 1 > b)
				b = h + 1;
		}
	for (h = p->bits - 1; h >= 0; h--)
		if (p->c >> h & 1) {
			if (h + 1 > b)
				b = h + 1;
			break;
		}
	return b;
}

static int
lp_pass(struct sbuf *rep, struct dotlog *log, int maxlog)
{
	const struct model *m = model_active();
	int W = (int)m->par[MP_WARP], k, n = 0;

	for (k = 0; k < SP.orig_nin && n < maxlog; k++) {
		const struct sins *I = &V.in[k];
		struct spvdot c;
		struct lperm_plan pl, pb;
		struct eqproof pr;
		struct sbuf d = {0};
		int16_t map[SG_MAXW];
		uint64_t sv;
		int rt, ixid, lane, lt, l, b, ok = 1, i, ut, bt, cur, nin0;
		double before, after, v;
		char sl[160], scope[64], lanetok[64], curtok[64], to[160];
		nid aff, tab[4], lv;

		if (SP.dead[k] || strcmp(I->op, "OpGroupNonUniformShuffle") ||
		    I->res < 0 || I->nop != 4)
			continue;
		if (!const_of(res_of(idx(I->opnd[1])), &sv) || sv != 3)
			continue;
		rt = idx(I->opnd[0]);
		if (V.id[rt].kind != K_TYPE || (T(rt)->k != S_INT &&
		    T(rt)->k != S_FLOAT) || T(rt)->w != 32)
			continue;
		ixid = res_of(idx(I->opnd[3]));
		memset(&c, 0, sizeof c);
		c.memo = xcalloc((size_t)(V.nid + 1024), sizeof *c.memo);
		c.f.anon = 1;
		c.f.body = spv_node(&c, ixid, 0);
		free(c.memo);
		if (c.fail || c.nleaf != 1 || !lp_lane_load(c.leaf[0]) ||
		    W < 2 || W > SG_MAXW || (W & (W - 1)))
			continue;
		lane = c.leaf[0];
		lt = V.id[lane].type;
		for (l = 0; l < W && ok; l++) {
			v = eval_const_at(c.f.body, 0, l, &ok);
			ok = ok && v >= 0 && v < W && v == floor(v);
			map[l] = (int16_t)(ok ? (int)v : -1);
		}
		if (!ok || lperm_plan(m, map, W, -1, &pl) == LPH_NONE ||
		    !pl.affine || pl.kind == LPH_IDENTITY)
			continue;
		src_line(ins_line(k), sl, sizeof sl);
		b = lp_block(&pl);
		lperm_plan(m, map, 1 << b, -1, &pb);
		if (pb.kind == LPH_SHUFFLE && pb.nst && isfinite(pb.stages_price))
			pb.kind = LPH_STAGES;	/* priced against the module below */
		if (pb.kind != LPH_STAGES || (pb.nst == 1 && !pb.st[0].m)) {
			/* a shuffle by lane xor k, or a quad's broadcast: the
			 * same instruction with its index, priced so already */
			continue;
		}
		/* before: the shuffle, and the index where only it reads it */
		before = sg_price(I, W, &i) + (SP.uses[ixid] == 1 ?
		    fuse_expr_cost(m, c.f.body) : 0);
		after = pb.stages_price;
		lperm_text(&d, &pb);
		if (!(after < before - 1e-9)) {
			sb_printf(rep, "    %s\n%s      the lane map %s is %s: %g "
			    "against %g under %s: left as it is\n", I->text, sl,
			    shared_str(c.f.body, 100), sb_str(&d), after, before,
			    sym_str(m->name));
			free(d.p);
			continue;
		}
		if (!lp_uniform(k)) {
			sb_printf(rep, "    %s\n%s      the lane map %s is %s (%g "
			    "against %g under %s), but it is not in the entry point's "
			    "first straight run of code: an exchange needs its partner "
			    "lane active; left as it is\n", I->text, sl,
			    shared_str(c.f.body, 100), sb_str(&d), after, before,
			    sym_str(m->name));
			free(d.p);
			continue;
		}
		if (b > 2) {
			sb_printf(rep, "    %s\n%s      the lane map %s is %s (%g "
			    "against %g under %s), exchanges within blocks of %d "
			    "lanes: proposed, not written, as it needs subgroups of "
			    "%d lanes or more (the pipeline's requiredSubgroupSize)\n",
			    I->text, sl, shared_str(c.f.body, 100), sb_str(&d), after,
			    before, sym_str(m->name), 1 << b, 1 << b);
			free(d.p);
			continue;
		}
		/* SAT: the index is the map on the low b bits, the rest kept */
		lv = mk_var(0, c.f.p[0].name, c.f.p[0].ty);
		for (l = 0; l < 1 << b; l++)
			tab[l] = mk_const_i(c.f.p[0].ty, map[l]);
		aff = mk_bin(O_OR, mk_bin(O_AND, lv, mk_const_i(c.f.p[0].ty,
		    ~(int64_t)((1 << b) - 1) & 0xffffffffLL)), mk_index(mk_table(tab,
		    (uint32_t)(1 << b)), mk_bin(O_AND, lv, mk_const_i(c.f.p[0].ty,
		    (1 << b) - 1))));
		if (equiv_decide(&c.f, c.f.body, aff, NULL, &pr) ||
		    (pr.how != EQ_SAT && pr.how != EQ_EXHAUSTIVE)) {
			sb_printf(rep, "    %s\n%s      the lane map %s: not proved "
			    "affine for every lane (SAT): left as it is\n", I->text,
			    sl, shared_str(c.f.body, 100));
			free(d.p);
			continue;
		}
		/* written before the shuffle */
		memset(&c.em, 0, sizeof c.em);
		c.k = k;
		c.fail = 0;
		nin0 = V.nin;
		ut = sg_type_id(0);
		bt = sg_type_id(1);
		(void)ut;
		snprintf(scope, sizeof scope, "%s", I->opnd[1]);
		snprintf(lanetok, sizeof lanetok, "%s", V.id[lane].tok);
		snprintf(curtok, sizeof curtok, "%s", I->opnd[2]);
		cur = -1;
		for (i = 0; i < pb.nst && !c.fail; i++) {
			const struct lperm_stage *s = &pb.st[i];
			const char *o[3];
			char ktok[64], mtok[64], ztok[64], onetok[64], shtok[64];
			int sh, a, cond, kk = const_id(lt, s->k), z = const_id(lt, 0);
			if (kk < 0 || z < 0) {
				c.fail = 1;
				break;
			}
			snprintf(ktok, sizeof ktok, "%s", V.id[kk].tok);
			snprintf(ztok, sizeof ztok, "%s", V.id[z].tok);
			o[0] = scope;
			o[1] = curtok;
			o[2] = ktok;
			sh = dot_ins(&c, "OpGroupNonUniformShuffleXor", rt, o, 3);
			if (sh < 0)
				break;
			snprintf(shtok, sizeof shtok, "%s", V.id[sh].tok);
			if (!s->m) {
				cur = sh;
				snprintf(curtok, sizeof curtok, "%s", shtok);
				continue;
			}
			{
				int mk = const_id(lt, s->m);
				if (mk < 0) {
					c.fail = 1;
					break;
				}
				snprintf(mtok, sizeof mtok, "%s", V.id[mk].tok);
			}
			o[0] = lanetok;
			o[1] = mtok;
			a = dot_ins(&c, "OpBitwiseAnd", lt, o, 2);
			if (a >= 0 && (s->m & (s->m - 1))) {
				int one = const_id(lt, 1), p;
				if (one < 0) {
					c.fail = 1;
					break;
				}
				snprintf(onetok, sizeof onetok, "%s", V.id[one].tok);
				o[0] = V.id[a].tok;
				p = dot_ins(&c, "OpBitCount", lt, o, 1);
				o[0] = p >= 0 ? V.id[p].tok : "";
				o[1] = onetok;
				a = p >= 0 ? dot_ins(&c, "OpBitwiseAnd", lt, o, 2) : -1;
			}
			if (a < 0)
				break;
			o[0] = V.id[a].tok;
			o[1] = ztok;
			cond = dot_ins(&c, "OpINotEqual", bt, o, 2);
			if (cond < 0)
				break;
			{
				char ctok[64];
				snprintf(ctok, sizeof ctok, "%s", V.id[cond].tok);
				o[0] = ctok;
				o[1] = s->e ? curtok : shtok;
				o[2] = s->e ? shtok : curtok;
				cur = dot_ins(&c, "OpSelect", rt, o, 3);
			}
			if (cur < 0)
				break;
			snprintf(curtok, sizeof curtok, "%s", V.id[cur].tok);
		}
		if (c.fail || cur < 0 || i < pb.nst) {
			int q, j;
			for (q = nin0; q < V.nin; q++) {
				for (j = 0; j < V.in[q].nop; j++)
					free(V.in[q].opnd[j]);
				free(V.in[q].text);
			}
			V.nin = nin0;
			free(d.p);
			continue;
		}
		SP.alias[I->res] = cur;
		SP.dead[k] = 1;
		snprintf(to, sizeof to, "%s", sb_str(&d));
		snprintf(log[n].from, sizeof log[n].from, "%s", I->text);
		snprintf(log[n].to, sizeof log[n].to, "%s", to);
		log[n].gain = before - after;
		log[n].before = before;
		log[n].after = after;
		log[n].line = ins_line(k);
		{
			struct sbuf p2 = {0};
			sb_printf(&p2, "the lane read, %s, is affine over the lane's "
			    "bits within blocks of %d lanes (SAT, every 32-bit lane: "
			    "its low %d bits mapped, the others kept); rank(I xor A) = "
			    "%d stages, composed on every lane of the block", shared_str(
			    c.f.body, 100), 1 << b, b, pb.rank);
			log[n].proof = p2.p;
			log[n].desc = strdup("every lane active (it runs before any "
			    "branch of the entry point), in a subgroup whose size is a "
			    "multiple of 4 (a quad's lanes exchange)");
		}
		sb_printf(rep, "    %s\n      ->  %s   (cost %g -> %g)\n%s      %s\n"
		    "      holds for %s\n", I->text, to, before, after, sl,
		    log[n].proof, log[n].desc);
		free(d.p);
		n++;
	}
	return n;
}
