import "server-only";

type Context = { params: Promise<{ deliveryId: string }> };

export async function GET(_request: Request, { params }: Context) {
  const { deliveryId } = await params;
  if (!/^[0-9a-f]{64}$/.test(deliveryId)) return new Response(null, { status: 404 });
  const base = process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  try {
    const response = await fetch(`${base}/public/storefront/images/${deliveryId}`, {
      cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(5000),
    });
    if (response.ok && response.headers.get("Content-Type") === "image/webp") {
      return new Response(response.body, { headers: {
        "Content-Type": "image/webp",
        "Cache-Control": "public, max-age=300",
        "X-Content-Type-Options": "nosniff",
      } });
    }
    await response.body?.cancel();
    if (response.status === 404) return new Response(null, { status: 404 });
  } catch { /* Return a controlled error for upstream failures. */ }
  return new Response(null, { status: 502 });
}
