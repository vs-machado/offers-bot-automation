import { getSession } from "@/lib/auth-session";
import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl =
  process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

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
  headers.delete("content-length");

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
    redirect: "manual",
  });

  return response;
}

async function handler(request: NextRequest, context: RouteContext) {
  const session = await getSession(request.headers);
  if (!session) {
    return NextResponse.json({ detail: "Sua sessão expirou. Entre novamente." }, { status: 401 });
  }
  const response = await proxyToBackend(request, context, session.sessionToken);

  if (response.status === 401) {
    return NextResponse.json(
      { detail: "Sua sessão expirou. Entre novamente." },
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
