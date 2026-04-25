/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // surface / neutral system: white surfaces, deep navy text
        surface: {
          DEFAULT: "#ffffff",
          50: "#ffffff",
          100: "#f8fafc",
          200: "#eef2f6",
          300: "#e2e8f0",
          400: "#cbd5e1",
          500: "#94a3b8",
          600: "#64748b",
          700: "#475569",
          800: "#334155",
          900: "#1e293b",
        },
        ink: {
          DEFAULT: "#0f172a",
          50: "#f8fafc",
          100: "#f1f5f9",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
          950: "#0a0f1d",
        },
        // War Child red — primary brand
        brand: {
          50: "#fff1f1",
          100: "#ffdfdf",
          200: "#ffc4c4",
          300: "#ff9b9b",
          400: "#fa6464",
          500: "#ee3535",
          600: "#e62e2e", // primary
          700: "#c11f1f",
          800: "#9d1d1d",
          900: "#811d1d",
        },
        // severity — calmer than v1 dark theme; reads as informational
        sev: {
          critical: "#c11f1f", // brand-700, but only on chips not full surfaces
          high: "#b07636",     // burnt amber
          medium: "#a17e2e",   // ochre
          low: "#3f7d4f",      // forest green
        },
      },
      fontFamily: {
        // Inter for UI body, Inter Tight (or Inter heavier weights) for display
        display: ['"Inter"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        meta: ["11px", { lineHeight: "16px", letterSpacing: "0.04em" }],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15, 23, 42, 0.04)",
        card: "0 2px 8px rgba(15, 23, 42, 0.06)",
        modal: "0 16px 40px rgba(15, 23, 42, 0.16)",
      },
    },
  },
  plugins: [],
};
