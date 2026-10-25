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
    groups:(gid,rec)=>groups(gid,rec), GL:()=>GL, catName:c=>catName(c), EMOJI, siteHash:()=>siteHash(),
    upr:typeof upr==="function"?upr:null};`, ctx);   // upr (vahid qiymət) olmasa səhifələr onsuz qurulur
  return ctx.__site;
}

const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => n.toFixed(2) + "\u00a0₼";   // bölünməz boşluq: "7.10" və "₼" ayrı sətrə düşmür
const num = n => n.toLocaleString("az");     // saytdakı kimi: 59.861
/* rəqəmdən sonra yiyəlik şəkilçisi rəqəmin son sözünə görə: 428-i (səkkiz), 202-si (iki), 3-ü (üç), 30-u (on), 40-ı (qırx), 100-ü (yüz), 1000-i (min) */
const poss = n => `${num(n)}-${n % 10 ? ["", "i", "si", "ü", "ü", "i", "sı", "si", "i", "u"][n % 10]
  : n % 100 ? ["", "u", "si", "u", "ı", "si", "ı", "i", "i", "ı"][n % 100 / 10] : n % 1000 ? "ü" : n % 1e6 ? "i" : "u"}`;
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

  /* 3. sitemap.xml — lastmod: data səhifələri üçün qiymət tarixi, haqqinda.html üçün səhifədəki "Son yenilənmə" (hər gün dəyişmir) */
  const day = isoDay(db.last_updated);
  let about = "";
  try { about = isoDay((/Son yenilənmə: (\d\d\.\d\d\.\d{4})/.exec(fs.readFileSync(path.join(ROOT, "haqqinda.html"), "utf8")) || [])[1]); } catch (e) {}
  const urls = [["", day], ["haqqinda.html", about], ...pages.map(u => [u, day])];
  writeAtomic(path.join(OUT, "sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    urls.map(([u, d]) => `  <url><loc>${esc(SITE + u)}</loc>${d ? `<lastmod>${d}</lastmod>` : ""}</url>`).join("\n") + `\n</urlset>\n`);
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
    let subs = g.cats.filter(c => (bySub.get(c) || []).length >= 5).map(c => ({ id: c, name: S.catName(c), cards: bySub.get(c) }));
    if (subs.length === 1 && subs[0].cards.length === cards.length) subs = [];   // tək alt növ bütün qrupdursa (Çörək, Digər…) ayrıca səhifə yox: siyahı qrup səhifəsindədir, eyni məzmunlu iki səhifə olmur
    groupsInfo.push({ g, cards, subs });
  }

  /* qovluqlar arası keçid: hub (qiymetler/), qrup (qiymetler/<qrup>/), alt növ (qiymetler/<qrup>/<alt>.html).
     crumbs / app sayt kökünə görə yazılır, page() səhifənin dərinliyinə görə "../" əlavə edir */
  const lead = (cards, champ) => { const cmp = cards.filter(c => c.n > 1).length;
    return `${num(cards.length)} məhsul${cmp ? ` · ${poss(cmp)} bir neçə mağazada` : ""}${champ ? ` · ən çox ən ucuz: <b>${esc(champ[0])}</b> (${num(champ[1])} məhsulda)` : ""}`; };
  const desc = (name, cards, champ) => { const cmp = cards.filter(c => c.n > 1).length;
    return `${name}: ${num(cards.length)} məhsul${cmp ? `, ${poss(cmp)} bir neçə mağazada müqayisə olunur` : ""}.${champ ? ` Ən çox ən ucuz: ${champ[0]}.` : ""} Mağazalar: ${storeList}.`; };
  const all = (cards, app) => { const list = pick(cards);   // qrup və alt növ səhifələri eyni dərinlikdədir (qiymetler/<qrup>/)
    return items(list, S) + (list.length < cards.length ? `<p class="mute">Burada ${num(list.length)} məhsul göstərilir. Hamısı (${num(cards.length)}), süzgəc və axtarış: <a href="../../${app}">saytda</a>.</p>` : ""); };
  const chip = (href, label, n) => `<li><a href="${href}">${label} <small>${num(n)}</small></a></li>`;   // say da linkin içində: bütöv düymə toxunulan sahədir
  const crumbs = [["", "Ana səhifə"], ["qiymetler/", "Bütün qiymətlər"]];
  for (const { g, cards, subs } of groupsInfo) {
    const em = S.EMOJI[g.id] || "📦";
    for (const sub of subs) {
      const title = `${sub.name} qiymətləri`, champ = champion(sub.cards), app = `#/c/${g.id}/${sub.id}`;
      write(`${g.id}/${sub.id}.html`, page({
        path: `qiymetler/${g.id}/${sub.id}.html`, title, desc: desc(sub.name, sub.cards, champ), upd,
        crumbs: [...crumbs, [`qiymetler/${g.id}/`, g.name]],
        h1: `${S.EMOJI[sub.id] || em} ${esc(title)}`, lead: lead(sub.cards, champ), app, body: all(sub.cards, app),
      }));
    }
    const top = cards.filter(c => c.n > 1).sort((a, b) => b.save - a.save).slice(0, 30);
    const champ = champion(cards), app = `#/c/${g.id}`;
    write(`${g.id}/index.html`, page({
      path: `qiymetler/${g.id}/`, title: `${g.name} qiymətləri`, desc: desc(g.name, cards, champ), upd, crumbs,
      h1: `${em} ${esc(g.name)}`, lead: lead(cards, champ), app,
      body: subs.length ? `<h2>Alt bölmələr</h2><ul class="subs">${subs.map(s => chip(`${s.id}.html`, `${S.EMOJI[s.id] || em} ${esc(s.name)}`, s.cards.length)).join("")}</ul>` +
        (top.length ? `<h2>Ən çox qənaət</h2>${items(top, S, true)}` : "") : all(cards, app),
    }));
  }
  write("index.html", page({
    path: "qiymetler/", title: "Bütün qiymətlər kateqoriyalar üzrə", upd,
    desc: `Bakı supermarketlərinin (${storeList}) qiymətləri kateqoriyalar üzrə: süd, ət, meyvə, tərəvəz, içkilər və s.`,
    crumbs: crumbs.slice(0, 1),
    h1: "🛒 Bütün qiymətlər",
    lead: `${storeList} — ${num(Object.values(CARDS).reduce((a, c) => a + c.length, 0))} məhsul`,
    app: "",
    body: groupsInfo.map(({ g, cards, subs }) => `<h2><a href="${g.id}/">${S.EMOJI[g.id] || "📦"} ${esc(g.name)}</a> <small>${num(cards.length)}</small></h2>` +
      (subs.length ? `<ul class="subs">${subs.map(s => chip(`${g.id}/${s.id}.html`, esc(s.name), s.cards.length)).join("")}</ul>` : "")).join("\n"),
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

/* ən çox kartda ən ucuz olan mağaza (ən azı 3 müqayisə; hamısında eyni qiymət olan kartlar sayılmır — orada "ən ucuz" yoxdur) */
function champion(cards) {
  const w = {};
  for (const c of cards) if (c.n > 1 && c.max > c.min) for (const [s, o] of Object.entries(c.offers)) if (!o.st && o.p === c.min) w[s] = (w[s] || 0) + 1;
  const best = Object.entries(w).sort((a, b) => b[1] - a[1])[0];
  return best && best[1] >= 3 ? best : null;
}

/* kart: ən ucuz mağaza yaşıl sətirdə, qalanları ucuzdan bahaya. Qiymət bərabərdirsə hamısı ən ucuzdur (birini seçib "ən ucuz" yazmırıq);
   hamısında eynidirsə "N mağazada eyni qiymət". save: qənaət məbləği də göstərilir ("Ən çox qənaət" siyahısı) */
function items(list, S, save) {
  return `<ul class="items">\n` + list.map(c => {
    const u = c.a && c.a.kg ? "/kq" : "", W = o => o.w ? "<sup>W</sup>" : "";
    const offs = Object.entries(c.offers).sort((a, b) => a[1].p - b[1].p), live = offs.filter(([, o]) => !o.st);
    const low = c.n > 1 ? live.filter(([, o]) => o.p === c.min) : [], same = low.length > 1 && low.length === live.length;
    const lbl = ([s, o]) => `<span>${esc(s)} ${fmt(o.p)}${u}${W(o)}${o.st ? " (arxiv)" : ""}</span>`, name = ([s, o]) => `<span>${esc(s)}${W(o)}</span>`;
    const head = !low.length ? "" : low.length === 1 ? `<i style="background:var(--${esc(low[0][0])})"></i>Ən ucuz: ${lbl(low[0])}`
      : same ? `${low.length} mağazada eyni qiymət: <span>${fmt(c.min)}${u}</span>` : `Ən ucuz: ${low.map(name).join(", ")} — <span>${fmt(c.min)}${u}</span>`;
    const first = (low[0] || live[0] || offs[0] || [])[1], up = S.upr && first ? S.upr(c, first.p) : null;   // vahid qiymət (₼/kq, ₼/L), saytdakı kimi
    const extra = (up && isFinite(up.v) && Math.abs(up.v - first.p) >= .005 ? ` <span class="u">· ${fmt(up.v)}/${esc(up.u)}</span>` : "") +   // 1 kq / 1 L qablaşdırmada təkrar olmasın
      (save && !same && c.save > 0 ? ` <span class="u">· ${fmt(c.save)} qənaət</span>` : "");
    const tail = (same ? low.map(name) : []).concat(offs.filter(x => !low.includes(x)).map(lbl)).join(" · ");
    return `<li><b>${esc(c.name)}</b>` + (head ? `<span class="best">${head}${extra}</span>` : "") +
      (tail || !head && extra ? `<small>${tail}${head ? "" : extra}</small>` : "") + `</li>`;
  }).join("\n") + `\n</ul>`;
}

function page({ path: p, title, desc, upd, crumbs, h1, lead, app, body }) {
  const up = "../".repeat(p.split("/").length - 1), url = SITE + p, full = `${title} — Bakı supermarketləri | Harda Ucuz`;   // dərinlik ünvandan: qiymetler/ → ../, qiymetler/sud/ → ../../
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
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#e35600">
<link rel="icon" href="${up}favicon.ico" sizes="48x48">
<link rel="icon" href="${up}assets/icons/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="${up}assets/icons/apple-touch-icon.png">
<style>
:root{--bg:#faf6ee;--card:#fff;--ink:#281505;--mute:#6b5a46;--line:#eedcc4;--brand:#bf4800;--on-brand:#fff;--good:#0b8043;--good-soft:#e6f6ee;
--Bravo:#d93025;--OBA:#0b79d0;--Araz:#8e44ad;--Neptun:#0f9d58;--Tamstore:#e6a100;--Rahat:#c2185b;--Bazarstore:#00897b;--SPAR:#7cb342}
@media (prefers-color-scheme:dark){:root{--bg:#151009;--card:#1f1810;--ink:#f5ebdc;--mute:#b4a58f;--line:#3a2e20;--brand:#ff7a2f;--on-brand:#151009;--good:#3ddc84;--good-soft:#12301f}}
/* mətn rəngləri WCAG AA (4.5:1): link #bf4800, yaşıl #0b8043; qaranlıq rejimdə narıncı düymədə tünd yazı */
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px 16px 48px}
a{color:var(--brand)}
nav ol{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;font-size:14px;color:var(--mute)}
nav li+li::before{content:"›";margin:0 6px}
nav a{display:inline-block;padding:4px 0;text-decoration:none}
h1{font-size:24px;line-height:1.2;margin:6px 0 4px}
h2{font-size:18px;margin:26px 0 8px}
h2 small,.subs small{color:var(--mute);font-weight:400;font-size:13px}
.mute{color:var(--mute);font-size:14px}
.go{display:inline-block;margin:12px 0 4px;background:var(--brand);color:var(--on-brand);text-decoration:none;font-weight:600;border-radius:12px;padding:10px 16px}
.subs{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:8px}
.subs li{background:var(--card);border:1px solid var(--line);border-radius:999px}
.subs a{display:block;padding:6px 12px;text-decoration:none;color:var(--ink);font-weight:600}
.items{list-style:none;padding:0;margin:12px 0}
.items li{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 14px;margin-bottom:8px}
.items b{display:block;font-size:15px}
.items .best{display:block;color:var(--good);font-weight:600;font-size:14px;margin-top:2px;font-variant-numeric:tabular-nums}
.items .best i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.items .u{color:var(--mute);font-weight:400}
.items small{display:block;color:var(--mute);font-size:13px;margin-top:2px;font-variant-numeric:tabular-nums}
.items small span,.items .best span{white-space:nowrap}
footer{margin-top:28px;color:var(--mute);font-size:12.5px;line-height:1.6}
</style>
</head>
<body>
<main>
<nav aria-label="Səhifə yolu"><ol itemscope itemtype="https://schema.org/BreadcrumbList">${crumbs.map(([h, t], i) =>
  `<li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem"><a itemprop="item" href="${up}${h}"><span itemprop="name">${esc(t)}</span></a><meta itemprop="position" content="${i + 1}"></li>`).join("")}</ol></nav>
<h1>${h1}</h1>
<p class="mute">${lead}<br>Son yenilənmə: ${esc(upd || "—")}</p>
<a class="go" href="${up}${app}">Saytda aç: axtar, süz, səbətə əlavə et →</a>
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
