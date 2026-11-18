#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export PDF_LAB_HOME="${PDF_LAB_HOME:-$PWD/data}"
exec uvicorn app:app --host "${PDF_LAB_HOST:-127.0.0.1}" --port "${PDF_LAB_PORT:-8787}"
