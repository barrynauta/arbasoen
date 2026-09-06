#!/bin/sh
# Smoke tests for the arbasoen validators. Run from anywhere:
#     sh validate/tests/run.sh
# Exits nonzero if any expectation is not met.
set -u
here=$(cd "$(dirname "$0")" && pwd)
validate="$here/.."
fail=0

expect() {          # expect <label> <wanted exit> <command...>
    label=$1; want=$2; shift 2
    "$@" >/dev/null 2>&1
    got=$?
    if [ "$got" -eq "$want" ]; then
        echo "ok    $label (exit $got)"
    else
        echo "FAIL  $label (exit $got, wanted $want)"
        fail=1
    fi
}

expect "cycles: loop fixture is caught"        1 python3 "$validate/validate_cycles.py"     "$here/loop.ged"
expect "cycles: chronology fixture is clean"   0 python3 "$validate/validate_cycles.py"     "$here/chronology.ged"
expect "chronology: error fixture is caught"   1 python3 "$validate/validate_chronology.py" "$here/chronology.ged"
expect "chronology: loop fixture is clean"     0 python3 "$validate/validate_chronology.py" "$here/loop.ged"

[ "$fail" -eq 0 ] && echo "all good"
exit $fail
