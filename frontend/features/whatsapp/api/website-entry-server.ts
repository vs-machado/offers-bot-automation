import "server-only";

const headers = { "Cache-Control": "no-store, max-age=0", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff" };
type Context = { params: Promise<{ publicId: string }> };

function unavailable(method: string) {
  return new Response(method === "HEAD" ? null : '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Grupo temporariamente indisponível</title><main><h1>Estamos preparando o próximo grupo</h1><p>Tente novamente em alguns instantes.</p></main></html>', {
    status: 503, headers: { ...headers, "Content-Type": "text/html; charset=utf-8", "Retry-After": "60", "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'" },
  });
}

async function enter(request: Request, context: Context) {
  const { publicId } = await context.params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(publicId)) return unavailable(request.method);
  const base = process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  try {
    // Public GET/HEAD only. No visitor credentials or query parameters reach the backend.
    const response = await fetch(`${base}/public/whatsapp/${publicId}`, {
      method: request.method, cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(5000),
    });
    const location = response.headers.get("Location");
    if (response.status === 302 && location && /^https:\/\/chat\.whatsapp\.com\/[A-Za-z0-9]{20,32}$/.test(location)) {
      await response.body?.cancel();
      return new Response(null, { status: 302, headers: { ...headers, Location: location } });
    }
    await response.body?.cancel();
  } catch { /* Connection errors return the same controlled unavailable page. */ }
  return unavailable(request.method);
}

export { enter as GET, enter as HEAD };
