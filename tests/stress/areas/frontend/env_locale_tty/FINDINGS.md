# Stress findings — `env_locale_tty`

_Original heading: FINDINGS — `env_locale_tty` (environment / locale / terminal sensitivity)_

# FINDINGS — `env_locale_tty` (environment / locale / terminal sensitivity)

Binary under test: `$ROOT/ucas` (prebuilt, not rebuilt).
All scratch lives in `./.scratch` and is removed on exit. Every child is `timeout`-bounded.

**Headline: no CRASH, HANG, or WRONG answer was found.** Output is byte-identical across
28 environment configurations (all available locales incl. comma-decimal `ro_RO`, an
invalid locale, bogus `UCAS`/`UCAS_BIN`/`UCAS_SPIRV_CROSS`/`UCAS_CC`, bogus/`unset`
`TMPDIR`/`HOME`, and 6 `TERM` values) — see `run_env_matrix.sh` (171/171 pass) and
`SUMMARY.md`. The items below are the genuine environment-dependent behaviours that
exist; they are design choices / UX limits, not soundness bugs, but they are recorded
because they are the exact places where the environment changes ucas's output.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| NLP | 1 | Unicode handling differs between English mode and expression mode |
| LIMIT | 3 | identical input prints different text on a TTY vs a pipe |

## Findings

### LIMIT-1 — identical input prints different text on a TTY vs a pipe
**Severity:** LIMIT
**Expected:** _not recorded_
`ucas` keys its REPL prompt and its NLP ambiguity dialogue off `isatty(0)`/`isatty(1)`.
The same English query therefore produces materially different stdout on a pipe versus a
pseudo-terminal.

**Reproducer:**
Reproducer (pipe):
```sh
printf 'what is log of x\n' | timeout 10 $ROOT/ucas 2>&1
```
**Observed:** (pipe):
```
  note: "log" without a base: read as the natural log, ln, not log base 2 or log base 10 (say "natural log", "log base 2" or "log base 10", or "assume log means base 2")
  ucas: it(x) = log(x)
  ucas: show it
it(x: real) = log(x)
  -> real
```

**Reproducer:**
Reproducer (pseudo-terminal):
```sh
printf 'what is log of x\n' | timeout 10 script -qec "$ROOT/ucas" /dev/null 2>&1 | cat -A
```
**Observed:** (pty; `^M` = CR inserted by the pty, not by ucas):
```
what is log of x^M
ucas>   ? "log" without a base:^M
      1) the natural log, ln^M
      2) log base 2^M
      3) log base 10^M
    which? [1] ^M
    (kept for this session; say "natural log", ...)^M
  ucas: it(x) = log(x)^M
  ucas: show it^M
it(x: real) = log(x)^M
  -> real^M
ucas> 
```
**Why it matters:** any golden captured under a pty will carry prompts, an interactive
menu, and CR line endings, so it will never diff against a pipe-captured golden. The
repo runner (`tests/stress/run.sh`) redirects stdout to a file, so all goldens in this
folder are captured in the non-interactive form. By design (see `src/main.c:44` and
`src/nlp.c:244-248`), not a bug — documented so nobody "fixes" it with a flaky golden.

### LIMIT-2 — half-interactive state: stdin is a TTY but stdout is redirected
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The REPL prompt checks only `isatty(0)`, while the NLP dialogue checks
`isatty(0) && isatty(1)`. With an interactive stdin but stdout sent to a file/pipe, the
`ucas> ` prompt is emitted **into the redirected stdout** (invisible to the user) while
ambiguities are silently resolved with a `note:` line. To a human this can look like a
hang: the program is waiting for input on the terminal but prints no prompt there.

**Reproducer:**
```sh
printf 'what is log of x\n' | timeout 10 script -qec \
  '$ROOT/ucas > /tmp/tty.mixed 2>&1' /dev/null >/dev/null 2>&1
cat -A /tmp/tty.mixed
```
**Observed:**
```
ucas>   note: "log" without a base: read as the natural log, ln, not ...
  ucas: it(x) = log(x)
  ucas: show it
it(x: real) = log(x)
  -> real
ucas> 
```
(`ucas> ` present, `which?` menu absent.) No crash/hang under `timeout`; the concern is
UX consistency across stdout modes.

### LIMIT-3 — non-ASCII in expressions is rejected and rendered as `'?'`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Any non-ASCII byte in a ucas expression is a lexical error; the offending byte is always
printed as a literal `?`, regardless of locale. Both NFC and NFD forms of the same
accented character are rejected (no Unicode normalization / no Unicode identifiers).

**Reproducer:**
```sh
for src in 'show café' 'show café' 'show α' 'show 😀'; do
  printf '%s\n' "$src" | timeout 8 $ROOT/ucas 2>&1 | head -2
done
```
**Observed:** (excerpt):
```
  error: unexpected character '?'       (NFC 'é', col 9)
  error: unexpected character '?'       (NFD 'e'+U+0301, col 10)
  error: unexpected character '?'       (Greek α)
  error: unexpected character '?'       (emoji)
```
Also true for bare invalid UTF-8 bytes (`0x80`, lone `0xC3`, overlong `C0 80`, `F5 80 80 80`):
each is reported as `unexpected character '?'` with no crash. The same outputs appear
under `LANG=C`, `LC_ALL=ro_RO.UTF-8`, and an invalid `LC_ALL` (byte-identical).

### NLP-1 — Unicode handling differs between English mode and expression mode
**Severity:** NLP
**Why it matters:** _not recorded_
The English frontend *does* accept several Unicode characters and maps them to ASCII
names, even though the expression lexer rejects non-ASCII (F3). The mapping is
locale-invariant but inconsistent in which characters it accepts, and unknown ones are
rendered with a U+FFFD replacement character in one path and `'?'` in another.

**Reproducer:**
```sh
for src in 'what is μ times 2' 'what is √ of 16' 'what is π' \
           'what is café' 'what is pi'; do
  printf '%s\n' "$src" | timeout 8 $ROOT/ucas 2>&1 | head -3
done
```
**Observed:** (selected):
```
what is μ times 2   ->  ucas: it(mu) = mu*2  /  it(mu: real) = 2mu
what is √ of 16     ->  ucas: sqrt(16)       /  4
what is π           ->  ucas: pi
what is café        ->  sorry: I can't read the character '<\uFFFD>'
```
Also observed: lowercase Greek `α β θ λ ω` map to `alpha beta theta lambda omega`;
curly quotes U+2019/U+201D fold to ASCII `'`/`"`; U+00A0 NBSP is **not** treated as
whitespace (yields the replacement-character error); en dash U+2013 and fullwidth colon
U+FF1A reach the expression lexer and yield `unexpected character '?'`.
**Expected:** one consistent policy for Unicode across the English and expression frontends.
Not a crash and locale-independent; recorded as a LIMIT/NLP inconsistency.

## Checks that passed

### Verified invariants (non-issues, for the record)
- **Numeric formatting never follows the locale.** ucas never calls `setlocale(3)`
  (confirmed by source inspection: no `setlocale`/`localeconv` anywhere in `src/`), so
  the C runtime stays in the `"C"` locale. `show 1/3`, `0.1+0.2`, `sqrt(2)`, `1e-20`,
  `1234567.891`, `error ...`, `range ...` produce byte-identical output under `C`,
  `C.UTF-8`, `en_US.UTF-8`, `ro_RO.UTF-8` (comma-decimal locale), `POSIX`, an invalid
  `xx_XX.INVALID`, and with `LC_NUMERIC=ro_RO.UTF-8`.
- **No stray file writes.** `plot X to NAME` writes `NAME.gif` in the **current
  directory**, not under `HOME` or `TMPDIR`, even with `HOME=/no/such/home` and
  `TMPDIR=/no/such/tmp`. The only `getenv("TMPDIR")` use is `adamfit`'s intentionally
  temporary build dir (`src/adamfit.c:1161`); bogus `TMPDIR` did not crash the measured
  path. `--version` is not a flag (treated as a filename) and is locale-invariant.
- **No hangs under a pty**, including pty + immediate stdin EOF.
- **Determinism:** every golden run twice is byte-identical.
