#!/bin/bash

. /opt/env/bin/activate

dir=$(cd "$(dirname "$0")" && pwd)

"$dir/checker/checker.py" "$@"
