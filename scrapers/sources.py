"""Mənbə konfiqurasiyası + təhlükəsiz JSON yazma/yoxlama.

Konfiqurasiya məqsədli olaraq sadədir: hər mağaza üçün aktiv mənbə tipi, avtomatik yenilənmənin açıq/bağlı olması
Heç nə uydurulmur.
"""
import json
import os
from datetime import datetime
from pathlib import Path

# type: "wolt"  – Wolt kataloqu (yalnız wolt_price)  |  "own" – mağazanın öz saytı/API-si  |  "own+wolt"
# auto: bu mağaza üçün gündəlik avtomatik yenilənmə açıqdır?
SOURCES = {
    "Bravo":      {"type": "wolt",     "auto": True},
    "OBA":        {"type": "own+wolt", "auto": True},
    "Araz":       {"type": "own+wolt", "auto": True},
    "Neptun":     {"type": "wolt",     "auto": True},
    "Tamstore":   {"type": "wolt",     "auto": True},
    "Rahat":      {"type": "wolt",     "auto": True},
    "Bazarstore": {"type": "own",      "auto": True},
}


def wolt_enabled(store=None, env=None):
    """Wolt-dan avtomatik məlumat toplama. `WOLT_ENABLED=0` bütün Wolt mənbələrini söndürür (rəsmi icazə olmadıqda).
    Köhnə Wolt məlumatları silinmir; mağazanın `meta`-sında `auto_update: false` və son uğurlu vaxt qalır."""
    env = os.environ if env is None else env
    if str(env.get("WOLT_ENABLED", "1")).strip().lower() in ("0", "false", "no", "off"):
        return False
    cfg = SOURCES.get(store) if store else None
    return not (cfg and not cfg.get("auto", True))


def source_meta(store, wolt_on):
    """meta[store]-yə yazılan mənbə təsviri (sayt/hesabat üçün)."""
    cfg = SOURCES.get(store, {})
    t = cfg.get("type", "own")
    if not wolt_on and "wolt" in t:
        t = "own" if t == "own+wolt" else "wolt-arxiv"
    return {"source_type": t, "auto_update": bool(wolt_on or t == "own")}


# ── Təhlükəsiz yazma ─────────────────────────────────────────────────────
def validate_prices(data, prev=None, min_ratio=0.4, min_prev=200):
    """(ok, [problemlər]). Sxem + qiymət etibarlılığı + əvvəlki nəticəyə nisbətən kəskin azalma."""
    errs = []
    if not isinstance(data, dict) or not isinstance(data.get("categories"), dict) or not data["categories"]:
        return False, ["categories yoxdur"]
    if not isinstance(data.get("stores"), list):
        errs.append("stores siyahı deyil")
    counts = {}
    for cid, c in data["categories"].items():
        st = c.get("stores") if isinstance(c, dict) else None
        if not isinstance(st, dict):
            errs.append(f"{cid}: stores yoxdur"); continue
        for s, items in st.items():
            if not isinstance(items, list):
                errs.append(f"{cid}/{s}: siyahı deyil"); continue
            for it in items:
                p = it.get("price", it.get("wolt_price")) if isinstance(it, dict) else None
                if not it.get("name") or not isinstance(p, (int, float)) or isinstance(p, bool) or not (0 < p < 10000):
                    errs.append(f"{cid}/{s}: etibarsız qeyd {str(it)[:60]}")
                    if len(errs) > 20: return False, errs
                    break
            counts[s] = counts.get(s, 0) + len(items)
    if prev:
        for s, n in prev.items():
            if n >= min_prev and counts.get(s, 0) < n * min_ratio:
                errs.append(f"{s}: məhsul sayı {n} → {counts.get(s, 0)} (kəskin azalma)")
    return not errs, errs


def store_counts(data):
    out = {}
    for c in (data or {}).get("categories", {}).values():
        for s, items in c.get("stores", {}).items():
            out[s] = out.get(s, 0) + len(items)
    return out


def atomic_write_json(obj, path):
    """Əvvəlcə müvəqqəti fayla yazır, sonra əvəz edir: yarımçıq fayl qalmır."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
