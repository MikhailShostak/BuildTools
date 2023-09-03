#!/bin/bash

ROOT=$(dirname "$0")

echo "Initializing .venv..."
python3 -m venv "$ROOT/.venv"

echo "Activating .venv..."
source "$ROOT/.venv/bin/activate"

echo "Checking python executables..."
which python3

echo "Installing packages..."
python3 -m pip install --upgrade pip

pip install -r "$ROOT/requirements.txt"

"$ROOT/Terminal.sh"

if [ $? -ne 0 ]; then
  read -p "Press any key to continue..."
fi
