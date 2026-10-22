"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { workspaceNavigation } from "@/lib/workspace-navigation";
import { cn } from "@/lib/utils";

export function WorkspaceNavigation({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <nav aria-label="Seções do painel" className="space-y-1">
      {workspaceNavigation.map(({ icon: Icon, ...item }) => {
        const active = pathname === item.href;
        const className = cn(
          "flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none",
          active
            ? "bg-sidebar-primary/15 font-semibold text-primary inset-ring-1 inset-ring-sidebar-primary/30 dark:text-sidebar-primary"
            : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        );
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={className}
          >
            <Icon aria-hidden="true" className="size-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
