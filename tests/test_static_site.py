# Statik səhifələr (qiymetler/), sitemap, haqqinda.html, manifest və sw.js: linklər, SEO teqləri, qiymət yazılışı, oflayn davranış
import copy
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://example.org/q/"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")


def _build(tmp_path, db):
    src = tmp_path / "prices.json"; src.write_text(json.dumps(db, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "site"
    r = subprocess.run(["node", str(ROOT / "scripts" / "build_site.js"), "--prices", str(src), "--out", str(out), "--site", SITE],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    return out


def _file(out, rel):
    """saytdakı ünvan → fayl: qurulan fayllar --out-da, qalanı (index.html, haqqinda.html, assets/) repoda"""
    base = out if rel.startswith("qiymetler/") or rel in ("sitemap.xml", "data/groups.json") else ROOT
    f = base / rel
    return f / "index.html" if rel == "" or rel.endswith("/") else f


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs = []; self.crumbs = []; self._pos = None
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag in ("a", "link") and "href" in a: self.hrefs.append(a["href"])
        if tag == "img" and "src" in a: self.hrefs.append(a["src"])
        if tag == "meta" and a.get("itemprop") == "position": self.crumbs.append(int(a["content"]))


def _site_pages(out):
    return sorted(p.relative_to(out).as_posix() for p in (out / "qiymetler").rglob("*.html"))


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    """real datanın yüngül nüsxəsi (hər mağazadan 40 məhsul)"""
    d = json.load(open(ROOT / "data" / "prices.json", encoding="utf-8"))
    for c in d["categories"].values():
        for s in c["stores"]:
            c["stores"][s] = c["stores"][s][:40]
    return _build(tmp_path_factory.mktemp("real"), d)


@node
def test_every_link_in_static_pages_resolves(real):
    pages = _site_pages(real)
    assert len(pages) > 20
    for rel in pages + ["haqqinda.html"]:
        html = _file(real, rel).read_text(encoding="utf-8")
        p = _Links(); p.feed(html)
        page_url = SITE + rel.replace("index.html", "")
        for h in p.hrefs:
            u = urljoin(page_url, h)
            if not u.startswith(SITE):
                assert urlparse(u).netloc != "example.org", (rel, h)   # öz saytımıza mütləq yanlış ünvan yoxdur
                continue
            target = urlparse(u).path[len(urlparse(SITE).path):]
            assert _file(real, target).exists(), f"{rel}: {h} → {target} yoxdur"
        if rel.startswith("qiymetler/"):
            assert p.crumbs == list(range(1, len(p.crumbs) + 1)) and p.crumbs, rel   # BreadcrumbList: 1, 2, ...
            assert "<script" not in html and "script-src 'none'" in html
            assert re.search(r'<a href="(\.\./)+haqqinda\.html">', html), rel   # alt qovluqdan haqqinda.html: qrup səhifəsində ../haqqinda.html 404 idi


@node
def test_sitemap_lists_exactly_the_built_pages(real):
    sm = (real / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    assert len(locs) == len(set(locs)) and all(u.startswith(SITE) for u in locs)
    rels = [u[len(SITE):] for u in locs]
    for r in rels:
        assert _file(real, r).exists(), r
    built = {p.replace("index.html", "") for p in _site_pages(real)}
    assert built == {r for r in rels if r.startswith("qiymetler/")}
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\d", d) for d in re.findall(r"<lastmod>([^<]+)</lastmod>", sm))
    about = re.search(r"Son yenilənmə: (\d\d)\.(\d\d)\.(\d{4})", (ROOT / "haqqinda.html").read_text(encoding="utf-8"))
    assert f"<loc>{SITE}haqqinda.html</loc><lastmod>{about[3]}-{about[2]}-{about[1]}</lastmod>" in sm   # haqqinda öz tarixi ilə, data tarixi ilə yox


@node
def test_titles_descriptions_canonical_unique(real):
    seen_t, seen_d = {}, {}
    for rel in _site_pages(real):
        html = (real / rel).read_text(encoding="utf-8")
        t = re.search(r"<title>([^<]+)</title>", html)[1]; d = re.search(r'<meta name="description" content="([^"]+)"', html)[1]
        assert t not in seen_t, (rel, seen_t.get(t)); assert d not in seen_d, (rel, seen_d.get(d))
        seen_t[t] = seen_d[d] = rel
        url = SITE + rel.replace("index.html", "")
        assert f'<link rel="canonical" href="{url}">' in html and f'<meta property="og:url" content="{url}">' in html
        assert '<html lang="az">' in html and "— —" not in t


def _db():
    def items(rows):   # (ad, Araz, Bravo-Wolt, OBA): None — bu mağazada yoxdur
        st = {"Araz": [], "Bravo": [], "OBA": []}
        for name, a, b, o in rows:
            if a is not None: st["Araz"].append({"name": name, "price": a})
            if b is not None: st["Bravo"].append({"name": name, "wolt_price": b})
            if o is not None: st["OBA"].append({"name": name, "price": o})
        return st
    sud = items([("Azərsüd Süd 3.2% 1 l", 2.8, 2.8, 2.8),        # hamısında eyni
                 ("Milla Süd 2.5% 1 l", 2.5, 2.5, 2.9),           # ikisi bərabər ən ucuz
                 ("Atena Süd 3.2% 0.5 l", 3.0, 2.7, None),         # tək ən ucuz
                 ("Palsüd Süd 1.5% 1 l", 2.2, None, None), ("Gilan Süd 3.5% 1 l", 2.6, None, None)])
    pendir = items([(f"{b} Pendir 400 q", 6.0 + i, None, None) for i, b in enumerate(["Hochland", "Pınar", "Kaanlar", "Sütaş", "Valio"])])
    corek = items([(f"{b} Çörək 500 q", 0.6 + i / 10, None, None) for i, b in enumerate(["Bakı", "Sumqayıt", "Zərif", "Səhər", "Kənd"])])
    return {"stores": ["Araz", "Bravo", "OBA"], "last_updated": "25.10.2026 10:00",
            "groups": [{"id": "sud", "name": "Süd məhsulları", "cats": ["sud", "pendir"]}, {"id": "corek", "name": "Çörək", "cats": ["corek"]}],
            "categories": {"sud": {"name": "Süd", "stores": sud}, "pendir": {"name": "Pendir", "stores": pendir},
                           "corek": {"name": "Çörək", "stores": corek}}}


@node
def test_cheapest_label_ties_prices_and_grammar(tmp_path):
    out = _build(tmp_path, _db())
    html = (out / "qiymetler" / "sud" / "sud.html").read_text(encoding="utf-8")
    li = {re.search(r"<b>([^<]+)</b>", x)[1]: x for x in re.findall(r"<li><b>.*?</li>", html)}
    assert "3 mağazada eyni qiymət: <span>2.80\u00a0₼</span>" in li["Azərsüd Süd 3.2% 1 l"] and "Ən ucuz" not in li["Azərsüd Süd 3.2% 1 l"]
    assert "Ən ucuz: <span>Araz</span>, <span>Bravo<sup>W</sup></span> — <span>2.50\u00a0₼</span>" in li["Milla Süd 2.5% 1 l"]
    assert "<span>OBA 2.90\u00a0₼</span>" in li["Milla Süd 2.5% 1 l"]
    assert "Ən ucuz: <span>Bravo 2.70\u00a0₼<sup>W</sup></span>" in li["Atena Süd 3.2% 0.5 l"]
    assert "5.40\u00a0₼/L" in li["Atena Süd 3.2% 0.5 l"]   # vahid qiymət (0.5 l → 1 L)
    # hər qiymət iki onluq rəqəmlə və ₼-dan əvvəl bölünməz boşluqla (₼ ayrı sətrə keçmir)
    text = re.sub(r"<[^>]+>", "", html)
    assert re.findall(r"\d+\.\d\d\u00a0₼", text) and not re.search(r"(?<!\d\.\d\d)\u00a0₼|\d ₼", text)
    assert "3-ü bir neçə mağazada" in html   # "3-i" yox: üç → 3-ü
    assert "səbətə əlavə et" in html and "siyahıya" not in html   # saytdakı ad: Səbət


@node
def test_single_subcategory_group_has_no_duplicate_page(tmp_path):
    out = _build(tmp_path, _db())
    assert not (out / "qiymetler" / "corek" / "corek.html").exists()   # tək alt növ = bütün qrup: eyni məzmunlu ikinci səhifə yoxdur
    grp = (out / "qiymetler" / "corek" / "index.html").read_text(encoding="utf-8")
    assert grp.count("<li><b>") == 5   # qrup səhifəsi boş qalmır, siyahını özü göstərir
    sm = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert "corek/corek.html" not in sm and "qiymetler/corek/</loc>" in sm and "qiymetler/sud/pendir.html" in sm
    hub = (out / "qiymetler" / "index.html").read_text(encoding="utf-8")
    assert 'href="corek/corek.html"' not in hub and 'href="sud/pendir.html"' in hub


def test_manifest_id_and_scope_match_site_path():
    m = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
    canon = re.search(r'<link rel="canonical" href="([^"]+)">', (ROOT / "index.html").read_text(encoding="utf-8"))[1]
    # id sayt kökünə (origin) görə həll olunur: "./" → https://<user>.github.io/ (eyni domendəki başqa tətbiqlərlə eyni olardı)
    assert m["id"] == urlparse(canon).path and m["start_url"] == "./" and m["scope"] == "./"
    assert all(urljoin(canon, s["url"]).startswith(canon) for s in m.get("shortcuts", []))


SW_HARNESS = r"""
const vm=require("vm"),fs=require("fs"),store=new Map(),L={};let net;
const caches={open:async n=>{if(!store.has(n))store.set(n,new Map());const m=store.get(n);
    return{put:async(k,r)=>{m.set(typeof k==="string"?k:k.url,r)},addAll:async()=>{},keys:async()=>[...m.keys()]}},
  match:async(q,o)=>{const u=new URL(typeof q==="string"?q:q.url);if(o&&o.ignoreSearch)u.search="";for(const m of store.values()){const r=m.get(u.href);if(r)return r.clone()}},
  keys:async()=>[...store.keys()],delete:async n=>store.delete(n)};
const self={addEventListener:(t,f)=>L[t]=f,registration:{scope:"https://x.test/q/"},skipWaiting(){},clients:{claim(){}}};
vm.runInContext(fs.readFileSync(process.argv[1],"utf8"),
  vm.createContext({self,caches,fetch:q=>net(q),Response,URL,setTimeout,clearTimeout,location:{origin:"https://x.test"},console}));
async function go(url,mode){let p=null;const w=[];L.fetch({request:{url,method:"GET",mode:mode||"cors"},respondWith:x=>p=x,waitUntil:x=>w.push(x)});
  if(!p)return null;const r=await p;await Promise.all(w);return[r.status,r.type==="error"?"":await r.text()];}
const ok=t=>()=>Promise.resolve(new Response(t,{status:200})),code=(t,s)=>()=>Promise.resolve(new Response(t,{status:s})),off=()=>Promise.reject(new TypeError("offline"));
(async()=>{const R={};const P="https://x.test/q/qiymetler/sud/";
  net=ok("təzə");R.fresh=await go(P+"?utm=1","navigate");R.keys=[...store.values()].flatMap(m=>[...m.keys()]);
  net=off;R.offline=await go(P,"navigate");
  net=code("xəta",503);R.down=await go(P,"navigate");
  net=off;R.uncached=await go("https://x.test/q/qiymetler/et/","navigate");
  net=code("yoxdur",404);R.missing=await go("https://x.test/q/yox.html","navigate");net=off;R.missingOff=await go("https://x.test/q/yox.html","navigate");
  (await caches.open("hu-shell-v1")).put("https://x.test/q/assets/twemoji.js",new Response("köhnə"));net=ok("yeni");R.js=await go("https://x.test/q/assets/twemoji.js");
  net=ok("şəkil");R.img1=await go("https://x.test/q/assets/fluent/1.webp");net=off;R.img2=await go("https://x.test/q/assets/fluent/1.webp");
  R.ext=await go("https://images.openfoodfacts.org/a.jpg");
  console.log(JSON.stringify(R));})();
"""


@node
def test_service_worker_network_first_offline_page_and_5xx_fallback():
    r = subprocess.run(["node", "-e", SW_HARNESS, str(ROOT / "sw.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]
    R = json.loads(r.stdout)
    assert R["fresh"] == [200, "təzə"] and "https://x.test/q/qiymetler/sud/" in R["keys"]
    assert not any("utm" in k for k in R["keys"])                       # ?utm=... ayrıca nüsxə yaratmır
    assert R["offline"] == [200, "təzə"] and R["down"] == [200, "təzə"]  # internetsiz və 5xx: son saxlanmış nüsxə
    assert R["uncached"][0] == 503 and "İnternet" in R["uncached"][1] and 'href="https://x.test/q/"' in R["uncached"][1]
    assert R["missing"][0] == 404 and R["missingOff"][0] == 503          # 404 keşə yazılmır
    assert R["js"] == [200, "yeni"]                                       # skript keşdə olsa da təzəsi (index.html ilə uyğun)
    assert R["img1"] == [200, "şəkil"] and R["img2"] == [200, "şəkil"]
    assert R["ext"] is None                                               # xarici ünvanlara toxunulmur
