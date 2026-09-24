#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

cd "$script_dir"/..
if command -v poetry >/dev/null 2>&1; then
    exec poetry run bstier "$@"
elif command -v python3 >/dev/null 2>&1 && python3 -m poetry --version >/dev/null 2>&1; then
    exec python3 -m poetry run bstier "$@"
else
    echo 'Error: Poetry is not installed. Run ./ci/setup.sh first.' >&2
    exit 1
fi
