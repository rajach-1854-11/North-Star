import { defineConfig } from "vitest/config.js";
import path from "path";

export default defineConfig({
	resolve: {
		alias: {
			"@": path.resolve(__dirname)
		}
	},
	test: {
		environment: "jsdom",
			include: ["tests/**/*.test.ts"],
			env: {
				NEXT_PUBLIC_API_BASE: "http://localhost:8000"
			}
	}
});
