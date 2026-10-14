import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, type Plugin } from 'vite';

// Compile straight into the directory the Python console serves, resolved
// relative to this config file so the repo stays relocatable.
const staticDir = path.resolve(
	path.dirname(fileURLToPath(import.meta.url)),
	'../../font_composer/composer/web/static'
);

// `npm run dev` only: the Python console picks its own port and saves it in font_composer.toml
// ([server] port); COMPOSER_PORT overrides it.
function consolePort(): number {
	const fromEnv = Number(process.env.COMPOSER_PORT);
	if (Number.isInteger(fromEnv) && fromEnv > 0) return fromEnv;
	try {
		const toml = readFileSync(
			path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../font_composer.toml'),
			'utf-8'
		);
		const section = /^\[server\][^[]*/m.exec(toml)?.[0] ?? '';
		const port = Number(/^\s*port\s*=\s*(\d+)/m.exec(section)?.[1]);
		if (Number.isInteger(port) && port > 0) return port;
	} catch {
		// no font_composer.toml yet
	}
	return 8765;
}

const consoleOrigin = `http://localhost:${consolePort()}`;

const namedChunks: Plugin = {
	name: 'named-chunks',
	apply: 'build',
	outputOptions(options) {
		const kitNames = options.chunkFileNames;
		if (typeof kitNames !== 'function') return null;
		return {
			...options,
			chunkFileNames: (chunk) => {
				const pattern = kitNames(chunk);
				return pattern.endsWith('/chunks/[hash].js')
					? pattern.replace('[hash].js', '[name].[hash].js')
					: pattern;
			}
		};
	}
};

export default defineConfig({
	plugins: [
		tailwindcss(),
		// Opt-in: `./compile-spa.sh --named-chunks` sets COMPOSER_NAMED_CHUNKS=1.
		...(process.env.COMPOSER_NAMED_CHUNKS === '1' ? [namedChunks] : []),
		...(await sveltekit({
			adapter: adapter({
				pages: staticDir,
				assets: staticDir,
				// SPA fallback for client-side routes; '200.html' (not 'index.html')
				// so it does not overwrite the prerendered '/' page.
				fallback: '200.html',
				precompress: false,
				strict: true
			})
		}))
	],
	build: {
		// Vite 8 minifies with Rolldown/Oxc; the old top-level `esbuild: {...}` block and
		// `minify: 'esbuild'` no longer apply. Minifier options go through
		// `rolldownOptions.output.minify`. To disable minification completely, replace this
		// block with `minify: false`.
		minify: 'oxc',
		cssMinify: 'lightningcss',
		sourcemap: false,
		rolldownOptions: {
			output: {
				// Otherwise exports shared between chunks are renamed to `$`, `A`, ...
				minifyInternalExports: false,
				minify: {
					// Readable output: no identifier mangling, original function/class names kept.
					mangle: false,
					compress: {
						keepNames: { function: true, class: true },
						dropConsole: true,
						dropDebugger: true
					},
					codegen: { removeWhitespace: true }
				}
			}
		}
	},
	server: {
		// `npm run dev` serves the SPA; the Python console must run alongside it
		// to answer the API and font-byte requests. It listens on both 127.0.0.1 and ::1,
		// so "localhost" works whichever address Node resolves it to.
		proxy: {
			'/api': consoleOrigin,
			'/fonts': consoleOrigin
		}
	}
});
