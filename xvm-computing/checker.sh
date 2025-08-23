#!/bin/bash

. /opt/env/bin/activate

dir=$(cd "$(dirname "$0")" && pwd)

export PWNLIB_NOTERM=1

# Build xvm if build directory doesn't exist
if [ ! -d "$dir/build" ]; then
    echo "[checker.sh] build directory not found; building xvm..."
    if command -v cmake >/dev/null 2>&1; then
        cmake -B build
        (cd "$dir/build" && make -j"$(nproc)") || {
            echo "[checker.sh] build failed" >&2
            exit 1
        }
    else
        echo "[checker.sh] cmake not found; cannot build xvm" >&2
        exit 1
    fi
fi

"$dir/checker/checker.py" "$@"
