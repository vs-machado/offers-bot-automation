import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { authOptions } from "@/auth";
import { Login } from "@/features/auth/Login";

export default async function Home({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const session = await getServerSession(authOptions);

  if (session) {
    redirect("/dashboard");
  }

  const { error } = await searchParams;
  return <Login errorCode={error} />;
}
