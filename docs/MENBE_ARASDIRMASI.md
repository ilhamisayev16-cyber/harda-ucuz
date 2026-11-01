# Qiymət mənbələrinin araşdırılması

Yoxlama tarixi: **1 noyabr 2026, Bakı vaxtı**.

Məqsəd: mövcud səkkiz mağazada — Bravo, OBA, Araz, Neptun, Tamstore, Rahat, Bazarstore və SPAR — mağazanın dərc etdiyi qiyməti, satış kanalını və şərtlərini ayrıca saxlamaq. Mağaza siyahısı bu işin çərçivəsində dəyişmir.

## Yoxlamanın sərhədi

Rəsmi səhifələr veb axtarış/açılış vasitəsi ilə yoxlanılıb; nəticələrdə keşlənmiş səhifələr də ola bilər. Bu iş mühitinin çıxış siyasəti mağaza domenlərinə birbaşa scraper sorğularına icazə vermir. Buna görə burada mənbənin mövcudluğu və dərc etdiyi məlumat təsdiqlənir, GitHub Actions-dan canlı inteqrasiya, kassadakı qiymət və stok təsdiqlənmir. Axtarış nəticəsinin yenicə indekslənməsi kataloqun qüvvədə olması demək deyil.

## Mövcud mağazaların rəsmi mənbələri və əlavə kanalları

| Mənbə | Təsdiqlənmiş məlumat | İnteqrasiya qərarı |
| --- | --- | --- |
| [Bravo xüsusi təklifləri](https://www.bravosupermarket.az/special-offers/) | Yoxlama zamanı 29 oktyabr–11 noyabr kampaniyaları Hiper, Super, Market və Express üçün ayrı göstərilir. | Ən güclü kataloq namizədi. Mağaza formatını və kampaniya tarixlərini məhsul qiyməti ilə birlikdə saxlamaq lazımdır. |
| [Bravo Hiper kampaniyası](https://www.bravosupermarket.az/special-offers/made-in-azerbaijan-5/) | Eyni tarix aralığını göstərir və [Publuu kataloqunu](https://publuu.com/flip-book/369021/2681082) rəsmi səhifədə yerləşdirir. Viewer-dən qiymət mətni çıxmadı. | Əvvəl kiçik əl ilə yoxlanmış kataloq idxalı; sonra şəkil/PDF emalı. Naməlum OCR nəticəsini avtomatik qiymətə çevirməmək. Publuu keçidi kampaniya dəyişəndə yenidən rəsmi səhifədən tapılmalıdır. |
| [Bravo Online](https://bravosupermarket.az/mobile-application/) | Rəsmi səhifə onlayn alış-veriş üçün Bravo mobil tətbiqinə yönəldir. | Rəsmi məhsul məlumat axını/ixracı üçün namizəd. Açıq, işlək qiymət API-si bu yoxlamada tapılmayıb; tətbiqin qiyməti ayrıca onlayn kanaldır. |
| [Tamstore kampaniyaları](https://www.tamstore.az/az/kampaniyalar) | Elektron jurnal və kampaniya şəkilləri var; açılmış şəkillərdən biri 11–14 mart tarixli idi. | Tam kataloq əvəzinə tarixli kampaniya idxalı. Köhnə şəklin hələ saytda olması cari qiymət üçün sübut deyil. |
| [Tamstore şərtləri](https://www.tamstore.az/az) və [FAQ](https://www.tamstore.az/az/haqqimizda) | Ana səhifə kampaniya/keşbek üçün bonus kartının təqdim edilməsini bildirir; FAQ kampaniyanın bütün filiallara aid olduğunu deyir. | Bonus kartı şərtini qiymət yanında göstərmək. Ümumi FAQ məhsulun konkret filialda stokda olduğunu sübut etmir. |
| [Rahat aksiyaları](https://rahatmarket.az/az/aksiyalar/rahat-market) | Kampaniya və məhsul şəkilləri açıqdır; oxunaqlı tam məhsul/qiymət cədvəli alınmadı. | Şəkil/PDF əsasında yoxlanan kampaniya idxalı namizədi; müddət və filial şərtləri hər kataloq üçün ayrıca yoxlanmalıdır. |
| [Neptun](https://neptun.az/) | Ana səhifədən oxunaqlı məhsul kataloqu alınmadı. Axtarışda rəsmi domendə köhnə kampaniya PDF-ləri görünür. | Hazırda canlı qiymət mənbəyi kimi aktivləşdirmək üçün kifayət qədər sübut yoxdur. Köhnə PDF qiymətini cari kimi istifadə etməmək; işlək kataloq və ya rəsmi məlumat axını gözləmək. |
| [SPAR Azerbaijan — rəsmi beynəlxalq səhifə](https://spar-international.com/country/azerbaijan-2/) | Yerli operatorun Araz olduğu təsdiqlənir; ayrıca məhsul qiymət kataloqu verilmir. | Operatorun eyni olması Araz qiymətlərinin SPAR üçün də keçərli olduğunu sübut etmir. Yalnız SPAR-ı açıq göstərən kampaniyanı və həmin kampaniyanın şərtlərini idxal etmək. |
| [OBA](https://oba.az/) və [məhsul kataloqu](https://oba.az/products/) | Ana səhifədə tarixli ümumi kampaniyalarla yanaşı, 22 oktyabr–1 noyabr “Sürətlə Qənaət et!” təklifi OBA Plus üzvlərinə özəl göstərilir; kassada tətbiqin oxudulması tələb olunur. Mövcud scraper məhsul kataloqundan istifadə edir. | Mövcud kataloq saxlanılır; ümumi və üzvlük tələb edən kampaniya qiymətlərini ayırmaq. GTIN yalnız mənbə onu açıq verərsə götürülməlidir. |
| [Araz](https://arazmarket.az/) | Layihə hazırda rəsmi API-dən məhsul və onlayn qiymət toplayır. Veb aləti ilə məhsul siyahısının bu yoxlamada açılması alınmadı. | Mövcud rəsmi inteqrasiyanı əsas saxlamaq; məhsul cavabında varsa GTIN, qiymətin vaxtı və kampaniya şərtlərini qorumaq. Yeni API və ya barkod sahəsinin mövcudluğu bu araşdırmada təsdiqlənmir. |
| [Bazarstore](https://bazarstore.az/) | Rəsmi onlayn kataloq və çatdırılma ünvanı/mağaza seçimi görünür; 28 May, Gənclik, Xətai və başqa seçimlər var. Mövcud scraper rəsmi kataloqdan qiymət toplayır. | Mövcud kataloq saxlanılır; mümkün olduqda seçilmiş filial və onlayn kanal konteksti qeyd edilir. Məhsul GTIN-i yalnız açıq və yoxlanmış sahədən götürülməlidir; daxili SKU barkod sayılmamalıdır. |

## Dəqiqliyi artıran prioritetlər

1. **Məhsul üzrə yoxlama vaxtı.** Mağazanın bir sorğusunun uğurlu olması bütün köhnə məhsulları təzə etmir. Hər təklifin öz son müşahidə vaxtını saxlayıb müddəti keçənləri ən ucuz/qənaət hesabından çıxarmaq.
2. **Kanalı aydın göstərmək.** Rəsmi onlayn qiymət, tarixli rəsmi kampaniya və Wolt qiyməti ayrı mənalar daşıyır. Wolt qiymətindən faiz çıxıb rəf qiyməti yaratmamaq.
3. **Kataloq idxalı üçün sübut.** Məhsul adı, qablaşdırma/ölçü, qiymət, rəsmi səhifə və kataloq keçidi/səhifə nömrəsi, başlanğıc/bitmə tarixi, filial/format və kart şərti saxlanmalıdır. İl göstərilməyibsə və ya tarix birmənalı deyilsə, idxal əl ilə yoxlanmalıdır.
4. **Bravo ilə kiçik sınaq.** Bir Hiper kataloqundan 20–30 aydın məhsulu yoxlayıb Wolt ilə qiymət fərqini ölçmək. Sonra Super/Market/Express üçün ayrıca genişləndirmək; formatlar arasında minimum qiyməti ümumi mağaza qiyməti kimi göstərməmək.
5. **Ştrix-kodla uyğunlaşdırma.** Mənbədə GTIN varsa onu ölçü/faizlə birlikdə istifadə etmək; eyni barkodda belə satış vahidi, çoxlu paket və çəkiyə görə satış şərtlərini yoxlamaq. Naməlum barkod uydurmamaq.
6. **Səhv qiymət bildirişi.** İstifadəçi filial, alış tarixi və qəbz/qiymət etiketi ilə düzəliş göndərə bilsin. Şəxsi məlumatları silinmiş sübut baxış növbəsinə düşsün; təsdiqsiz qiymət avtomatik yayımlanmasın.
7. **Rəsmi məlumat axınları.** Mövcud mağazalardan, xüsusən Bravo Online üçün razılaşdırılmış CSV/JSON ixracı istəmək; Araz, OBA və Bazarstore-un mövcud rəsmi kataloqlarında varsa GTIN və kampaniya şərtlərini qorumaq. Yeni məlumat axını və ya sahə təsdiqlənənə qədər bu, gələcək işdir.

Növbəti mərhələnin üç əsas istiqaməti: tarix/şərtləri yoxlanan kataloq idxalı; rəsmi məlumat axını və GTIN; filial və mənbə üzrə ayrıca qiymət tarixçəsi. Sonuncu üçün Wolt filiallarını birləşdirərkən eyni məhsulun təkrar qeydlərini və GTIN uyğunluğunu da yoxlamaq lazımdır. Hazırda bu, gələcək yoxlama mövzusudur, canlı filial korpusu ilə təsdiqlənmiş düzəliş deyil.

## İdxalı aktivləşdirmə meyarları

- Rəsmi səhifədən məhsula və qiymətə təkrar əldə edilən keçid var.
- Satış kanalı, ölçü və qüvvədəolma vaxtı aydındır; kart, filial, stok və minimum alış şərtləri itib getmir.
- Köhnə kampaniya bitəndə qiymət avtomatik müqayisədən çıxır.
- Boş/yarımçıq cavab köhnə qiymətə yeni yoxlama vaxtı yazmır.
- Canlı mənbə nümunələri ilə yoxlama və avtomatlaşdırılmış parser testləri keçib.

Bu sənəddəki namizədlərin siyahısı onların scraper-də aktiv olması demək deyil. Təsdiqlənməmiş mənbələrdən qiymət əlavə edilməməlidir.
