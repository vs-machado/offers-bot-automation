import { NextResponse } from "next/server";

const apiBaseUrl =
  process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export async function POST(request: Request) {
  const body = await request.json();

  const response = await fetch(`${apiBaseUrl}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const data = await response.json().catch(() => null);

  return NextResponse.json(data, { status: response.status });
}
