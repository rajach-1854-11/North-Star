import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        deep: "#0D1117",
        panel: "#161B22",
        action: "#3B82F6",
        text: "#E5E7EB",
        meta: "#9CA3AF",
        subtlePurple: "#8B5CF6",
        mutedTeal: "#14B8A6"
      },
      borderRadius: { "2xl": "1rem" },
      boxShadow: {
        soft: "0 10px 40px rgba(0,0,0,0.35)",
        lift: "0 20px 60px rgba(0,0,0,0.45)"
      },
      fontFamily: {
        inter: ["var(--font-inter)"],
        lexend: ["var(--font-lexend)"],
        jet: ["var(--font-jetbrains)"]
      }
    }
  },
  plugins: []
};
export default config;
