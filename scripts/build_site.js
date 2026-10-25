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

const crypto = require("crypto");
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
    setIds(ids){DB.product_ids=ids;}, aliases:g=>aliases(g), hash:(s,n)=>hk(s,n), groups:(gid,rec)=>groups(gid,rec), GL:()=>GL, catName:c=>catName(c), EMOJI, siteHash:()=>siteHash()};`, ctx);
  return ctx.__site;
}

const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => n.toFixed(2) + " ₼";
const cardJSON = cards => JSON.stringify(cards.map(g => { const { mi, ...r } = g; return r; }));

function main() {
  const S = loadSite();
  let registry={}; try{ registry=JSON.parse(fs.readFileSync(path.join(OUT,"data","product_ids.json"),"utf8")); }catch(e){ if(e.code!=="ENOENT") throw e; }
  const raw=JSON.parse(fs.readFileSync(PRICES,"utf8")); raw.product_ids=registry;
  const db = S.setDB(raw);   // saytın öz yoxlaması (sane): brauzerlə eyni data, səhifələrə yalnız düzgün format düşür

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

  // Persist aliases, so reordering, new stores and display-name changes keep existing URLs.
  const assigned=new Map();
  for(const cards of Object.values(CARDS)) for(const c of cards){
    const aliases=S.aliases(c), known=aliases.map(k=>registry[k]).filter(x=>/^s[a-f0-9]{16}$/.test(x||""));
    c.pid=known[0]||c.pid; let split=false;
    const codes=aliases.filter(k=>k.startsWith("gtin:")), previous=assigned.get(c.pid);
    if(previous&&((codes.length&&previous.codes.size&&!codes.some(k=>previous.codes.has(k)))||!aliases.some(k=>previous.aliases.has(k))))
      { c.pid="s"+S.hash("product-split",c.t+"|"+aliases.slice().sort().join("|")); split=true; }
    const current=assigned.get(c.pid)||{aliases:new Set(),codes:new Set()};
    aliases.forEach(k=>current.aliases.add(k));codes.forEach(k=>current.codes.add(k));assigned.set(c.pid,current);
    for(const k of aliases) if(split||!registry[k]) registry[k]=c.pid;
  }
  db.product_ids=registry; S.setIds(registry);
  writeAtomic(path.join(OUT,"data","product_ids.json"),JSON.stringify(registry));
  const catalog={version:1,last_updated:db.last_updated,stores:db.stores,groups:db.groups,
    highlights:{},categoryCounts:{},categories:Object.fromEntries(Object.entries(db.categories).map(([k,c])=>[k,{name:c.name,stores:{}}])),counts:{},files:{}};
  const highlights=[];
  for(const [cid,c] of Object.entries(db.categories)){
    catalog.categoryCounts[cid]=Math.max(0,...Object.values(c.stores).map(l=>l.length));
    for(const [store,items] of Object.entries(c.stores)) for(const it of items){
      const p=it.price??it.wolt_price, ratio=it.pp?(it.pp-p)/it.pp:0;
      if(it.pd&&!it.stale&&p>=.3&&ratio>=.08&&ratio<=.6&&(Date.now()-new Date(it.pd))/864e5<=7) highlights.push({cid,store,it,ratio});
    }
  }
  for(const {cid,store,it} of highlights.sort((a,b)=>b.ratio-a.ratio).slice(0,40)){
    const c=catalog.highlights[cid]||(catalog.highlights[cid]={name:db.categories[cid].name,stores:{}});
    (c.stores[store]||(c.stores[store]=[])).push(it);
  }
  for(const g of db.groups){
    const categories=Object.fromEntries(g.cats.map(k=>[k,db.categories[k]])), ids={};
    for(const c of CARDS[g.id]) for(const k of S.aliases(c)) ids[k]=registry[k];
    const payload=JSON.stringify({last_updated:db.last_updated,stores:db.stores,groups:[g],categories,product_ids:ids});
    const digest=crypto.createHash("sha256").update(payload).digest("hex").slice(0,16), file=`catalog/${g.id}-${digest}.json`;
    catalog.counts[g.id]=Object.values(categories).reduce((n,c)=>n+Object.values(c.stores).reduce((m,l)=>m+l.length,0),0);
    catalog.files[g.id]=file; writeAtomic(path.join(OUT,"data",file),payload);
  }
  // Retain only the current snapshot; a version mismatch asks the browser to refresh.
  const shardDir=path.join(OUT,"data","catalog"), keep=new Set(Object.values(catalog.files).map(f=>path.basename(f)));
  for(const f of fs.readdirSync(shardDir)) if(/^[a-z0-9_-]+\.json$/.test(f)&&!keep.has(f)) fs.unlinkSync(path.join(shardDir,f));
  writeAtomic(path.join(OUT,"data","catalog.json"),JSON.stringify(catalog));
  buildProducts(db,CARDS,S);

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
      depth: 2, path: `qiymetler/${g.id}/`, title: `${g.name} — qiymətlər`, upd,
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

function buildProducts(db,CARDS,S){
  const dir=path.join(OUT,"mehsullar"), tmp=dir+".tmp"; fs.rmSync(tmp,{recursive:true,force:true}); fs.mkdirSync(tmp,{recursive:true});
  let history={};try{history=JSON.parse(fs.readFileSync(path.join(path.dirname(PRICES),"history.json"),"utf8")).h||{};}catch(e){}
  const urls=[], seen=new Set(), activeIds=new Set(Object.values(CARDS).flatMap(cs=>cs.map(c=>c.pid)));
  for(const cards of Object.values(CARDS)) for(const c of cards){
    if(seen.has(c.pid))continue;seen.add(c.pid);
    const rel=`mehsullar/${c.pid}.html`, offers=Object.entries(c.offers).sort((a,b)=>a[1].p-b[1].p);
    const body=`<h2>Mağazalar üzrə qiymətlər</h2>`+items([c])+`<h2>Qiymət tarixçəsi</h2>`+offers.map(([store,o])=>{
      const h=history[S.hash(store,o.n)]||[], rows=h.slice(-30);
      return `<details><summary>${esc(store)} · ${o.w?"Wolt":"Mağazanın onlayn qiyməti"}${o.st?" · köhnə məlumat":""}</summary><p class="mute">Qeydə alınmış qiymət dəyişiklikləri; gündəlik stok göstəricisi deyil.</p>`+(rows.length?`<ul>${rows.map(([d,p])=>`<li>${esc(d)} — ${fmt(p)}</li>`).join("")}</ul>`:`<p>Hələ qiymət dəyişikliyi qeydə alınmayıb.</p>`)+`</details>`;
    }).join("")+`<h2>Oxşar məhsulları araşdır</h2><a href="../qiymetler/${c.t}/${c.c}.html">${esc(S.catName(c.c))} qiymətləri</a>`;
    const html=page({depth:1,path:rel,title:c.name+" — qiymət müqayisəsi",desc:`${c.name}: ${offers.map(([s,o])=>s+" "+fmt(o.p)).join(", ")}. Mənbələr və qeydə alınmış qiymət tarixçəsi.`,upd:db.last_updated,crumbs:[["../","Ana səhifə"],[`../qiymetler/${c.t}/`,"Kateqoriya"]],h1:esc(c.name),lead:`${offers.length} mağazada qiymət məlumatı · ${c.a.kg?"1 kq üçün":"qablaşdırma üçün"}`,app:`../#/c/${c.t}/${c.pid}`,body});
    fs.writeFileSync(path.join(tmp,c.pid+".html"),html);urls.push(rel);
    // Old ids remain valid when two previously separate cards are merged.
    for(const k of S.aliases(c)){ const old=db.product_ids[k]; if(old&&old!==c.pid&&!seen.has(old)&&!activeIds.has(old)){fs.writeFileSync(path.join(tmp,old+".html"),html);seen.add(old);} }
  }
  // When a GTIN correction splits an old identity, keep its URL without publishing stale prices.
  if(fs.existsSync(dir)) for(const file of fs.readdirSync(dir)){
    if(!/^s[a-f0-9]{16}\.html$/.test(file)||fs.existsSync(path.join(tmp,file)))continue;
    const old=fs.readFileSync(path.join(dir,file),"utf8"), match=/<h1>(.*?)<\/h1>/.exec(old), group=/#\/c\/([a-z0-9_]+)/.exec(old);
    const name=(match?match[1]:"Məhsul").replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,"<").replace(/&gt;/g,">").replace(/&amp;/g,"&");
    const html=page({depth:1,path:"mehsullar/"+file,title:name,desc:"Məhsul uyğunluğu yenilənib. Aktual qiymət üçün məhsulu yenidən seçin.",upd:db.last_updated,crumbs:[["../","Ana səhifə"]],h1:esc(name),lead:"Bu məhsulun əvvəlki müqayisə qrupu dəyişib.",app:group?"../#/c/"+group[1]:"../",body:"<p>Köhnə qiymət göstərilmir. Aktual müqayisə üçün kateqoriyadan uyğun məhsulu yenidən seçin.</p>"}).replace("<head>",'<head><meta name="robots" content="noindex,follow">');
    fs.writeFileSync(path.join(tmp,file),html);
  }
  fs.rmSync(dir,{recursive:true,force:true});fs.renameSync(tmp,dir);
  const parts=[];
  for(let i=0;i<urls.length;i+=40000){const file=`sitemap-products-${parts.length+1}.xml`;parts.push(file);writeAtomic(path.join(OUT,file),`<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">`+urls.slice(i,i+40000).map(p=>`<url><loc>${esc(SITE+p)}</loc></url>`).join("")+`</urlset>`);}
  writeAtomic(path.join(OUT,"sitemap-products.xml"),`<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">`+parts.map(p=>`<sitemap><loc>${esc(SITE+p)}</loc></sitemap>`).join("")+`</sitemapindex>`);
  writeAtomic(path.join(OUT,"robots.txt"),`User-agent: *\nAllow: /\nSitemap: ${SITE}sitemap.xml\nSitemap: ${SITE}sitemap-products.xml\n`);
  console.log(`mehsullar/: ${urls.length} sabit məhsul səhifəsi`);
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
    const lbl = ([s, o]) => `${esc(s)} ${fmt(o.p)}${u}${o.w ? "<sup>W</sup>" : " (onlayn)"}${o.wp ? " · Wolt: " + fmt(o.wp) : ""}`;
    const rest = offs.filter(x => x !== cheap).map(lbl).join(" · ");
    return `<li><b><a href="${esc(SITE)}mehsullar/${c.pid}.html">${esc(c.name)}</a></b>` +
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
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:${STATS ? " " + new URL(STATS).origin : ""}; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; upgrade-insecure-requests">
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
<link rel="stylesheet" href="${up}assets/catalog.css">
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
