# 🛒 QİYMƏTMÜQAYİSƏ

Azərbaycan supermarketlərindəki ərzaq qiymətlərini müqayisə edən sayt.

## Fayllar

```
qiymet-project/
├── index.html              ← Saytın özü
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
2. Scraper Bravo, Neptun (Wolt), Araz, OBA-dan qiymətləri toplayır
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

## Mağazalar
- **Bravo** → Wolt
- **Neptun** → Wolt  
- **OBA** → oba.az
- **Araz** → arazmarket.az API (+ Wolt)
- **Tamstore**, **Rahat** → Wolt
- **Bazarstore** → bazarstore.az (öz saytı, nopCommerce HTML)

## Yeni mağaza əlavə etmək
`scraper.py` faylında `SCRAPERS` lüğətinə yeni scrape funksiyası əlavə edin.


## Sevimlilər, qiymət dəyişikliyi, vahid qiymət
- **Alış-veriş siyahısı** (♥): məhsul kartında ♡ düyməsi; siyahı brauzerdə (`localStorage`) saxlanır, mağazalar üzrə cəm və "hər məhsulu ən ucuz yerdən alsan" göstərilir, mətn kimi kopyalanır.
- **Qiymət dəyişikliyi**: scraper hər mağaza üçün əvvəlki qiymətlə müqayisə edir; dəyişən məhsulda `pp` (əvvəlki qiymət) və `pd` (tarix) yazılır — kartda ↓/↑ nişanı, ana səhifədə "ucuzlayanlar". Tam tarixçə `data/history.json`-dadır (açar: `hk(mağaza|ad)`, scraper və index.html-də eyni; 90 gün).
- **Vahid qiymət**: çəkili qablaşdırma 1 kq-a, həcmli 1 L-ə görə (>5 kq/L göstərilmir); "Vahid qiymət" sıralaması.
