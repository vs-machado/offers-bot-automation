"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";

const subscribe = () => () => {};
const getClientSnapshot = () => true;
const getServerSnapshot = () => false;

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    subscribe,
    getClientSnapshot,
    getServerSnapshot
  );

  const isDark = resolvedTheme !== "light";

  return (
    <Button
      className="size-9 border-transparent bg-transparent p-0 text-muted-foreground shadow-none hover:bg-accent hover:text-foreground"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      suppressHydrationWarning
      type="button"
      variant="outline"
    >
      {mounted ? (
        isDark ? (
          <Sun className="size-4" />
        ) : (
          <Moon className="size-4" />
        )
      ) : (
        <span aria-hidden="true" className="size-4" />
      )}
    </Button>
  );
}
