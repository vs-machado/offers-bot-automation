"use client";

import { LogOut } from "lucide-react";
import { signOut } from "next-auth/react";

import { Button } from "@/components/ui/button";

type LogoutButtonProps = {
  compact?: boolean;
};

export function LogoutButton({ compact = false }: LogoutButtonProps) {
  return (
    <Button
      aria-label={compact ? "Sair" : undefined}
      className={
        compact
          ? "size-9 border-transparent bg-transparent p-0 text-muted-foreground shadow-none hover:bg-red-500/8 hover:text-red-700 dark:hover:text-red-200"
          : "h-11 w-full justify-start gap-3 border-transparent bg-transparent text-sm font-medium text-muted-foreground hover:bg-red-500/8 hover:text-red-700 dark:text-slate-400 dark:hover:text-red-200"
      }
      onClick={() => signOut({ callbackUrl: "/" })}
      type="button"
      variant="outline"
    >
      <LogOut className="size-4" strokeWidth={1.8} />
      {compact ? null : <span>Sair</span>}
    </Button>
  );
}
