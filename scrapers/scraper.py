#!/usr/bin/env python3
"""
QiymətMüqayisə Scraper
  Bravo  -> Wolt
  OBA    -> oba.az
  Araz   -> arazmarket.az API (+ Wolt)
  Neptun -> Wolt

İstifadə:
  python scraper.py
  python scraper.py --store bravo
  python scraper.py --store oba
  python scraper.py --recategorize   (şəbəkəsiz: mövcud datanı yenidən təsnif edir)
"""
import json, os, re, time, argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

CATEGORIES = {   # sıra vacibdir: ilk uyğun gələn kateqoriya götürülür
    # ev / gigiyena (ən əvvəl: "limon ətirli qabyuyan" meyvə olmasın)
    "qabyuyan":  {"name":"Qabyuyan maye",    "kw":["qabyuyan","qab yuyan","fairy"]},
    "yuyucu":    {"name":"Yuyucu toz/gel",   "kw":["yuyucu toz","paltaryuyan","kir yuyan","ariel","persil","yumşaldıcı","kondisioner"]},
    "temizlik":  {"name":"Təmizləyici",      "kw":["təmizləyici","ağardıcı","dezinfeksiya","domestos","cif "]},
    "gigiyena":  {"name":"Sabun/Şampun/Kağız","kw":["sabun","şampun","duş geli","dezodorant","diş pastası","diş fırçası",
                  "tualet kağız","kağız dəsmal","salfet","bədən üçün","üz üçün","uşaq bezi"]},
    # şirniyyat / içki (emal olunmuş məhsullar meyvə-tərəvəzdən əvvəl)
    "pecenye":   {"name":"Peçenye/Biskvit",  "kw":["peçenye","biskvit","kraker","vafli"]},
    "sokolad":   {"name":"Şokolad",          "kw":["şokolad"]},
    "halva":     {"name":"Halva/Konfet",     "kw":["halva","konfet","karamel","marmelad"]},
    "dondurma":  {"name":"Dondurma",         "kw":["dondurma","plombir"]},
    "bal":       {"name":"Bal",              "kw":["təbii bal","çiçək balı","bal "]},
    "energetik": {"name":"Energetik",        "kw":["red bull","monster","burn ","hell energy"]},
    "kola":      {"name":"Kola/Limonad",     "kw":["kola","limonad","pepsi","fanta","sprite"]},
    "cay":       {"name":"Çay",              "kw":["çay","lipton","ahmad"],"excl":["çaydan"]},
    "qehve":     {"name":"Qəhvə",            "kw":["qəhvə","nescafe","lavazza"]},
    "sire":      {"name":"Şirə/Mors/Nektar", "kw":["şirəsi","şirə","mors","nektar",
                                                    "meyvə suyu","alma suyu","portağal suyu"]},
    "su":        {"name":"Su",               "kw":["mineral su","içməli su","mənbə suyu"]},
    "mayonez":   {"name":"Mayonez",          "kw":["mayonez"]},
    "ketcup":    {"name":"Ketçup/Sous",      "kw":["ketçup","ketchup","sous"]},
    "zeytun_yagi":{"name":"Zeytun yağı",     "kw":["zeytun yağ"]},
    "bitki_yagi":{"name":"Bitki yağı",       "kw":["günəbaxan yağ","ayçiçəyi yağ","bitki yağ"]},
    "makaron":   {"name":"Makaron",          "kw":["makaron","spagetti","vermişel"]},
    "corek":     {"name":"Çörək",            "kw":["çörək","lavaş"]},
    # ət
    "sosis":     {"name":"Sosis",            "kw":["sosis","sosiska"]},
    "kolbasa":   {"name":"Kolbasa",          "kw":["kolbasa","salam"],"excl":["sosis"]},
    "baliq":     {"name":"Balıq",            "kw":["balıq","tuna","skumbriya","losos"]},
    "toyuq":     {"name":"Toyuq",            "kw":["toyuq","cücə","broylyer"]},
    "dana_ati":  {"name":"Dana əti",         "kw":["dana"]},
    "qoyun_ati": {"name":"Qoyun/Quzu əti",   "kw":["qoyun","quzu"]},
    "hindi":     {"name":"Hindi",            "kw":["hindi"]},
    # süd məhsulları
    "pendir":    {"name":"Pendir",           "kw":["pendir"]},
    "kere_yagi": {"name":"Kərə yağı",        "kw":["kərə yağ","butter"]},
    "xama":      {"name":"Xama",             "kw":["xama","smetana"]},
    "qatiq":     {"name":"Qatıq/Yoqurt",     "kw":["qatıq","yoqurt","yogurt"],
                  "excl":["içki","şirə"]},
    "kefir":     {"name":"Kefir",            "kw":["kefir"]},
    "ayran":     {"name":"Ayran",            "kw":["ayran"]},
    "sud":       {"name":"Süd",              "kw":["süd"],"excl":["kakao","soya"]},
    "yumurta":   {"name":"Yumurta",          "kw":["yumurta"]},
    # tərəvəz
    "kartof":    {"name":"Kartof",           "kw":["kartof"]},
    "pomidor":   {"name":"Pomidor",          "kw":["pomidor","tomat"]},
    "xiyar":     {"name":"Xiyar",            "kw":["xiyar"]},
    "soyan":     {"name":"Soğan",            "kw":["soğan","soyan"]},
    "kelem":     {"name":"Kələm",            "kw":["kələm","kapusta"]},
    "yerkoyu":   {"name":"Yerkökü",          "kw":["yerkökü","morkov"]},
    "cuqundur":  {"name":"Çuğundur",         "kw":["çuğundur","svekla"]},
    "badimcan":  {"name":"Badımcan",         "kw":["badımcan"]},
    "biber":     {"name":"Bibər",            "kw":["bibər"]},
    "sarimsaq":  {"name":"Sarımsaq",         "kw":["sarımsaq"]},
    # meyvə
    "alma":      {"name":"Alma",             "kw":["alma"],"excl":["sirkə"]},
    "armud":     {"name":"Armud",            "kw":["armud"]},
    "saftal":    {"name":"Şaftalı",          "kw":["şaftalı","nektarin"]},
    "gilas":     {"name":"Gilas/Albalı",     "kw":["gilas","albalı"]},
    "uzum":      {"name":"Üzüm",             "kw":["üzüm"],"excl":["sirkə","şərab","kişmiş"]},
    "banan":     {"name":"Banan",            "kw":["banan"]},
    "kivi":      {"name":"Kivi",             "kw":["kivi"]},
    "limon":     {"name":"Limon",            "kw":["limon"]},
    "portaqal":  {"name":"Portağal",         "kw":["portağal","portakal"]},
    "nar":       {"name":"Nar",              "kw":["nar"]},
    # bakaliya
    "duyu":      {"name":"Düyü",             "kw":["düyü","pirinc"]},
    "merci":     {"name":"Mərcimək",         "kw":["mərcimək"]},
    "noxud":     {"name":"Noxud",            "kw":["noxud"]},
    "fasulya":   {"name":"Fasulya",          "kw":["fasulya","lobya"]},
    "qarabashaq":{"name":"Qarabaşaq",        "kw":["qarabaşaq","grechka"]},
    "yulaf":     {"name":"Yulaf",            "kw":["yulaf","ovsyanka"]},
    "un":        {"name":"Un",               "kw":["buğda unu","ali növ un","birinci növ un","çovdar unu"]},
    "duz":       {"name":"Duz",              "kw":["duz"]},
    "sekerqum":  {"name":"Şəkər",            "kw":["şəkər"]},
    "istiot":    {"name":"İstiot/Ədviyyat",  "kw":["istiot","ədviyyat","zirə","darçın"]},
}

# Saytda göstərilən ümumi kateqoriyalar (alt növlər = yuxarıdakı kateqoriyalar)
GROUPS = [
    {"id":"meyve",    "name":"Meyvə",                 "cats":["alma","armud","saftal","gilas","uzum","banan","kivi","limon","portaqal","nar"]},
    {"id":"sebze",    "name":"Tərəvəz",               "cats":["kartof","pomidor","xiyar","soyan","kelem","yerkoyu","cuqundur","badimcan","biber","sarimsaq"]},
    {"id":"sud",      "name":"Süd məhsulları",        "cats":["sud","qatiq","xama","kefir","ayran","kere_yagi","pendir","yumurta"]},
    {"id":"et",       "name":"Ət və balıq",           "cats":["toyuq","dana_ati","qoyun_ati","hindi","kolbasa","sosis","baliq"]},
    {"id":"bakaliya", "name":"Taxıl və makaron",      "cats":["duyu","merci","noxud","fasulya","qarabashaq","yulaf","un","makaron"]},
    {"id":"corek",    "name":"Çörək",                 "cats":["corek"]},
    {"id":"sirniyyat","name":"Şirniyyat",             "cats":["pecenye","sokolad","halva","dondurma","bal"]},
    {"id":"iceckiler","name":"İçkilər",               "cats":["cay","qehve","sire","su","kola","energetik"]},
    {"id":"yag_sous", "name":"Yağ, sous, ədviyyat",   "cats":["zeytun_yagi","bitki_yagi","mayonez","ketcup","duz","sekerqum","istiot"]},
    {"id":"ev",       "name":"Ev kimyası",            "cats":["qabyuyan","yuyucu","temizlik"]},
    {"id":"gigiyena", "name":"Gigiyena",              "cats":["gigiyena"]},
]
_missing = {c for g in GROUPS for c in g["cats"]} ^ set(CATEGORIES)
assert not _missing, _missing

ALL_STORES = ["Bravo","OBA","Araz","Neptun"]

# Hər mağaza üçün bir neçə Wolt filialı: ilk işləyən istifadə olunur.
# Mühit dəyişəni ilə əvəz etmək olar: WOLT_SLUG_NEPTUN=... (vergüllə bir neçə)
WOLT_SLUGS = {
    "Bravo":  ["bravo-supermarket-globus-centre", "bravo-supermarket-28-may",
               "bravo-supermarket-narimanov"],
    "OBA":    ["oba-market-nerimanov-1", "oba-market-narimanov", "oba-market-yasamal"],
    "Araz":   ["araz-supermarket-20-yanvarr", "araz-supermarket-narimanov", "araz-supermarket-yasamal",
               "araz-supermarket-28-may"],
    "Neptun": ["neptun-supermarket-narimanovv", "neptun-supermarket-28", "neptun-supermarket-narimanov",
               "neptun-supermarket-nizami"],
}

def wolt_slugs(store):
    env = os.environ.get("WOLT_SLUG_" + store.upper(), "")
    extra = [x.strip() for x in env.split(",") if x.strip()]
    return extra + WOLT_SLUGS.get(store, [])

JUICE_WORDS = ["şirəsi","suyu","nektarı","mors","şərbəti","kompot","içkisi","limonadı"]
_WATER = re.compile(r"mineral su|içməli su|mənbə suyu|qazlı su")

def clean_price(raw):
    if raw is None: return None
    s = re.sub(r"[^\d,.]", "", str(raw)).replace(",",".")
    m = re.search(r"\d+\.?\d*", s)
    if not m: return None
    v = float(m.group())
    return round(v, 2) if 0.05 < v < 9999 else None

_IMG_KEYS = ("image","img","image_url","imageUrl","thumbnail","thumb","photo","picture","cover","main_image")
_IMG_LISTS = ("images","photos","pictures","media","gallery")
_IMG_INNER = ("url","src","original","large","medium","small","path","thumbnail")

def _pick_img(v):
    if isinstance(v, str): return v.strip()
    if isinstance(v, dict):
        for k in _IMG_INNER:
            r = _pick_img(v.get(k))
            if r: return r
    if isinstance(v, list):
        for x in v:
            r = _pick_img(x)
            if r: return r
    return None

def img_of(item, base=""):
    """Məhsul obyektindən şəkil linkini çıxarır (sahə adları mənbədən asılı olaraq fərqlənir)."""
    for k in _IMG_KEYS + _IMG_LISTS:
        u = _pick_img(item.get(k))
        if not u: continue
        if u.startswith("//"): u = "https:" + u
        elif u.startswith("/") and base: u = base.rstrip("/") + u
        if u.startswith("https://"): return u
    return None

def has_juice(name):
    n = name.lower()
    return any(w in n for w in JUICE_WORDS)

def _kw_re(words):
    # söz əvvəlində uyğunluq: "nar" -> "Nar", amma "Qarnar"/"Narzan" yox
    # qısa açar sözlər (nar, bal, su, un) tam söz kimi axtarılır
    parts = [re.escape(w.lower()) + (r"(?!\w)" if not w.endswith(" ") and (len(w) <= 3 or w.lower() in ("nar", "bal", "duz")) else "")
             for w in words]
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + ")")

_CAT_RE = {
    cid: (_kw_re(info["kw"]), _kw_re(info["excl"]) if info.get("excl") else None)
    for cid, info in CATEGORIES.items()
}

_ADJ = re.compile(r"l[ıiuü]$")   # "limonlu", "pendirli" -> dad bildirən sifət, məhsulun özü deyil
# təbii məhsul kateqoriyaları: "dadlı/aromalı/konserv" olanlar bura aid deyil
_STRICT = {c for g in GROUPS if g["id"] in ("meyve","sebze","et") for c in g["cats"]} - {"kolbasa","sosis"}
_STRICT_EXCL = _kw_re(["şirə","suyu","sous","pasta","konserv","turşu","mürəbbə","cem","kompot","çip",
                       "dadlı","aromalı","ətirli","ləzzətli","qurusu","kürü","duzu","povidla","tablet","cleaner",
                       "pürə","yoqurt","yogurt","mirinda","spr","qurudulmuş","pastila","gel","krem"])
_MEAT = {"toyuq","dana_ati","qoyun_ati","hindi","baliq"}
_PET = _kw_re(["yem","pişik","itlər","bulyon","əriştə","kub"])
_LIQUID = re.compile(r"\d\s*(?:ml|l|lt|litr)(?!\w)")

def assign_cat(name):
    n = name.lower()
    if _WATER.search(n):
        return "su"
    if has_juice(n):
        return "sire"
    for cid, (kw, ex) in _CAT_RE.items():
        if ex and ex.search(n):
            continue
        if cid in _STRICT and (_STRICT_EXCL.search(n) or _LIQUID.search(n)):
            continue
        m = kw.search(n)
        if not m:
            continue
        if cid in _STRICT:   # real məhsulun adı açar sözlə başlayır: "Yerli Alma", "Limon kq"
            pos = len(re.findall(r"[\w-]+", n[:m.start()]))
            if pos > (2 if cid in _MEAT else 1) or (cid in _MEAT and _PET.search(n)):
                continue
        word = re.match(r"\w+", n[m.start():]).group()
        if len(word) > len(m.group()) and _ADJ.search(word):
            continue
        return cid
    return None

def sim(a, b):
    wa = set(re.sub(r"[^\w\s]","",a.lower()).split())
    wb = set(re.sub(r"[^\w\s]","",b.lower()).split())
    if not wa or not wb: return 0
    return len(wa & wb) / max(len(wa), len(wb))

def empty_data():
    return {
        "last_updated": "",
        "stores": ALL_STORES,
        "groups": GROUPS,
        "categories": {
            cid: {"name": info["name"], "stores": {s: [] for s in ALL_STORES}}
            for cid, info in CATEGORIES.items()
        }
    }

# ── OBA ──────────────────────────────────────────────────────────────────

_OBA_CARD = re.compile(
    r'<h3[^>]*>([^<]+)</h3>.*?<p class="color-mako[^>]*>([^<]*)</p>.*?'
    r'<span class="fs-lg-24 fs-20 lh-24 fw-400">([\d.,]+)</span>', re.S)
OBA_STEP = 24

def _oba_cards(html):
    from html import unescape
    return [(unescape(n).strip(), unescape(c).strip(), pr) for n, c, pr in _OBA_CARD.findall(html)]

def scrape_oba():
    """oba.az/products/ — server tərəfindən render olunan HTML, ?start= ilə səhifələmə."""
    ses = _session()
    ses.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124",
                        "Accept-Language": "az"})
    ses.headers.pop("Content-Type", None)

    def page(start):
        try:
            r = ses.get("https://oba.az/products/", params={"start": start} if start else None, timeout=30)
            return _oba_cards(r.text) if r.status_code == 200 else []
        except Exception:
            return []

    results = {c: [] for c in CATEGORIES}
    seen, total, start, empty = set(), 0, 0, 0
    print("  [OBA] oba.az/products/ …", end="", flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        while start < 60000 and empty < 1:
            offsets = [start + i * OBA_STEP for i in range(8)]
            new_in_batch = 0
            for cards in ex.map(page, offsets):
                for name, _cat, raw in cards:
                    price = clean_price(raw)
                    key = (name.lower(), price)
                    if not name or price is None or key in seen: continue
                    seen.add(key); total += 1; new_in_batch += 1
                    cat = assign_cat(name)
                    if cat: results[cat].append({"name": name, "price": price})
            if new_in_batch == 0: empty += 1
            start += 8 * OBA_STEP
            print(f" {total}", end="", flush=True)
    print(f"\n  [OBA] ✓ {total} məhsul")
    return results if total else None

# ── ARAZ — arazmarket.az API ─────────────────────────────────────────────
ARAZ_API = "https://b7x9kq.arazmarket.az/api"

def _araz_price(p):
    """Rəfdəki faktiki qiymət: endirim varsa endirimli, yoxsa adi qiymət."""
    if p.get("is_discount") and p.get("discount_price"):
        v = clean_price(p.get("discount_price"))
        if v: return v
    return clean_price(p.get("sales_price"))

def _araz_leaves(nodes, out):
    for n in nodes or []:
        if n.get("sub"): _araz_leaves(n["sub"], out)
        else: out.append(n["id"])
    return out

def scrape_araz():
    """Araz-ın öz API-si. Uğursuz olarsa None qaytarır (Wolt-a keçilir)."""
    ses = _session()
    ses.headers.update({"Accept": "application/json", "Origin": "https://arazmarket.az",
                        "Referer": "https://arazmarket.az/", "Accept-Language": "az"})
    try:
        r = ses.get(f"{ARAZ_API}/categories", timeout=40)
        r.raise_for_status()
        leaves = _araz_leaves(r.json().get("data"), [])
    except Exception as e:
        print(f"  [Araz] ✗ kateqoriyalar alınmadı: {e}")
        return None
    print(f"  [Araz] {len(leaves)} alt kateqoriya")

    def fetch(cid):
        items, page = [], 1
        while page <= 60:
            try:
                r = ses.get(f"{ARAZ_API}/products/category/{cid}", params={"page": page}, timeout=30)
                if r.status_code != 200: break
                d = (r.json().get("data") or {})
                items += d.get("products") or []
                if page >= int((d.get("pagination") or {}).get("last_page") or 1): break
                page += 1
            except Exception:
                break
        return items

    results = {c: [] for c in CATEGORIES}
    seen, total = set(), 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for items in ex.map(fetch, leaves):
            for p in items:
                pid, name, price = p.get("id"), (p.get("title") or "").strip(), _araz_price(p)
                if pid in seen or not name or price is None: continue
                seen.add(pid); total += 1
                cat = assign_cat(name)
                if cat:
                    e = {"name": name, "price": price}
                    im = img_of(p, "https://arazmarket.az")
                    if im: e["img"] = im
                    results[cat].append(e)
    print(f"  [Araz] ✓ {total} məhsul (arazmarket.az)")
    return results if total else None

# ── WOLT ─────────────────────────────────────────────────────────────────
WOLT_HEADS = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
    "Content-Type":"application/json",
    "Origin":"https://wolt.com",
    "Referer":"https://wolt.com/",
}

def _session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    ses = requests.Session()
    retry = Retry(total=3, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=None)
    ses.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    ses.headers.update(WOLT_HEADS)
    return ses

def _wolt_url(slug):
    return (f"https://consumer-api.wolt.com/consumer-api/consumer-assortment"
            f"/v1/venues/slug/{slug}/assortment/items/search?language=az")

def _wolt_price(item):
    for k in ("price", "baseprice", "unit_price"):
        v = item.get(k)
        if isinstance(v, dict): v = v.get("amount") or v.get("value")
        if isinstance(v, (int, float)) and v > 0:
            return round(v / 100, 2)
    return None

def _wolt_weight(item):
    """Çəkiyə görə satılan "ədəd" məhsulda bir ədədin təxmini çəkisi (qram): sell_by_weight_config.grams_per_step.
    input_type="grams" olanlarda (meyvə-tərəvəz) parça çəkisi yoxdur, qiymət 1 kq üçün qalır."""
    c = item.get("sell_by_weight_config")
    if isinstance(c, dict) and c.get("input_type") == "number_of_items":
        g = c.get("grams_per_step")
        if isinstance(g, (int, float)) and g > 0:
            return round(g)
    return None

def scrape_wolt(store):
    """Wolt-dan çəkir: filialları yoxlayır, sorğuları paralel göndərir."""
    ses = _session()
    url = None
    for attempt in range(3):
        for slug in wolt_slugs(store):
            try:
                r = ses.post(_wolt_url(slug), json={"q": "süd"}, timeout=15)
                if r.status_code == 200 and (r.json().get("items") is not None):
                    url = _wolt_url(slug)
                    print(f"  [Wolt/{store}] filial: {slug}")
                    break
                print(f"  [Wolt/{store}] {slug}: HTTP {r.status_code}")
            except Exception as e:
                print(f"  [Wolt/{store}] {slug}: {type(e).__name__}")
        if url: break
        time.sleep(10 * (attempt + 1))   # müvəqqəti blok/limit ola bilər
    if not url:
        print(f"  [Wolt/{store}] ✗ heç bir filial cavab vermədi "
              f"(WOLT_SLUG_{store.upper()} ilə düzgün slug verin)")
        return None   # None = uğursuz, boş nəticə ilə qarışdırılmasın

    queries = sorted({kw.strip() for info in CATEGORIES.values() for kw in info["kw"]})

    def run(q):
        try:
            r = ses.post(url, json={"q": q}, timeout=20)
            return r.json().get("items") or [] if r.status_code == 200 else []
        except Exception:
            return []

    results = {c: [] for c in CATEGORIES}
    seen = set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for items in ex.map(run, queries):
            for item in items:
                name = item.get("name", "")
                if isinstance(name, dict): name = name.get("az") or name.get("en") or ""
                price = _wolt_price(item)
                if not name or price is None or price >= 999: continue
                uid = name.lower().strip()
                if uid in seen: continue
                seen.add(uid)
                cat = assign_cat(name)
                if cat:
                    e = {"name": name, "wolt_price": price}
                    im = img_of(item)
                    if im: e["img"] = im
                    wt = _wolt_weight(item)
                    if wt: e["wt"] = wt
                    results[cat].append(e)
    total = sum(len(v) for v in results.values())
    print(f"  [Wolt/{store}] {total} məhsul")
    return results if total else None

# ── BİRLƏŞDİRMƏ ──────────────────────────────────────────────────────────
def merge_own_wolt(own_list, wolt_list):
    merged = []
    used = set()
    for item in own_list:
        entry = {"name": item["name"], "price": item["price"]}
        if item.get("img"): entry["img"] = item["img"]
        best_s, best_i = 0, -1
        for i, w in enumerate(wolt_list):
            s = sim(item["name"], w["name"])
            if s > best_s: best_s, best_i = s, i
        if best_s >= 0.5 and best_i >= 0:
            wp = wolt_list[best_i]["wolt_price"]
            if abs(wp - item["price"]) > 0.005:
                entry["wolt_price"] = wp
            if "img" not in entry and wolt_list[best_i].get("img"):
                entry["img"] = wolt_list[best_i]["img"]
            if wolt_list[best_i].get("wt"):
                entry["wt"] = wolt_list[best_i]["wt"]
            used.add(best_i)
        merged.append(entry)
    # Wolt-only items
    for i, w in enumerate(wolt_list):
        if i not in used:
            merged.append({k: w[k] for k in ("name", "wolt_price", "img", "wt") if k in w})
    return merged

def apply_to_data(own_res, wolt_res, store, data):
    own_res, wolt_res = own_res or {}, wolt_res or {}
    if not any(own_res.values()) and not any(wolt_res.values()):
        print(f"  [{store}] ⚠ nəticə boşdur — köhnə qiymətlər saxlanıldı")
        return False
    wolt_only = store in ("Bravo", "Neptun")
    for cid in CATEGORIES:
        if wolt_only:
            items = [{k: w[k] for k in ("name", "wolt_price", "img", "wt") if k in w}
                     for w in wolt_res.get(cid,[])]
        else:
            items = merge_own_wolt(own_res.get(cid,[]), wolt_res.get(cid,[]))
        data["categories"][cid]["stores"][store] = items
    data.setdefault("meta", {})[store] = {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "own": sum(len(v) for v in own_res.values()),
        "wolt": sum(len(v) for v in wolt_res.values()),
    }
    return True

# ── MAIN ─────────────────────────────────────────────────────────────────
def recategorize(data):
    """Mövcud məhsulları yenidən təsnif edir (şəbəkə tələb olunmur)."""
    old = data.get("categories", {})
    new = empty_data()["categories"]
    seen = set()
    for c in old.values():
        for store, items in c["stores"].items():
            for it in items:
                cid = assign_cat(it["name"])
                key = (store, cid, it["name"].lower())
                if cid and key not in seen:
                    seen.add(key)
                    new[cid]["stores"].setdefault(store, []).append(it)
    data["categories"] = new
    data["groups"] = GROUPS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recategorize", action="store_true")
    ap.add_argument("--store", choices=["bravo","oba","araz","neptun","all"], default="all")
    ap.add_argument("--wolt-only",  action="store_true")
    ap.add_argument("--own-only",   action="store_true")
    ap.add_argument("--out", default="../data/prices.json")
    args = ap.parse_args()

    out = (Path(__file__).parent / args.out).resolve()
    if out.exists():
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        if "stores" not in data: data["stores"] = ALL_STORES
        # köhnə (artıq istifadə olunmayan) kateqoriyaları at: onlarda köhnəlmiş qiymətlər qalır
        data["categories"] = {k: v for k, v in data["categories"].items() if k in CATEGORIES}
        for cid, info in CATEGORIES.items():
            if cid not in data["categories"]:
                data["categories"][cid] = {"name":info["name"],"stores":{s:[] for s in ALL_STORES}}
    else:
        data = empty_data()

    if args.recategorize:
        recategorize(data)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print("✅  Yenidən təsnif edildi:", out)
        return

    name_map = {"bravo":"Bravo","oba":"OBA","araz":"Araz","neptun":"Neptun"}
    targets = list(name_map.keys()) if args.store=="all" else [args.store]

    for t in targets:
        sname = name_map[t]
        print(f"\n{'─'*50}\n  {sname}\n{'─'*50}")
        own_res, wolt_res = {}, {}

        # Öz mənbə (Bravo və Neptun üçün yoxdur — yalnız Wolt)
        if not args.wolt_only:
            if sname == "OBA":
                own_res = scrape_oba()
            elif sname == "Araz":
                own_res = scrape_araz() or {}

        # Wolt
        if not args.own_only:
            wolt_res = scrape_wolt(sname)

        apply_to_data(own_res, wolt_res, sname, data)

    data["groups"] = GROUPS
    data["last_updated"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out,"w",encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n✅  Saxlandı: {out}  ({out.stat().st_size//1024} KB)")
    print("\n📊  Nəticə:")
    for s in ALL_STORES:
        own_c  = sum(1 for c in data["categories"].values()
                     for p in c["stores"].get(s,[]) if "price" in p)
        wolt_c = sum(1 for c in data["categories"].values()
                     for p in c["stores"].get(s,[]) if "wolt_price" in p)
        print(f"   {s:8} → öz: {own_c:4}  |  Wolt: {wolt_c:4}")

if __name__ == "__main__":
    main()
