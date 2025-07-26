#!/bin/bash

. /opt/env/bin/activate

dir=$(dirname $0)
$dir/checker.py "$@"
