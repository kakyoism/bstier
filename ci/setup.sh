#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
cd "$repo_dir"

install_apt_packages() {
    if [ "$(id -u)" -eq 0 ]; then
        apt-get update
        apt-get install -y "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y "$@"
    else
        echo 'Error: apt-get requires root or sudo to install dependencies.' >&2
        exit 1
    fi
}

if command -v python3 >/dev/null 2>&1; then
    python_bin=$(command -v python3)
elif command -v brew >/dev/null 2>&1; then
    brew install python
    python_bin=$(command -v python3)
elif command -v apt-get >/dev/null 2>&1; then
    install_apt_packages python3 python3-pip python3-venv
    python_bin=$(command -v python3)
else
    echo 'Error: Python 3 is missing and no supported package manager was found.' >&2
    echo 'Install Python 3.11 or newer, then run this script again.' >&2
    exit 1
fi

if ! "$python_bin" -m pip --version >/dev/null 2>&1; then
    "$python_bin" -m ensurepip --upgrade
fi

if command -v poetry >/dev/null 2>&1; then
    poetry_bin=$(command -v poetry)
else
    "$python_bin" -m pip install --user poetry
    user_base=$($python_bin -m site --user-base)
    poetry_bin="$user_base/bin/poetry"
    if [ ! -x "$poetry_bin" ]; then
        echo 'Error: Poetry was installed but its executable could not be found.' >&2
        exit 1
    fi
fi

if ! command -v tesseract >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        brew install tesseract
    elif command -v apt-get >/dev/null 2>&1; then
        install_apt_packages tesseract-ocr
    else
        echo 'Error: Tesseract is missing and no supported package manager was found.' >&2
        exit 1
    fi
fi

if ! command -v magick >/dev/null 2>&1 && ! command -v convert >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        brew install imagemagick
    elif command -v apt-get >/dev/null 2>&1; then
        install_apt_packages imagemagick
    else
        echo 'Error: ImageMagick is missing and no supported package manager was found.' >&2
        exit 1
    fi
fi

"$poetry_bin" install
echo 'Setup complete. Use ./ci/run.sh for bstier commands.'