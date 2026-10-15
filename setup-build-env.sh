#!/usr/bin/env bash
# Set up everything a fresh clone needs to run font_composer.
#
#   1. Create the virtualenv .fontbuilder.venv/ (unless it already exists) and
#      install requirements.txt into it.
#   2. If the compiled web console is missing (fresh clone), run compile-spa.sh
#      to install the dependencies with Bun and build the SPA.
#
# Both steps are skipped when already done, so running this script again is cheap
# and safe (that is what the VS Code folder-open task relies on). Runs on macOS
# and Linux; needs python3, and bun for step 2.

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

VENV=".fontbuilder.venv"
STATIC_DIR="font_composer/composer/web/static"

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "setup-build-env.sh: python3 $(python3 -V 2>&1) is too old; Python 3.12 or later is required" >&2
    exit 1
fi

if [ ! -x "${VENV}/bin/python" ]; then
    echo "creating virtualenv ${VENV}"
    python3 -m venv "${VENV}"
fi

# shellcheck source=/dev/null
source "${VENV}/bin/activate"
pip install -q -r requirements.txt

# 200.html is the page the server needs for every client-side route; a missing or
# interrupted build lacks it and is redone.
if [ ! -f "${STATIC_DIR}/200.html" ]; then
    echo "compiled web console not found; building it"
    ./compile-spa.sh
fi

echo "setup complete: put font family folders in fonts/, then start the console with"
echo "  ${VENV}/bin/python -m font_composer compose"
