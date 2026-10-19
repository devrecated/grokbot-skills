// Minimal Discord integration Worker. Placeholders only; configure via env/secrets.
// Secrets: DISCORD_BOT_TOKEN, DISCORD_PUBLIC_KEY, INGEST_SECRET (wrangler secret put ...)
export interface Env {
  DISCORD_BOT_TOKEN: string;
  DISCORD_PUBLIC_KEY: string;
  INGEST_SECRET: string;
  ROUTES: string;            // JSON: {"github":"<CHANNEL_ID>","ci":"<CHANNEL_ID>",...}
  AI_ALLOWED_CHANNELS: string; // JSON: ["<CHANNEL_ID>"]
  BOT_USER_ID: string;       // <BOT_USER_ID>
  SEEN: KVNamespace;         // idempotency store
}

type Stream = "github" | "deploys" | "ci" | "releases" | "sales" | "goals" | "leaderboard" | "meetings" | "visits";
interface Payload { id: string; stream: Stream; title: string; body?: string; url?: string; status?: string; source?: string; occurredAt: string; }

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function isPayload(x: any): x is Payload {
  return x && typeof x.id === "string" && typeof x.stream === "string" && typeof x.title === "string" && typeof x.occurredAt === "string";
}

/** Rule: forward to the AI bot only from allow-listed channels AND with an explicit @mention. */
export function shouldForward(msg: { channelId: string; content: string; authorIsBot: boolean; webhookId?: string }, env: Env): boolean {
  if (msg.authorIsBot || msg.webhookId) return false;
  const allowed: string[] = JSON.parse(env.AI_ALLOWED_CHANNELS || "[]");
  if (!allowed.includes(msg.channelId)) return false;
  return new RegExp(`<@!?${env.BOT_USER_ID}>`).test(msg.content);
}

async function postToChannel(env: Env, channelId: string, p: Payload): Promise<Response> {
  const colors: Record<string, number> = { success: 0x2ecc71, failure: 0xe74c3c, pending: 0xf1c40f, info: 0x3498db };
  return fetch(`https://discord.com/api/v10/channels/${channelId}/messages`, {
    method: "POST",
    headers: { authorization: `Bot ${env.DISCORD_BOT_TOKEN}`, "content-type": "application/json" },
    body: JSON.stringify({
      embeds: [{ title: p.title.slice(0, 256), description: p.body?.slice(0, 4000), url: p.url,
        color: colors[p.status ?? "info"], footer: p.source ? { text: `source: ${p.source}` } : undefined, timestamp: p.occurredAt }],
      allowed_mentions: { parse: [] },
    }),
  });
}

async function ingest(req: Request, env: Env): Promise<Response> {
  const auth = req.headers.get("authorization") ?? "";
  if (!safeEqual(auth, `Bearer ${env.INGEST_SECRET}`)) return json({ error: "unauthorized" }, 401);
  const body = await req.json().catch(() => null);
  if (!isPayload(body)) return json({ error: "invalid payload" }, 400);
  const routes: Record<string, string> = JSON.parse(env.ROUTES || "{}");
  const channelId = routes[body.stream];
  if (!channelId) return json({ error: `unknown stream ${body.stream}` }, 400);
  const key = `seen:${body.stream}:${body.id}`;
  if (await env.SEEN.get(key)) return json({ ok: true, duplicate: true });
  const res = await postToChannel(env, channelId, body);
  if (res.status === 404) return json({ error: "channel not found (dead channel ID?)" }, 502);
  if (!res.ok) return json({ error: `discord ${res.status}` }, 502);
  await env.SEEN.put(key, "1", { expirationTtl: 60 * 60 * 24 * 7 });
  return json({ ok: true });
}

function hexToBytes(hex: string): Uint8Array {
  return new Uint8Array((hex.match(/.{2}/g) ?? []).map((h) => parseInt(h, 16)));
}

async function verifyDiscord(req: Request, env: Env, raw: string): Promise<boolean> {
  const sig = req.headers.get("x-signature-ed25519");
  const ts = req.headers.get("x-signature-timestamp");
  if (!sig || !ts) return false;
  const key = await crypto.subtle.importKey("raw", hexToBytes(env.DISCORD_PUBLIC_KEY), { name: "Ed25519" }, false, ["verify"]);
  return crypto.subtle.verify("Ed25519", key, hexToBytes(sig), new TextEncoder().encode(ts + raw));
}

async function interactions(req: Request, env: Env): Promise<Response> {
  const raw = await req.text();
  if (!(await verifyDiscord(req, env, raw))) return new Response("bad signature", { status: 401 });
  const i = JSON.parse(raw);
  if (i.type === 1) return json({ type: 1 }); // PING
  if (i.type === 2 && i.data?.name === "status") {
    // Dependent command: fail gracefully instead of erroring.
    const up = await fetch("https://<GATEWAY_HOST>/health").then((r) => r.ok).catch(() => false);
    return json({ type: 4, data: { content: up ? "gateway online" : "gateway offline, try again later", flags: 64 } });
  }
  return json({ type: 4, data: { content: "unknown command", flags: 64 } });
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(req.url);
    if (req.method === "POST" && pathname.startsWith("/ingest")) return ingest(req, env);
    if (req.method === "POST" && pathname === "/interactions") return interactions(req, env);
    if (pathname === "/health") return json({ ok: true });
    return json({ error: "not found" }, 404);
  },
};
