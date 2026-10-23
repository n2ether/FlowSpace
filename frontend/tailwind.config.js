// FlowSpace palette from backend/design_plan_standards.py (BRAND_PALETTE + BRAND_TINTS),
// the same tokens the Design Plan board, Companion Guide and emails render with.
// The stock emerald / slate / sky / amber scales are remapped onto it so every
// page picks up the approved identity without per-class rewrites.
const brand = {
  green: "#2F5D50",
  sage: "#A8C3B0",
  off: "#F6F7F4",
  greige: "#E6E1DB",
  char: "#2B2B2B",
  sageLight: "#E4ECE6",
  sageLine: "#D3E0D6",
  greigeLight: "#F1EEE9",
  line: "#E2DED7",
  muted: "#5E625F",
  body: "#454845",
  clay: "#C08A6C",
  softBlue: "#8AA4B5",
};

const green = {
  50: "#F0F5F1",
  100: brand.sageLight,
  200: brand.sageLine,
  300: brand.sage,
  400: "#6F9483",
  500: brand.green,
  600: "#294F44",
  700: "#24463C",
  800: "#1E3A32",
  900: "#182F29",
  950: "#0F1F1B",
};

const neutral = {
  50: brand.off,
  100: brand.greigeLight,
  200: brand.line,
  300: "#CFC9C0",
  400: "#9F9A92",
  500: "#75726C",
  600: brand.muted,
  700: brand.body,
  800: "#363836",
  900: brand.char,
  950: "#1B1B1B",
};

const softBlue = {
  50: "#F1F5F7",
  100: "#E1E9EE",
  200: "#C9D7E0",
  300: "#AFC2CF",
  400: brand.softBlue,
  500: "#6F8B9D",
  600: "#5A7486",
  700: "#4A6070",
  800: "#3D4F5C",
  900: "#32414C",
  950: "#202A31",
};

const clay = {
  50: "#FAF4EF",
  100: "#F3E6DC",
  200: "#E8CFBD",
  300: "#D9B299",
  400: "#CB9C80",
  500: brand.clay,
  600: "#A5704F",
  700: "#895B40",
  800: "#6E4934",
  900: "#593B2A",
  950: "#39261B",
};

/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Montserrat", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"],
        display: ["Montserrat", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)'
      },
      colors: {
        brand,
        emerald: green,
        slate: neutral,
        sky: softBlue,
        amber: clay,
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chart: {
          '1': 'hsl(var(--chart-1))',
          '2': 'hsl(var(--chart-2))',
          '3': 'hsl(var(--chart-3))',
          '4': 'hsl(var(--chart-4))',
          '5': 'hsl(var(--chart-5))'
        }
      },
      keyframes: {
        'accordion-down': {
          from: {
            height: '0'
          },
          to: {
            height: 'var(--radix-accordion-content-height)'
          }
        },
        'accordion-up': {
          from: {
            height: 'var(--radix-accordion-content-height)'
          },
          to: {
            height: '0'
          }
        }
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out'
      }
    }
  },
  plugins: [require("tailwindcss-animate")],
};