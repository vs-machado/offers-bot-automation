"use client";

import { LogOut } from "lucide-react";
import { signOut } from "next-auth/react";

import { Button } from "@/components/ui/button";

export function LogoutButton() {
  return (
    <Button
      className="h-11 w-full justify-start gap-3 border-transparent bg-transparent text-sm font-medium text-muted-foreground hover:bg-red-500/[0.08] hover:text-red-700 dark:text-slate-400 dark:hover:text-red-200"
      onClick={() => signOut({ callbackUrl: "/" })}
      type="button"
      variant="outline"
    >
      <LogOut className="size-4" strokeWidth={1.8} />
      <span>Logout</span>
    </Button>
  );
}
