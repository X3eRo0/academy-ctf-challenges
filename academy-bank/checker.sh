#!/bin/bash

. /opt/env/bin/activate

dir=$(cd "$(dirname "$0")" && pwd)

python3 "$dir/checker/checker.py" "$@"
