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

export default defineConfig({
	plugins: [
		tailwindcss(),
		...(await sveltekit({
			adapter: adapter({
				pages: staticDir,
				assets: staticDir,
				fallback: 'index.html',
				precompress: false,
				strict: true
			})
		}))
	],
	server: {
		// `npm run dev` serves the SPA; the Python console must run alongside it
		// (default port 8765) to answer the API and font-byte requests.
		proxy: {
			'/api': 'http://localhost:8765',
			'/fonts': 'http://localhost:8765'
		}
	}
});
