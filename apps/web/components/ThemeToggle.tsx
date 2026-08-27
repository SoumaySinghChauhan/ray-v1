"use client";

import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

type Theme = "dark" | "light";

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("ray-theme", theme);
  } catch {
    // localStorage unavailable (private mode, etc) — theme just won't persist.
  }
}

/** Light/dark toggle. Reads the theme the anti-flash script already applied, so it never mismatches on mount. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
    });
    return () => cancelAnimationFrame(id);
  }, []);

  const toggle = () => {
    const next: Theme = theme === "light" ? "dark" : "light";
    applyTheme(next);
    setTheme(next);
  };

  return (
    <button
      onClick={toggle}
      aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
      className="t-fast relative w-8 h-8 flex items-center justify-center border border-separator text-ink-2 hover:text-ink hover:bg-surface-2 rounded-sm"
    >
      {theme === null ? (
        <span className="w-3.5 h-3.5" aria-hidden="true" />
      ) : theme === "light" ? (
        <Sun size={14} strokeWidth={1.75} className="anim-fade" />
      ) : (
        <Moon size={14} strokeWidth={1.75} className="anim-fade" />
      )}
    </button>
  );
}
