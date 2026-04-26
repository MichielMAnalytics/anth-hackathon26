/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Clean cool-gray surface system. Pure white cards on near-white app bg.
        surface: {
          DEFAULT: "#ffffff",
          50: "#ffffff",
          100: "#fafafa", // app background
          200: "#f4f4f5", // subtle fills
          300: "#e8e8eb", // hairline borders
          400: "#c8c8cc",
          500: "#9a9a9f",
          600: "#6e6e74",
          700: "#46464b",
          800: "#272729",
          900: "#171718",
        },
        ink: {
          DEFAULT: "#0a0a0b",
          50: "#fafafa",
          100: "#f4f4f5",
          400: "#a1a1a6",
          500: "#73737a",
          600: "#52525a",
          700: "#3a3a40",
          800: "#1d1d20",
          900: "#0a0a0b",
          950: "#050506",
        },
        // War Child red — primary brand (preserved)
        brand: {
          50: "#fff1f1",
          100: "#ffdfdf",
          200: "#ffc4c4",
          300: "#ff9b9b",
          400: "#fa6464",
          500: "#ee3535",
          600: "#e62e2e",
          700: "#c11f1f",
          800: "#9d1d1d",
          900: "#811d1d",
        },
        // Severity — flat, restrained.
        sev: {
          critical: "#dc2626", // red-600 — only on chips, never as backgrounds
          high: "#b45309", // amber-700
          medium: "#a16207", // yellow-700
          low: "#16a34a", // green-600
        },
      },
      fontFamily: {
        // Inter Tight for display (tighter, more editorial), Inter for body.
        display: ['"Inter Tight"', '"Inter"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        meta: ["10.5px", { lineHeight: "16px", letterSpacing: "0.12em" }],
      },
      letterSpacing: {
        tightest: "-0.04em",
        tighter: "-0.025em",
      },
      borderRadius: {
        sm: "3px",
        DEFAULT: "5px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(10, 10, 11, 0.04)",
        card: "0 1px 0 rgba(10, 10, 11, 0.03)",
        modal: "0 20px 50px -12px rgba(10, 10, 11, 0.25)",
      },
      keyframes: {
        "fade-rise": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.45", transform: "scale(0.85)" },
        },
      },
      animation: {
        "fade-rise": "fade-rise 0.5s cubic-bezier(0.2, 0.6, 0.2, 1) both",
        "pulse-dot": "pulse-dot 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
