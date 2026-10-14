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
#
# Usage: compile-spa.sh [--named-chunks]
#   --named-chunks  local testing only: prefix shared chunk filenames with their module
#                   name (chunks/Dropdown.<hash>.js instead of chunks/<hash>.js). Without
#                   it, which is how setup-build-env.sh, the VS Code tasks and the release
#                   workflow call this script, the build uses SvelteKit's default names.

set -euo pipefail

named_chunks=0
for arg in "$@"; do
    case "$arg" in
        --named-chunks) named_chunks=1 ;;
        *)
            echo "compile-spa.sh: unknown argument '$arg' (usage: compile-spa.sh [--named-chunks])" >&2
            exit 2
            ;;
    esac
done

if ! command -v npm > /dev/null 2>&1; then
    echo "compile-spa.sh: npm not found; install Node.js (22 or later) and npm first" >&2
    exit 1
fi

# Read by src/composer-web/vite.config.ts. Set or unset explicitly so a value left over
# in the caller's environment can never switch the option on without the flag.
if [ "$named_chunks" = "1" ]; then
    export COMPOSER_NAMED_CHUNKS=1
else
    unset COMPOSER_NAMED_CHUNKS
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/src/composer-web"
if [ "${CI:-}" = "true" ]; then
    npm ci
else
    npm install
fi
npm run build
