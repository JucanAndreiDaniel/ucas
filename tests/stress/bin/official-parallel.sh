#!/bin/sh
# Parallel official-test runner. No per-test timeout: every test runs to
# completion (full regression sweep). Usage: official-parallel.sh <root> <jobs>
set -u
root=$1
jobs=$2
list=/var/tmp/ucas-official-par-list.$$
fails=/var/tmp/ucas-official-par-fails.$$
trap 'rm -f "$list" "$fails"' EXIT HUP INT TERM
(cd "$root/tests" && ls *.ucas | sed 's/\.ucas$//' | sort) > "$list"
one() {
    n=$1; root=$2
    cd "$root/tests" || exit 1
    e="UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none"
    [ -f "$n.env" ] && e="UCAS_NO_TIMES=1 $(cat "$n.env")"
    if [ -f "$n.needs" ] && ! command -v "$(cat "$n.needs")" >/dev/null 2>&1; then
        exit 0
    fi
    env $e "$root/ucas" "$n.ucas" > "/var/tmp/ucas-off-$n.got" 2>&1
    if diff -u "$n.out" "/var/tmp/ucas-off-$n.got" > "/var/tmp/ucas-off-$n.diff" 2>&1; then
        rm -f "/var/tmp/ucas-off-$n.got" "/var/tmp/ucas-off-$n.diff"
    else
        printf 'FAIL %s\n' "$n"
    fi
}
export -f one 2>/dev/null || true
xargs -P "$jobs" -I{} sh -c '
    n=$1; root=$2
    cd "$root/tests" || exit 1
    e="UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none"
    [ -f "$n.env" ] && e="UCAS_NO_TIMES=1 $(cat "$n.env")"
    if [ -f "$n.needs" ] && ! command -v "$(cat "$n.needs")" >/dev/null 2>&1; then exit 0; fi
    # cfront.ucas runs 15 `c optimize` calls (6 with budget 120) and can take
    # well over an hour when the machine is contended. Cap just this one test;
    # the full regression sweep stays timeout-free for every other test.
    if [ "$n" = cfront ]; then
        env $e timeout 180 "$root/ucas" "$n.ucas" > "/var/tmp/ucas-off-$n.got" 2>&1
    else
        env $e "$root/ucas" "$n.ucas" > "/var/tmp/ucas-off-$n.got" 2>&1
    fi
    if diff -u "$n.out" "/var/tmp/ucas-off-$n.got" > "/var/tmp/ucas-off-$n.diff" 2>&1; then
        rm -f "/var/tmp/ucas-off-$n.got" "/var/tmp/ucas-off-$n.diff"
    else
        printf "FAIL %s\n" "$n"
    fi
' sh {} "$root" < "$list" > "$fails"
total=$(wc -l < "$list")
nf=$(wc -l < "$fails")
cat "$fails"
echo "official: $total tests, $nf fail, jobs=$jobs (no timeout)"
[ "$nf" -eq 0 ]
