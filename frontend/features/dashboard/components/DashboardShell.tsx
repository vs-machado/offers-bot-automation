import type { ReactNode } from "react";
import { ArrowUpRight, Send, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { buttonVariants } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { LogoutButton } from "@/features/dashboard/components/LogoutButton";
import { MobileSidebar } from "@/features/dashboard/components/MobileSidebar";
import { dashboardNavigation } from "@/features/dashboard/lib/navigation";
import { cn } from "@/lib/utils";

type DashboardShellProps = {
  userName: string;
  userEmail: string;
  isAdmin: boolean;
  children: ReactNode;
};

export function DashboardShell({
  userName,
  userEmail,
  isAdmin,
  children,
}: DashboardShellProps) {
  const userInitial = userName.trim().charAt(0).toUpperCase() || "U";

  return (
    <div className="min-h-dvh bg-background text-foreground">
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
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Send aria-hidden="true" className="size-4" />
          </span>
          TG Offers Bot
        </Link>
        <div className="flex-1 overflow-y-auto p-3">
          <p className="px-3 pb-2 pt-4 text-xs font-medium text-muted-foreground">
            Workspace
          </p>
          <nav aria-label="Seções do painel" className="space-y-1">
            {dashboardNavigation.map(({ icon: Icon, ...item }) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={item.active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none",
                  item.active
                    ? "bg-sidebar-accent font-semibold text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                )}
              >
                <Icon aria-hidden="true" className="size-4" />
                {item.label}
                {item.active ? (
                  <span
                    aria-hidden="true"
                    className="ml-auto size-1.5 rounded-full bg-sidebar-primary"
                  />
                ) : null}
              </Link>
            ))}
          </nav>
          {isAdmin ? (
            <Link
              href="/admin/source-groups"
              className="mt-6 flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-2 focus-visible:outline-ring"
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
      <div className="min-w-0 lg:pl-60">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b bg-background px-4 sm:px-6 lg:px-8">
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
              <span className="text-muted-foreground">Visão geral</span>
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-2 [&_button]:min-h-11 [&_button]:min-w-11">
            <Link
              href="/settings"
              className={cn(
                buttonVariants({ variant: "ghost" }),
                "hidden min-h-11 gap-2 motion-reduce:transition-none sm:inline-flex",
              )}
            >
              Gerenciar automação{" "}
              <ArrowUpRight aria-hidden="true" className="size-4" />
            </Link>
            <ThemeToggle />
          </div>
        </header>
        <main
          id="dashboard-content"
          className="mx-auto max-w-360 px-4 py-6 sm:px-6 lg:p-8"
          tabIndex={-1}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
