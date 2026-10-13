#!/usr/bin/env bash
# Compile the composer web console SPA.
#
# Installs the npm dependencies of src/composer-web/ and builds the SvelteKit app
# into font_composer/composer/web/static/, the directory the Python console serves.
# Safe to re-run: the build wipes and rewrites that directory, so this script is how
# you choose when to recompile.
#
# Used by setup-build-env.sh on a fresh clone and by .github/workflows/release.yml.
# Runs on macOS and Linux; needs node and npm on PATH.

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/src/composer-web"
npm install
npm run build
