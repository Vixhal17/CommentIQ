/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        subtle: "var(--subtle)",
        surface: "var(--surface)",
        "surface-hover": "var(--surface-hover)",
        "surface-active": "var(--surface-active)",
        "surface-elevated": "var(--surface-elevated)",

        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        "border-focus": "var(--border-focus)",

        primary: "var(--text-primary)",
        secondary: "var(--text-secondary)",
        muted: "var(--text-muted)",
        faint: "var(--text-faint)",

        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          subtle: "var(--accent-subtle)",
        },

        status: {
          auto: "var(--status-auto)",
          draft: "var(--status-draft)",
          escalate: "var(--status-escalate)",
          sensitive: "var(--status-sensitive)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(0, 0, 0, 0.4)",
        elevated: "0 4px 20px -2px rgba(0, 0, 0, 0.5), 0 0 0 1px var(--border)",
        drawer: "-12px 0 36px 0 rgba(0, 0, 0, 0.7), -1px 0 0 0 var(--border)",
        floating: "0 12px 32px -4px rgba(0, 0, 0, 0.65), 0 0 0 1px var(--border-strong)",
      },
      transitionTimingFunction: {
        "spring-subtle": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};


