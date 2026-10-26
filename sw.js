// Service worker: sayt telefona "tətbiq" kimi quraşdırılanda internetsiz də açılsın (index.html qeydiyyatdan keçirir).
// Yalnız öz saytımızın faylları keşlənir; mağaza / Open Food Facts şəkilləri və statistika olduğu kimi şəbəkədən gedir.
// - səhifələr, data/*.json (data/catalog/ da), skriptlər, stillər (.js, .css) və manifest: əvvəlcə şəbəkə (təzə qiymət / kod), alınmasa, server xətası verərsə (5xx)
//   və ya çox gecikərsə son saxlanmış nüsxə. Skript index.html ilə birlikdə dəyişir: köhnəsi keşdən gəlsə yeni səhifə ilə uyuşmaz
// - şəkillər, ikonlar (assets/): əvvəlcə keş (adı dəyişmir), yoxdursa şəbəkə
// - keşdə olmayan səhifə internetsiz açılanda brauzerin xəta səhifəsi əvəzinə qısa izah və ana səhifəyə link
// Keşin strukturu dəyişəndə VER-i artırın: köhnə keş activate-də silinir.
const VER = "v2", SHELL = "hu-shell-" + VER, DATA = "hu-data-" + VER;
const PRE = ["./", "index.html", "haqqinda.html", "manifest.webmanifest", "assets/twemoji.js",
  "assets/icons/icon-192.png", "assets/icons/favicon.svg"];

self.addEventListener("install", e => {
  // data da ilk açılışdan saxlanır (brauzer onu adətən elə indi yükləyib, HTTP keşdən gəlir); alınmasa quraşdırma pozulmur
  const data = caches.open(DATA).then(c => c.addAll(["data/catalog.json", "data/groups.json"])).catch(() => {});
  e.waitUntil(Promise.all([caches.open(SHELL).then(c => c.addAll(PRE)), data]).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k.startsWith("hu-") && k !== SHELL && k !== DATA).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// keşə yazmaq: ünvan sorğu hissəsiz (?utm=... hər dəfə ayrı nüsxə yaratmasın)
const save = (cache, req, r) => { const u = new URL(req.url); u.search = ""; const c = r.clone(); return caches.open(cache).then(x => x.put(u.href, c)).catch(() => {}); };

// internetsiz və keşdə olmayan səhifə üçün (skriptsiz, ana səhifə keşdədir)
const offline = () => new Response(`<!doctype html><html lang="az"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>İnternet yoxdur — Harda Ucuz</title>
<style>body{margin:0;font:16px/1.5 system-ui,sans-serif;background:#faf6ee;color:#281505}main{max-width:520px;margin:0 auto;padding:48px 16px}a{color:#bf4800;font-weight:600}
@media (prefers-color-scheme:dark){body{background:#151009;color:#f5ebdc}a{color:#ff7a2f}}</style></head>
<body><main><h1>İnternet bağlantısı yoxdur</h1><p>Bu səhifə hələ cihazınızda saxlanmayıb. Son saxlanmış qiymətlər ana səhifədədir.</p>
<p><a href="${self.registration.scope}">Ana səhifəyə keç →</a></p></main></body></html>`,
  { status: 503, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });

// şəbəkə; ms-dən çox gecikərsə, alınmasa və ya 5xx olarsa keşdəki nüsxə. Şəbəkə cavabı gec gəlsə də keşə yazılır (növbəti açılış üçün)
function netFirst(e, cache, ms, none) {
  const req = e.request; let saved;
  const net = fetch(req).then(r => { if (r.ok) saved = save(cache, req, r); return r; });
  e.waitUntil(net.then(() => saved, () => {}));   // cavab keşdən gedibsə də işçi şəbəkə cavabını keşə yazmamış dayandırılmasın
  const cached = () => caches.match(req, { ignoreSearch: true });
  return new Promise(resolve => {
    let done = false;
    const end = r => { if (!done) { done = true; resolve(r); } };
    const fallback = () => cached().then(r => { if (r) end(r); return r; });
    const t = setTimeout(fallback, ms);
    net.then(r => { clearTimeout(t); if (r.status < 500) return end(r); fallback().then(c => { if (!c) end(r); }); })   // server xətası: keşdə varsa o
      .catch(() => { clearTimeout(t); fallback().then(r => { if (!r) end(none ? none() : Response.error()); }); });
  });
}

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;   // xarici şəkillər, statistika: toxunulmur
  const path = url.pathname;
  if (req.mode === "navigate") { e.respondWith(netFirst(e, SHELL, 3000, offline)); return; }
  if (/\/data\/(?:catalog\/)?[\w-]+\.json$/.test(path)) { e.respondWith(netFirst(e, DATA, 8000)); return; }
  if (/\.(?:js|css|webmanifest)$/.test(path)) { e.respondWith(netFirst(e, SHELL, 3000)); return; }   // assets/catalog.css da adı dəyişmədən yenilənir
  if (/\/assets\//.test(path)) {
    e.respondWith(caches.match(req).then(r => r || fetch(req).then(n => { if (n.ok) e.waitUntil(save(SHELL, req, n)); return n; })));
  }
});
