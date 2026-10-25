#!/usr/bin/env node
/* Saytın serverdə hazırlanan hissələri (GitHub Actions-da scraper-dən sonra işləyir):
   1. data/groups.json — "eyni məhsul" kartları index.html-in ÖZ group() funksiyası ilə bir dəfə hesablanır;
      brauzer onları hazır götürür və ilk axtarışda telefon 67 min məhsulu yenidən müqayisə etmir.
      Fayl yalnız eyni data (last_updated) və eyni sayt kodu (skript xeşi) üçün qəbul olunur, əks halda sayt özü hesablayır.
   2. qiymetler/ — hər ana qrup və alt növ üçün statik HTML səhifə (Google üçün: "pendir qiyməti" axtarışı).
   3. sitemap.xml — Google Search Console-a veriləcək səhifə siyahısı.

   İşlətmək:  node scripts/build_site.js [--prices data/prices.json] [--out .] [--site https://.../]
*/
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const PRICES = path.resolve(arg("--prices", path.join(ROOT, "data", "prices.json")));
const OUT = path.resolve(arg("--out", ROOT));
const SITE = (arg("--site", process.env.SITE_URL || "https://ilhamisayev16-cyber.github.io/harda-ucuz/")).replace(/\/?$/, "/");
const STATS = process.env.STATS_URL ?? "https://qiymetmuqayise.goatcounter.com/count";   // anonim ziyarət sayı (cookie yoxdur); "" söndürür
const MAX_ITEMS = 150;   // alt növ səhifəsində ən çox kart (səhifə yüngül qalsın; tam siyahı saytdadır)

/* ── index.html-in skriptini node-da yükləmək (DOM yoxdur: sadə əvəzlər) ── */
function loadSite() {
  const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8").replace(/\r\n?/g, "\n");   // brauzer də sətir sonlarını belə normallaşdırır
  const js = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).pop();
  const el = () => ({ classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } }, style: {}, dataset: {},
    setAttribute() {}, addEventListener() {}, querySelectorAll: () => [], querySelector: () => el(), scrollIntoView() {}, blur() {} });
  const ctx = { console, TextEncoder, performance, innerWidth: 390, location: { hash: "" }, window: { scrollTo() {} },
    document: { currentScript: { textContent: js }, addEventListener() {}, getElementById: el, querySelector: el, querySelectorAll: () => [] },
    localStorage: { getItem: () => null, setItem() {} }, addEventListener() {}, fetch: () => new Promise(() => {}),
    setTimeout: () => 0, clearTimeout() {} };
  vm.createContext(ctx);
  vm.runInContext(js + `;globalThis.__site={
    setDB(d){DB=sane(d);stores=DB.stores;GL=DB.groups;GM=Object.fromEntries(GL.map(g=>[g.id,g]));PRE=null;for(const k in GROUPS)delete GROUPS[k];return DB;},
    setPre(p){PRE=p;for(const k in GROUPS)delete GROUPS[k];},
    groups:(gid,rec)=>groups(gid,rec), GL:()=>GL, catName:c=>catName(c), EMOJI, siteHash:()=>siteHash()};`, ctx);
  return ctx.__site;
}

const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => n.toFixed(2) + " ₼";
const cardJSON = cards => JSON.stringify(cards.map(g => { const { mi, ...r } = g; return r; }));

function main() {
  const S = loadSite();
  const db = S.setDB(JSON.parse(fs.readFileSync(PRICES, "utf8")));   // saytın öz yoxlaması (sane): brauzerlə eyni data, səhifələrə yalnız düzgün format düşür

  /* 1. kartlar + hazır üzv siyahısı; yoxlama: hazır siyahı ilə qurulan kartlar brauzerin hesabladığı ilə eyni olmalıdır */
  const t0 = Date.now(), pre = {}, CARDS = {};
  for (const g of S.GL()) {
    const cards = S.groups(g.id, true);
    CARDS[g.id] = cards;
    pre[g.id] = { n: cards.N, m: cards.filter(c => c.mi.length > 1).map(c => c.mi) };
  }
  const t1 = Date.now();
  S.setPre(pre);
  for (const g of S.GL()) {
    if (cardJSON(S.groups(g.id)) !== cardJSON(CARDS[g.id])) {
      console.warn(`  ⚠ ${g.id}: hazır kartlar fərqli nəticə verdi — bu qrup brauzerdə hesablanacaq`);
      delete pre[g.id];
    }
  }
  const out = { v: db.last_updated || "", s: S.siteHash(), g: pre };
  writeAtomic(path.join(OUT, "data", "groups.json"), JSON.stringify(out));
  const nCards = Object.values(CARDS).reduce((a, c) => a + c.length, 0);
  console.log(`groups.json: ${Object.keys(pre).length}/${S.GL().length} qrup, ${nCards} kart, qruplaşdırma ${t1 - t0} ms`);

  /* 2. statik səhifələr */
  const pages = buildPages(db, S, CARDS);
  console.log(`qiymetler/: ${pages.length} səhifə`);

  /* 3. sitemap.xml */
  const day = isoDay(db.last_updated);
  const urls = ["", "haqqinda.html", ...pages];
  writeAtomic(path.join(OUT, "sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    urls.map(u => `  <url><loc>${esc(SITE + u)}</loc>${day ? `<lastmod>${day}</lastmod>` : ""}</url>`).join("\n") + `\n</urlset>\n`);
  console.log(`sitemap.xml: ${urls.length} ünvan`);
}

/* yarımçıq fayl qalmasın: əvvəl müvəqqəti fayla, sonra əvəz */
function writeAtomic(f, text) { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f + ".tmp", text); fs.renameSync(f + ".tmp", f); }

const isoDay = s => { const m = /^(\d\d)\.(\d\d)\.(\d{4})/.exec(s || ""); return m ? `${m[3]}-${m[2]}-${m[1]}` : ""; };

/* ── statik səhifələr ── */
function buildPages(db, S, CARDS) {
  const final = path.join(OUT, "qiymetler"), dir = final + ".tmp";   // əvvəl müvəqqəti qovluğa: skript yarıda dayansa köhnə səhifələr qalır
  fs.rmSync(dir, { recursive: true, force: true });
  const stores = db.stores || [], upd = db.last_updated || "", written = [];
  const write = (rel, html) => {
    if (!/^(?:[a-z][a-z0-9_]*\/)?[a-z][a-z0-9_]*\.html$/.test(rel)) throw new Error("yanlış səhifə yolu: " + rel);   // qovluqdan kənara yazılmasın
    const f = path.join(dir, rel); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, html); written.push("qiymetler/" + rel.replace(/index\.html$/, "")); };
  const storeList = stores.join(", ");

  const groupsInfo = [];
  for (const g of S.GL()) {
    const cards = CARDS[g.id] || [];
    if (!cards.length) continue;
    const bySub = new Map();
    for (const c of cards) { const k = c.c || g.id; (bySub.get(k) || bySub.set(k, []).get(k)).push(c); }
    const subs = g.cats.filter(c => (bySub.get(c) || []).length >= 5).map(c => ({ id: c, name: S.catName(c), cards: bySub.get(c) }));
    groupsInfo.push({ g, cards, subs });
  }

  /* qovluqlar arası keçid: hub (qiymetler/), qrup (qiymetler/<qrup>/), alt növ (qiymetler/<qrup>/<alt>.html) */
  for (const { g, cards, subs } of groupsInfo) {
    const em = S.EMOJI[g.id] || "📦";
    for (const sub of subs) {
      const title = `${sub.name} qiymətləri`;
      const list = pick(sub.cards);
      const cmp = sub.cards.filter(c => c.n > 1).length;
      const champ = champion(sub.cards);
      const desc = `${sub.name}: ${sub.cards.length} məhsulun qiyməti${cmp ? `, ${cmp} məhsul bir neçə mağazada müqayisə` : ""}. ` +
        `${champ ? `Ən çox ən ucuz: ${champ[0]}. ` : ""}${storeList}.`;
      write(`${g.id}/${sub.id}.html`, page({
        depth: 2, path: `qiymetler/${g.id}/${sub.id}.html`, title, desc, upd,
        crumbs: [["../../", "Ana səhifə"], ["../", "Bütün qiymətlər"], ["./", g.name]],
        h1: `${S.EMOJI[sub.id] || em} ${esc(title)}`,
        lead: `${sub.cards.length} məhsul${cmp ? ` · ${cmp}-i bir neçə mağazada` : ""}${champ ? ` · ən çox ən ucuz: <b>${esc(champ[0])}</b> (${champ[1]} məhsulda)` : ""}`,
        app: `../../#/c/${g.id}/${sub.id}`,
        body: items(list) + (list.length < sub.cards.length ? `<p class="mute">Burada ${list.length} məhsul göstərilir. Hamısı, süzgəc və axtarış saytdadır.</p>` : ""),
      }));
    }
    const top = cards.filter(c => c.n > 1).sort((a, b) => b.save - a.save).slice(0, 30);
    const champ = champion(cards);
    write(`${g.id}/index.html`, page({
      depth: 1, path: `qiymetler/${g.id}/`, title: `${g.name} — qiymətlər`, upd,
      desc: `${g.name}: ${cards.length} məhsulun qiyməti ${storeList} mağazalarında müqayisə.${champ ? ` Ən çox ən ucuz: ${champ[0]}.` : ""}`,
      crumbs: [["../../", "Ana səhifə"], ["../", "Bütün qiymətlər"]],
      h1: `${em} ${esc(g.name)}`,
      lead: `${cards.length} məhsul${champ ? ` · ən çox ən ucuz: <b>${esc(champ[0])}</b> (${champ[1]} məhsulda)` : ""}`,
      app: `../../#/c/${g.id}`,
      body: (subs.length ? `<h2>Alt bölmələr</h2><ul class="subs">${subs.map(s => `<li><a href="${s.id}.html">${S.EMOJI[s.id] || em} ${esc(s.name)}</a> <small>${s.cards.length}</small></li>`).join("")}</ul>` : "") +
        (top.length ? `<h2>Ən çox qənaət</h2>${items(top)}` : ""),
    }));
  }
  write("index.html", page({
    depth: 1, path: "qiymetler/", title: "Bütün supermarket qiymətləri", upd,
    desc: `Bakı supermarketlərinin (${storeList}) qiymətləri kateqoriyalar üzrə: süd, ət, meyvə, tərəvəz, içkilər və s.`,
    crumbs: [["../", "Ana səhifə"]],
    h1: "🛒 Bütün qiymətlər",
    lead: `${storeList} — ${Object.values(CARDS).reduce((a, c) => a + c.length, 0).toLocaleString("az")} məhsul`,
    app: "../",
    body: groupsInfo.map(({ g, cards, subs }) => `<h2><a href="${g.id}/">${S.EMOJI[g.id] || "📦"} ${esc(g.name)}</a> <small>${cards.length}</small></h2>` +
      (subs.length ? `<ul class="subs">${subs.map(s => `<li><a href="${g.id}/${s.id}.html">${esc(s.name)}</a> <small>${s.cards.length}</small></li>`).join("")}</ul>` : "")).join("\n"),
  }));
  fs.rmSync(final, { recursive: true, force: true });   // yalnız bu skriptin yaratdığı qovluq: silinmiş alt növlərin səhifəsi qalmasın
  fs.renameSync(dir, final);
  return written.sort();
}

/* bir neçə mağazada olanlar əvvəl (çox mağaza, sonra böyük qənaət), sonra tək mağazalılar (ada görə) */
function pick(cards) {
  const multi = cards.filter(c => c.n > 1).sort((a, b) => b.n - a.n || b.save - a.save || a.name.localeCompare(b.name, "az"));
  const single = cards.filter(c => c.n <= 1).sort((a, b) => a.name.localeCompare(b.name, "az"));
  return multi.concat(single).slice(0, MAX_ITEMS);
}

/* ən çox kartda ən ucuz olan mağaza (ən azı 3 müqayisə) */
function champion(cards) {
  const w = {};
  for (const c of cards) if (c.n > 1) for (const [s, o] of Object.entries(c.offers)) if (!o.st && o.p === c.min) w[s] = (w[s] || 0) + 1;
  const best = Object.entries(w).sort((a, b) => b[1] - a[1])[0];
  return best && best[1] >= 3 ? best : null;
}

function items(list) {
  return `<ul class="items">\n` + list.map(c => {
    const u = c.a && c.a.kg ? "/kq" : "";
    const offs = Object.entries(c.offers).sort((a, b) => a[1].p - b[1].p);
    const cheap = c.n > 1 ? offs.find(([, o]) => !o.st && o.p === c.min) : null;
    const lbl = ([s, o]) => `${esc(s)} ${fmt(o.p)}${u}${o.w ? "<sup>W</sup>" : ""}`;
    const rest = offs.filter(x => x !== cheap).map(lbl).join(" · ");
    return `<li><b>${esc(c.name)}</b>` +
      (cheap ? `<span class="best"><i style="background:var(--${esc(cheap[0])})"></i>Ən ucuz: ${lbl(cheap)}</span>` : "") +
      (rest ? `<small>${rest}</small>` : "") + `</li>`;
  }).join("\n") + `\n</ul>`;
}

function page({ depth, path: p, title, desc, upd, crumbs, h1, lead, app, body }) {
  const up = "../".repeat(depth), url = SITE + p, full = `${title} — Bakı supermarketləri | Harda Ucuz`;
  return `<!doctype html>
<html lang="az">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:${STATS ? " " + new URL(STATS).origin : ""}; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; upgrade-insecure-requests">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>${esc(full)}</title>
<meta name="description" content="${esc(desc.slice(0, 300))}">
<link rel="canonical" href="${esc(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Harda Ucuz">
<meta property="og:locale" content="az_AZ">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc.slice(0, 300))}">
<meta property="og:url" content="${esc(url)}">
<meta property="og:image" content="${esc(SITE)}og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#e35600">
<link rel="icon" href="${SITE}favicon.ico" sizes="48x48">
<link rel="icon" href="${SITE}assets/icons/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="${SITE}assets/icons/apple-touch-icon.png">
<style>
:root{--bg:#faf6ee;--card:#fff;--ink:#281505;--mute:#6b5a46;--line:#eedcc4;--brand:#e35600;--good:#0f9d58;--good-soft:#e6f6ee;
--Bravo:#d93025;--OBA:#0b79d0;--Araz:#8e44ad;--Neptun:#0f9d58;--Tamstore:#e6a100;--Rahat:#c2185b;--Bazarstore:#00897b;--SPAR:#7cb342}
@media (prefers-color-scheme:dark){:root{--bg:#151009;--card:#1f1810;--ink:#f5ebdc;--mute:#b4a58f;--line:#3a2e20;--brand:#ff7a2f;--good:#3ddc84;--good-soft:#12301f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px 16px 48px}
a{color:var(--brand)}
nav{font-size:14px;color:var(--mute)}
nav a{text-decoration:none}
h1{font-size:24px;line-height:1.2;margin:10px 0 4px}
h2{font-size:18px;margin:26px 0 8px}
h2 small,.subs small{color:var(--mute);font-weight:400;font-size:13px}
.mute{color:var(--mute);font-size:14px}
.go{display:inline-block;margin:12px 0 4px;background:var(--brand);color:#fff;text-decoration:none;font-weight:600;border-radius:12px;padding:10px 16px}
.subs{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:8px}
.subs li{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:6px 12px}
.subs a{text-decoration:none;color:var(--ink);font-weight:600}
.items{list-style:none;padding:0;margin:12px 0}
.items li{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 14px;margin-bottom:8px}
.items b{display:block;font-size:15px}
.items .best{display:block;color:var(--good);font-weight:600;font-size:14px;margin-top:2px;font-variant-numeric:tabular-nums}
.items .best i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.items small{display:block;color:var(--mute);font-size:13px;margin-top:2px;font-variant-numeric:tabular-nums}
footer{margin-top:28px;color:var(--mute);font-size:12.5px;line-height:1.6}
</style>
</head>
<body>
<main>
<nav>${crumbs.map(([h, t]) => `<a href="${h}">${esc(t)}</a>`).join(" › ")}</nav>
<h1>${h1}</h1>
<p class="mute">${lead}<br>Son yenilənmə: ${esc(upd || "—")}</p>
<a class="go" href="${app}">Saytda aç: axtar, süz, siyahıya əlavə et →</a>
${body}
<footer>Qiymətlər mağazaların açıq saytlarından gündə bir dəfə avtomatik toplanır və yalnız məlumat xarakterlidir; kassadakı qiymət fərqlənə bilər.
<sup>W</sup> — Wolt-dan alınan qiymət (rəfdəki qiymətdən fərqli ola bilər). Sayt heç bir mağaza ilə əlaqəli deyil.
<a href="${up}haqqinda.html">Haqqında, şərtlər və məxfilik</a></footer>
${STATS ? `<img src="${esc(STATS)}?p=${encodeURIComponent("/" + p)}" alt="" width="1" height="1" style="position:absolute;left:-9px">` : ""}
</main>
</body>
</html>
`;
}

main();
