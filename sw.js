// Service worker: sayt telefona "tətbiq" kimi quraşdırılanda internetsiz də açılsın (index.html qeydiyyatdan keçirir).
// Yalnız öz saytımızın faylları keşlənir; mağaza / Open Food Facts şəkilləri və statistika olduğu kimi şəbəkədən gedir.
// - səhifələr və data/*.json: əvvəlcə şəbəkə (təzə qiymət), alınmasa və ya çox gecikərsə son saxlanmış nüsxə
// - ikonlar, assets/: əvvəlcə keş (dəyişmir), yoxdursa şəbəkə
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

// şəbəkə; ms-dən çox gecikərsə (və ya alınmasa) keşdəki nüsxə. Şəbəkə cavabı gec gəlsə də keşə yazılır (növbəti açılış üçün)
function netFirst(req, cache, ms) {
  const net = fetch(req).then(r => {
    if (r.ok) { const c = r.clone(); caches.open(cache).then(x => x.put(req, c)); }
    return r;
  });
  const cached = () => caches.match(req, { ignoreSearch: true });
  return new Promise(resolve => {
    let done = false;
    const fallback = () => cached().then(r => { if (r && !done) { done = true; resolve(r); } return r; });
    const t = setTimeout(fallback, ms);
    net.then(r => { clearTimeout(t); if (!done) { done = true; resolve(r); } })
      .catch(() => { clearTimeout(t); fallback().then(r => { if (!r && !done) { done = true; resolve(Response.error()); } }); });
  });
}

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;   // xarici şəkillər, statistika: toxunulmur
  const path = url.pathname;
  if (req.mode === "navigate") { e.respondWith(netFirst(req, SHELL, 3000)); return; }
  if (/\/data\/(?:catalog\/)?[\w-]+\.json$/.test(path)) { e.respondWith(netFirst(req, DATA, 8000)); return; }
  if (/\/assets\//.test(path) || /\.webmanifest$/.test(path)) {
    e.respondWith(caches.match(req).then(r => r || fetch(req).then(n => {
      if (n.ok) { const c = n.clone(); caches.open(SHELL).then(x => x.put(req, c)); }
      return n;
    })));
  }
});
