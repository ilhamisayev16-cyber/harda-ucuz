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
