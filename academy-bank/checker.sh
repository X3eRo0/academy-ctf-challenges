#!/bin/bash

. /opt/env/bin/activate

dir=$(cd "$(dirname "$0")" && pwd)

export PWNLIB_NOTERM=1

# Build xvm if build directory doesn't exist
if [ ! -d "$dir/build" ]; then
    echo "[checker.sh] build directory not found; building academy-bank..."
    if command -v make >/dev/null 2>&1; then
        make
        (cd "$dir/build") || {
            echo "[checker.sh] build failed" >&2
            exit 1
        }
    else
        echo "[checker.sh] cmake not found; cannot build xvm" >&2
        exit 1
    fi
fi

python3 "$dir/checker/checker.py" "$@"