#!/bin/bash

ROOT=$(cd "$(dirname "$0")"; pwd)
export CONAN_HOME="$ROOT/.conan"

source "$ROOT/.venv/bin/activate"

"$@"
