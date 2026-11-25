"use client";

import { Dialog } from "@base-ui/react/dialog";
import { Menu, X } from "lucide-react";
import Image from "next/image";
import { useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { LogoutButton } from "@/components/workspace/LogoutButton";
import { WorkspaceNavigation } from "@/components/workspace/WorkspaceNavigation";

type MobileSidebarProps = {
  userEmail: string;
  userInitial: string;
  userName: string;
  isAdmin: boolean;
};

export function MobileSidebar({
  userEmail,
  userInitial,
  userName,
  isAdmin,
}: MobileSidebarProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger
        render={
          <Button
            variant="ghost"
            className="size-11 motion-reduce:transition-none"
            aria-label="Abrir menu"
          />
        }
      >
        <Menu aria-hidden="true" className="size-5" />
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-40 bg-foreground/40" />
        <Dialog.Popup className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[calc(100vw-2rem)] flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground outline-none">
          <div className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-sidebar-border px-4">
            <Dialog.Title className="flex items-center gap-3 font-semibold tracking-tight">
              <Image src="/vsm_ofertas.jpeg" alt="VSM Ofertas" width={32} height={32} className="size-8 rounded-lg" />
              Offers Bot
            </Dialog.Title>
            <Dialog.Close
              render={
                <Button
                  variant="ghost"
                  className="size-11 motion-reduce:transition-none"
                  aria-label="Fechar menu"
                />
              }
            >
              <X aria-hidden="true" className="size-5" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">
            Navegue entre o painel, destinos, afiliados e configurações.
          </Dialog.Description>
          <div className="flex-1 space-y-1 overflow-y-auto p-3">
            <WorkspaceNavigation onNavigate={() => setIsOpen(false)} />
            {isAdmin ? (
              <div className="mt-4"><WorkspaceNavigation admin onNavigate={() => setIsOpen(false)} /></div>
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
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
