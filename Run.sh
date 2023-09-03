#!/bin/bash

ROOT=$(dirname "$0")
export CONAN_HOME="$ROOT/.conan"

source "$ROOT/.venv/bin/activate"

"$@"
