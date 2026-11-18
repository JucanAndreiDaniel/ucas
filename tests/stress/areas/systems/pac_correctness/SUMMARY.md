# pac_correctness — summary

## Counts

- 4 CLI goldens (inputs `01_`..`04_`, paired `.out` files).

## Issues by severity

- None. All goldens match the fixed binary under the canonical environment.

## Takeaway

The optional certificate modes expose the cofactors already present in a
kernel proof in a concise, independently checkable form, and the checker
localizes an injected fault to the exact step. Default proof output is
untouched, so existing goldens remain stable.
