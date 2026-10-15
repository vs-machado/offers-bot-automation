import { getSession } from "@/lib/auth-session";
import { redirect } from "next/navigation";

import { Login } from "@/features/auth/Login";
import { isPublicRegistrationDisabled } from "@/lib/registration-policy";

export default async function Home({ searchParams }: { searchParams: Promise<{ error?: string; mode?: string }> }) {
  const session = await getSession();

  if (session) {
    redirect("/dashboard");
  }

  const { error, mode } = await searchParams;
  return <Login errorCode={error} initialMode={isPublicRegistrationDisabled || mode === "signin" ? "signin" : "register"} registrationDisabled={isPublicRegistrationDisabled} />;
}
