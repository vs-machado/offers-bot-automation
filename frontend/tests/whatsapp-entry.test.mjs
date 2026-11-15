import { before, after, test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";

const publicId = "31c6f27a-85dd-47a5-a74b-2c225430acb0";
const invite = "https://chat.whatsapp.com/ABCDEFGHIJKLMNOPQRSTUV";
let upstream;
let app;
let origin;
let requestSeen;
let responseStatus = 302;
let responseLocation = invite;
let output = "";

before(async () => {
  upstream = createServer((request, response) => {
    requestSeen = { url: request.url, method: request.method, headers: request.headers };
    response.writeHead(responseStatus, { Location: responseLocation });
    response.end("private-upstream-detail");
  });
  await new Promise(resolve => upstream.listen(0, "127.0.0.1", resolve));
  const probe = createServer();
  await new Promise(resolve => probe.listen(0, "127.0.0.1", resolve));
  const port = probe.address().port;
  await new Promise(resolve => probe.close(resolve));
  origin = `http://127.0.0.1:${port}`;
  app = spawn(process.execPath, ["node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1", "--port", String(port)], {
    detached: true, stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, API_BASE_URL: `http://127.0.0.1:${upstream.address().port}`, NEXT_TELEMETRY_DISABLED: "1" },
  });
  app.stdout.on("data", chunk => { output += chunk; });
  app.stderr.on("data", chunk => { output += chunk; });
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      if ((await fetch(`${origin}/join/whatsapp/${publicId}`, { redirect: "manual" })).status === 302) return;
    } catch { /* Server warming up. */ }
    if (app.exitCode !== null) throw new Error(output);
    await new Promise(resolve => setTimeout(resolve, 300));
  }
  throw new Error(output);
});

after(async () => {
  if (app?.pid) {
    try { process.kill(-app.pid, "SIGTERM"); } catch { /* Already stopped. */ }
    await new Promise(resolve => app.exitCode === null ? app.once("exit", resolve) : resolve());
  }
  if (upstream?.listening) await new Promise(resolve => upstream.close(resolve));
});

test("public GET and HEAD preserve 302 without forwarding visitor credentials or query", async () => {
  for (const method of ["GET", "HEAD"]) {
    const response = await fetch(`${origin}/join/whatsapp/${publicId}?url=https://evil.example`, {
      method, redirect: "manual", headers: { Authorization: "Bearer visitor-secret", Cookie: "visitor=private" },
    });
    assert.equal(response.status, 302);
    assert.equal(response.headers.get("location"), invite);
    assert.match(response.headers.get("cache-control"), /no-store/);
    assert.equal(await response.text(), "");
    assert.equal(requestSeen.url, `/public/whatsapp/${publicId}`);
    assert.equal(requestSeen.method, method);
    assert.equal(requestSeen.headers.authorization, undefined);
    assert.equal(requestSeen.headers.cookie, undefined);
  }
});

test("invalid targets and upstream failures return a sanitized no-store unavailable page", async () => {
  for (const [status, location] of [[302, "https://evil.example"], [500, invite], [503, invite]]) {
    responseStatus = status;
    responseLocation = location;
    for (const method of ["GET", "HEAD"]) {
      const response = await fetch(`${origin}/join/whatsapp/${publicId}`, { method, redirect: "manual" });
      assert.equal(response.status, 503);
      assert.match(response.headers.get("cache-control"), /no-store/);
      assert.equal(response.headers.get("location"), null);
      const text = await response.text();
      assert.ok(!text.includes("private-upstream-detail"));
      if (method === "HEAD") assert.equal(text, "");
    }
  }
  requestSeen = null;
  assert.equal((await fetch(`${origin}/join/whatsapp/invalid`)).status, 503);
  assert.equal(requestSeen, null);
});

test("backend outage does not require login or expose a raw network error", async () => {
  await new Promise(resolve => upstream.close(resolve));
  const response = await fetch(`${origin}/join/whatsapp/${publicId}`);
  assert.equal(response.status, 503);
  assert.match(await response.text(), /Estamos preparando/);
});
