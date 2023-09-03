#!/bin/bash

ROOT=$(dirname "$0")

"$ROOT/Run.sh" python "$ROOT/Conan/tools.py" "$@"
