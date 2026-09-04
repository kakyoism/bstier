#! /bin/sh

# fail on first error
set -e

# protect cwd
pushd . &> /dev/null

ScriptDir="$( cd "$( dirname "$0" )" && pwd )"
PoetryBin="`which poetry`"

# script is at proj_root/
cd "$ScriptDir"
servName=$(basename "$ScriptDir")
$PoetryBin run python src/cli.py "$@"

popd &> /dev/null
