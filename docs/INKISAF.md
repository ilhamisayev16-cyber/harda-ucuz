# Səbət planlaşdırması və məhsul kataloqu

Ana səhifə səbət planlaşdırmasını önə çıxarır: aydın başlıq, iki əsas keçid, böyük toxunma sahələri, mobil və qaranlıq rejimə uyğun rənglər. Kateqoriya siyahısı və mövcud müqayisə funksiyaları saxlanır.

## İstifadə

- Səbətdə hər sətirdə bir məhsul yazılır. `2 x süd 1 L` iki qablaşdırma deməkdir; `1 kq düyü` axtarış sorğusudur. Bir dəfədə ən çox 30 sətir qəbul edilir. Tapılan məhsul istifadəçi seçmədən səbətə əlavə edilmir.
- Tam səbət bir və maksimum iki mağazada müqayisə olunur. Hər istifadə olunan mağazanın yol/çatdırılma xərci əlavə edilir. Köhnə və çatışmayan qiymətlər tam plan kimi təqdim edilmir. Bu, filial stokunun təsdiqi deyil.
- Məhsul kartında “Qiyməti izlə” seçilir və manatla hədd daxil edilir. Yalnız seçilən mağaza və eyni qiymət mənbəyi müqayisə olunur. Mənbə dəyişibsə, izləməni yenidən qurmaq tələb olunur.
- İzləmələr həmin brauzerin localStorage yaddaşında qalır. Ana səhifə izlənən kateqoriyaları yoxlayıb nəticə göstərir. Sayt bağlı olanda push və ya e-poçt göndərilmir; bunun üçün ayrıca bildiriş xidməti lazımdır.

## Sabit kimlik və SEO

`data/product_ids.json` mağaza+məhsul adı xeşini və mövcud GTIN-i saxlanan məhsul kimliyinə bağlayır. Faylı hər build-də sıfırlamaq olmaz. Eyni kartın mağaza sırası dəyişəndə kimlik saxlanır. Ad dəyişibsə, digər məlum təklif və ya GTIN davamlılığı qoruya bilər; heç bir ortaq kimlik yoxdursa yeni məhsul yaranır. Əvvəl ayrı olub birləşən kartların köhnə kimlikləri də işləyir.

`mehsullar/` altında qiymətlər, mənbələr və mövcud tarixçə ilə statik məhsul səhifələri qurulur. Tarixçə müşahidə edilmiş dəyişikliklərdir; gündəlik stok və ya fasiləsiz qiymət qeydi deyil. Kateqoriya səhifələri məhsullara keçid verir. `sitemap-products.xml` məhsul sitemap indeksidir; hər hissədə ən çox 40 000 URL var. Search Console-a həm `sitemap.xml`, həm də `sitemap-products.xml` təqdim edilə bilər.

## Mərhələli yüklənmə

`data/catalog.json` kiçik başlanğıc kataloqudur. Kateqoriya açılarkən yalnız onun `data/catalog/<qrup>-<xeş>.json` faylı gətirilir. Ümumi axtarış və səbət planlaşdırması bütün kateqoriyaları lazım olduqda yükləyir; axtarış hələ ayrıca kiçik indeks istifadə etmir. Şəkillər mövcud qaydada gec yüklənir. Service worker baxılmış kateqoriyaları keşləyir; bütün kataloq əvvəlcədən offline saxlanmır.

## Qurma və yoxlama

```
node scripts/csp_hash.js
node scripts/build_site.js
python -m pytest tests -q
```

Workflow-lar kimlik reyestrini, kateqoriya hissələrini, statik məhsul səhifələrini və sitemap-ləri birlikdə commit edir. Hazırkı kataloq təxminən 60 min məhsul səhifəsi yaratdığı üçün build çıxışı böyükdür (təxminən 256 MB disk istifadəsi); ortaq `assets/catalog.css` üslub təkrarını azaldır. Bu ölçü ilə GitHub Pages çıxış həcmini və build müddətini izləmək lazımdır. Dəyişikliklər özlüyündə yerləşdirmə və ya Google indekslənməsi demək deyil.

## Açıq lisenziyalı şəkillər və qiymət mənbələri

`data/photo_rights.json` mağaza şəkilləri üçün icazə qeydləridir. İlkin `stores` boşdur: mağaza şəkilləri göstərilmir, OFF uyğunluğu və ya ikon seçilir. Yalnız həqiqətən yoxlanmış istifadə hüququ olduqda mağaza koduna (`o`, `a`, `b`) `approved: true` və boş olmayan `evidence` qeydi əlavə edilməlidir. İctimai URL və ya robots.txt özlüyündə belə sübut deyil. Bu nəzarət Wolt qiymətlərini söndürmür.

OFF şəkillərində mənbə səhifəsi, CC BY-SA 3.0 keçidi və dəyişdirilmədiyi göstərilir. Yeni API cavablarından varsa uploader müəllifi də saxlanır. Köhnə müsbət keşlər müəllif məlumatı üçün yenidən soruşulur; yeni sorğu alınmadıqda mövcud keş saxlanır. Konkret şəklin hüquq məlumatının düzgünlüyü mənbədən asılıdır; sayt bütün üçüncü tərəf hüquqlarına təminat vermir.

`OFF_OFFLINE=1 python scrapers/off_images.py` şəbəkəyə çıxmadan mövcud keşlə işləyir. GTIN ilə şəkil seçimi üstün tutulur. GTIN yoxdursa, yalnız eyni alt kateqoriyada tam normallaşdırılmış eyni ad və ölçü, tək şəkil qovluğu və ziddiyyətli GTIN olmadığı halda şəkil paylaşılır. Belə uyğunluq `im_match: exact_name` ilə işarələnir və təsdiqlənmiş barkod yaratmır. Əl ilə gizlədilmiş şəkillər yayılmır.

Böyük onlayn endirim artıq avtomatik Wolt qiyməti ilə əvəz edilmir. Hər iki müşahidə edilmiş qiymət saxlanır, onlayn qiymət açıq işarələnir. Bu qayda növbəti uğurlu scrape-də tətbiq edilir; əvvəl silinmiş qiymətlər uydurularaq bərpa olunmur. Fərqli məlum GTIN-li məhsullar scraper və brauzer müqayisəsində ayrılır; buna görə əvvəl birləşmiş kartlar bölünə bilər. Qiymətin daha tez və ya kassadakı qiymətlə eyni olduğunu bu dəyişikliklər təmin etmir.
