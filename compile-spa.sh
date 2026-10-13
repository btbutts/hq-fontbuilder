#!/usr/bin/env bash
# Compile the composer web console SPA.
#
# Installs the npm dependencies of src/composer-web/ and builds the SvelteKit app
# into font_composer/composer/web/static/, the directory the Python console serves.
# Safe to re-run: the build wipes and rewrites that directory, so this script is how
# you choose when to recompile.
#
# Used by setup-build-env.sh on a fresh clone and by .github/workflows/release.yml.
# Runs on macOS and Linux; needs node and npm on PATH. Under CI (CI=true, which
# GitHub Actions sets) the dependencies are installed with `npm ci`, exactly as
# package-lock.json pins them; otherwise `npm install` is used, which may update it.

set -euo pipefail

if ! command -v npm > /dev/null 2>&1; then
    echo "compile-spa.sh: npm not found; install Node.js (22 or later) and npm first" >&2
    exit 1
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/src/composer-web"
if [ "${CI:-}" = "true" ]; then
    npm ci
else
    npm install
fi
npm run build
