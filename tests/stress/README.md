# Stress suite

This suite stresses ucas. It finds crashes, hangs, wrong answers and weak English parse results.
It is separate from `make test`.

The `.out` files record the current output. Some outputs show bugs. When the output changes, the test fails.
This is how you notice a fix.

## Layout

```text
tests/stress/
  README.md  SPEC.md  MASTER_FINDINGS.md  AREAS.md
  docs/    research notes
  areas/   seven domains with 127 areas
```

Each area has inputs, `.out` files, `FINDINGS.md` and `SUMMARY.md`.
See `SPEC.md` for the rules. See `MASTER_FINDINGS.md` for the bugs. See `AREAS.md` for the index.

## Run the tests

Build ucas, then run the stress target from the repo root:

```sh
bmake
bmake stress-test
```

Set `STRESS_AREA=NAME` to run one area:

```sh
bmake stress-test STRESS_AREA=sat_hard_mult
```

The Makefile writes a `NAME.diff` file next to each golden that fails.

Recapture one area after a fix:

```sh
bmake stress-accept STRESS_AREA=<area>
```

Crash and hang reproducers have no `.out` file. They stay in `FINDINGS.md` as commands.
