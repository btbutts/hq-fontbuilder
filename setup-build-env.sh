#!/usr/bin/env bash
# Set up everything a fresh clone needs to run font_composer.
#
#   1. Create the virtualenv .fontbuilder.venv/ (unless it already exists) and
#      install requirements.txt into it.
#   2. If the compiled web console is missing (fresh clone), run compile-spa.sh
#      to install the npm dependencies and build the SPA.
#
# Both steps are skipped when already done, so running this script again is cheap
# and safe (that is what the VS Code folder-open task relies on). Runs on macOS
# and Linux; needs python3, and node/npm for step 2.

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

VENV=".fontbuilder.venv"
STATIC_DIR="font_composer/composer/web/static"

if [ ! -x "${VENV}/bin/python" ]; then
    echo "creating virtualenv ${VENV}"
    python3 -m venv "${VENV}"
fi

# shellcheck source=/dev/null
source "${VENV}/bin/activate"
pip install -q -r requirements.txt

if [ ! -d "${STATIC_DIR}" ] || [ -z "$(ls -A "${STATIC_DIR}")" ]; then
    echo "compiled web console not found; building it"
    ./compile-spa.sh
fi

echo "setup complete: run the console with"
echo "  ${VENV}/bin/python -m font_composer compose --fonts-dir fonts --config composer.toml"
