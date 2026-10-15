# QiymətMüqayisə — layihənin tam izahı (ChatGPT / yeni developer üçün)

> Bu sənəd layihəni sıfırdan başa salmaq üçündür: nə edir, data haradan və necə yığılır, necə təmizlənir və təsnif olunur,
> saytda məhsullar necə müqayisə olunur, nələr bilərəkdən belə seçilib və hansı zəif yerlər var.
> ChatGPT-yə verəndə təklif olunan başlanğıc: *"Aşağıdakı sənəd mənim Bakı supermarket qiymət müqayisə saytımın izahıdır.
> Onu oxu, sonra mənə [sual / dəyişiklik] ilə kömək et."*

---

## 1. Layihə nədir

**Məqsəd:** Bakıdakı supermarketlərin qiymətlərini bir yerdə göstərmək: istifadəçi bir məhsulu axtarır və hansı mağazada ən ucuz olduğunu görür.

- **Sayt:** statik veb-sayt (GitHub Pages), backend yoxdur. Bir fayl: `index.html` (vanilla JavaScript, framework yoxdur).
- **Data:** `data/prices.json` (~8–10 MB) — scraper hər gün yeniləyir. Sayt bu faylı brauzerdə oxuyur və bütün hesablamaları (qruplaşdırma, axtarış, süzgəc) **brauzerdə** edir.
- **Scraper:** `scrapers/scraper.py` (Python), GitHub Actions ilə hər gün 06:00 (Bakı vaxtı) işləyir və nəticəni repoya commit edir.
- **Mağazalar (7):** Bravo, OBA, Araz, Neptun, Tamstore, Rahat, Bazarstore.
- **Həcm:** təxminən 53–67 min məhsul sətri (mağaza × məhsul), ~140 alt kateqoriya, 21 ana qrup.
- **Dil:** interfeys Azərbaycan dilindədir. Məhsul adları qarışıqdır: Azərbaycan (ə ı ö ü ç ş ğ), ruscadan latın hərflərinə çevrilmiş (Xlebtsi/Xlebçi), türk və ingilis sözləri.

```
qiymet-muqayise/
├── index.html                  ← bütün sayt (HTML + CSS + JS, ~100 KB)
├── data/
│   ├── prices.json             ← əsas data (scraper yazır, sayt oxuyur)
│   └── history.json            ← qiymət tarixçəsi (yalnız dəyişənlər, 90 gün)
├── scrapers/scraper.py         ← bütün scrape + təsnifat məntiqi (~1500 sətir)
├── requirements.txt            ← requests, beautifulsoup4, lxml
├── .github/workflows/scrape.yml← gündəlik avtomatik scrape
├── .github/dependabot.yml      ← asılılıq təhlükəsizlik yeniləmələri
└── docs/LAYIHE_ARXITEKTURASI.md← bu sənəd
```

---

## 2. Ümumi axın (pipeline)

```
        ┌──────────── GitHub Actions (hər gün 06:00 Bakı) ────────────┐
        │                                                              │
Mənbələr│  Wolt API ─┐                                                 │
        │  Araz API ─┤                                                 │
        │  oba.az ───┼─►  scraper.py                                   │
        │  bazarstore┘    1. məhsulları çək (ad, qiymət, çəki, şəkil)   │
        │                 2. mağaza kateqoriyasına + ada görə təsnif et   │
        │                 3. öz sayt qiyməti + Wolt qiymətini birləşdir   │
        │                 4. əvvəlki qiymətlə müqayisə (pp/pd, history)  │
        │                 5. data/prices.json + data/history.json yaz    │
        │                 6. "Price Bot" commit + push                   │
        └──────────────────────────────┬───────────────────────────────┘
                                       ▼
                         GitHub Pages: index.html
                         brauzer prices.json-u yükləyir və
                         7. məhsulları mağazalar arası eyni-məhsul kartlarına qruplaşdırır
                         8. axtarış / süzgəc / sıralama / siyahı göstərir
```

İki əsas çətin problem: **(a)** hər mağazanın data formatı və adlandırması fərqlidir → eyni məhsulu tapmaq; **(b)** bəzi mağazaların öz katalogu yoxdur, yalnız Wolt-dadır, Wolt qiyməti isə rəf qiymətindən bahadır.

---

## 3. Data mənbələri (hər mağaza necə yığılır)

| Mağaza | Mənbə | Necə | Qiymət dəqiqliyi |
|---|---|---|---|
| **Bravo** | yalnız Wolt | Wolt kataloqu, **6 filial** birləşdirilir | Wolt qiyməti (rəfdən bir qədər yüksək) |
| **Neptun** | yalnız Wolt | **5 filial** birləşdirilir | Wolt qiyməti |
| **Tamstore** | yalnız Wolt | **6 filial** birləşdirilir | Wolt qiyməti |
| **Rahat** | yalnız Wolt | 1 filial (Yasamal), başqası tapılmadı | Wolt qiyməti |
| **Araz** | öz API-si + Wolt | `arazmarket.az` API (əsas) + Wolt (əlavə) | öz sayt qiyməti = dəqiq |
| **OBA** | öz saytı + Wolt | `oba.az` HTML (əsas) + Wolt | öz sayt qiyməti = dəqiq |
| **Bazarstore** | öz saytı | `bazarstore.az` HTML (Wolt-da yoxdur/istifadə olunmur) | öz sayt qiyməti = dəqiq |

> Qaydalar: mağazanın **öz saytından** gələn qiymət (`price`) həmişə Wolt qiymətindən (`wolt_price`) üstündür.
> Saytda Wolt qiymətləri **W** işarəsi ilə göstərilir. Bravo/Neptun/Tamstore/Rahat-ın öz kataloqu yoxdur (mobil tətbiq API-ləri bilərəkdən istifadə edilmir), buna görə onlar yalnız Wolt-dan gəlir.

### 3.1 Wolt (Bravo, Neptun, Tamstore, Rahat + Araz/OBA əlavəsi)
- Sənədsiz "consumer assortment" API: `consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/<filial-slug>/assortment` (kateqoriya ağacı) və `.../categories/slug/<kateqoriya>?language=az&page_token=...` (səhifələmə `page_token` ilə).
- Hər yarpaq kateqoriya çəkilir; məhsulun Wolt kateqoriya yolu (`Üst > Alt > Yarpaq`) təsnifat üçün saxlanılır.
- Qiymət qəpiklə gəlir (`/100` ilə manata çevrilir). **Çəkiyə görə satılan** məhsul üçün `sell_by_weight_config.grams_per_step` oxunur (`wt` sahəsi): Wolt belə məhsulu "~250 q" parça kimi göstərir, qiymət isə **1 kq üçündür**.
- Limit (HTTP 429): GitHub Actions IP-lərinə Wolt bəzən limit qoyur. Hər sorğu 4 dəfə təkrarlanır; alınmayanlar sonda bir-bir, uzun fasilə ilə 3 dəfə yenidən yoxlanılır; qalan səhvlər logda yazılır.
- **Çoxfilialli rejim (`WOLT_BRANCHES`):** hər şəbəkənin bir neçə filialı (Wolt-un Bakı ana səhifəsi sorğusu ilə tapılıb) ardıcıl yüklənir, məhsullar **ada görə birləşdirilir** (hipermarketlər kiçik filialların tapmadığı minlərlə məhsul gətirir), qiymət = filiallar üzrə **median (aşağı orta)**. Ölçmə: Neptun/Tamstore qiymətləri filiallarda 100% eynidir; Bravo hipermarketi (Koroğlu) ortaq məhsullarda ~3% fərqlidir, ona görə median. Mühit dəyişəni ilə dəyişdirmək olar: `WOLT_BRANCHES_BRAVO=slug1,slug2`. Mənbə üsulu (tək filial → median) dəyişən gün saxta "qiymət dəyişdi" nişanı yazılmır.

### 3.2 Araz
- `b7x9kq.arazmarket.az/api/categories` (26 üst kateqoriya) və `/products/category/<id>?page=1&per_page=5000` — hər üst kateqoriya bir sorğu ilə (səhifələmə etibarsız idi, `per_page=5000` ilə düzəldi). Məhsulda `category_title` var.
- Qiymət endirimli qiymət daxil, API-dən. Wolt-dan əlavə məhsullar da götürülür (Araz kataloqunda olmayan).

### 3.3 OBA
- `oba.az/products/?start=<offset>` — server tərəfindən render olunmuş HTML; hər səhifə 24 məhsul kartı (`<!-- Product card -->`), regex ilə ad / kateqoriya / qiymət çıxarılır. ~12 dəqiqə çəkir.
- OBA-nın cəmi ~17 iri kateqoriyası var ("Şirniyyat", "Quru qida"...), alt bölgüsü yoxdur → alt növ **ada görə** təyin olunur.

### 3.4 Bazarstore
- nopCommerce HTML. Menyudan ~357 yarpaq kateqoriya tapılır, hər birinin səhifələri çəkilir; sonra "Bütün məhsullar" siyahısı ilə kateqoriyaya düşməyənlər əlavə edilir (cəmi ~12 min məhsul).
- Məhsul məlumatı `data-bzdl-item` JSON atributundadır (`item_name`, `price`, `item_category`).
- Adlar 40 simvolda kəsilir və BÖYÜK hərflə yazılır → `_title()` ilə düzəldilir; sayt tərəfində kəsilmiş son söz üçün xüsusi qayda var.

### 3.5 Öz saytı + Wolt birləşdirmə (`merge_own_wolt`)
Araz/OBA üçün öz siyahı əsasdır; adı ≥0.5 oxşar olan Wolt məhsulu varsa onun qiyməti `wolt_price` kimi əlavə olunur (yalnız fərqlidirsə). Öz kataloqda olmayan Wolt məhsulları ayrıca əlavə olunur.

---

## 4. Data formatı (`data/prices.json`)

```json
{
  "last_updated": "15.10.2026 18:59",
  "stores": ["Bravo","OBA","Araz","Neptun","Tamstore","Rahat","Bazarstore"],
  "groups": [ {"id":"sud","name":"Süd məhsulları və yumurta","cats":["sud","yoqurt","qatiq","kefir", "..."]} , "... 21 qrup"],
  "categories": {
    "sud": {
      "name": "Süd",
      "stores": {
        "Bravo": [ {"name":"Süd Atena 1l", "wolt_price":2.60, "img":"https://...", "wt":250, "pp":2.90, "pd":"2026-10-15"} ],
        "Araz":  [ {"name":"Eker Sutlac 150qr", "price":1.85, "wolt_price":1.99, "img":"https://..."} ]
      }
    }
  },
  "meta": { "Araz": {"updated":"15.10.2026 18:49", "own":5161, "wolt":9640} }
}
```

Sahələr: `price` = mağazanın öz qiyməti, `wolt_price` = Wolt qiyməti, `img` = şəkil linki, `wt` = Wolt-un təxmini parça çəkisi (qram) yalnız çəkiyə görə satılanlarda, `pp`/`pd` = əvvəlki qiymət və dəyişmə tarixi. **Məhsul id-si yoxdur**: məhsul = mağaza + ad. Kateqoriya "yarpaq" səviyyəsindədir (`categories[cid]`), `groups` isə saytdakı ana qrupları sadalayır.

**Təhlükəsizlik qaydası:** scrape boş nəticə qaytararsa köhnə qiymətlər silinmir; hər mağaza ayrıca yadda saxlanır (timeout olsa belə əvvəlki mağazalar itmir).

---

## 5. Kateqoriyalara bölmə (təsnifat)

Hər məhsul 21 ana qrup / 139 alt növdən birinə düşür (Meyvə, Tərəvəz, Süd, Ət, Çörək, Taxıl, Şirniyyat, İçkilər, Gigiyena, Ev, Heyvan yemi, Uşaq, Spirtli, Tütün, Geyim, Sağlam qida, Digər və s.). Məntiq `scraper.py`-dadır (`classify(name, path)`):

1. **Mağazanın öz kateqoriyası (yol) əsasdır** (Wolt: "Süd > Yoqurt", Araz: `category_title`, OBA: kart kateqoriyası, Bazarstore: menyu yolu). Yol seqmentləri ən dərindən yuxarıya yoxlanılır (`_PATH_SPEC` və `_PATH_GEN` regex qaydaları).
2. Yol **ümumi** ("Şirniyyat", "Quru qida", "Ev əşyaları"), **"digər"** və ya naməlumdursa, **məhsulun adına** görə dəqiqləşdirilir (`CATEGORIES`-dəki açar sözlər; **sıra vacibdir**, ilk uyğunluq qalib gəlir).
3. Məhsul adı yolun öz alt növünün açar sözünü təkrar edirsə mağaza rəfi qalır; ad başqa qrupun qida sözü göstərirsə, bu çox vaxt **dad/içlikdir** ("Fındıqlı şokolad" şirniyyatdır, fındıq deyil). Buna görə maddi qaydalar var: sifət qaydası (`-lı/-li`: "limonlu"), meyvə/tərəvəz/ət üçün "ad əvvəlində olmalıdır" qaydası (`_STRICT`), qeyri-qida rəfi qida sözünə uymur ("Rexona … -un- …" un deyil), şirniyyat rəfində dad sözləri və s.
4. **Diakritikasız uyğunluq:** `_f()` = kiçik hərf + `İ/I/ı→i` + `ə→e, ö→o, ü→u, ç→c, ş→s, ğ→g` + kiril → latın. OBA/Bazarstore adları `Gunebaxan Yagi` kimi yazıldığı üçün lazımdır. Ehtiyatlı olmaq üçün `sh→s` kimi aqressiv qaydalar təsnifatda istifadə edilmir (`"Dish"` → `"diş"` səhvinə səbəb olurdu); transliterasiya (`_k`) yalnız ad heç nə verməyəndə ikinci cəhd kimi işlənir.
5. Nəticə: "Digər" kateqoriyası <2%.

Yoxlama: ~56 min (mağaza, ad, yol) nümunəsi olan korpusda köhnə/yeni təsnifat müqayisə olunub, təsadüfi seçmələr əl ilə qiymətləndirilib; sistemli səhv nümunələri düzəldilib (qalan geriləmə ~2–3%, sistemli yox).

`python scrapers/scraper.py --recategorize` mövcud `prices.json`-u şəbəkəsiz yenidən təsnif edir (qeyd: kateqoriya yolu datada saxlanmadığı üçün tam dəqiq olmur, düzgün nəticə növbəti scrape ilə gəlir).

---

## 6. Qiymət dəyişikliyi və tarixçə

- `apply_to_data` mağazanı yazmazdan əvvəl köhnə qiymətləri (ada görə) yeniləri ilə müqayisə edir. Fərq >0.004 ₼ olsa məhsulda `pp` (əvvəlki), `pd` (bugünkü tarix) yazılır. Yaxın günlərdə dəyişibsə (≤14 gün) nişan saxlanır.
- `data/history.json`: `{ "h": { "<açar>": [["2026-10-14", 2.0], ["2026-10-15", 1.7]] } }`. Açar = `hk(mağaza + "|" + ad)` — 64-bit xeş (FNV-1a + djb2, 32 bit hər biri), Python `_hk()` və JS `hk()` **eyni** nəticə verir. Yalnız dəyişən məhsullar saxlanır, 90 gündən köhnələr silinir.
- Saytda: kartda ↓12% / ↑8% nişanı (son 14 gün, ≥2%), ana səhifədə "Son günlərdə ucuzlayanlar" (≥8% və ≤60% enmə, son 7 gün), mağaza sətrinə toxunanda tarixçə.

---

## 7. Sayt (`index.html`) necə işləyir

Hər şey brauzerdə baş verir: `prices.json` yüklənir → hər ana qrup üçün **kartlar** qurulur (lazy, ilk istifadədə) → UI.

### 7.1 Məhsulları mağazalar arası "eyni məhsul" kartına birləşdirmək (`group()`) — ən mürəkkəb hissə
Hədəf: bir kart = **eyni brend + eyni növ/dad + eyni ölçü + eyni faiz**, mağaza başına bir qiymət. Əsas ideyalar:

1. **Normallaşdırma (`fold`, `tokens`, `stem`, `kw`)**: kiçik hərf, diakritika (ə/e, ş/sh, ç/ch, ı/i, ü/u, kiril, İ), vahid yazılışları (`qr/gr/q/g`, `kq/kg`, `l/lt/litr`), ondalıq vergül, şəkilçilər (`-lı/-li`, `-lar/-lər`, `-sı`), ingilis/türk/rus sinonimləri (`TSYN`: peynir=pendir, chicken=toyuq...). Ölçü, faiz, barkod, qablaşdırma səs-küyü sözlərdən çıxarılır.
2. **Atributlar (`parseSize`, `attrs`)**: çəki (q/kq), həcm (ml/L), ədəd, çoxlu qablaşdırma (`12x1.5kq` = 18 kq), faiz (`3.2%`), "kq ilə satılır" (ölçüsüz məhsul = 1 kq üçün qiymət). Yazı səhvləri düzəldilir (`500l` → 500 ml).
3. **`compat()`**: eyni satış növü (kq ilə / qablaşdırılmış), eyni faiz, eyni ölçü ailəsi və fərq ≤0.5 (q/ml-ə çevrilmiş).
4. **Oxşarlıq**: IDF çəkili ortaq sözlər / bütün sözlər ≥ 0.5 (nadir söz çox, ümumi söz az çəkir).
5. **Qadağalar (oxşarlıq = 0)**: fərqli dad/rəng/xətt sözü (`çiyələkli` ≠ `vanilli`, `qırmızı` ≠ `ağ`, `gourmet`, `light`...), fərqli nömrə/model/paket sayı (`2li`, `4+1`, `3in1`), fərqli material (tənəkə ≠ paket, plastik ≠ karton), hər iki adda qarşılığı olmayan məlumatlı söz, marka (ilk söz) yoxdur, qiymət 3 dəfədən çox fərqlənir.
6. **"Əkiz sübutu"**: bir mağaza eyni markanı həmin sözlə və sözsüz (eyni ölçüdə) ayrıca satırsa, o söz fərqləndiricidir (`Doymak Spagetti` ≠ `Doymak İncə Spagetti`).
7. **Kart qurulması**: ən oxşar cütlərdən başlayaraq birləşdirmə; yeni üzv kartdakı **bütün** digər mağaza məhsulları ilə uyğun olmalıdır (zəncir yoxdur); bir kartda bir mağazadan **bir** məhsul; kəsilmiş adlar (Bazarstore 40 simvol) prefikslə uyğunlaşır.

Ölçmələr (əl ilə etiketlənmiş cütlərlə, agent qiymətləndirməsi): köhnə versiyada yeni birləşmələrin təxminən 40%-i səhv idi, indiki versiyada ~0–2% (təsadüfi yoxlama), düzgün birləşmələrin ~20%-i ayrı kartda qalır (qəsdən ehtiyatlıdır: səhv birləşmə "ən ucuz" qiyməti yanlış göstərir, ayrı qalma isə yalnız müqayisəni azaldır).

### 7.2 Qiymət göstərmə
- Kartda **ən ucuz mağaza** yaşıl blokda, altında bütün mağazalar **ucuzdan bahaya** sıralı; ən ucuz yaşıl fon, ən baha qırmızı qiymət; `W` = Wolt qiyməti.
- "Qənaət" = ən bahalı − ən ucuz mağaza fərqi (defolt sıralama: ən çox qənaət əvvəl).
- Çəkiyə görə satılan məhsul: qiymət **1 kq üçün** (`₼/kq`), Wolt-un təxmini parça çəkisi varsa "~250 q ≈ 4.50 ₼" kimi parça qiyməti də göstərilir.
- **Vahid qiymət (`upr`)**: çəkili qablaşdırma ₼/kq, həcmli ₼/L; 5 kq/L-dən böyük ölçülər (toptan/adda səhv) göstərilmir; "Vahid qiymət" sıralaması var.

### 7.3 Axtarış və süzgəclər
- **Global axtarış (`search`)**: sorğu `qparse` ilə sözlərə, ölçüyə, faizə ayrılır; diakritikasız (süd = sud), ingilis (milk, chicken, shampoo), rus-latın, türk, şəkilçili ("südlü", "toyuğu") və yazı səhvli (redaktə məsafəsi ≤1) sorğular dəstəklənir. Uyğunluq balı: söz tam uyğunluğu > prefiks > alt sətir; ad axtarılan sözlə başlayırsa üstünlük; məhsulun alt növü sorğuya uyğundursa bal əlavə; qısa ad (sadə məhsul) uzun addan əvvəl; tapılmasa 1 söz əskik ola bilər. Kateqoriya "çipləri" də göstərilir.
- **Kateqoriya səhifəsi**: alt növ düymələri (məntiqi sıra, say ilə), rejim ("Çəki / Həcm / Kq ilə satılan / Digər"), ölçü və faiz düymələri (cari siyahıya görə), siyahıda süzgəc (eyni uyğunluq funksiyası), sıralama (Qənaət / Ucuz / Vahid qiymət / A→Z).
- **Marşrut** (hash): `#/c/<qrup>`, `#/c/<qrup>/<alt növ>`, `#/c/<qrup>/<kart id>`, `#/c/<qrup>?q=<mətn>`, `#/list`.

### 7.4 Alış-veriş siyahısı (♥)
Kartda ♡; siyahı `localStorage`-da saxlanır (hər element: qrup + adın normallaşmış forması + miqdar, çünki kart nömrələri data yenilənəndə dəyişir). `#/list` səhifəsi: mağazalar üzrə cəm (tam səbət ən ucuz = yaşıl), "hər məhsulu ən ucuz mağazadan alsan" yekunu, miqdar (−/+), mətn kimi kopyalama.

### 7.5 Görünüş və təhlükəsizlik
- Telefon-first: tək sütun, böyük toxunma sahələri; kompüterdə (≥1000 px) CSS `zoom` ilə 1.25–1.7× böyüdülür, məzmun ortada dar sütundadır.
- Məhsul **şəkilləri saytda göstərilmir** (müəllif hüququ riski): əvəzində kateqoriya ikonları (emoji). Datada `img` sahəsi hələ var.
- Content-Security-Policy `<meta>` ilə (`img-src 'self' data:`, `connect-src 'self'`, xarici skript yoxdur); bütün mətn `esc()` ilə təmizlənir.

---

## 8. Avtomatlaşdırma (GitHub Actions)

`.github/workflows/scrape.yml`:
- `schedule`: `0 2 * * *` (UTC) = 06:00 Bakı; əl ilə: `workflow_dispatch` (parametr `store`: `all`, `bravo`, `oba`, ...).
- Python 3.11, `pip install -r requirements.txt`, `python scrapers/scraper.py --store "$STORE"` (giriş whitelist ilə yoxlanır, injection yoxdur).
- Scrape addımı `timeout-minutes: 85`, job 100; commit addımı `if: always()` — vaxt bitsə də hazır olan mağazalar commit olunur. `concurrency: scrape` eyni anda iki scrape qoymur.
- Commit "Price Bot" adından: `git add data/prices.json data/history.json`, `git pull --rebase`, `git push`.
- Tam scrape ~15 dəq (tək filial) və çoxfilialli rejimdə təxminən 30–45 dəq.

Yerli işlətmək: `pip install -r requirements.txt && python scrapers/scraper.py --store bravo --out /tmp/test.json` (`--out` ilə real datanı pozmadan). Sayt üçün: repo kökündə `python3 -m http.server 8765` və `http://localhost:8765/index.html`.

---

## 9. Vacib qərarlar və niyə

| Qərar | Səbəb |
|---|---|
| Backend yoxdur, hamısı statik + brauzerdə hesablama | pulsuz hosting (GitHub Pages), sadəlik; bahası: 8–10 MB JSON və ilk axtarışda ~2–3 san qruplaşdırma |
| Mağaza kateqoriyası əsas, ad ikinci | mağazanın öz bölgüsü daha etibarlıdır; adla təsnifat səhv ola bilər (dad sözləri) |
| Bilərəkdən ehtiyatlı birləşmə | səhv eyni-məhsul = yanlış "ən ucuz" qiymət; ayrı qalmaq yalnız müqayisəni azaldır |
| Wolt qiymətlərini "rəf qiymətinə çevirmək" **edilmir** | Wolt əlavəsi mağaza/filial üzrə sabit deyil; təxmini düzəliş yanıldıcı ola bilər. Əvəzinə `W` işarəsi |
| Median (filiallar üzrə) | bir filialın qiyməti fərqli ola bilər (xüsusilə hipermarket) |
| Bravo/Neptun/Tamstore/Rahat üçün mobil API-lər istifadə edilmir | hüquqi/etik səbəb və etibarlılıq; yalnız açıq Wolt kataloqu |
| Şəkillər göstərilmir | müəllif hüququ riski |

---

## 10. Məlum məhdudiyyətlər

1. **Wolt qiyməti rəf qiymətindən yüksəkdir** (4 mağaza yalnız Wolt-dandır). Bravo-da hipermarket və supermarket fərqli qiymətdədir; yalnız hipermarketdə olan məhsulun qiyməti ~3% fərqli ola bilər.
2. **Yanlış birləşmə/ayrı qalma** hələ mümkündür (təxminən 2% yanlış, ~20% qaçırılmış uyğunluq). Eyni məhsulun fərqli adlandırılması (xüsusilə Bazarstore qısaldılmış adlar) əsas səbəbdir.
3. **Təsnifat** ~2–3% səhv ola bilər (qeyri-adi dad adları, nadir markalar).
4. **Wolt limiti** (429): Actions-da bəzi sorğular alınmaya bilər; log-da `sorğu alınmadı` sayı görünür.
5. **Performans**: ~67 min məhsul ilə ana səhifə ~2 san, ilk axtarış ~3 san (mobildə daha yavaş ola bilər). Gələcək: datanı qruplara bölmək.
6. Məhsul id-si yoxdur; məhsulun adı dəyişsə sevimlilərdən "tapılmadı" olur.
7. OBA-nın öz kateqoriya bölgüsü cəmi 17 iri kateqoriyadır (alt növ adla təyin olunur).

---

## 11. Növbəti ideyalar (hələ edilməyib)

- **Apteklər** (Wolt-da 15+ aptek): dərman/vitamin qiymət müqayisəsi, eyni Wolt kataloq kodu ilə.
- Yeni qida mağazaları Wolt-da: Wolt Market, Delicates, Super Köşk, OBA Market, Bravo Ekspress; kosmetika (Rossmann, The Body Shop), heyvan yemi, uşaq mağazaları.
- Barkodla pulsuz Open Food Facts bazasından tərkib/məlumat.
- Datanı qruplara bölmək (yalnız seçilən kateqoriya yüklənsin), PWA (ana ekrana əlavə, oflayn).
- Köhnə data xəbərdarlığı (mağazanın datası 2 gündən köhnədirsə).

---

## 12. Necə işləyirik (iş qaydası)

- Dəyişikliklər branch-da edilir, **draft PR** açılır, sahibi "merge" deyəndə squash merge olunur; data dəyişəndə `scrape.yml` əl ilə işə salınır.
- Bot data commit-ləri (`Qiymətlər yeniləndi`) `main`-ə düşür, ona görə branch-ı `main`-dən təzələmək lazımdır.
- Layihə bir neçə AI sessiyası tərəfindən paralel inkişaf etdirilir; dəyişiklikdən əvvəl `main`-dəki son vəziyyət yoxlanmalıdır (eyni iş təkrarlanmasın).
