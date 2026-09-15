import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        /* Primary — DSE 必勝藍 */
        primary: {
          DEFAULT: "#2563eb",
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#2563eb",
          600: "#1d4ed8",
          700: "#1e40af",
          800: "#1e3a8a",
          900: "#172554",
        },
        /* Secondary — 智能科技紫 */
        secondary: {
          DEFAULT: "#6d28d9",
          50: "#f5f3ff",
          100: "#ede9fe",
          200: "#ddd6fe",
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#6d28d9",
          700: "#5b21b6",
          800: "#4c1d95",
          900: "#3b0764",
        },
        /* Accent — 弱項/警示 */
        accent: {
          red: "#ef4444",
          amber: "#f59e0b",
        },
        /* Surface — Dark Mode Zinc palette */
        surface: {
          DEFAULT: "#09090b",
          card: "#18181b",
          elevated: "#27272a",
          border: "#3f3f46",
        },
      },
      backgroundImage: {
        "gradient-primary": "linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%)",
        "gradient-ai": "linear-gradient(135deg, #6d28d9 0%, #2563eb 100%)",
        "gradient-hero": "radial-gradient(ellipse at 50% 0%, rgba(37,99,235,0.15) 0%, transparent 60%)",
      },
      fontFamily: {
        sans: ["Inter", "Noto Sans TC", "system-ui", "sans-serif"],
        display: ["Inter", "Noto Sans TC", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0, 0, 0, 0.37)",
        "glass-hover": "0 12px 40px rgba(37, 99, 235, 0.2)",
        card: "0 4px 24px rgba(0, 0, 0, 0.4)",
      },
      animation: {
        shimmer: "shimmer 2s infinite linear",
        "cursor-blink": "blink 1s step-end infinite",
        "fade-in": "fadeIn 0.4s ease-out",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
