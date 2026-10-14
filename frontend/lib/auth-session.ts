import "server-only";
import { headers } from "next/headers";
import { getAuth } from "@/auth";

export async function getSession(requestHeaders?: Headers) {
  const request = requestHeaders ?? await headers();
  const session = await getAuth().api.getSession({ headers: request, query: { disableCookieCache: true } });
  return session ? { ...session, sessionToken: session.session.token } : null;
}
