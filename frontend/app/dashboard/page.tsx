import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { authOptions } from "@/auth";

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/");
  }

  return (
    <main className="min-h-[100dvh] bg-slate-950 px-6 py-10 text-white">
      <section className="mx-auto max-w-4xl rounded-[2rem] border border-white/10 bg-white/5 p-8">
        <p className="text-sm font-medium text-emerald-200">Signed in</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          Welcome to Offers Bot
        </h1>
        <p className="mt-4 text-slate-300">
          Session ready for {session.user?.email}. Dashboard features can use
          server routes to attach the stored FastAPI access token.
        </p>
      </section>
    </main>
  );
}
