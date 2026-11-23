// Tailwind v4 configuration using @tailwindcss/vite plugin
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./index.html"
  ],
  theme: {
    extend: {
      colors: {
        primary: "#2563EB", // blue-600
        secondary: "#10B981", // emerald-500
        accent: "#F59E0B" // amber-500
      }
    }
  },
  plugins: []
};