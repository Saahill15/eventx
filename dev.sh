#!/usr/bin/env bash
# Starts the API (port 8000) and the website (port 3000) together. Stop both with Ctrl+C.
# Uses the Node in .tools/ and the Python in back/venv, so nothing needs to be installed or on your PATH.
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$ROOT/.tools/node/bin:$PATH"

[ -x "$ROOT/back/venv/bin/uvicorn" ] || { echo "Missing back/venv. Run: cd back && python3 -m venv venv && ./venv/bin/pip install -r requirements-dev.txt"; exit 1; }
[ -x "$ROOT/.tools/node/bin/node" ] || { echo "Missing .tools/node (the Node runtime)."; exit 1; }
[ -d "$ROOT/front/node_modules" ] || (cd "$ROOT/front" && npm install)

# Free the ports if an old copy is still running
for port in 8000 3000; do pids=$(lsof -ti tcp:$port 2>/dev/null); [ -n "$pids" ] && kill $pids 2>/dev/null; done
sleep 1

cleanup() { echo; echo "Stopping…"; kill $API_PID $WEB_PID 2>/dev/null; wait 2>/dev/null; exit 0; }
trap cleanup INT TERM

(cd "$ROOT/back" && exec ./venv/bin/uvicorn app.main:app --reload --port 8000) &
API_PID=$!
(cd "$ROOT/front" && exec npm run dev) &
WEB_PID=$!

echo
echo "  Website  http://localhost:3000"
echo "  API      http://localhost:8000   (docs: /docs)"
echo "  Admin    http://localhost:3000/admin/login"
echo
wait
