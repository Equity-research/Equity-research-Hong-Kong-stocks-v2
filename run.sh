#!/bin/sh
set -e
if [ -x .local-bin/node/bin/node ]; then
  PATH="$(pwd)/.local-bin/node/bin:$PATH"
  export PATH
fi
if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip install -r requirements.txt
(cd frontend && npm install)
python main.py &
backend_pid=$!
trap 'kill $backend_pid 2>/dev/null || true' EXIT INT TERM
(cd frontend && npm run dev)
