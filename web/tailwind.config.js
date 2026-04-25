/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // warm parchment surface
        paper: {
          50: "#fbfaf6",
          100: "#f5f2ea",
          200: "#ece7d9",
          300: "#ddd5c1",
          400: "#b8ad94",
          500: "#8e836b",
          600: "#6e6552",
          700: "#534b3d",
          800: "#3a3429",
          900: "#221f18",
        },
        // deep civic teal — used sparingly for primary actions / selection
        accent: {
          50: "#eef4f4",
          100: "#dae8e8",
          200: "#b6d2d2",
          300: "#8cb4b4",
          400: "#5e8e8e",
          500: "#3a6f6f",
          600: "#2a5757",
          700: "#1f4242",
          800: "#163131",
          900: "#0e2020",
        },
        // severity — informational, not alarming
        sev: {
          critical: "#9b4a3a", // terracotta
          high: "#b07636",     // burnt amber
          medium: "#b4943f",   // ochre
          low: "#6a8957",      // sage
        },
      },
      fontFamily: {
        display: ['"Fraunces"', "ui-serif", "Georgia", "serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        meta: ["11px", { lineHeight: "16px", letterSpacing: "0.02em" }],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "10px",
        xl: "14px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(34, 31, 24, 0.04)",
        card: "0 2px 8px rgba(34, 31, 24, 0.06)",
        modal: "0 12px 32px rgba(34, 31, 24, 0.12)",
      },
    },
  },
  plugins: [],
};
