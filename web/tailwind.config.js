/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        cinema: {
          bg: "#0B0B0D",
          card: "#16161A",
          cardHover: "#1E1E24",
          border: "#2A2A30",
          borderFocus: "#E8B86D",
          text: "#E8E8EA",
          muted: "#8A8A93",
          darker: "#060608",
        },
        amber: {
          cta: "#E8B86D",
          ctaHover: "#F0C885",
          glow: "rgba(232, 184, 109, 0.25)",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Noto Sans TC"',
          '"Microsoft JhengHei"',
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
