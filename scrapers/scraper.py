#!/usr/bin/env python3
"""
QiymətMüqayisə Scraper
  Bravo  -> Wolt
  OBA    -> oba.az
  Araz   -> arazmarket.az API (+ Wolt)
  Neptun -> Wolt
  Tamstore -> Wolt

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
                  "tualet kağız","kağız dəsmal","salfet","bədən üçün","üz üçün","uşaq bezi","pambıq","ülgüc","tampon",
                  "gigiyenik","losyon","parfüm","maska","saç ","vanna"]},
    "heyvan_yemi":{"name":"Heyvan yemi",     "kw":["pişik","itlər","köpək","nəm yem","quru yem","whiskas","purina","pedigree","felix","kitekat","royal canin","sheba"]},
    "usaq_qida": {"name":"Uşaq qidası",      "kw":["uşaq","sıyıq","bebi","aptamil","nutrilon","kabrita","gerber","hipp","agusha","nanny","fruto"]},
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
    "makaron":   {"name":"Makaron/Əriştə",   "kw":["makaron","spagetti","vermişel","əriştə","doşirak","noodle"]},
    "corek":     {"name":"Çörək",            "kw":["çörək","lavaş"]},
    "hazir_yemek":{"name":"Hazır yemək",     "kw":["pelmen","manti","xinkali","vareniki","naget","nuggets","pizza","piroq","lahmacun","hazır yemək"]},
    "cips":      {"name":"Çips/Qəlyanaltı",  "kw":["çips","chips","suxari","popkorn","lays","pringles","cheetos","qəlyanaltı"]},
    "konserv":   {"name":"Konserv/Turşu/Zeytun","kw":["konserv","turşu","zeytun","maslin","qarğıdalı konserv"]},
    "murebbe":   {"name":"Mürəbbə/Cem",      "kw":["mürəbbə","povidla","cem "]},
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
    "qoz":       {"name":"Qoz-fındıq/Quru meyvə","kw":["fındıq","qoz","badam","fıstıq","kişmiş","qurudulmuş","çərəz","püstə","kaju","xurma","quru ərik","innab"]},
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
    "mesis":     {"name":"Məişət əşyaları",  "kw":["stəkan","boşqab","qaşıq","çəngəl","tava","qazan","süpürgə","əlcək","zibil","folqa","pergament","batareya","lampa","kibrit","plastik","sellofan","paket"]},
    # aşağıdakıların açar sözü yoxdur: yalnız mağazanın öz kateqoriya adına görə təyin olunur (CATEGORY_PATH_RULES)
    "spirtli":   {"name":"Spirtli içkilər",  "kw":[]},
    "meyve_diger":{"name":"Digər meyvə",     "kw":[]},
    "sebze_diger":{"name":"Digər tərəvəz",   "kw":[]},
    "dondurulmus":{"name":"Dondurulmuş məhsul","kw":[]},
    "bakliyyat": {"name":"Taxıl/Bakliyyat",  "kw":[]},
    "diger":     {"name":"Digər məhsullar",  "kw":[]},   # heç bir kateqoriyaya düşməyənlər (atılmasın)
}

# Saytda göstərilən ümumi kateqoriyalar (alt növlər = yuxarıdakı kateqoriyalar)
GROUPS = [
    {"id":"meyve",    "name":"Meyvə",                 "cats":["alma","armud","saftal","gilas","uzum","banan","kivi","limon","portaqal","nar","meyve_diger"]},
    {"id":"sebze",    "name":"Tərəvəz",               "cats":["kartof","pomidor","xiyar","soyan","kelem","yerkoyu","cuqundur","badimcan","biber","sarimsaq","sebze_diger"]},
    {"id":"sud",      "name":"Süd məhsulları",        "cats":["sud","qatiq","xama","kefir","ayran","kere_yagi","pendir","yumurta"]},
    {"id":"et",       "name":"Ət və balıq",           "cats":["toyuq","dana_ati","qoyun_ati","hindi","kolbasa","sosis","baliq"]},
    {"id":"bakaliya", "name":"Taxıl və makaron",      "cats":["duyu","merci","noxud","fasulya","qarabashaq","yulaf","un","makaron","bakliyyat"]},
    {"id":"corek",    "name":"Çörək",                 "cats":["corek"]},
    {"id":"sirniyyat","name":"Şirniyyat",             "cats":["pecenye","sokolad","halva","dondurma","bal","murebbe"]},
    {"id":"iceckiler","name":"İçkilər",               "cats":["cay","qehve","sire","su","kola","energetik"]},
    {"id":"yag_sous", "name":"Yağ, sous, ədviyyat",   "cats":["zeytun_yagi","bitki_yagi","mayonez","ketcup","duz","sekerqum","istiot","konserv"]},
    {"id":"ev",       "name":"Ev və məişət",          "cats":["qabyuyan","yuyucu","temizlik","mesis"]},
    {"id":"gigiyena", "name":"Gigiyena",              "cats":["gigiyena"]},
    {"id":"hazir",    "name":"Qəlyanaltı və hazır yemək","cats":["hazir_yemek","cips","qoz","dondurulmus"]},
    {"id":"usaq",     "name":"Uşaq qidası",           "cats":["usaq_qida"]},
    {"id":"heyvan",   "name":"Heyvan yemi",           "cats":["heyvan_yemi"]},
    {"id":"spirtli",  "name":"Spirtli içkilər",       "cats":["spirtli"]},
    {"id":"diger",    "name":"Digər məhsullar",       "cats":["diger"]},
]
_missing = {c for g in GROUPS for c in g["cats"]} ^ set(CATEGORIES)
assert not _missing, _missing

ALL_STORES = ["Bravo","OBA","Araz","Neptun","Tamstore"]

# Hər mağaza üçün bir neçə Wolt filialı: ilk işləyən istifadə olunur.
# Mühit dəyişəni ilə əvəz etmək olar: WOLT_SLUG_NEPTUN=... (vergüllə bir neçə)
WOLT_SLUGS = {
    "Bravo":  ["bravo-supermarket-globus-centre", "bravo-supermarket-28-may",
               "bravo-supermarket-narimanov"],
    "OBA":    ["oba-market-nerimanov-1", "oba-market-narimanov", "oba-market-yasamal"],
    "Araz":   ["araz-supermarket-20-yanvarr", "araz-supermarket-narimanov", "araz-supermarket-yasamal",
               "araz-supermarket-28-may"],
    "Tamstore": ["tamstore-narimanov-1", "tamstore-papanin"],
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
    for cid, info in CATEGORIES.items() if info["kw"]
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
    n = _low(name)
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
    return "diger"

# Mağazanın öz kateqoriya adı (Wolt/Araz/OBA) -> bizim kateqoriya. Sıra vacibdir.
CATEGORY_PATH_RULES = [(re.compile(r, re.I), cid) for r, cid in [
    (r"spirtsiz piv", "kola"), (r"piv|araq|viski|şərab|spirtli|likor|tekila|vermut|konyak|şampan", "spirtli"),
    (r"uşaq.*(bez|baxım|sabun|salfet|krem|diş)", "gigiyena"), (r"uşaq", "usaq_qida"),
    (r"ev heyvan|it və pişik|pişiklər|itlər üçün", "heyvan_yemi"),
    (r"qabyuyan", "qabyuyan"), (r"yuyucu|paltaryuyan|yumşaldıcı|ağardıcı|çamaşır", "yuyucu"),
    (r"təmizlik|təmizləyici|həşərat|hava təravət", "temizlik"),
    (r"saç|şampun|dezodar|dezodor|ətir|kaloniya|sabun|duş gel|gigiyen|diş|dəri|təraş|kosmetik|manikür|qoruyucu|günəş krem|şəxsi baxım|salfet|kağız məhsulları|tualet|ağız təravət", "gigiyena"),
    (r"xırdavat|məişət|bişirmə|folqa|streç|birdəfə|zibil|şamlar|difüzor|batareya|lampa|ləvazimat", "mesis"),
    (r"tütün|siqaret|alışqan|terea|oyuncaq|məktəb|ofis|maşın|avtomobil|tekstil|hədiyyə|sağlam qida|dietik", "diger"),
    (r"energetik|enerji", "energetik"), (r"şirə|nektar|kompot", "sire"),
    (r"sular|su$|mineral", "su"), (r"cola|soda|limonad|spirtsiz içki|soyuq çay", "kola"),
    (r"qəhvə|kofe|kakao", "qehve"), (r"çay", "cay"),
    (r"dondurma", "dondurma"), (r"dondurulmuş|donmuş", "dondurulmus"),
    (r"konserv|turşu|zeytun", "konserv"), (r"hazır", "hazir_yemek"),
    (r"yumurta", "yumurta"), (r"toyuq", "toyuq"), (r"dəniz|balıq", "baliq"),
    (r"kolbasa|delikates|sosis|qastronom|hisə verilmiş", "kolbasa"), (r"ət məhsulları|təzə ət", "dana_ati"),
    (r"pendir|şor|labne", "pendir"), (r"xama", "xama"), (r"qatıq|ayran|kefir|dovğa", "qatiq"),
    (r"zeytun yağ|günəbaxan|qarğıdalı yağ|duru yağ", "bitki_yagi"), (r"kərə|spred", "kere_yagi"),
    (r"süd|kəsmik|qaymaq|yoqurt|sırok", "sud"),
    (r"çips|tum|snack|qəlyanaltı", "cips"), (r"çərəz|quru meyvə", "qoz"),
    (r"bal,|cem|mürəbbə|əzmə|krem pasta|\bbal\b", "murebbe"),
    (r"şokolad", "sokolad"), (r"vafli|kurabiy|keks|kruassan", "pecenye"),
    (r"şirniyyat|şirin|konfet|halva|marmelad|lokum|saqqız", "halva"),
    (r"mayonez", "mayonez"), (r"ketçup|sous", "ketcup"), (r"duz", "duz"), (r"ədviyyat|bulyon|xardal|sirkə", "istiot"),
    (r"şəkər", "sekerqum"), (r"makaron", "makaron"), (r"düyü", "duyu"), (r"dənli|paxla|bakliyyat|taxıl|müsli|sıyıq|səhər", "bakliyyat"),
    (r"^un$|un məhsul|(^|> )un\b", "un"), (r"çörək|lavaş|un məmulat", "corek"),
    (r"tərəvəz", "sebze_diger"), (r"meyvə", "meyve_diger"),
]]

def _low(t):
    return t.replace("İ", "i").lower()   # "SPİRTLİ".lower() -> "spi̇rtli̇" (birləşən nöqtə) olmasın

def cat_from_path(path):
    p = _low(path)
    for rx, cid in CATEGORY_PATH_RULES:
        if rx.search(p): return cid
    return None

def classify(name, path=""):
    """Əvvəl məhsulun adına, tapılmazsa mağazanın kateqoriya adına görə."""
    cid = assign_cat(name)
    if cid == "diger" and path:
        return cat_from_path(path) or "diger"
    return cid

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
                for name, ocat, raw in cards:
                    price = clean_price(raw)
                    key = (name.lower(), price)
                    if not name or price is None or key in seen: continue
                    seen.add(key); total += 1; new_in_batch += 1
                    cat = classify(name, ocat)
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

def scrape_araz():
    """Araz-ın öz API-si. Səhifələmə etibarsızdır (səhifələr arasında təkrar/itkin məhsullar), ona görə
    hər ana kateqoriya (alt kateqoriyaları da əhatə edir) per_page=5000 ilə BİR sorğuda çəkilir.
    Uğursuz olarsa None qaytarır (Wolt-a keçilir)."""
    ses = _session()
    ses.headers.update({"Accept": "application/json", "Origin": "https://arazmarket.az",
                        "Referer": "https://arazmarket.az/", "Accept-Language": "az"})
    try:
        r = ses.get(f"{ARAZ_API}/categories", timeout=40)
        r.raise_for_status()
        tops = [(n["id"], n.get("title") or "") for n in r.json().get("data") or []]
    except Exception as e:
        print(f"  [Araz] ✗ kateqoriyalar alınmadı: {e}")
        return None
    print(f"  [Araz] {len(tops)} ana kateqoriya", flush=True)

    def get(top):
        cid, title = top
        for attempt in range(3):
            try:
                r = ses.get(f"{ARAZ_API}/products/category/{cid}", params={"page": 1, "per_page": 5000}, timeout=180)
                if r.status_code == 200:
                    return title, (r.json().get("data") or {})
            except Exception:
                pass
            time.sleep(3 * (attempt + 1))
        return title, None

    results = {c: [] for c in CATEGORIES}
    seen, failed = set(), []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for title, d in ex.map(get, tops):
            if d is None: failed.append(title); continue
            if int((d.get("pagination") or {}).get("last_page") or 1) > 1:
                print(f"  [Araz] ⚠ {title}: bir səhifəyə sığmadı", flush=True)
            for p in d.get("products") or []:
                pid, name, price = p.get("id"), (p.get("title") or "").strip(), _araz_price(p)
                if pid in seen or not name or price is None: continue
                seen.add(pid)
                cat = classify(name, f"{title} > {p.get('category_title') or ''}")
                e = {"name": name, "price": price}
                im = img_of(p, "https://arazmarket.az")
                if im: e["img"] = im
                results[cat].append(e)
    total = len(seen)
    print(f"  [Araz] ✓ {total} məhsul (arazmarket.az)" + (f"; alınmadı: {failed}" if failed else ""), flush=True)
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

def _wolt_entry(item, path=""):
    """Wolt məhsul obyektindən (ad, kateqoriya, yazı) çıxarır; uyğun deyilsə None."""
    name = item.get("name", "")
    if isinstance(name, dict): name = name.get("az") or name.get("en") or ""
    price = _wolt_price(item)
    if not name or price is None or price >= 999: return None
    e = {"name": name, "wolt_price": price}
    im = img_of(item)
    if im: e["img"] = im
    wt = _wolt_weight(item)
    if wt: e["wt"] = wt
    return classify(name, path), e

def _wolt_base(slug):
    return f"https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/{slug}/assortment"

def _wolt_pick_venue(ses, store, probe):
    """İşləyən filialı tapır (müvəqqəti blok üçün 3 cəhd). probe(slug) -> True/False."""
    for attempt in range(3):
        for slug in wolt_slugs(store):
            try:
                if probe(slug):
                    print(f"  [Wolt/{store}] filial: {slug}")
                    return slug
                print(f"  [Wolt/{store}] {slug}: cavab yoxdur")
            except Exception as e:
                print(f"  [Wolt/{store}] {slug}: {type(e).__name__}")
        time.sleep(10 * (attempt + 1))
    return None

def scrape_wolt_full(store):
    """Filialın BÜTÜN kataloqu: kateqoriya ağacı -> hər yarpaq kateqoriya (səhifələmə ilə).
    Açar söz axtarışından çox məhsul verir. Uğursuz olarsa None."""
    ses = _session()
    def probe(slug):
        r = ses.get(_wolt_base(slug), params={"language": "az"}, timeout=30)
        return r.status_code == 200 and bool(r.json().get("categories"))
    slug = _wolt_pick_venue(ses, store, probe)
    if not slug: return None
    base = _wolt_base(slug)
    tree = ses.get(base, params={"language": "az"}, timeout=30).json()["categories"]
    leaves = []   # (slug, "Üst > Alt")
    def walk(nodes, trail=""):
        for c in nodes:
            t = f"{trail} > {c.get('name','')}" if trail else c.get("name", "")
            if c.get("subcategories"): walk(c["subcategories"], t)
            elif c.get("slug"): leaves.append((c["slug"], t))
    walk(tree)

    failed = []   # alınmayan səhifələr (limit/şəbəkə); səssizcə itməsin
    def fetch(leaf):
        cs, trail = leaf
        out, tok = [], None
        for _ in range(100):
            params = {"language": "az"}
            if tok: params["page_token"] = tok
            d = None
            for attempt in range(4):
                try:
                    r = ses.get(f"{base}/categories/slug/{cs}", params=params, timeout=30)
                    if r.status_code == 200:
                        d = r.json(); break
                    status = r.status_code
                except Exception as e:
                    status = type(e).__name__
                time.sleep(2 * (attempt + 1))
            if d is None:
                failed.append((cs, status)); break
            out += d.get("items") or []
            tok = (d.get("metadata") or {}).get("next_page_token")
            if not tok: break
        return trail, out

    results = {c: [] for c in CATEGORIES}
    seen = set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for trail, items in ex.map(fetch, leaves):
            for item in items:
                uid = item.get("id") or item.get("name")
                if uid in seen: continue
                seen.add(uid)
                r = _wolt_entry(item, trail)
                if r: results[r[0]].append(r[1])
    total = sum(len(v) for v in results.values())
    print(f"  [Wolt/{store}] tam kataloq: {len(leaves)} kateqoriya, {total} məhsul"
          + (f"; {len(failed)} sorğu alınmadı {sorted({str(f[1]) for f in failed})}" if failed else ""), flush=True)
    return results if total else None

def scrape_wolt(store):
    """Əvvəl tam kataloq; alınmasa açar söz axtarışı (köhnə üsul)."""
    full = scrape_wolt_full(store)
    if full: return full
    print(f"  [Wolt/{store}] tam kataloq alınmadı → açar söz axtarışı")
    ses = _session()
    def probe(slug):
        r = ses.post(_wolt_url(slug), json={"q": "süd"}, timeout=15)
        return r.status_code == 200 and r.json().get("items") is not None
    slug = _wolt_pick_venue(ses, store, probe)
    if not slug:
        print(f"  [Wolt/{store}] ✗ heç bir filial cavab vermədi (WOLT_SLUG_{store.upper()} ilə düzgün slug verin)")
        return None   # None = uğursuz, boş nəticə ilə qarışdırılmasın
    url = _wolt_url(slug)
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
                r = _wolt_entry(item)
                if not r: continue
                uid = r[1]["name"].lower().strip()
                if uid in seen: continue
                seen.add(uid)
                results[r[0]].append(r[1])
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
    wolt_only = store in ("Bravo", "Neptun", "Tamstore")
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
def _save(data, out):
    data["groups"] = GROUPS
    data["last_updated"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

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
    ap.add_argument("--store", choices=["bravo","oba","araz","neptun","tamstore","all"], default="all")
    ap.add_argument("--wolt-only",  action="store_true")
    ap.add_argument("--own-only",   action="store_true")
    ap.add_argument("--out", default="../data/prices.json")
    args = ap.parse_args()

    out = (Path(__file__).parent / args.out).resolve()
    if out.exists():
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        data["stores"] = ALL_STORES
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

    name_map = {"bravo":"Bravo","oba":"OBA","araz":"Araz","neptun":"Neptun","tamstore":"Tamstore"}
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
        _save(data, out)   # timeout olarsa əvvəlki mağazaların nəticəsi itməsin

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
