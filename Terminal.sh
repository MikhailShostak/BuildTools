#!/bin/bash

ROOT=$(cd "$(dirname "$0")"; pwd)

"$ROOT/Run.sh"

pushd "$ROOT/.."
bash
