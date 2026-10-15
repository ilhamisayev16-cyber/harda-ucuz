# 🛒 QİYMƏTMÜQAYİSƏ

Azərbaycan supermarketlərindəki ərzaq qiymətlərini müqayisə edən sayt.

## Fayllar

```
qiymet-project/
├── index.html              ← Saytın özü
├── haqqinda.html           ← Haqqında, şərtlər, məxfilik, düzəliş sorğuları
├── data/
│   └── prices.json         ← Qiymətlər (scraper tərəfindən yenilənir)
├── scrapers/
│   └── scraper.py          ← Python scraper
├── requirements.txt        ← Python asılılıqları
└── .github/workflows/
    └── scrape.yml          ← Avtomatik gündəlik scrape
```

## Necə işləyir?

1. GitHub Actions hər gün saat 06:00-da (Bakı vaxtı) `scraper.py`-ı işlədir
2. Scraper mağazaların öz saytından/API-sindən, olmayanda Wolt-dan qiymətləri toplayır
3. `data/prices.json` faylını yeniləyir
4. `index.html` bu JSON-dan oxuyaraq cədvəli göstərir

## Quraşdırma addımları

### 1. GitHub hesabı açın
→ github.com

### 2. Yeni repo yaradın
→ "qiymet-muqayise" adı ilə

### 3. Bu faylları yükləyin
→ Bütün faylları repo-ya əlavə edin

### 4. GitHub Pages aktivləşdirin
→ Settings → Pages → Source: main branch → / (root)
→ Saytınız: https://ADINIZ.github.io/qiymet-muqayise

### 5. Hazırdır! 
Scraper hər gün avtomatik işləyəcək.

## Qiymət mənbələri və etibarlılıq
- Mağazanın öz saytından/API-dən alınan qiymət (`price`) həmişə Wolt qiymətindən (`wolt_price`) üstün tutulur.
- Cədvəldə Wolt qiymətləri <sup>W</sup> ilə işarələnir (Wolt qiyməti rəf qiymətindən bir qədər yüksək ola bilər).
- Scrape boş nəticə qaytararsa, köhnə qiymətlər silinmir (`meta` bölməsində hər mağazanın son yenilənmə vaxtı var).
- Wolt filialının slug-ı dəyişibsə, mühit dəyişəni ilə verin: `WOLT_SLUG_NEPTUN=neptun-supermarket-...` (vergüllə bir neçə).
- Çoxfilialli mağazalarda (`WOLT_BRANCHES`: Bravo, Neptun, Tamstore) bir neçə filialın kataloqu birləşdirilir: məhsul sayı artır, qiymət filiallar üzrə mediandır.
- "Wolta Özəl" kimi yalnız Wolt-a aid endirim kateqoriyalarındakı məhsullar götürülmür (bu endirim mağazanın rəfində yoxdur). Təxmini çevirmə (məs. Wolt qiymətindən faiz çıxmaq) edilmir.
- Öz saytı yoxlanılıb, qiymətli kataloq tapılmayıb (2026-10): neptun.az (boş cavab), bravosupermarket.az, tamstore.az, rahatmarket.az (yalnız kampaniyalar). Bunlar üçün yeganə mənbə Wolt-dur.

## Mağazalar
- **Bravo** → Wolt (bir neçə filial)
- **Neptun** → Wolt (bir neçə filial)
- **OBA** → oba.az
- **Araz** → arazmarket.az API (+ Wolt)
- **Tamstore** → Wolt (bir neçə filial)
- **Rahat** → Wolt
- **Bazarstore** → bazarstore.az (öz saytı, nopCommerce HTML)
- **SPAR** → Wolt

## Yeni mağaza əlavə etmək
`scraper.py`-da `ALL_STORES`-a ad, Wolt-dadırsa `WOLT_SLUGS`-a filial slug-ları (və `WOLT_ONLY`-ə), öz saytı varsa `main()`-ə scrape funksiyası; `index.html`-də `--<Ad>` rəngi; `scrape.yml`-də `case` siyahısına açar əlavə edin.


## Sevimlilər, qiymət dəyişikliyi, vahid qiymət
- **Alış-veriş siyahısı** (♥): məhsul kartında ♡ düyməsi; siyahı brauzerdə (`localStorage`) saxlanır, mağazalar üzrə cəm və "hər məhsulu ən ucuz yerdən alsan" göstərilir, mətn kimi kopyalanır.
- **Qiymət dəyişikliyi**: scraper hər mağaza üçün əvvəlki qiymətlə müqayisə edir; dəyişən məhsulda `pp` (əvvəlki qiymət) və `pd` (tarix) yazılır — kartda ↓/↑ nişanı, ana səhifədə "ucuzlayanlar". Tam tarixçə `data/history.json`-dadır (açar: `hk(mağaza|ad)`, scraper və index.html-də eyni; 90 gün).
- **Vahid qiymət**: çəkili qablaşdırma 1 kq-a, həcmli 1 L-ə görə (>5 kq/L göstərilmir); "Vahid qiymət" sıralaması.

## Wolt söndürmə açarı və təhlükəsiz yazma
- `WOLT_ENABLED=0` (və ya `python scrapers/scraper.py --no-wolt`): Wolt-a heç bir sorğu göndərilmir. GitHub-da: Settings → Variables → `WOLT_ENABLED`.
- Köhnə Wolt qiymətləri silinmir; `stale: true` ("arxiv qiymət") işarələnir, ən ucuz/qənaət hesabına girmir; `meta[mağaza]`-da `source_type`, `auto_update`, `last_success`.
- `prices.json` yazılmazdan əvvəl sxem/qiymət yoxlanır, mağaza nəticəsi >60% azalıbsa köhnə data saxlanır, yazma atomikdir.
- Testlər: `pip install pytest && python -m pytest tests` (`scrapers/sources.py` — mənbə konfiqurasiyası).
