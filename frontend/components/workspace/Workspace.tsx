import "server-only";
import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth-session";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

export async function Workspace({ children }: { children: ReactNode }) {
  const session = await getSession();
  if (!session?.sessionToken) redirect("/");
  const apiBaseUrl =
    process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  const response = await fetch(`${apiBaseUrl}/users/me`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${session.sessionToken}` },
  });
  if (response.status === 401) redirect("/");
  if (!response.ok)
    throw new Error("Não foi possível carregar sua conta. Tente novamente.");
  const user = (await response.json()) as {
    email: string;
    full_name: string | null;
    role: string;
  };
  const userEmail = user.email || session.user?.email || "Conta conectada";
  return (
    <WorkspaceShell
      userEmail={userEmail}
      userName={user.full_name?.trim() || session.user?.name || userEmail}
      isAdmin={user.role === "admin"}
    >
      {children}
    </WorkspaceShell>
  );
}
