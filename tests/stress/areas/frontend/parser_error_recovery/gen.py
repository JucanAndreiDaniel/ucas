#!/usr/bin/env python3
"""
Generator for tests/stress/parser_error_recovery.

Every .ucas file isolates one "syntax error, then valid statements" scenario.
A trailing sentinel (bigint 2^N) proves the interpreter continued; a `show NAME`
after a failed definition checks whether a partial definition leaked into state.
Outputs are produced by run.sh, which keeps a golden only for deterministic runs.
"""
import os

OUT = os.path.dirname(os.path.abspath(__file__))

# (shortname, list-of-statements).  "#" lines are comments.
CASES = []


def add(name, *stmts):
    CASES.append((name, list(stmts)))


# ---------------------------------------------------------------- 01 unmatched parenthesis
add("unclosed_paren_show", "show (1 + 2", "bigint 2^10", "bigint 3^10")
add("unclosed_paren_parse", "parse (x + y", "bigint 2^11", "parse 1+1")
add("unclosed_paren_range", "range (x: u8) x + 1", "bigint 2^12", "bigint 3^12")
add("unclosed_paren_nested", "show ((1 + 2)", "bigint 2^13", "bigint 3^13")
add("extra_close_paren", "show 1 + 2)", "bigint 2^14", "bigint 3^14")
add("extra_close_double", "show 1))", "bigint 2^15", "parse 2+2")
add("empty_parens", "show ()", "bigint 2^16", "bigint 3^16")
add("paren_continuation", "show (1 +", "  bigint 4^10", "bigint 2^17")
add("paren_in_def", "f(x: u8) = (x + 1", "bigint 2^18", "show f")
add("paren_command_arg", "equiv (x+1)^2 (x+1)^2", "bigint 2^19", "bigint 3^19")

# ---------------------------------------------------------------- 02 brackets
add("unclosed_bracket", "show [1, 2, 3", "bigint 2^20", "bigint 3^20")
add("extra_close_bracket", "show [1,2]]", "bigint 2^21", "parse 1+1")
add("bracket_no_comma", "show [1 2 3]", "bigint 2^22", "bigint 3^22")
add("bracket_trailing_comma", "parse [1, 2,][0]", "bigint 2^23", "bigint 3^23")
add("bracket_index_bad", "show [1,2]['a']", "bigint 2^24", "bigint 3^24")
add("bracket_unclosed_index", "show [1,2,3][0", "bigint 2^25", "bigint 3^25")
add("bracket_in_def", "f(x: u8) = [x, x+1", "bigint 2^26", "show f")
add("bracket_double_index", "parse [[1,2],[3,4]][i][j]", "bigint 2^27", "bigint 3^27")

# ---------------------------------------------------------------- 03 braces
add("unclosed_brace_match", "parse match x { 0 => 1", "bigint 2^28", "bigint 3^28")
add("extra_close_brace", "parse match x { 0 => 1 }}", "bigint 2^29", "parse 1+1")
add("empty_brace", "parse match x {}", "bigint 2^30", "bigint 3^30")
add("brace_no_arm", "parse match x { 0 1, _ => 2 }", "bigint 2^31", "bigint 3^31")
add("brace_bad_arrow", "parse match x { 0 = 1, _ => 2 }", "bigint 2^32", "bigint 3^32")
add("brace_code_block", "f(x: u8) = { y = x + 1; y }", "bigint 2^33", "show f")

# ---------------------------------------------------------------- 04 stray operators
add("stray_plus", "show 1 + + 2", "bigint 2^34", "bigint 3^34")
add("stray_star", "show 2 * * 3", "bigint 2^35", "bigint 3^35")
add("stray_equal", "show x = = 1", "bigint 2^36", "bigint 3^36")
add("trailing_plus", "show 1 +", "bigint 2^37", "bigint 3^37")
add("leading_plus", "show + 1", "bigint 2^38", "bigint 3^38")
add("double_comma", "parse [1,,2]", "bigint 2^39", "bigint 3^39")
add("stray_bang", "parse !a", "bigint 2^40", "bigint 3^40")
add("stray_arrow", "parse 1 -> 2", "bigint 2^41", "bigint 3^41")
add("stray_semicolon", "parse 1 ; ;", "bigint 2^42", "bigint 3^42")
add("stray_dotdot", "parse 1 .. 2", "bigint 2^43", "bigint 3^43")
add("stray_colon", "parse 1 : 2", "bigint 2^44", "bigint 3^44")
add("stray_percent", "show % 5", "bigint 2^45", "bigint 3^45")
add("stray_caret", "show ^ 2", "bigint 2^46", "bigint 3^46")
add("stray_question", "parse ? x : y", "bigint 2^47", "bigint 3^47")

# ---------------------------------------------------------------- 05 bad types
add("type_bogus", "f(x: bogus) = x", "bigint 2^48", "show f")
add("type_empty", "f(x:) = x", "bigint 2^49", "show f")
add("type_f128", "f(x: f128) = x", "bigint 2^50", "show f")
add("type_u0", "f(x: u0) = x", "bigint 2^51", "show f")
add("type_u65", "f(x: u65) = x", "bigint 2^52", "show f")
add("type_ineg", "f(x: i-8) = x", "bigint 2^53", "show f")
add("type_missing_colon", "f(x u8) = x", "bigint 2^54", "show f")
add("type_no_params_list", "f x = x + 1", "bigint 2^55", "show f")
add("type_bad_range", "f(x: u8 in a..b) = x", "bigint 2^56", "show f")
add("type_dup_param", "f(x: u8, x: i8) = x", "bigint 2^57", "show f")

# ---------------------------------------------------------------- 06 undefined names
add("undef_show", "show totally_undefined_zz", "bigint 2^58", "parse 1+1")
add("undef_range", "range totally_undefined_zz", "bigint 2^59", "bigint 3^59")
add("undef_bigint", "bigint totally_undefined_zz", "bigint 2^60", "bigint 3^60")
add("undef_in_def", "f(x: u8) = nosuch_fn(x)", "bigint 2^61", "show f")
add("undef_call", "show nosuch_fn(3)", "bigint 2^62", "bigint 3^62")
add("undef_then_define", "show ghost(x) + 1", "ghost(x: u8) = x", "show ghost", "bigint 2^63")

# ---------------------------------------------------------------- 07 bad annotations
add("annot_inline", "show (x: u8) 1 < x < 5", "bigint 2^64", "parse 1+1")
add("annot_open_low", "f(x: int) = x where x in ..5", "bigint 2^65", "show f")
add("annot_open_high", "f(x: int) = x where x in 5..", "bigint 2^66", "show f")
add("annot_open_both", "f(x: int) = x where x in ..", "bigint 2^67", "show f")
add("annot_paren_range", "f(x: int) = x where x in (0..5)", "bigint 2^68", "show f")
add("annot_where_expr", "parse x ? y : z where x in 0..3", "bigint 2^69", "bigint 3^69")
add("annot_double_where", "f(x: int) = x where x in 0..5 where x in 1..3", "bigint 2^70", "show f")
add("annot_bad_in", "f(x: u8) = x where x in", "bigint 2^71", "show f")
add("annot_range_on_expr", "range (x: u8 in 0..10) x mod 2 == 0", "bigint 2^72", "bigint 3^72")

# ---------------------------------------------------------------- 08 incomplete definitions
add("def_no_body", "f(x: u8) =", "bigint 2^73", "show f")
add("def_trailing_op", "f(x: u8) = x +", "bigint 2^74", "show f")
add("def_no_equal", "f(x: u8) x + 1", "bigint 2^75", "show f")
add("def_no_name", "f =", "bigint 2^76", "show f")
add("def_unclosed_params", "f(x: u8, y: u8 = x + y", "bigint 2^77", "show f")
add("def_extra_comma", "f(x: u8,) = x", "bigint 2^78", "show f")
add("def_bad_param", "f(1: u8) = x", "bigint 2^79", "show f")
add("def_empty_body_paren", "f(x: u8) = ()", "bigint 2^80", "show f")

# ---------------------------------------------------------------- 09 bad match
add("match_bad_arm", "parse match x { 0 => 1, => 2, _ => 3 }", "bigint 2^81", "bigint 3^81")
add("match_unclosed", "parse match x { 0 => (1, _ => 3 }", "bigint 2^82", "bigint 3^82")
add("match_guard", "parse match x { n if n > 0 => n, _ => 0 }", "bigint 2^83", "bigint 3^83")
add("match_open_range", "parse match x { 0 => 1, 1 => 2, 3.. => 4, _ => 5 }", "bigint 2^84", "bigint 3^84")
add("match_no_default", "parse match x { 1 => 2 }", "bigint 2^85", "bigint 3^85")
add("match_bad_pattern", "parse match x { foo => 1, _ => 2 }", "bigint 2^86", "bigint 3^86")
add("match_double_arrow", "parse match x { 0 => => 1, _ => 2 }", "bigint 2^87", "bigint 3^87")
add("match_bad_default", "parse match x { 0 => 1, default => 2 }", "bigint 2^88", "bigint 3^88")
add("match_in_def", "f(x: u8) = match x { 0 => 1, => 2 }", "bigint 2^89", "show f")

# ---------------------------------------------------------------- 10 bad where
add("where_bad_cond", "f(x: u8) = x where x ??? 3", "bigint 2^90", "show f")
add("where_trailing", "f(x: u8) = x where", "bigint 2^91", "show f")
add("where_double_comma", "f(x: u8) = x where x in 0..3,, x>1", "bigint 2^92", "show f")
add("where_in_expr", "parse x where y = 1", "bigint 2^93", "bigint 3^93")
add("where_keyword_only", "f(x: u8) = x where x", "bigint 2^94", "show f")
add("where_on_command", "range x where x in 0..3", "bigint 2^95", "bigint 3^95")

# ---------------------------------------------------------------- 11 unterminated strings (lexical abort)
add("unterminated_double", 'show "unterminated', "bigint 2^96", "bigint 3^96")
add("unterminated_single", "show 'unterminated", "bigint 2^97", "bigint 3^97")
add("unterminated_in_parse", 'parse "abc', "bigint 2^98", "bigint 3^98")
add("unterminated_after_valid", "bigint 2^99", 'show "abc', "bigint 3^99")
add("bad_escape", 'show "a\\q"', "bigint 2^100", "bigint 3^100")

# ---------------------------------------------------------------- 12 bad unicode / bytes
add("unicode_infinity", "parse ∞", "bigint 2^101", "bigint 3^101")
add("unicode_sup4", "parse x⁴", "bigint 2^102", "bigint 3^102")
add("unicode_cjk", "parse 变量", "bigint 2^103", "bigint 3^103")
add("unicode_emoji", "parse x😀", "bigint 2^104", "bigint 3^104")
add("unicode_degree_ok", "parse 90° + )", "bigint 2^105", "bigint 3^105")
add("unicode_pi_col", "parse π + )", "bigint 2^106", "bigint 3^106")
add("unicode_le_col", "parse x ≤ y + )", "bigint 2^107", "bigint 3^107")

# ---------------------------------------------------------------- 13 errors inside functions
add("fn_body_stray", "f(x: u8) = x + )", "bigint 2^108", "show f", "bigint 3^108")
add("fn_body_incomplete", "f(x: u8) = (x +", "bigint 2^109", "show f")
add("fn_body_undef", "f(x: u8) = unknown(x)", "bigint 2^110", "show f")
add("fn_loop_bad", "w(n: u8) = { o: u32 = n; for i in 0..3 { o = o + ; }; o }", "bigint 2^111", "show w")
add("fn_loop_unclosed", "w(n: u8) = { o: u32 = n; for i in 0..3 { o = o + 1; o }", "bigint 2^112", "show w")
add("fn_while_bad", "w(n: u8) = { v: u8 = n; while v > ) { v = v - 1 }; v }", "bigint 2^113", "show w")
add("fn_codeblock_badtype", "w(n: u8) = { v: bogus = n; v }", "bigint 2^114", "show w")
add("fn_then_valid", "bad(x: u8) = x + )", "good(x: u8) = x + 1", "show good", "show bad")
add("fn_redefine_after_error", "f(x: u8) = x + )", "f(x: u8) = x * 2", "show f")
add("fn_recover_then_call", "f(x: u8) = x + )", "f(x: u8) = x + 1", "bigint f(3)", "show f")

# ---------------------------------------------------------------- 14 errors inside if / control
add("if_then_else", "g(x: u8) = if x > 3 then x else", "bigint 2^115", "show g")
add("if_no_then", "g(x: u8) = if x > 3", "bigint 2^116", "show g")
add("ternary_missing_colon", "parse x > 0 ? 1 2", "bigint 2^117", "bigint 3^117")
add("ternary_extra_colon", "parse x > 0 ? 1 : 2 : 3", "bigint 2^118", "bigint 3^118")
add("for_bad_range", "w(n: u8) = { for i in .. { } }", "bigint 2^119", "show w")
add("for_no_body", "w(n: u8) = { for i in 0..3 }", "bigint 2^120", "show w")
add("while_no_cond", "w(n: u8) = { while { n = n - 1 } }", "bigint 2^121", "show w")
add("if_in_bare", "parse if x then y else z", "bigint 2^122", "bigint 3^122")

# ---------------------------------------------------------------- 15 position cases
add("pos_leading_blank", "", "bigint 2^123", "", "show (1 +", "bigint 3^123")
add("pos_leading_spaces", "    show 1 + )", "bigint 2^124", "bigint 3^124")
add("pos_tab", "\tshow (x", "bigint 2^125", "bigint 3^125")
add("pos_long_ident", "show " + "a"*60 + " + )", "bigint 2^126", "bigint 3^126")
add("pos_multiline", "show 1 +\n  2 + )", "bigint 2^127", "bigint 3^127")
add("pos_error_on_line5", "bigint 2^2", "bigint 3^2", "bigint 5^2", "bigint 7^2", "show 1 + )", "bigint 11^2")
add("pos_pi_before", "parse π + )", "bigint 2^128", "bigint 3^128")
add("pos_stray_at_eol", "show 1 + )", "bigint 2^129", "bigint 3^129")

# ---------------------------------------------------------------- 16 cascading errors
add("cascade_two_bad", "show 1 + )", "show 2 * )", "bigint 2^130", "bigint 3^130")
add("cascade_three_bad", "show )", "show ]", "parse !x", "bigint 2^131", "bigint 3^131")
add("cascade_bad_then_good", "show 1 + )", "bigint 2^132", "show 3 + 4", "bigint 5^132")
add("cascade_bad_def_chain", "f(x) = y + )", "g(y) = f(y)", "range g", "bigint 2^133")
add("cascade_unclosed_swallow", "show (1 + 2", "bigint 9^133", "bigint 8^133")
add("cascade_error_then_error", "f(x: u8) =", "g(x: u8) =", "show f", "show g", "bigint 2^134")
add("cascade_mixed", "parse )", "bigint 2^135", "parse ]", "bigint 3^135", "show }")

# ---------------------------------------------------------------- 17 state corruption
add("state_failed_def_name", "alpha(x: u8) = x + )", "show alpha", "range alpha", "bigint alpha(3)")
add("state_failed_def_then_use", "beta(x: u8) = x +", "bigint beta(2)", "show beta")
add("state_failed_then_valid_same", "gamma(x: u8) = x + )", "gamma(x: u8) = x + 10", "show gamma", "bigint gamma(1)")
add("state_partial_then_range", "delta(x: u8) = unknown(x)", "range delta", "show delta")
add("state_show_new_vs_failed", "show never_defined", "eps(x: u8) = x + )", "show eps")
add("state_w_complex", "w(x: u8) = x + )", "show w", "range w")
add("state_z_complex", "z(x: u8) = x + )", "show z", "range z")
add("state_overwrite_bad_good", "ok(x: u8) = x + 1", "show ok", "ok(x: u8) = x + )", "show ok")

# ---------------------------------------------------------------- 18 trailing-operator continuation (swallows next line)
add("cont_plus_swallow", "show 1 +", "  bigint 5^20", "bigint 2^140", "bigint 3^140")
add("cont_star_swallow", "parse 2 *", "  parse 9+9", "bigint 2^141", "bigint 3^141")
add("cont_minus_swallow", "show 5 -", "  bigint 7^20", "bigint 2^142")
add("cont_caret_swallow", "show 2 ^", "  bigint 7^21", "bigint 2^143")
add("cont_amp_swallow", "show 3 &", "  bigint 7^22", "bigint 2^144")
add("cont_comma_swallow", "show [1,", "  bigint 7^23", "bigint 2^145")
add("cont_arrow_swallow", "parse match x { 0 =>", "  bigint 7^24", "bigint 2^146")
add("cont_chain_swallow", "show 1 +", "  show 2 +", "  bigint 7^25", "bigint 2^147")

# ---------------------------------------------------------------- 19 command word swallowed as a variable
add("cmd_show_plus", "show + 1", "bigint 2^148", "bigint 3^148")
add("cmd_show_star", "show * 1", "bigint 2^149", "bigint 3^149")
add("cmd_range_plus", "range + 1", "bigint 2^150", "bigint 3^150")
add("cmd_bigint_plus", "bigint + 1", "bigint 2^151", "bigint 3^151")
add("cmd_parse_question", "parse ? x : y", "bigint 2^152", "bigint 3^152")
add("cmd_equiv_plus", "equiv + 1 2", "bigint 2^153", "bigint 3^153")
add("cmd_show_bang", "show !x", "bigint 2^154", "bigint 3^154")
add("cmd_show_double_eq", "show = = 1", "bigint 2^155", "bigint 3^155")

# ---------------------------------------------------------------- 20 byte-vs-char columns (Unicode before the error)
add("col_pi", "parse π + )", "bigint 2^156")
add("col_oplus", "parse a ⊕ b + )", "bigint 2^157")
add("col_leq", "parse x ≤ y + )", "bigint 2^158")
add("col_times", "parse x × y + )", "bigint 2^159")
add("col_sqrt", "parse √x + )", "bigint 2^160")
add("col_degree", "parse 90° + )", "bigint 2^161")
add("col_pi2", "parse 2π + )", "bigint 2^162")
add("col_mixed_unicode", "parse π² + )", "bigint 2^163")

# ---------------------------------------------------------------- 21 more state corruption
add("state_leak_show_range", "zeta(x: u8) = x + )", "show zeta", "range zeta", "bigint 2^164")
add("state_leak_then_define", "eta(x: u8) = x + )", "show eta", "eta(x: u8) = x + 2", "show eta")
add("state_two_failed", "th1(x: u8) = x + )", "th2(x: u8) = x * )", "show th1", "show th2", "bigint 2^165")
add("state_failed_used_in_valid", "bad(x: u8) = x + )", "good(x: u8) = bad(x) + 1", "show good", "show bad")
add("state_error_then_call_leak", "theta(x: u8) = x + )", "bigint theta(3)", "show theta")
add("state_leak_pi_name", "pi2(x: u8) = x + )", "show pi2", "range pi2")

# ---------------------------------------------------------------- 22 NUL byte / control characters
add("nul_truncation", "show 1 + \x00 2", "bigint 2^170", "bigint 3^170")
add("nul_mid_identifier", "show ab\x00cd", "bigint 2^171")
add("cont_chain", "show 1 +", "  show 2 +", "  bigint 7^30", "bigint 2^172")
add("unclosed_bracket_swallow", "show [1, 2,", "  bigint 7^31", "bigint 2^173")


def main():
    for i, (name, stmts) in enumerate(CASES, 1):
        fn = f"{i:03d}_{name}.ucas"
        header = f"# parser_error_recovery: {name}\n"
        body = "\n".join(stmts) + "\n"
        with open(os.path.join(OUT, fn), "w", encoding="utf-8") as f:
            f.write(header + body)
    print(f"wrote {len(CASES)} .ucas files")


if __name__ == "__main__":
    main()
