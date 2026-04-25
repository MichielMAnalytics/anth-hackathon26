/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b0d10",
          900: "#11141a",
          800: "#1a1e26",
          700: "#272d38",
          600: "#3a4150",
          500: "#5a6473",
          400: "#8a93a3",
          300: "#b6bcc7",
          200: "#d4d8df",
          100: "#eceef2",
        },
        sev: {
          critical: "#dc2626",
          high: "#ea7c1c",
          medium: "#d6a92a",
          low: "#5b9c6e",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
