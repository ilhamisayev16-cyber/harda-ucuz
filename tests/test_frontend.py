"""index.html-in ön tərəf məntiqi (node-da, saxta DOM ilə): ucuzlayanlar zolağı, ölçü oxunuşu, ən ucuz mağaza, səbət mətni."""
import json
import subprocess
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# site_harness.js-dən fərqli: getElementById hər id üçün eyni obyekti qaytarır (innerHTML oxunsun), daxili funksiyalar da açılır
LOADER = r"""
const fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(process.argv[1],'utf8');
const js=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).pop();
const els={}, mkEl=()=>({classList:{toggle(){},add(){},remove(){},contains(){return false}},style:{},dataset:{},setAttribute(){},
  addEventListener(){},querySelectorAll:()=>[],querySelector:()=>mkEl(),scrollIntoView(){},blur(){},innerHTML:"",textContent:"",hidden:false});
const ctx={console,TextEncoder,document:{addEventListener(){},getElementById:id=>els[id]||(els[id]=mkEl()),querySelector:mkEl,querySelectorAll:()=>[]},
  localStorage:{getItem:()=>null,setItem(){}},addEventListener(){},fetch:async()=>({ok:false,status:0}),setTimeout:()=>0,clearTimeout(){},
  location:{hash:''},window:{scrollTo(){}},innerWidth:390,performance};
vm.createContext(ctx);
vm.runInContext(js+`;globalThis.__t={setDB(d){DB=sane(d);stores=DB.stores;GL=DB.groups;GM=Object.fromEntries(GL.map(g=>[g.id,g]));for(const k in GROUPS)delete GROUPS[k];},
  renderDrops:()=>renderDrops(), groups:g=>groups(g), card:g=>card(g), cheap:g=>cheap(g), parseSize:n=>parseSize(n), tokens:f=>[...tokens(fold(f))],
  favText:()=>favText(), setFav:f=>{FAV=f;}, favKey:g=>favKey(g), cats:()=>DB.categories, histHtml:(o,h,d)=>histHtml(o,h,d)};`,ctx);
const T=ctx.__t, raw=JSON.parse(fs.readFileSync(0,'utf8'));
"""


def _node(code, db):
    r = subprocess.run(["node", "-e", LOADER + code, str(ROOT / "index.html")], input=json.dumps(db),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def _db(cats, groups):
    stores = sorted({s for c in cats.values() for s in c["stores"]})
    return {"last_updated": "25.10.2026 10:00", "stores": stores, "groups": groups,
            "categories": {k: {"name": v.get("name", k), "stores": v["stores"]} for k, v in cats.items()}}


def test_zero_space_decimal_sizes_are_read_as_decimals():
    # Rahat / Araz adlarında "0 5 Lt" = 0.5 L (əvvəl 5 L oxunurdu: ölçü, vahid qiymət və uyğunlaşdırma səhv idi)
    out = _node("""console.log(JSON.stringify([
  T.parseSize("Rahat Qazsiz Su 0 5 Litr"), T.parseSize("Vodka Xortitsa Platinum 0 7l"), T.parseSize("Superfresh Milfoy Xəmir 0 5 Kq"),
  T.parseSize("Coca-cola 1.5l"), T.parseSize("Milla Süd 2 5% 1l"), T.tokens("Pive Tuborq Gold Şüşə 5 6% 0 5 Lt"), T.tokens("Pive Tuborq Gold Şüşə 0.5 Lt")]));""",
                _db({"su": {"stores": {"Rahat": [{"name": "x", "wolt_price": 1}]}}}, [{"id": "iceckiler", "name": "İçkilər", "cats": ["su"]}]))
    (water, vodka, dough, cola, milk, tk_space, tk_dot) = out
    assert (water["wv"], water["wu"]) == (0.5, "L")
    assert (vodka["wv"], vodka["wu"]) == (0.7, "L")
    assert (dough["wv"], dough["wu"]) == (0.5, "kq")
    assert (cola["wv"], cola["wu"]) == (1.5, "L")          # adi yazılış dəyişmir
    assert (milk["wv"], milk["wu"]) == (1, "L")
    assert sorted(tk_space) == sorted(tk_dot)              # uyğunlaşdırma sözlərində artıq "0" qalmır


def test_size_glued_to_abbreviation_dot():
    # Bazarstore / Araz: "Çubuq.100 Q", "Lim.500ml" — əvvəl ".100" = 0.1 q oxunurdu
    out = _node("""console.log(JSON.stringify([T.parseSize("Kuzya Qarğidali Çubuq.100 Q"), T.parseSize("Era Ov Təmizləyici Toz Lim.500ml"),
  T.parseSize("Dr.Oetker Vanil 1.5 q"), T.tokens("Kuzya Qarğidali Çubuq.100 Q"), T.tokens("Kuzya Qarğidali Çubuq 100 Q")]));""",
                _db({"su": {"stores": {"Rahat": [{"name": "x", "wolt_price": 1}]}}}, [{"id": "iceckiler", "name": "İçkilər", "cats": ["su"]}]))
    stick, cleaner, vanil, tk_dot, tk_space = out
    assert (stick["wv"], stick["wu"]) == (100, "q")
    assert (cleaner["wv"], cleaner["wu"]) == (500, "ml")
    assert (vanil["wv"], vanil["wu"]) == (1.5, "q")        # ondalıq ölçü dəyişmir
    assert sorted(tk_dot) == sorted(tk_space)


def test_best_block_names_every_store_that_ties_for_cheapest():
    def card(prices):
        return {"stores": {s: [{"name": "Azərsüd Süd 3.2% 1l", "price": p}] for s, p in prices.items()}}
    cats = {"a": card({"Bravo": 7.0, "OBA": 7.0, "Araz": 7.0, "Neptun": 8.0}),
            "b": card({"Bravo": 7.0, "OBA": 7.0, "Araz": 7.0, "Neptun": 7.0, "Rahat": 9.0}),
            "c": card({"Bravo": 7.0, "OBA": 7.0}),
            "d": card({"Bravo": 6.0, "OBA": 7.0})}
    groups = [{"id": k, "name": k, "cats": [k]} for k in cats]
    out = _node("""T.setDB(raw); console.log(JSON.stringify(["a","b","c","d"].map(k=>{ const h=T.card(T.groups(k)[0]);
  return h.match(/<div class="best">[\\s\\S]*?<\\/div>/)[0].replace(/<[^>]+>/g," ").replace(/\\s+/g," ").trim(); })));""", _db(cats, groups))
    assert out[0].startswith("Ən ucuz: Bravo, OBA, Araz 1.00 ₼ qənaət")
    assert out[1].startswith("4 mağazada eyni qiymət 2.00 ₼ qənaət")
    assert out[2].startswith("Ən ucuz: Bravo, OBA mağazalar arasında fərq yoxdur")
    assert out[3].startswith("Ən ucuz: Bravo 1.00 ₼ qənaət")


def _drop(name, p, pp, days=1, own=True):
    return {"name": name, ("price" if own else "wolt_price"): p, "pp": pp, "pd": (date.today() - timedelta(days=days)).isoformat()}


def test_price_drop_strip_dedupes_product_lines_and_prefers_food():
    cats = {
        "pecenye": {"stores": {"Bazarstore": [_drop("Ulker Cizi Citir Kreker 50 Q Pend Biber", 0.6, 1.2),
                                               _drop("Ulker Cizi Citir Kreker 50 Q Pendir Soga", 0.6, 1.2),
                                               _drop("Biskvit Ozmo 30 qr", 0.9, 1.1)]}},
        "konserv": {"stores": {"Araz": [_drop("Dobroflot Qorbuşa Natural 245qr", 2.55, 5.05)],
                               "SPAR": [_drop("Dobroflot Qorbuşa Natural 245qr", 2.55, 5.05, own=False)]}},
        "sud": {"stores": {"Bravo": [_drop("Süd Atena 1l", 2.0, 2.5, own=False)]}},
        "mesis": {"stores": {"Bravo": [_drop("Birpa Şirniyyat Maşası 0.80 mm AGN-142", 0.5, 1.0, own=False)]}},
        "tras": {"stores": {"Araz": [_drop("Gillette Fus.pow.proglid Style Raz+1cart", 16.59, 33.15)]}},
        "kefir": {"stores": {"Neptun": [_drop("Kefir Köhnə 1l", 1.0, 1.5, days=20)],    # 7 gündən köhnə
                             "Rahat": [{**_drop("Kefir Arxiv 1l", 0.5, 1.0, own=False), "stale": True}]}},   # arxiv qiymət
    }
    groups = [{"id": "sirniyyat", "name": "Şirniyyat", "cats": ["pecenye"]}, {"id": "konserv", "name": "Konserv", "cats": ["konserv"]},
              {"id": "sud", "name": "Süd", "cats": ["sud", "kefir"]}, {"id": "ev", "name": "Ev", "cats": ["mesis"]},
              {"id": "gigiyena", "name": "Gigiyena", "cats": ["tras"]}]
    out = _node("""T.setDB(raw); T.renderDrops(); const h=ctx.document.getElementById("drops").innerHTML;
console.log(JSON.stringify([...h.matchAll(/data-q="([^"]*)"/g)].map(m=>m[1])));""", _db(cats, groups))
    assert len(out) == 4
    assert sum("Ulker Cizi" in n for n in out) == 1          # eyni aksiya (variantlar) bir dəfə
    assert sum("Dobroflot" in n for n in out) == 1           # Araz + SPAR eyni məhsul bir dəfə
    assert "Kefir Köhnə 1l" not in out and "Kefir Arxiv 1l" not in out
    assert out[:3] == ["Ulker Cizi Citir Kreker 50 Q Pend Biber", "Dobroflot Qorbuşa Natural 245qr", "Süd Atena 1l"]   # əvvəl ərzaq (alt növlər müxtəlif)
    assert out[3] in ("Biskvit Ozmo 30 qr",)                 # ərzaq çatırsa qeyri-qida (Gillette, maşa) zolağa düşmür


def test_cheapest_store_and_basket_text_ignore_archived_prices():
    cats = {"sud": {"stores": {"Bravo": [{"name": "Süd Atena 1l", "wolt_price": 2.0, "stale": True}],
                               "OBA": [{"name": "Süd Atena 1l", "price": 2.5}],
                               "Araz": [{"name": "Süd Atena 1l", "price": 2.7}]}},
            "banan": {"stores": {"Araz": [{"name": "Banan kq", "price": 2.6}], "OBA": [{"name": "Banan kq", "price": 2.9}]}}}
    groups = [{"id": "sud", "name": "Süd", "cats": ["sud"]}, {"id": "meyve", "name": "Meyvə", "cats": ["banan"]}]
    out = _node("""T.setDB(raw); const g=T.groups("sud")[0], b=T.groups("meyve")[0];
T.setFav([{k:T.favKey(g),t:"sud",n:g.name,q:2},{k:T.favKey(b),t:"meyve",n:b.name,q:1}]);
console.log(JSON.stringify({best:T.card(g).match(/Ən ucuz: (\\w+)/)[1], cheap:T.cheap(g), text:T.favText()}));""", _db(cats, groups))
    assert out["best"] == "OBA" and out["cheap"] == {"s": "OBA", "p": 2.5}   # Bravo-nun arxiv qiyməti "ən ucuz" deyil
    lines = out["text"].splitlines()
    assert lines[0] == "• Süd Atena 1l × 2 — OBA 5.00 ₼ (2.50 ₼)"      # sətrin cəmi + vahid qiymət
    assert lines[1] == "• Banan kq × 1 kq — Araz 2.60 ₼"
    assert "Hər məhsulu ən ucuz olduğu mağazadan: 7.60 ₼" in out["text"]   # tam səbət heç bir mağazada olmasa da


def test_archived_offer_is_not_highlighted_and_wolt_source_is_visible():
    cats = {"sud": {"stores": {
        "Bravo": [{"name": "Atena Süd 1l", "wolt_price": 2.5, "stale": True}],
        "OBA": [{"name": "Atena Süd 1l", "price": 2.5}],
        "Araz": [{"name": "Atena Süd 1l", "price": 3.0}],
    }}}
    groups = [{"id": "sud", "name": "Süd", "cats": ["sud"]}]
    html = _node('T.setDB(raw); console.log(JSON.stringify(T.card(T.groups("sud")[0])));', _db(cats, groups))
    assert 'class="o" data-s="Bravo"' in html
    assert 'class="o min" data-s="OBA"' in html
    assert "Wolt · filialdan asılıdır" in html
    assert "arxiv qiymət" in html


def test_implausible_prices_are_dropped_but_expensive_brands_kept():
    # Rahat-ın Wolt menyusundakı yazı səhvləri (2026-10): 1 kq / 1 L qiyməti eyni markadan ≥40 dəfə, marka azdırsa kateqoriyadan ≥100 dəfə baha
    temizlik = {"Rahat": [{"name": "Domestos 7 Expert Ultra Ağ 1 l", "wolt_price": 256.25},
                          {"name": "Domestos Sarı Limon 1 l", "wolt_price": 4.9}],
                "Bravo": [{"name": "Domestos Ultra Ağ 750 ml", "wolt_price": 3.99}, {"name": "Domestos Okean 1.5 l", "wolt_price": 6.5},
                          {"name": "Domestos Pink 500 ml", "wolt_price": 2.9}]}
    # baha marka: hamısı baha, öz markası ilə müqayisədə adi; ölçü yazı səhvi ("0.75ml" = 0.75 L) yoxlanmır
    serab = {"Rahat": [{"name": f"Gaja Barolo {y} 0.75 l", "wolt_price": p} for y, p in ((2015, 245.49), (2016, 230.0), (2017, 219.0), (2018, 199.0))]
             + [{"name": "Bottega Pinot Grigio 12% 0.75ml", "wolt_price": 32.0}]}
    # kateqoriyada markanın tayı yoxdur: kateqoriyanın medianı ilə (30 məhsul ~30 ₼/kq)
    usaq = {"Araz": [{"name": f"Fruto Sıyıq {i} 200 qr", "price": 5.0 + i / 10} for i in range(30)],
            "Rahat": [{"name": "Heinz Balqabaq-Gavalı Südli Qarğıdalı Kasa 170 qr", "wolt_price": 644.15},
                      {"name": "Hipp Orqanik Sıyıq 250 qr", "wolt_price": 12.5}]}
    cats = {"temizlik": {"stores": temizlik}, "serab": {"stores": serab}, "usaq_qida": {"stores": usaq}}
    groups = [{"id": k, "name": k, "cats": [k]} for k in cats]
    out = _node("""T.setDB(raw); console.log(JSON.stringify(Object.fromEntries(Object.entries(DBx()).map(([k,c])=>
  [k,Object.values(c.stores).flat().map(i=>i.name)]))));""".replace("DBx()", "T.cats()"),
                _db(cats, groups))
    assert "Domestos 7 Expert Ultra Ağ 1 l" not in out["temizlik"] and len(out["temizlik"]) == 4
    assert len(out["serab"]) == 5                                    # baha çaxır və "0.75ml" yazılışı toxunulmur
    assert "Heinz Balqabaq-Gavalı Südli Qarğıdalı Kasa 170 qr" not in out["usaq_qida"] and "Hipp Orqanik Sıyıq 250 qr" in out["usaq_qida"]
    assert len(out["usaq_qida"]) == 31


def test_price_history_panel_shows_full_dates_and_since_when():
    # mağaza sətrinə basanda: "12.10.2026: 25.00 ₼ → 13.10.2026: 23.00 ₼"; dəyişiklik yoxdursa "23.00 ₼ (13.10.2026)" (əvvəl "10.12" = 12 oktyabr idi)
    out = _node("""console.log(JSON.stringify([
  T.histHtml({p:23},[["2026-10-12",25],["2026-10-13",23]],"2026-10-25"),
  T.histHtml({p:23},[["2026-10-13",23]],"2026-10-25"),
  T.histHtml({p:21},[["2026-10-12",25],["2026-10-13",23]],"2026-10-25"),
  T.histHtml({p:23,pp:25,pd:"2026-10-13"},null,"2026-10-25"),
  T.histHtml({p:23},undefined,"2026-10-25")]));""",
                _db({"su": {"stores": {"Rahat": [{"name": "x", "wolt_price": 1}]}}}, [{"id": "iceckiler", "name": "İçkilər", "cats": ["su"]}]))
    m = lambda v: f"{v:.2f} ₼"
    assert out[0] == f"12.10.2026: {m(25)} → 13.10.2026: <b>{m(23)}</b>"
    assert out[1] == f"<b>{m(23)}</b> (13.10.2026)"
    assert out[2] == f"12.10.2026: {m(25)} → 13.10.2026: {m(23)} → 25.10.2026: <b>{m(21)}</b>"   # tarixçə geri qalıbsa indiki qiymət
    assert out[3] == f"{m(25)} → 13.10.2026: <b>{m(23)}</b>"
    assert out[4] == f"<b>{m(23)}</b> (25.10.2026) · qiymət dəyişikliyi qeydə alınmayıb"
