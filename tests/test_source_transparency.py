"""Source timestamps survive the static catalog; archived observations cannot price a basket."""
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")


def _db():
    return {
        "last_updated": "01.11.2026 19:00",
        "stores": ["Araz", "Bravo"],
        "groups": [{"id": "sud", "name": "Süd məhsulları", "cats": ["sud"]}],
        "categories": {"sud": {"name": "Süd", "stores": {
            "Araz": [{"name": "Atena Süd 1 L", "price": 2.5}],
            "Bravo": [{"name": "Atena Süd 1 L", "wolt_price": 2.0, "stale": True}],
        }}},
        "meta": {
            "Araz": {"updated": "01.11.2026 18:00", "last_success": "2026-11-01T18:00:00",
                     "last_attempt": "2026-11-01T18:00:00", "check_status": "ok", "source_type": "own+wolt", "auto_update": True},
            "Bravo": {"updated": "31.10.2026 06:00", "last_success": "2026-10-31T06:00:00",
                      "last_attempt": "2026-11-01T18:50:00", "check_status": "failed", "source_type": "wolt", "auto_update": True},
        },
    }


def _node(db, code):
    script = f"""const api=require({json.dumps(str(ROOT / 'tests' / 'site_harness.js'))})({json.dumps(str(ROOT / 'index.html'))});
const raw=JSON.parse(require('fs').readFileSync(0,'utf8'));
{code}
"""
    run = subprocess.run(["node", "-e", script], input=json.dumps(db), capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-1500:]
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_source_timestamps_survive_manifest_shard_and_browser(tmp_path):
    db = _db()
    db["meta"]["Bravo"]["raw_html"] = '<img src=x onerror="alert(1)">'
    source = tmp_path / "prices.json"
    source.write_text(json.dumps(db), encoding="utf-8")
    out = tmp_path / "site"
    run = subprocess.run(["node", str(ROOT / "scripts" / "build_site.js"), "--prices", str(source), "--out", str(out)],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-1500:]
    catalog = json.loads((out / "data" / "catalog.json").read_text())
    shard = json.loads((out / "data" / catalog["files"]["sud"]).read_text())
    expected = copy.deepcopy(db["meta"])
    del expected["Bravo"]["raw_html"]
    assert catalog["meta"] == shard["meta"] == expected
    result = _node(catalog, "const d=api.sane(raw); console.log(JSON.stringify({meta:d.meta,html:api.sourceDetails(d)}));")
    assert result["meta"] == expected
    assert "31.10.2026 06:00" in result["html"]
    assert "Son cəhd: 01.11.2026 18:50" in result["html"]
    assert "Son yoxlama alınmadı" in result["html"]
    assert "01.11.2026 19:00" not in result["html"]  # global rebuild cannot refresh a failed retailer
    assert "https://www.bravosupermarket.az/special-offers/" in result["html"]
    assert "qiymətlər avtomatik köçürülmür" in result["html"]
    product_html = next((out / "mehsullar").glob("*.html")).read_text()
    description = re.search(r'<meta name="description" content="([^"]*)"', product_html)[1]
    assert "Bravo 2.00\u00a0₼ (arxiv)" in description
    assert "Araz 2.50\u00a0₼ (arxiv)" not in description


def test_untrusted_metadata_cannot_create_source_links_or_markup():
    db = _db()
    db["meta"]["Bravo"].update({"source_type": '<img src=x onerror="alert(1)">', "updated": "<script>alert(1)</script>",
                                 "last_success": "bad", "check_status": "<b>ok</b>", "url": "javascript:alert(1)", "auto_update": "false"})
    db["meta"]["Unknown"] = {"source_type": "own", "updated": "01.11.2026 18:00"}
    result = _node(db, "const d=api.sane(raw); console.log(JSON.stringify({meta:d.meta,html:api.sourceDetails(d)}));")
    assert result["meta"]["Bravo"] == {"last_attempt": "2026-11-01T18:50:00"}
    assert "Unknown" not in result["meta"]
    assert "<script>" not in result["html"] and "onerror" not in result["html"] and "javascript:" not in result["html"]


@pytest.mark.parametrize("all_stale", [False, True])
def test_archived_prices_cannot_win_or_complete_a_basket(all_stale):
    db = _db()
    if all_stale:
        db["categories"]["sud"]["stores"]["Araz"][0]["stale"] = True
    result = _node(db, """api.setDB(api.sane(raw)); const g=api.groups('sud')[0];
api.setFav([{k:api.favKey(g),t:g.t,n:g.name,q:2}]);
const b=api.basket(), split=api.splitBasket([{f:{q:2},g}],raw.stores);
console.log(JSON.stringify({n:g.n,save:g.save,best:api.bestOf(g),full:b.full,part:b.part,ideal:b.ideal,text:api.favText(),split}));""")
    if all_stale:
        assert result["n"] == 0 and result["save"] == 0
        assert "Ən ucuz" not in result["best"] and "arxiv" in result["best"]
        assert result["full"] == result["part"] == result["split"] == []
        assert result["ideal"] is None and "aktual qiymət yoxdur" in result["text"]
        assert "Səbətin cəmi" not in result["text"]
    else:
        assert result["n"] == 1
        assert "Ən ucuz: Araz" in result["best"] and "Ən ucuz: Bravo" not in result["best"]
        assert [(x["s"], x["t"]) for x in result["full"]] == [("Araz", 5.0)]
        assert result["ideal"] == 5.0 and result["split"][0]["stores"] == ["Araz"]
        assert "Bravo 4.00" not in result["text"]


@pytest.mark.parametrize("archived_price", [2.5, 2.7])
def test_archived_tie_cannot_win_category_stats_or_get_price_highlight(archived_price):
    db = _db()
    db["stores"] = ["Bravo", "Araz", "OBA"]
    db["categories"]["sud"]["stores"]["Bravo"][0]["wolt_price"] = archived_price
    db["categories"]["sud"]["stores"]["OBA"] = [{"name": "Atena Süd 1 L", "price": 2.7}]
    result = _node(db, """api.setDB(api.sane(raw)); const g=api.groups('sud')[0];api.openCat('sud');
console.log(JSON.stringify({champ:api.el('champ').textContent,archive:api.offer(g,'Bravo'),live:api.offer(g,'Araz')}));""")
    assert "Ən sərfəli: Araz" in result["champ"]
    assert 'class="o min"' not in result["archive"] and 'class="o max"' not in result["archive"]
    assert 'class="o min"' in result["live"]


def test_existing_stores_official_campaign_links_explain_conditions():
    db = _db()
    db["stores"].extend(["OBA", "Rahat"])
    result = _node(db, "console.log(JSON.stringify(api.sourceDetails(api.sane(raw))));")
    assert "https://rahatmarket.az/az/aksiyalar/rahat-market" in result
    assert "hansı filiallara aid olduğunu" in result
    assert "OBA Plus şərtlərini yoxlayın" in result
    link = _node(db, "console.log(JSON.stringify(api.shopLink('Rahat',{w:true,n:'Süd 1 L'})));")
    assert link == {"u": "https://rahatmarket.az/az/aksiyalar/rahat-market", "x": 0, "t": "kampaniyalar"}
