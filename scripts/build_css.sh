#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# Supply a local, verified Tailwind v3.4.17 standalone binary (or CLI).
TAILWIND_BIN="${TAILWIND_BIN:-tailwindcss}"
"$TAILWIND_BIN" -c tailwind.config.js -i static/css/input.css -o static/css/app.css --minify
