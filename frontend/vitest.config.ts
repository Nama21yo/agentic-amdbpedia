import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config.ts';

export default mergeConfig(
	viteConfig,
	defineConfig({
		resolve: {
			conditions: ['browser']
		},
		test: {
			environment: 'jsdom',
			setupFiles: ['./vitest-setup-client.ts'],
			include: ['src/**/*.{test,spec}.{js,ts}'],
			globals: false
		}
	})
);
