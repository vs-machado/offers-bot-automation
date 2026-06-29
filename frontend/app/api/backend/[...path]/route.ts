import { getToken } from "next-auth/jwt";
import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl =
  process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

async function exchangeGoogleSession(token: {
  email?: string | null;
  name?: string | null;
  provider?: string;
  providerAccountId?: string;
}) {
  if (
    token.provider !== "google" ||
    !token.email ||
    !token.providerAccountId ||
    !process.env.NEXTAUTH_BACKEND_SECRET
  ) {
    return null;
  }

  const response = await fetch(`${apiBaseUrl}/auth/session/exchange`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: token.email,
      provider: token.provider,
      provider_account_id: token.providerAccountId,
      full_name: token.name ?? null,
      secret: process.env.NEXTAUTH_BACKEND_SECRET,
    }),
  });

  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as { access_token?: string };
  return data.access_token ?? null;
}

async function proxyToBackend(
  request: NextRequest,
  context: RouteContext,
  accessToken: string,
) {
  const { path = [] } = await context.params;
  const incomingUrl = new URL(request.url);
  const targetUrl = `${apiBaseUrl}/${path.join("/")}${incomingUrl.search}`;
  const headers = new Headers(request.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  headers.delete("host");
  headers.delete("cookie");

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
  });

  return response;
}

async function handler(request: NextRequest, context: RouteContext) {
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });
  const accessToken = token?.accessToken;
  if (typeof accessToken !== "string") {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  let response = await proxyToBackend(request, context, accessToken);
  if (response.status === 401) {
    const refreshedToken = token ? await exchangeGoogleSession(token) : null;
    if (refreshedToken) {
      response = await proxyToBackend(request, context, refreshedToken);
    }
  }

  if (response.status === 401) {
    return NextResponse.json(
      { detail: "FastAPI session expired. Sign in again." },
      { status: 401 },
    );
  }

  return new NextResponse(response.body, {
    status: response.status,
    headers: response.headers,
  });
}

export {
  handler as DELETE,
  handler as GET,
  handler as PATCH,
  handler as POST,
  handler as PUT,
};
