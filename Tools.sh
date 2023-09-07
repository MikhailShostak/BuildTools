#!/bin/bash

ROOT=$(cd "$(dirname "$0")"; pwd)

"$ROOT/Run.sh" python "$ROOT/Conan/tools.py" "$@"
