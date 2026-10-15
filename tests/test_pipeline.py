import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import scraper as S
import sources as SRC

ROOT = Path(__file__).resolve().parent.parent
PRICES = json.load(open(ROOT / "data" / "prices.json", encoding="utf-8"))
HIST = json.load(open(ROOT / "data" / "history.json", encoding="utf-8"))


def mini(store="Neptun", n=300, price=1.0, wolt=True):
    key = "wolt_price" if wolt else "price"
    items = [{"name": f"Məhsul {i}", key: price} for i in range(n)]
    return {"stores": [store], "groups": [], "categories": {"sud": {"name": "Süd", "stores": {store: items}}}, "meta": {}}


# 9. mövcud formatlar qorunur
def test_existing_prices_json_format():
    ok, errs = SRC.validate_prices(PRICES, SRC.store_counts(PRICES))
    assert ok, errs
    assert set(PRICES) >= {"stores", "groups", "categories", "last_updated"}
    for c in PRICES["categories"].values():
        assert set(c) >= {"name", "stores"}


def test_existing_history_json_format():
    assert list(HIST) == ["h"]
    for k, v in list(HIST["h"].items())[:500]:
        assert len(k) == 16 and all(len(p) == 2 and isinstance(p[1], (int, float)) for p in v)


# 8. tarixçə əvvəlki kimi işləyir
def test_history_hash_stable_and_tracking():
    assert S._hk("Bravo", "Süd 1 L") == S._hk("Bravo", "Süd 1 L") and len(S._hk("Bravo", "x")) == 16
    d = mini("Araz", 3, 2.0, wolt=False)
    hist = {}
    old = S.track_changes("Araz", d, hist)
    items = [{"name": "Məhsul 0", "price": 1.5}, {"name": "Məhsul 1", "price": 2.0}]
    S.mark_changes(old, items, "Araz", hist, "2026-10-16", "2026-10-15")
    assert items[0]["pp"] == 2.0 and items[0]["pd"] == "2026-10-16" and "pp" not in items[1]
    assert hist[S._hk("Araz", "Məhsul 0")] == [["2026-10-15", 2.0], ["2026-10-16", 1.5]]


# 6. boş / kəskin azalmış nəticə köhnə datanı silmir
def test_empty_result_keeps_old_data():
    d = mini()
    before = copy.deepcopy(d)
    assert S.apply_to_data({}, {}, "Neptun", d, {}) is False
    assert d["categories"] == before["categories"]


def test_sharp_drop_keeps_old_data():
    d = mini(n=1000)
    new = {"sud": [{"name": "Y", "wolt_price": 1.0}] * 10}
    assert S.apply_to_data({}, new, "Neptun", d, {}) is False
    assert len(d["categories"]["sud"]["stores"]["Neptun"]) == 1000


def test_invalid_data_never_overwrites_file(tmp_path):
    out = tmp_path / "prices.json"
    good = mini()
    assert S._save(good, out) and out.exists()
    saved = out.read_text(encoding="utf-8")
    bad = copy.deepcopy(good)
    bad["categories"]["sud"]["stores"]["Neptun"][0]["wolt_price"] = -5
    assert S._save(bad, out) is False
    assert out.read_text(encoding="utf-8") == saved
    assert not list(tmp_path.glob("*.tmp"))


# Wolt söndürmə açarı
def test_wolt_switch_env_and_store_flag():
    assert SRC.wolt_enabled("Bravo", {}) is True
    for v in ("0", "false", "OFF", "no"):
        assert SRC.wolt_enabled("Bravo", {"WOLT_ENABLED": v}) is False


def test_wolt_off_sends_no_requests_and_keeps_data(tmp_path, monkeypatch):
    out = tmp_path / "prices.json"
    d = mini("Neptun", 300, 1.5)
    d["meta"]["Neptun"] = {"updated": "10.10.2026 07:00"}
    S._save(d, out)
    (tmp_path / "history.json").write_text('{"h":{}}')
    def boom(*a, **k): raise AssertionError("Wolt söndürülüb: sorğu göndərilməməlidir")
    for fn in ("scrape_wolt", "scrape_wolt_full", "scrape_wolt_multi", "_session"):
        monkeypatch.setattr(S, fn, boom)
    monkeypatch.setenv("WOLT_ENABLED", "0")
    monkeypatch.setattr("sys.argv", ["scraper.py", "--store", "neptun", "--out", str(out)])
    S.main()
    r = json.load(open(out, encoding="utf-8"))
    items = r["categories"]["sud"]["stores"]["Neptun"]
    assert len(items) == 300                                   # silinmədi
    assert all(i["wolt_price"] == 1.5 and i["stale"] for i in items)   # qiymət dəyişmədi, "arxiv" işarəli
    assert r["meta"]["Neptun"]["auto_update"] is False and r["meta"]["Neptun"]["updated"] == "10.10.2026 07:00"
    assert all("pp" not in i for i in items)                   # keçmiş qiymət "dəyişiklik" kimi göstərilmir


def test_wolt_off_own_plus_wolt_store_keeps_archived_wolt_items():
    d = S.empty_data()
    d["categories"]["sud"]["stores"]["OBA"] = [{"name": "A", "price": 1.0, "wolt_price": 1.1}, {"name": "OnlyWolt", "wolt_price": 2.0}]
    own = {"sud": [{"name": "A", "price": 1.2}]}
    assert S.apply_to_data(own, {}, "OBA", d, {}, wolt_on=False)
    items = {i["name"]: i for i in d["categories"]["sud"]["stores"]["OBA"]}
    assert items["A"]["price"] == 1.2 and "stale" not in items["A"]
    assert items["OnlyWolt"]["wolt_price"] == 2.0 and items["OnlyWolt"]["stale"] is True


def test_failed_run_keeps_previous_files(tmp_path, monkeypatch):
    out = tmp_path / "prices.json"
    S._save(mini("Neptun", 300), out)
    (tmp_path / "history.json").write_text('{"h":{"abc":[["2026-10-01",1.0]]}}')
    b1, b2 = out.read_bytes(), (tmp_path / "history.json").read_bytes()
    monkeypatch.setattr(S, "scrape_wolt", lambda s: {})        # Wolt boş qaytardı
    monkeypatch.setattr("sys.argv", ["scraper.py", "--store", "neptun", "--out", str(out)])
    S.main()
    r = json.load(open(out, encoding="utf-8"))
    assert len(r["categories"]["sud"]["stores"]["Neptun"]) == 300
    assert json.load(open(tmp_path / "history.json"))["h"]["abc"] == [["2026-10-01", 1.0]]


# 10. kateqoriyalaşdırma reqressiya
@pytest.mark.parametrize("name,cat", [("Dobry Alma şirəsi 1 L", "sirə"), ("Coca-Cola 1 L", "kola"), ("Nescafe Gold 190 q", "qəhvə")])
def test_classification_smoke(name, cat):
    got = S.classify(name)
    assert got in S.CATEGORIES and got != "diger", (name, got)


def test_classification_corpus_from_real_data():
    """Real datadakı məhsulların 'digər' payı kiçik qalır (təsnifat pozulmayıb)."""
    n = dg = 0
    for cid, c in PRICES["categories"].items():
        for items in c["stores"].values():
            for it in items:
                n += 1; dg += cid == "diger"
    assert n > 10000 and dg / n < 0.05


# 7. yeni JSON ilə index.html uyğunluğu (node varsa)
@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_index_html_reads_new_and_old_json(tmp_path):
    d = copy.deepcopy(PRICES)
    for c in d["categories"].values():                         # yüngül nüsxə
        for s in c["stores"]:
            c["stores"][s] = c["stores"][s][:25]
    cid = next(k for k, c in d["categories"].items() if c["stores"].get("Bravo"))
    d["categories"][cid]["stores"]["Bravo"][0].update({"stale": True})
    d["meta"] = {"Bravo": {"source_type": "wolt-arxiv", "auto_update": False, "last_success": None}}
    f = tmp_path / "db.json"; f.write_text(json.dumps(d, ensure_ascii=False))
    js = f"""const api=require({json.dumps(str(ROOT / 'tests' / 'site_harness.js'))})({json.dumps(str(ROOT / 'index.html'))});
const db=JSON.parse(require('fs').readFileSync({json.dumps(str(f))},'utf8'));
for(const old of [true,false]){{
  const D=JSON.parse(JSON.stringify(db)); if(old) for(const c of Object.values(D.categories)) for(const s in c.stores) for(const it of c.stores[s]){{delete it.stale}}
  api.setDB(D); let n=0; for(const g of api.GL()) n+=api.groups(g.id).length;
  if(!(n>0)) throw new Error('qrup yoxdur'); console.log('ok',old,n);
}}"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and r.stdout.count("ok") == 2, r.stderr[-500:]


# ── ad təmizliyi, dublikatlar, şəkil linkləri ──
def test_clean_name():
    assert S.clean_name("FAIRY LIMON MAYE QABYUYAN , 750 ml") == "Fairy Limon Maye Qabyuyan, 750 ml"
    assert S.clean_name("Princessa Nuri Zavtrak V Benqali ,") == "Princessa Nuri Zavtrak V Benqali"
    assert S.clean_name("Crystalex  Maye ( Limon )  750 ml") == "Crystalex Maye (Limon) 750 ml"
    assert S.clean_name("Coca-Cola 1 L") == "Coca-Cola 1 L"


def test_dedupe_keeps_own_then_cheaper_and_distinct_sizes():
    items = [{"name": "Vernel 1.44 L Lale", "price": 8.99}, {"name": "Vernel 1,44 L Lalə", "price": 5.99},
             {"name": "Su 1.5 L", "price": 1.0}, {"name": "Su 15 L", "price": 5.0},
             {"name": "Klar Maye 500ml", "wolt_price": 2.49}, {"name": "KLAR MAYE, 500 ml", "price": 3.99}]
    out = S.dedupe(items)
    assert [i["name"] for i in out] == ["Vernel 1,44 L Lalə", "Su 1.5 L", "Su 15 L", "KLAR MAYE, 500 ml"]


def test_tidy_cleans_old_data_and_drops_images():
    d = mini("OBA", 2, 1.0, wolt=False)
    d["categories"]["sud"]["stores"]["OBA"] = [{"name": "Süd , 1 l", "price": 1.2, "img": "https://x/y.png"},
                                               {"name": "Süd, 1 l", "price": 1.1}]
    S.tidy(d)
    assert d["categories"]["sud"]["stores"]["OBA"] == [{"name": "Süd, 1 l", "price": 1.1}]


def test_apply_to_data_cleans_names_and_keeps_change_tracking():
    d = S.empty_data()
    d["categories"]["sud"]["stores"]["Neptun"] = [{"name": "Süd Atena , 1 l", "wolt_price": 2.0}]
    new = {"sud": [{"name": "Süd Atena , 1 l", "wolt_price": 1.5}, {"name": "Süd  Atena, 1 l", "wolt_price": 1.6}]}
    assert S.apply_to_data({}, new, "Neptun", d, {})
    items = d["categories"]["sud"]["stores"]["Neptun"]
    assert len(items) == 1 and items[0]["name"] == "Süd Atena, 1 l" and items[0]["wolt_price"] == 1.5
    assert items[0]["pp"] == 2.0                               # köhnə (təmizlənməmiş) adla da qiymət dəyişikliyi tapılır


def test_no_image_links_written():
    _, e = S._wolt_entry({"name": "Süd 1 L", "price": 199, "image": {"url": "https://img/x.png"}})
    assert e == {"name": "Süd 1 L", "wolt_price": 1.99}


# ── öz sayt ↔ Wolt birləşdirmə: ölçü, diakritika, dad/rəng ──
def test_merge_own_wolt_needs_same_size():
    own = [{"name": "Süd Atena 1 L", "price": 2.6}]
    wolt = [{"name": "Atena Süd 0.5 L", "wolt_price": 1.5}, {"name": "Atena Süd 1000 ml", "wolt_price": 2.7}]
    out = S.merge_own_wolt(own, wolt)
    assert out[0] == {"name": "Süd Atena 1 L", "price": 2.6, "wolt_price": 2.7}
    assert {"name": "Atena Süd 0.5 L", "wolt_price": 1.5} in out and len(out) == 2   # 0.5 L itmir


def test_merge_own_wolt_folds_diacritics_and_rejects_variants():
    own = [{"name": "GUNEBAXAN YAGI ATENA, 1 l", "price": 4.0}, {"name": "Crystalex Qabyuyan Maye Limon 450ml", "price": 2.49},
           {"name": "Chivas Regal Viski 18 Yaş 700ml", "price": 163.0}]
    wolt = [{"name": "Atena Günəbaxan yağı 1 L", "wolt_price": 4.3}, {"name": "Crystalex Qabyuyan Maye Alma 450ml", "wolt_price": 2.25},
            {"name": "Chivas Regal Viski 12 Yaş 700 ml", "wolt_price": 160.0}]
    out = {i["name"]: i for i in S.merge_own_wolt(own, wolt)}
    assert out["GUNEBAXAN YAGI ATENA, 1 l"].get("wolt_price") == 4.3
    assert "wolt_price" not in out["Crystalex Qabyuyan Maye Limon 450ml"]     # Limon ≠ Alma
    assert "wolt_price" not in out["Chivas Regal Viski 18 Yaş 700ml"]          # 18 ≠ 12
    assert len(out) == 5


def test_merge_own_wolt_rejects_far_prices():
    out = S.merge_own_wolt([{"name": "Prezident Kərə Yağı 82% 1kq", "price": 38.1}], [{"name": "Prezident Kərə Yağı 82% 1 kg", "wolt_price": 7.65}])
    assert "wolt_price" not in out[0] and len(out) == 2


# ── vaxt: Bakı vaxtı ──
def test_times_are_baku_time():
    from datetime import timedelta
    assert SRC.now().utcoffset() == timedelta(hours=4)
    d = S.empty_data()
    assert S.apply_to_data({}, {"sud": [{"name": "Məhsul 0", "wolt_price": 1.0}]}, "Neptun", d, {})
    from datetime import datetime
    upd = datetime.strptime(d["meta"]["Neptun"]["updated"], "%d.%m.%Y %H:%M")
    assert abs(upd - SRC.now().replace(tzinfo=None)) < timedelta(minutes=2)


# ── sayt qurma: hazır kartlar, statik səhifələr, sitemap (node varsa) ──
@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_build_site(tmp_path):
    d = copy.deepcopy(PRICES)
    for c in d["categories"].values():                         # yüngül nüsxə
        for s in c["stores"]:
            c["stores"][s] = c["stores"][s][:40]
    src = tmp_path / "prices.json"; src.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(ROOT / "scripts" / "build_site.js"), "--prices", str(src), "--out", str(tmp_path / "site"),
                        "--site", "https://example.org/q/"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    assert "⚠" not in r.stdout + r.stderr                      # hazır kartlar brauzerin hesabladığı ilə eynidir
    g = json.load(open(tmp_path / "site" / "data" / "groups.json", encoding="utf-8"))
    assert g["v"] == d["last_updated"] and len(g["s"]) == 16
    assert set(g["g"]) == {x["id"] for x in d["groups"] if any(d["categories"].get(c, {}).get("stores", {}).get(s) for c in x["cats"] for s in d["stores"])}
    for p in g["g"].values():
        ix = [i for m in p["m"] for i in m]
        assert len(ix) == len(set(ix)) and all(0 <= i < p["n"] for i in ix)
    sm = (tmp_path / "site" / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://example.org/q/qiymetler/</loc>" in sm and sm.count("<url>") > 20
    page = (tmp_path / "site" / "qiymetler" / "sud" / "index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://example.org/q/qiymetler/sud/">' in page and "#/c/sud" in page and "<script" not in page


# ── böyük aksiya (50%+): Wolt qiyməti varsa o göstərilir ──
def test_big_own_discount_falls_back_to_wolt_price():
    own = [{"name": "Avokado əd", "price": 0.99, "rp": 3.49}, {"name": "Banan kq", "price": 2.0, "rp": 2.5},
           {"name": "Kivi kq", "price": 1.0, "rp": 4.0}]
    wolt = [{"name": "Avokado əd", "wolt_price": 1.99}, {"name": "Banan kq", "wolt_price": 2.2}]
    out = {i["name"]: i for i in S.merge_own_wolt(own, wolt)}
    assert out["Avokado əd"] == {"name": "Avokado əd", "wolt_price": 1.99}      # 72% aksiya → Wolt
    assert out["Banan kq"] == {"name": "Banan kq", "price": 2.0, "wolt_price": 2.2}   # kiçik aksiya: öz qiymət
    assert out["Kivi kq"] == {"name": "Kivi kq", "price": 1.0}                  # Wolt yoxdur: öz qiymət qalır
    assert len(out) == 3 and all("rp" not in i for i in out.values())


# ── BÖYÜK hərfli adlar ──
@pytest.mark.parametrize("raw,want", [
    ("DR.MILK KAUNAS XAMA 20% 350 GR", "Dr.Milk Kaunas Xama 20% 350 gr"),
    ("KLAR ULTRA YAG SOKUCU, 500 ml", "Klar Ultra Yag Sokucu, 500 ml"),
    ("TAC GİLƏZİ AĞ YUMURTA 10 ƏD", "Tac Giləzi Ağ Yumurta 10 əd"),
    ("Coca-Cola 1 L", "Coca-Cola 1 L"), ("XXL", "XXL"), ("Pencil Coloredi-252", "Pencil Coloredi-252")])
def test_all_caps_names_are_normalised(raw, want):
    assert S.clean_name(raw) == want


# ── "Digər"-dəki məhsulların yeri ──
def test_reassign_other_by_keyword_brand_word_and_duplicate():
    d = S.empty_data()
    st = d["categories"]
    st["siqaret"]["stores"]["Bravo"] = [{"name": f"Kent Nanotek {i}", "wolt_price": 5.0} for i in range(3)]
    st["konfet"]["stores"]["Bravo"] = [{"name": "Beyaz Trubka, 1 kg", "price": 3.0}]
    st["diger"]["stores"]["Bazarstore"] = [{"name": "Kent Nanotek Neo 4", "price": 5.2},       # brend → siqaret
                                           {"name": "St Skuter Sc001 530-12", "price": 40.0},  # açar söz → oyuncaq
                                           {"name": "Urojay Qapaq 82 Mm 20 Li", "price": 2.0},  # qeyri-qida → məişət
                                           {"name": "Bumbuz 1 Kq", "price": 4.0}]               # bilinmir → qalır
    st["diger"]["stores"]["Bravo"] = [{"name": "Beyaz Trubka , 1 kg", "price": 3.0}]          # eyni mağazada artıq var → silinir
    assert S.reassign_other(d) == 4
    assert [i["name"] for i in st["diger"]["stores"]["Bazarstore"]] == ["Bumbuz 1 Kq"] and st["diger"]["stores"]["Bravo"] == []
    assert {i["name"] for i in st["siqaret"]["stores"]["Bazarstore"]} == {"Kent Nanotek Neo 4"}
    assert st["oyuncaq"]["stores"]["Bazarstore"][0]["name"].startswith("St Skuter")
    assert st["mesis"]["stores"]["Bazarstore"][0]["name"].startswith("Urojay Qapaq")


def test_reassign_other_on_real_data_shrinks_other():
    d = copy.deepcopy(PRICES)
    n0 = sum(len(l) for l in d["categories"]["diger"]["stores"].values())
    S.reassign_other(d)
    n1 = sum(len(l) for l in d["categories"]["diger"]["stores"].values())
    assert n1 < n0 / 2 or n0 < 20
    ok, errs = SRC.validate_prices(d)
    assert ok, errs


# ── kartın adı: ən oxunaqlı üzv ──
@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_card_shows_most_readable_name(tmp_path):
    db = {"stores": ["OBA", "Bravo"], "groups": [{"id": "sud", "name": "Süd", "cats": ["qatilasdirilmis"]}],
          "categories": {"qatilasdirilmis": {"name": "Qatılaşdırılmış süd", "stores": {
              "OBA": [{"name": "QUSTIYAR QATILASDIRILMIS SUD, 370 g", "price": 2.89}],
              "Bravo": [{"name": "Qustiyar Qatılaşdırılmış Süd 370qr", "wolt_price": 2.7}]}}}}
    f = tmp_path / "db.json"; f.write_text(json.dumps(db, ensure_ascii=False))
    js = f"""const api=require({json.dumps(str(ROOT / 'tests' / 'site_harness.js'))})({json.dumps(str(ROOT / 'index.html'))});
api.setDB(JSON.parse(require('fs').readFileSync({json.dumps(str(f))},'utf8')));
const g=api.groups('sud'); console.log(JSON.stringify(g.map(x=>[x.name,Object.keys(x.offers).length])));"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    assert json.loads(r.stdout.strip()) == [["Qustiyar Qatılaşdırılmış Süd 370qr", 2]]
