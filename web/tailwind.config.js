/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Geist"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"Geist Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      colors: {
        anvil: { black: "#2b2d30", steel: "#4a4d52", floor: "#363839" },
        forge: { ember: "#c2662d", floor: "#363839", deep: "#7a3d1e" },
        ember: { DEFAULT: "#c2662d", heated: "#e8956a", cooling: "#f5c4a1" },
        linen: { DEFAULT: "#f0f0ec", off: "#f5f5f2", bench: "#e5e5e0" },
      },
    },
  },
  plugins: [],
};
