import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

// Compile straight into the directory the Python console serves, resolved
// relative to this config file so the repo stays relocatable.
const staticDir = path.resolve(
	path.dirname(fileURLToPath(import.meta.url)),
	'../../font_composer/composer/web/static'
);

// `npm run dev` only: the Python console picks its own port and saves it in composer.toml
// ([server] port); COMPOSER_PORT overrides it.
function consolePort(): number {
	const fromEnv = Number(process.env.COMPOSER_PORT);
	if (Number.isInteger(fromEnv) && fromEnv > 0) return fromEnv;
	try {
		const toml = readFileSync(
			path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../composer.toml'),
			'utf-8'
		);
		const section = /^\[server\][^[]*/m.exec(toml)?.[0] ?? '';
		const port = Number(/^\s*port\s*=\s*(\d+)/m.exec(section)?.[1]);
		if (Number.isInteger(port) && port > 0) return port;
	} catch {
		// no composer.toml yet
	}
	return 8765;
}

const consoleOrigin = `http://localhost:${consolePort()}`;

export default defineConfig({
	plugins: [
		tailwindcss(),
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
