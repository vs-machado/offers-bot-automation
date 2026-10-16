"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { workspaceNavigation } from "@/lib/workspace-navigation";
import { cn } from "@/lib/utils";

function subscribe(listener: () => void) {
  window.addEventListener("hashchange", listener);
  window.addEventListener("popstate", listener);
  return () => {
    window.removeEventListener("hashchange", listener);
    window.removeEventListener("popstate", listener);
  };
}

export function WorkspaceNavigation({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const hash = useSyncExternalStore(
    subscribe,
    () => window.location.hash,
    () => "",
  );
  const activeHref =
    pathname === "/settings" && ["#destinations", "#affiliates"].includes(hash)
      ? `${pathname}${hash}`
      : pathname;
  return (
    <nav aria-label="Seções do painel" className="space-y-1">
      {workspaceNavigation.map(({ icon: Icon, ...item }) => {
        const active = activeHref === item.href;
        const className = cn(
          "flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none",
          active
            ? "bg-sidebar-accent font-semibold text-sidebar-accent-foreground"
            : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        );
        const content = (
          <>
            <Icon aria-hidden="true" className="size-4" />
            {item.label}
          </>
        );
        return item.href.startsWith(`${pathname}#`) ? (
          <a
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "location" : undefined}
            className={className}
          >
            {content}
          </a>
        ) : (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={className}
          >
            {content}
          </Link>
        );
      })}
    </nav>
  );
}
