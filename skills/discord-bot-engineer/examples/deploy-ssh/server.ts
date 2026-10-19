// Run the same Worker handler on any Linux host with plain node:http (Node 20+).
// Reuses ../worker.ts unchanged; swaps Cloudflare KV for a tiny file-backed store.
import { createServer } from "node:http";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { app as worker, type Env, type KVLike } from "../worker.js";

function fileKV(path: string): KVLike {
  const data: Record<string, { v: string; exp?: number }> = existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
  const save = () => writeFileSync(path, JSON.stringify(data));
  return {
    async get(key) {
      const e = data[key];
      if (!e) return null;
      if (e.exp && e.exp < Date.now()) { delete data[key]; save(); return null; }
      return e.v;
    },
    async put(key, value, opts) {
      data[key] = { v: value, exp: opts?.expirationTtl ? Date.now() + opts.expirationTtl * 1000 : undefined };
      save();
    },
  };
}

function need(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`missing env ${name}`);
  return v;
}

const env: Env = {
  DISCORD_BOT_TOKEN: need("DISCORD_BOT_TOKEN"),
  DISCORD_PUBLIC_KEY: need("DISCORD_PUBLIC_KEY"),
  INGEST_SECRET: need("INGEST_SECRET"),
  ROUTES: process.env.ROUTES ?? "{}",
  AI_ALLOWED_CHANNELS: process.env.AI_ALLOWED_CHANNELS ?? "[]",
  BOT_USER_ID: process.env.BOT_USER_ID ?? "",
  GATEWAY_HEALTH_URL: process.env.GATEWAY_HEALTH_URL ?? "",
  SEEN: fileKV(process.env.KV_FILE ?? "./seen.json"),
};

const port = Number(process.env.PORT ?? 8787);

createServer(async (req, res) => {
  try {
    const chunks: Buffer[] = [];
    for await (const c of req) chunks.push(c as Buffer);
    const body = chunks.length ? Buffer.concat(chunks) : undefined;
    const headers = new Headers();
    for (const [k, v] of Object.entries(req.headers)) if (typeof v === "string") headers.set(k, v);
    const request = new Request(`http://localhost${req.url ?? "/"}`, {
      method: req.method, headers, body: req.method === "GET" || req.method === "HEAD" ? undefined : body,
    });
    const out = await worker.fetch(request, env);
    res.writeHead(out.status, Object.fromEntries(out.headers));
    res.end(Buffer.from(await out.arrayBuffer()));
  } catch (err) {
    console.error(err);
    res.writeHead(500, { "content-type": "application/json" }).end('{"error":"internal"}');
  }
}).listen(port, process.env.HOST ?? "127.0.0.1", () => console.log(`listening on port ${port}`));
