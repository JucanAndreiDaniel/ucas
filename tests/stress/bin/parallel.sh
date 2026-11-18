#!/bin/sh
# Parallel stress runner: run goldens concurrently, with a serial lane for
# the few CPU-budget-sensitive cases so parallel oversubscription cannot trip
# their "computation grows too large" guard.
# Usage: parallel.sh <root> <jobs> [area-filter]
# Outputs FAIL lines and a summary; exits 1 if any golden differs.
set -u
root=$1
jobs=$2
area=${3:-}
list=/var/tmp/ucas-stress-par-list.$$
filt=/var/tmp/ucas-stress-par-filt.$$
serial=/var/tmp/ucas-stress-par-serial.$$
fails=/var/tmp/ucas-stress-par-fails.$$
trap 'rm -f "$list" "$filt" "$serial" "$fails"' EXIT HUP INT TERM

find "$root/tests/stress/areas" -mindepth 3 -maxdepth 3 \
    \( -name '*.ucas' -o -name '*.jsonl' \) | sort > "$list"

# Serial lane: the 4 goldens whose expected output IS the CPU-budget guard.
# With a raised budget they would run for hours; keep their default limit and
# never run them concurrently with heavy jobs.
guard_re='grows too large|coefficients grow too large'
: > "$filt"; : > "$serial"
while IFS= read -r t; do
    case "$t" in *"$area"*) ;; *) continue ;; esac
    b=${t%.*}; [ -f "$b.out" ] || continue
    if grep -qE "$guard_re" "$b.out" 2>/dev/null; then
        printf '%s\n' "$t" >> "$serial"
    else
        printf '%s\n' "$t" >> "$filt"
    fi
done < "$list"

one() {
    t=$1
    b=${t%.*}; [ -f "$b.out" ] || return 0
    d=$(dirname "$t"); n=$(basename "$t")
    case "$n" in
      *.ucas) (cd "$d" && env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none \
               "$root/ucas" "$n") > "$b.got" 2>&1 ;;
      json_*) (cd "$d" && env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none \
               "$root/ucas" --json --files none < "$n") > "$b.got" 2>&1 ;;
      *)      fl=$(cat "$b.flags" 2>/dev/null || true)
              (cd "$d" && env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none \
               "$root/ucas" --mcp $fl < "$n") > "$b.got" 2>&1 ;;
    esac
    if diff -u "$b.out" "$b.got" > "$b.diff" 2>&1; then
        rm -f "$b.got" "$b.diff"
    else
        printf 'FAIL %s\n' "${t#$root/tests/stress/}"
    fi
}

# serial lane first (default CPU budget), one at a time
while IFS= read -r t; do one "$t"; done < "$serial" > "$fails"
# parallel lane (raised CPU budget so oversubscription is harmless)
xargs -P "$jobs" -I{} sh -c '
    t=$1; root=$2
    b=${t%.*}; [ -f "$b.out" ] || exit 0
    d=$(dirname "$t"); n=$(basename "$t")
    case "$n" in
      *.ucas) (cd "$d" && env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none UCAS_GB_LIMIT=60 UCAS_PM_LIMIT=60 "$root/ucas" "$n") > "$b.got" 2>&1 ;;
      json_*) (cd "$d" && env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none UCAS_GB_LIMIT=60 UCAS_PM_LIMIT=60 "$root/ucas" --json --files none < "$n") > "$b.got" 2>&1 ;;
      *)      fl=$(cat "$b.flags" 2>/dev/null || true)
              (cd "$d" && env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none UCAS_GB_LIMIT=60 UCAS_PM_LIMIT=60 "$root/ucas" --mcp $fl < "$n") > "$b.got" 2>&1 ;;
    esac
    if diff -u "$b.out" "$b.got" > "$b.diff" 2>&1; then rm -f "$b.got" "$b.diff"; else printf "FAIL %s\n" "${t#$root/tests/stress/}"; fi
' sh {} "$root" < "$filt" >> "$fails"

total=$(( $(wc -l < "$filt") + $(wc -l < "$serial") ))
nf=$(wc -l < "$fails")
cat "$fails"
echo "stress: $total goldens, $nf fail, jobs=$jobs"
[ "$nf" -eq 0 ]
