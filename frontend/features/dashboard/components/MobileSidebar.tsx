"use client";

import {
  CalendarClock,
  FileText,
  Home,
  Link2,
  Menu,
  MessageSquareText,
  Send,
  Settings,
  UsersRound,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { LogoutButton } from "@/features/dashboard/components/LogoutButton";

const mobileSidebarItems: Array<{
  icon: LucideIcon;
  label: string;
  active?: boolean;
}> = [
  { icon: Home, label: "Início", active: true },
  { icon: MessageSquareText, label: "Mensagens" },
  { icon: CalendarClock, label: "Agendamentos" },
  { icon: UsersRound, label: "Grupos" },
  { icon: Link2, label: "Afiliados" },
  { icon: FileText, label: "Modelos de mensagem" },
  { icon: Settings, label: "Configurações" },
];

type MobileSidebarProps = {
  userEmail: string;
  userInitial: string;
  userName: string;
};

export function MobileSidebar({
  userEmail,
  userInitial,
  userName,
}: MobileSidebarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const previousOverflow = document.body.style.overflow;
    const trigger = triggerRef.current;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
      trigger?.focus();
    };
  }, [isOpen]);

  return (
    <>
      <Button
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-label="Abrir menu"
        className="size-9 border-transparent bg-transparent p-0 text-foreground shadow-none hover:bg-accent"
        onClick={() => setIsOpen(true)}
        ref={triggerRef}
        type="button"
        variant="outline"
      >
        <Menu className="size-5" />
      </Button>

      {isOpen
        ? createPortal(
            <div className="fixed inset-0 z-50 lg:hidden">
              <button
                aria-label="Fechar menu"
                className="animate-in fade-in absolute inset-0 bg-slate-950/55 backdrop-blur-[2px] duration-200 motion-reduce:animate-none"
                onClick={() => setIsOpen(false)}
                type="button"
              />
              <aside
                aria-label="Menu de navegação"
                aria-modal="true"
                className="animate-in slide-in-from-left relative flex h-full w-[min(84vw,320px)] flex-col border-r border-sidebar-border bg-sidebar p-4 text-sidebar-foreground shadow-2xl duration-300 ease-out motion-reduce:animate-none"
                role="dialog"
              >
                <div className="flex h-10 items-center justify-between gap-3 px-1">
                  <div className="flex items-center gap-2.5 text-sm font-bold tracking-tight">
                    <Send className="size-5 fill-sidebar-primary text-sidebar-primary" />
                    <span>TG OFFERS BOT</span>
                  </div>
                  <Button
                    aria-label="Fechar menu"
                    className="size-9 border-transparent bg-transparent p-0 shadow-none hover:bg-sidebar-accent"
                    onClick={() => setIsOpen(false)}
                    ref={closeButtonRef}
                    type="button"
                    variant="outline"
                  >
                    <X className="size-5" />
                  </Button>
                </div>

                <nav aria-label="Seções do painel" className="mt-5 space-y-1">
                  {mobileSidebarItems.map((item) => {
                    const Icon = item.icon;

                    return (
                      <Button
                        className={
                          item.active
                            ? "h-11 w-full justify-start gap-3 bg-sidebar-primary/10 text-sm font-semibold text-sidebar-primary shadow-none hover:bg-sidebar-primary/15"
                            : "h-11 w-full justify-start gap-3 border-transparent bg-transparent text-sm font-medium text-muted-foreground shadow-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                        }
                        key={item.label}
                        onClick={() => setIsOpen(false)}
                        type="button"
                        variant={item.active ? "default" : "outline"}
                      >
                        <Icon className="size-5" strokeWidth={1.9} />
                        <span>{item.label}</span>
                      </Button>
                    );
                  })}
                </nav>

                <div className="mt-auto">
                  <Separator className="my-4" />
                  <div className="flex items-center gap-3 px-1">
                    <Avatar className="size-10 bg-sidebar-primary/15">
                      <AvatarFallback className="bg-sidebar-primary/15 font-semibold text-sidebar-primary">
                        {userInitial}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{userName}</p>
                      <p className="truncate text-xs text-muted-foreground">{userEmail}</p>
                    </div>
                  </div>
                  <Separator className="my-4" />
                  <LogoutButton />
                </div>
              </aside>
            </div>,
            document.body
          )
        : null}
    </>
  );
}
