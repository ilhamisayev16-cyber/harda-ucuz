"""Məhsul şəkilləri Open Food Facts-dən (açıq məhsul bazası, şəkillər CC BY-SA 3.0), ştrix-koda görə.

Scraper Wolt məhsullarına "gtin" (ştrix-kod) yazır. Bu skript onu prices.json-da "im"-ə çevirir: OFF-dakı ön şəklin yolu,
məs. "476/009/510/1025/front_az.3" (sayt https://images.openfoodfacts.org/images/products/<im>.200.jpg göstərir), sonra
"gtin" məhsul kimliyi üçün saxlanır. OFF-da şəkli olmayan məhsulda "im" yoxdur, sayt ikon göstərir. Mağazanın/Wolt-un şəkli istifadə olunmur.

Keş: data/off_images.json {gtin: [yol və ya "", "YYYY-MM-DD"]}. Tapılmayanlar RECHECK_DAYS gündən sonra yenidən soruşulur.
Bir şəkli saytdan götürmək lazım olsa (pis şəkil, etiraz): onun yolunu data/overrides.json-da "hide_photo"-ya yaz (sayt da göstərmir).
"""
import json, os, re, sys, time
from datetime import date, timedelta

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICES = os.path.join(ROOT, "data", "prices.json")
CACHE = os.path.join(ROOT, "data", "off_images.json")
OVERRIDES = os.path.join(ROOT, "data", "overrides.json")   # sahibin əl ilə yazdığı fayl: "hide_photo" siyahısındakı şəkil yazılmır
API = "https://search.openfoodfacts.org/search"
UA = "harda-ucuz/1.0 (https://github.com/ilhamisayev16-cyber/harda-ucuz)"
BATCH = 100
RECHECK_DAYS = 30
BUDGET = int(os.environ.get("OFF_BUDGET_SEC", "1500"))   # vaxt bitərsə qalanı növbəti gün (scrape-i ləngitməsin)
LANGS = ("az", "en", "ru", "tr")
IM_RX = re.compile(r"^\d{3}/\d{3}/\d{3}/\d+/front_[a-z]{2,3}\.\d+$")   # index.html də eyni yoxlamanı edir


def folder(code):
    """OFF şəkil qovluğu: 13 rəqəmə qədər soldan 0, sonra 3/3/3/qalan."""
    c = code.zfill(13)
    return f"{c[:3]}/{c[3:6]}/{c[6:9]}/{c[9:]}"


def front(code, images):
    """Ön şəklin yolu (200 px ölçüsü olan); dil sırası LANGS, sonra istənilən front_*. Yoxdursa ""."""
    fr = {k[6:]: v for k, v in (images or {}).items() if k.startswith("front_") and isinstance(v, dict)}
    for lang in [l for l in LANGS if l in fr] + sorted(l for l in fr if l not in LANGS):
        v = fr[lang]
        rev = str(v.get("rev") or "")
        if rev.isdigit() and "200" in (v.get("sizes") or {}) and re.fullmatch(r"[a-z]{2,3}", lang):
            im = f"{folder(code)}/front_{lang}.{rev}"
            if IM_RX.match(im): return im
    return ""


def lookup(ses, codes):
    """{gtin: yol} — OFF axtarışı, bir sorğuda BATCH kod. Cavabda olmayan kod = şəkil yoxdur."""
    r = None
    for attempt in range(4):
        try:
            r = ses.get(API, params={"q": "code:(" + " OR ".join(codes) + ")", "fields": "code,images",
                                     "page_size": len(codes)}, timeout=60)
            if r.status_code == 200: break
        except requests.RequestException:
            r = None
        time.sleep(5 * (attempt + 1))
    if r is None or r.status_code != 200: return None
    out = {c: "" for c in codes}
    for p in r.json().get("hits") or []:
        c = str(p.get("code") or "")
        if c in out:
            images = p.get("images") or {}
            im = front(c, images)
            author = ""
            if im:
                lang = im.rsplit("/front_", 1)[1].split(".")[0]
                selected = images.get("front_" + lang) or {}
                original = images.get(str(selected.get("imgid"))) or {}
                author = str(original.get("uploader") or "")[:120]
            out[c] = {"im": im, "author": author, "source": "https://world.openfoodfacts.org/product/" + c,
                      "license": "CC-BY-SA-3.0"}
    return out


def enrich(data, cache, hidden=()):
    """Use existing OFF matches only: GTIN first, then an unambiguous exact packaged name in the same category.

    No fuzzy image guesses or barcode guesses from product names. A conflicting GTIN or image folder blocks sharing.
    """
    from scraper import name_key
    hidden = set(hidden)
    reverse = {}
    for code, row in cache.items():
        if re.fullmatch(r"\d{8,14}", code) and isinstance(row, list) and row and IM_RX.fullmatch(str(row[0])):
            reverse.setdefault(row[0], set()).add(code)
    recovered = added = 0
    for cat in data.get("categories", {}).values():
        items = [it for rows in cat.get("stores", {}).values() for it in rows]
        for it in items:
            im = it.get("im")
            codes = reverse.get(im, set())
            if not it.get("gtin") and len(codes) == 1 and im not in hidden and it.get("im_match") != "exact_name":
                it["gtin"] = next(iter(codes)); recovered += 1
            row = cache.get(it.get("gtin"), [])
            if row and len(row) > 2 and isinstance(row[2], dict) and row[2].get("author"):
                it["im_by"] = str(row[2]["author"])[:120]
            if not im and row and IM_RX.fullmatch(str(row[0])) and row[0] not in hidden:
                it["im"] = row[0]; added += 1
        donors = {}
        for it in items:
            im = it.get("im", "")
            if IM_RX.fullmatch(im) and im not in hidden:
                donors.setdefault(name_key(it["name"]), []).append(it)
        for it in items:
            if it.get("im") or not re.search(r"\d\s*(?:[.,]\d+)?\s*(?:kq|kg|qr|gr|ml|ltr|litr|lt|l|q|g|əd|ed)(?![a-z])", it["name"], re.I):
                continue
            matches = donors.get(name_key(it["name"]), [])
            folders = {x["im"].split("/front_")[0] for x in matches}
            codes = {x["gtin"] for x in matches if x.get("gtin")}
            if len(folders) != 1 or len(codes) > 1 or it.get("gtin") and codes and it["gtin"] not in codes:
                continue
            if it.get("gtin") and not codes:
                continue  # cannot prove a donor without a code is this coded product
            it["im"] = max((x["im"] for x in matches), key=lambda x: int(x.rsplit(".", 1)[1]))
            it["im_match"] = "exact_name"
            authors = {x.get("im_by") for x in matches if x.get("im_by")}
            if len(authors) == 1: it["im_by"] = next(iter(authors))
            # Exact-name image reuse does not establish a barcode; do not assign a donor's GTIN.
            added += 1
    return {"recovered_barcodes": recovered, "added_images": added}


def run():
    with open(PRICES, encoding="utf-8") as f: data = json.load(f)
    try:
        with open(CACHE, encoding="utf-8") as f: cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    today = date.today().isoformat()
    stale = (date.today() - timedelta(days=RECHECK_DAYS)).isoformat()
    try:
        with open(OVERRIDES, encoding="utf-8") as f: hide = set(json.load(f).get("hide_photo") or [])
    except (OSError, ValueError, AttributeError):
        hide = set()
    before = enrich(data, cache, hide)
    print(f"[OFF] mövcud keş: {before}", flush=True)
    items = [it for c in data["categories"].values() for l in c["stores"].values() for it in l if it.get("gtin")]
    need = sorted({it["gtin"] for it in items if it["gtin"] not in cache or (cache[it["gtin"]][1] < stale or cache[it["gtin"]][0] and len(cache[it["gtin"]]) < 3)})
    print(f"[OFF] ştrix-kodlu məhsul: {len(items)}, soruşulacaq kod: {len(need)}", flush=True)
    ses = requests.Session(); ses.headers["User-Agent"] = UA
    t0, done = time.time(), 0
    for i in range(0, 0 if os.environ.get("OFF_OFFLINE") == "1" else len(need), BATCH):
        if time.time() - t0 > BUDGET:
            print(f"[OFF] vaxt bitdi, qalan {len(need) - i} kod növbəti dəfə", flush=True); break
        res = lookup(ses, need[i:i + BATCH])
        if res is None:
            print("[OFF] axtarış cavab vermir, növbəti dəfə", flush=True); break
        for c, value in res.items():
            if isinstance(value, dict): cache[c] = [value["im"], today, {k: value[k] for k in ("author", "source", "license")}]
            else: cache[c] = [value, today, {}]
        done += len(res)
        time.sleep(1)
    try:
        with open(OVERRIDES, encoding="utf-8") as f: hide = set(json.load(f).get("hide_photo") or [])
    except (OSError, ValueError, AttributeError):
        hide = set()
    n = 0
    for c in data["categories"].values():
        for l in c["stores"].values():
            for it in l:
                g = it.get("gtin")
                if g is None or g not in cache: continue
                im = (cache.get(g) or [""])[0]
                if im and im not in hide: it["im"] = im; n += 1
                else: it.pop("im", None)
    after = enrich(data, cache, hide)
    print(f"[OFF] əlavə uyğunluqlar: {after}", flush=True)
    with open(PRICES + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))   # scraper.py ilə eyni format
    os.replace(PRICES + ".tmp", PRICES)
    with open(CACHE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dict(sorted(cache.items())), f, separators=(",", ":"))
        f.write("\n")
    os.replace(CACHE + ".tmp", CACHE)
    hit = sum(1 for v in cache.values() if v[0])
    print(f"[OFF] soruşuldu {done}; keşdə {len(cache)} kod, {hit} şəkilli; şəkilli məhsul {n}/{len(items)}", flush=True)


if __name__ == "__main__":
    sys.exit(run())
