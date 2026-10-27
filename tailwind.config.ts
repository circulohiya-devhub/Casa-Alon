import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#122321",
        tide: "#1F3A3D",
        sand: "#EFE6D8",
        foam: "#FAF6EE",
        seafoam: "#7FA996",
        gold: "#C9962C",
      },
      fontFamily: {
        display: ["var(--font-fraunces)", "ui-serif", "Georgia", "serif"],
        body: ["var(--font-work-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      maxWidth: {
        measure: "68ch",
      },
    },
  },
  plugins: [],
};

export default config;
