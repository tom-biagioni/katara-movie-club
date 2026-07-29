/* Katara's Movie Club — offline cache.
   Cache-first for the shell; background revalidation at most every 6 hours;
   posts {type:"new-edition"} to pages when a new index has been fetched. */
const CACHE = "kmc-v1";
const SHELL = ["./", "./providers.json", "./titles.json", "./add.html"];
const MAX_AGE = 6 * 60 * 60 * 1000;

self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await c.addAll(SHELL);
    await putMeta(c, Date.now());
    self.skipWaiting();
  })());
});

self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
    await self.clients.claim();
  })());
});

async function putMeta(c, ts) {
  await c.put("./__meta__", new Response(JSON.stringify({ ts })));
}
async function getMeta(c) {
  try { const r = await c.match("./__meta__"); return r ? await r.json() : { ts: 0 }; }
  catch (e) { return { ts: 0 }; }
}

async function revalidate(c) {
  const meta = await getMeta(c);
  if (Date.now() - meta.ts < MAX_AGE) return;
  await putMeta(c, Date.now());   // stamp first so parallel loads don't stampede
  let changed = false;
  for (const path of SHELL) {
    try {
      const old = await c.match(path);
      const fresh = await fetch(path, { cache: "no-cache" });
      if (!fresh || !fresh.ok) continue;
      const oldTag = old && (old.headers.get("etag") || old.headers.get("last-modified"));
      const newTag = fresh.headers.get("etag") || fresh.headers.get("last-modified");
      await c.put(path, fresh.clone());
      if (path === "./" && old && oldTag && newTag && oldTag !== newTag) changed = true;
    } catch (e) { /* offline is fine */ }
  }
  if (changed) {
    for (const client of await self.clients.matchAll()) {
      client.postMessage({ type: "new-edition" });
    }
  }
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  const key = url.pathname.endsWith("/")
    ? "./"
    : "." + url.pathname.slice(url.pathname.lastIndexOf("/"));
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const cached = await c.match(key);
    if (cached) {
      e.waitUntil(revalidate(c));
      return cached;
    }
    try {
      const fresh = await fetch(req);
      if (fresh && fresh.ok && SHELL.includes(key)) await c.put(key, fresh.clone());
      return fresh;
    } catch (err) {
      return cached || Response.error();
    }
  })());
});
