"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const baseClasses =
    "px-3 py-1.5 rounded-md text-sm font-medium transition-colors";

  return (
    <div className="flex gap-2">
      <button
        onClick={() => setTheme("light")}
        className={`${baseClasses} ${
          theme === "light"
            ? "bg-primary text-primary-foreground"
            : "bg-secondary text-secondary-foreground "
        }`}
      >
        Light
      </button>
      <button
        onClick={() => setTheme("dark")}
        className={`${baseClasses} ${
          theme === "dark"
            ? "bg-primary text-primary-foreground"
            : "bg-secondary text-secondary-foreground"
        }`}
      >
        Dark
      </button>
      <button
        onClick={() => setTheme("system")}
        className={`${baseClasses} ${
          theme === "system"
            ? "bg-primary text-primary-foreground"
            : "bg-secondary text-secondary-foreground "
        }`}
      >
        System
      </button>
    </div>
  );
}
