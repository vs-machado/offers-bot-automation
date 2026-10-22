"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ThemeToggle } from "@/components/theme-toggle";
import { LogoutButton } from "@/components/workspace/LogoutButton";
import { MobileSidebar } from "@/components/workspace/MobileSidebar";
import { WorkspaceNavigation } from "@/components/workspace/WorkspaceNavigation";
import { cn } from "@/lib/utils";
import { workspaceNavigation } from "@/lib/workspace-navigation";

type WorkspaceShellProps = {
  userName: string;
  userEmail: string;
  isAdmin: boolean;
  children: ReactNode;
};

export function WorkspaceShell({
  userName,
  userEmail,
  isAdmin,
  children,
}: WorkspaceShellProps) {
  const userInitial = userName.trim().charAt(0).toUpperCase() || "U";
  const pathname = usePathname();
  const isDashboard = pathname === "/dashboard";
  const isAdminPage = pathname.startsWith("/admin");
  const pageTitle = isDashboard
    ? "Visão geral"
    : isAdminPage
      ? "Administração"
      : workspaceNavigation.find((item) => item.href === pathname)?.label ??
        "Configurações";

  return (
    <div className="relative h-dvh overflow-hidden bg-background text-foreground">
      <a
        href="#dashboard-content"
        className="sr-only z-50 rounded-lg bg-primary px-4 py-3 text-primary-foreground focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Pular para o conteúdo
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground lg:flex">
        <Link
          href="/dashboard"
          className="flex h-16 shrink-0 items-center gap-3 border-b border-sidebar-border px-6 font-semibold tracking-tight focus-visible:outline-2 focus-visible:outline-ring"
        >
          <Image src="/vsm_ofertas.jpeg" alt="VSM Ofertas" width={32} height={32} className="size-8 rounded-lg" />
          TG Offers Bot
        </Link>
        <div className="flex-1 overflow-y-auto p-3">
          <p className="px-3 pb-2 pt-4 text-xs font-medium text-muted-foreground">
            Workspace
          </p>
          <WorkspaceNavigation />
          {isAdmin ? (
            <Link
              href="/admin/source-groups"
              aria-current={isAdminPage ? "page" : undefined}
              className={cn(
                "mt-6 flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-2 focus-visible:outline-ring",
                isAdminPage
                  ? "bg-sidebar-accent font-semibold text-sidebar-accent-foreground"
                  : "text-muted-foreground",
              )}
            >
              <ShieldCheck aria-hidden="true" className="size-4" />
              Administração
            </Link>
          ) : null}
        </div>
        <div className="border-t border-sidebar-border p-4">
          <div className="mb-3 flex items-center gap-3">
            <Avatar className="size-9">
              <AvatarFallback className="bg-muted font-medium">
                {userInitial}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{userName}</p>
              <p className="truncate text-xs text-muted-foreground">
                {userEmail}
              </p>
            </div>
          </div>
          <LogoutButton />
        </div>
      </aside>
      <div className="flex h-full min-w-0 flex-col lg:pl-60">
        <header className="z-20 flex h-16 shrink-0 items-center justify-between gap-3 border-b bg-background px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="lg:hidden">
              <MobileSidebar
                userName={userName}
                userEmail={userEmail}
                userInitial={userInitial}
                isAdmin={isAdmin}
              />
            </div>
            <span className="truncate text-sm font-medium">
              Painel{" "}
              <span aria-hidden="true" className="mx-2 text-muted-foreground">
                /
              </span>{" "}
              <span className="text-muted-foreground">{pageTitle}</span>
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-2 [&_button]:min-h-11 [&_button]:min-w-11">
            <ThemeToggle />
          </div>
        </header>
        <main
          id="dashboard-content"
          key={pathname}
          className={cn(
            "min-h-0 flex-1 outline-none",
            isDashboard
              ? "flex overflow-hidden"
              : "overflow-y-auto overscroll-contain scrollbar-gutter-stable",
          )}
          tabIndex={-1}
        >
          <div
            className={cn(
              "mx-auto w-full max-w-360 px-4 py-6 sm:px-6 lg:p-8",
              isDashboard
                ? "flex min-h-0 flex-1 flex-col"
                : "space-y-6 [&_button]:min-h-11 [&_input:not([type=checkbox])]:min-h-11 [&_input:not([type=checkbox])]:text-base **:data-[slot=card]:shadow-none **:data-[slot=card]:ring-1 **:data-[slot=card]:ring-border",
            )}
          >
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
