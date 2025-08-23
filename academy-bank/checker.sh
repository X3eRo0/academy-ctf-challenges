#!/bin/bash

. /opt/env/bin/activate

export PWNLIB_NOTERM=1

dir=$(cd "$(dirname "$0")" && pwd)

python3 "$dir/checker/checker.py" "$@"
