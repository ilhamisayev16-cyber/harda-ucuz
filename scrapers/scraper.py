#!/usr/bin/env python3
"""
QiymətMüqayisə Scraper
  Bravo  -> Wolt
  OBA    -> oba.az
  Araz   -> arazmarket.az API (+ Wolt)
  Neptun -> Wolt
  Tamstore, Rahat -> Wolt
  Bazarstore -> bazarstore.az (nopCommerce HTML)

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

def _low(t):
    """Kiçik hərf + I/İ/ı eyniləşdirilir (saytlar böyük hərfdə "QIRMIZI"/"QİRMİZİ" qarışıq yazır)."""
    return t.replace("İ", "i").replace("ı", "i").replace("I", "i").lower()


_FOLD = str.maketrans("əöüçşğ", "eoucsg")
def _f(t):
    """Diakritiksiz müqayisə: OBA/Bazarstore adları "Gunebaxan Yagi" kimi yazılır."""
    return _low(t).translate(_FOLD)


# ── Kateqoriyalar: Wolt (Bravo/Tamstore), Araz və OBA-nın öz bölgüsünə uyğun ~19 qrup / alt növlər ──────────
# "kw" = məhsul adında açar söz (mağazanın kateqoriyası yoxdursa); kw=[] olanlar yalnız mağaza kateqoriyasına görə.
# SIRA VACİBDİR: ad üzrə ilk uyğun gələn götürülür.
def _c(name, kw=(), excl=()):
    d = {"name": name, "kw": list(kw)}
    if excl: d["excl"] = list(excl)
    return d

CATEGORIES = {
    # geyim / tekstil (Bazarstore, OBA)
    "tekstil":   _c("Ev tekstili",       ["hamam dəsmal","əl dəsmal","yastıq","yorğan","kilim","pərdə","çarpayı","xalça","ədyal","paltar asılqan","əl-üz dəsmal","hamam dəs","alez"]),
    "ayaqqabi":  _c("Ayaqqabı, corab",   ["ayaqqabı","çəkənək","corab","çorab","kalqotka","kapron","ayaqalt"]),
    "geyim":     _c("Geyim",             ["köynək","mayka","futbolka","boxer","şort","gödəkçə","hoody","shirt","kota ","fufayka","svitşot","ətək","etek","köynək","şalvar","şərf"]),
    # ev / gigiyena (ən əvvəl: "limon ətirli qabyuyan" meyvə olmasın)
    "qabyuyan":  _c("Qabyuyan vasitə",   ["qabyuyan","qab yuyan","fairy"]),
    "yuyucu":    _c("Paltar yuyucu",     ["yuyucu","paltaryuyan","kir yuyan","ariel","persil","yumşaldıcı","kondisioner","perwoll","yuma gel","yuma toz","yumuşaldıcı","bingo","avtomat","softener","vernel","pods"]),
    "temizlik":  _c("Təmizlik vasitəsi", ["təmizləyici","ağardıcı","dezinfeksiya","domestos","cif ","təmizlik","təravətləndirici","həşərat","ləkə aparan","ləkə təmizləyən","hava trvt","hava təravətləndirici","ağcaqanad","ovma tozu","vanish","glade","air-wick","wc","bulasik","bulaşıq","sökücü"]),
    "zibil":     _c("Zibil torbası",     ["zibil"]),
    "bisirme":   _c("Folqa, streç, bişirmə", ["folqa","streç","pergament","bişirmə kağız","sellofan"]),
    "kagiz":     _c("Kağız məhsulları",  ["tualet kağız","kağız dəsmal","salfet","dəsmal","kağız məhsul"]),
    "qadin_gig": _c("Qadın gigiyenası",  ["molped","always","kotex","tampon","gigiyenik","gündəlik","bella","ped "]),
    "usaq_baxim":_c("Uşaq baxımı",       ["uşaq bezi","bezi","pampers","huggies","molfix","uşaq şampun","uşaq sabun","uşaq krem","tuman","pants","baby ","junior"]),
    "dis_baximi":_c("Diş və ağız baxımı",["diş","ağız","colgate","listerine","splat","oral-b","oral b"]),
    "sac_boya":  _c("Saç boyası",        ["saç boyası","palette","boyası"]),
    "sac_baximi":_c("Saç baxımı",        ["şampun","saç","balzam","pantene","elseve","head & shoulders","h&s","garnier"]),
    "deo":       _c("Dezodorant",        ["dezodorant","deodorant","deo","antiperspirant","rexona","old spice","speed stick"]),
    "tras":      _c("Təraş",             ["təraş","gillette","ülgüc","arko"]),
    "etir":      _c("Parfüm və ətir",    ["parfüm","ətir","tualet suyu","kolon"]),
    "kosmetika": _c("Makiyaj və kosmetika",["makiyaj","dırnaq boyası","kirpik","dodaq","pudra","maskara","lak ","kosmetik","manikür","miselyar","makyaj"]),
    "beden_baximi":_c("Bədən və üz baxımı",["sabun","duş gel","duş geli","əl kremi","üz kremi","bədən kremi","losyon","nivea","dove","maska","tonik","serum",
                  "bədən üçün","üz üçün","günəş krem","vazelin","pambıq","vanna","geli","sprey","vaseline","prezervativ","əl krem","krem yağı","qulaq çöpü"]),
    # heyvan / uşaq
    "pisik_yemi":_c("Pişik yemi",        ["pişik","whiskas","felix","kitekat","sheba"]),
    "it_yemi":   _c("İt yemi",           ["itlər","köpək","pedigree","chappi","it üçün","it yemi"]),
    "heyvan_diger":_c("Heyvan baxımı, aksesuar", ["nəm yem","quru yem","royal canin"]),
    "usaq_qida": _c("Uşaq qidası",       ["uşaq","sıyıq","bebi","aptamil","nutrilon","kabrita","gerber","hipp","agusha","nanny","fruto","nestogen"]),
    # spirtli / tütün
    "pive":      _c("Pivə",              ["pivə"], ["spirtsiz","alkoqolsuz"]),
    "araq":      _c("Araq və votka",     ["araq","votka","kazatskaya"]),
    "viski":     _c("Viski",             ["viski","burbon"]),
    "serab":     _c("Şərab və şampan",   ["şərab","şampan","vermut","martini","sidr"]),
    "likor":     _c("Konyak, likör, digər",["konyak","brendi","likör","tekila","rakı","spirtli","gin ","beefeater"], ["spirtsiz","alkoqolsuz"]),
    "siqaret":   _c("Siqaret və tütün",  ["siqaret","tütün","terea","heets","ploom","rothmans","sobranie","marlboro","winston","parliament","davidoff","dunhill","compact","pall mall","alışqan","nano ","viceroy","ld club","kent beat","argo","black style","want line"], ["dəsmal","makyaj","hava","qab","oyun","çöpü","qulaq","baby","bag"]),
    # şirniyyat / içki (emal olunmuş məhsullar meyvə-tərəvəzdən əvvəl)
    "pecenye":   _c("Peçenye və biskvit",["biskrem","peçenye","biskvit","kraker","kreker","bisküvit","kurabiye","kurabiyə","pryanik","biskuvi","biskivit","pirojnı","biskuvi","pryannik","pryanko","peçenya","qurabiye","digestive","otrubi","etimek"]),
    "vafli":     _c("Vafli",             ["vafli","gofret"]),
    "keks":      _c("Keks və kruasan",   ["keks","kruasan","rulet","pirojna","kruassan","kruasan","muffin","brauni","browni","cake","popkek","kek","künəfə","topkek","macarons","puf "]),
    "tort":      _c("Tort",              ["tort","paxlava","ptifur","kadayif"]),
    "sokolad":   _c("Şokolad",           ["şokolad","shokolad","baton","choco","pudinq","kitkat","snickers","twix","bounty","pralin","mars ","biskolata","biscolata","today goldies","konfirom","plitka","tweels","alpengold"]),
    "konfet":    _c("Konfet, jele, saqqız",["konfet","karamel","jele","zefir","draje","saqqız","jelibon","marmelad","pastila","roshen","ülker","tic tac","sour","qummi","haribo","kinder","ferrero","raffaello","lolipop","candy","bonbon","medvejata","toybox","bükmə","ozmo","kakoslu","gummi","marshmallow","sufle","waflim","bebeto","chupa chups"]),
    "halva":     _c("Halva və lokum",    ["halva","lokum","kozinak","pişmaniyə","pismaniye"]),
    "dondurma":  _c("Dondurma",          ["dondurma","plombir","cornetto","magnum","algida","vienetta","maxibon","eskimo"]),
    "bal":       _c("Bal",               ["təbii bal","çiçək balı","bal ","dağ balı","çiçək balı","cökə balı","ağac balı","süzmə bal"]),
    "krem_pasta":_c("Şokolad əzməsi, krem pasta",["nutella","əzmə","krem şokolad","krem pasta","şanti"]),
    "energetik": _c("Enerji içkisi",     ["red bull","monster","burn ","hell energy","enerji"]),
    "kola":      _c("Kola və qazlı içki",["kola","pepsi","fanta","sprite","qazlı içki","soda","qazlı","cola","mountain dew","mirinda","7up","kokteyl"]),
    "limonad":   _c("Limonad",           ["limonad","içki","icki","mountain dew","kvas","moxito"]),
    "soyuq_cay": _c("Soyuq çay",         ["soyuq çay","ice tea","fuse tea","bubble tea","buzz tea"]),
    "cay":       _c("Çay",               ["çay","lipton","ahmad","azərçay","pekoe","tamashaee","akbar","greenfield","buket"], ["çaydan"]),
    "qehve":     _c("Qəhvə və kakao",    ["qəhvə","nescafe","lavazza","kofe","kakao","jacobs","caffito","3-də 1","3ü 1","monarch","cappuccino","latte"]),
    "sire":      _c("Şirə və nektar",    ["şirəsi","şirə","mors","nektar","meyvə suyu","alma suyu","portağal suyu","kompot","sandora","cappy"]),
    "qazli_su":  _c("Qazlı su, mineral",  ["mineral su","qazlı su","borjomi","narzan"]),
    "su":        _c("Su",                ["içməli su","mənbə suyu","qazsız","essentuki","yessentuki","sirab","bonaqua","badamlı","dübrar","kəhriz","sarıkız","damla su"]),
    "mayonez":   _c("Mayonez",           ["mayonez"]),
    "ketcup":    _c("Ketçup və sous",    ["ketçup","ketchup","sous"]),
    "xardal":    _c("Xardal, xrən, acika",["xardal","xrən","acika"]),
    "sirke":     _c("Sirkə",             ["sirkə"]),
    "zeytun_yagi":_c("Zeytun yağı",      ["zeytun yağ"]),
    "bitki_yagi":_c("Bitki yağı",        ["günəbaxan","ayçiçəyi yağ","bitki yağ","qarğıdalı yağ","gunebaxan","günəbaxan yağ"]),
    "makaron":   _c("Makaron",           ["makaron","spagetti","vermişel"]),
    "eriste":    _c("Əriştə",            ["əriştə","doşirak","noodle"]),
    "corek":     _c("Çörək",             ["çörək","lavaş","çörəyi","coreyi","hot dog","tost","bulka"]),
    "hazir_yemek":_c("Hazır yemək, şorba",["pelmen","manti","xinkali","vareniki","naget","nuggets","pizza","piroq","lahmacun","hazır yemək","şorba","xacapuri","hazır sup","sup ","xəngəl","dolma","kabab","xəmir"]),
    "susi":      _c("Suşi",              ["suşi","sushi","nori"]),
    "cips":      _c("Çips",              ["çips","chips","popkorn","lays","pringles","cheetos","çubuq","crisp","potato","xlebsi","suxari","snack","sticks","poof","joyzz"]),
    "tum":       _c("Tum və ləpə",       ["tum","tumu","ləpə","suxari"]),
    "konserv":   _c("Konserv",           ["konserv","tomatda","sardina","kilka","ajvar","salatı","leco","lecho"]),
    "zeytun":    _c("Zeytun",            ["zeytun","maslin"]),
    "tursu":     _c("Turşu",             ["turşu"]),
    "pomidor_pasta":_c("Pomidor pastası", ["pomidor pasta","tomat pasta"]),
    "murebbe":   _c("Mürəbbə və cem",    ["mürəbbə","povidla","cem ","povidlo","bəkməz","behmez"]),
    # ət
    "sosis":     _c("Sosis",             ["sosis","sosiska"]),
    "kolbasa":   _c("Kolbasa",           ["kolbasa","salam","servelat","vetçina","sucuq","sucuk","jambon","krakov","doktorskaya","rosko"], ["sosis"]),
    "hise":      _c("Hisə verilmiş ət",  ["hisə verilmiş","hisə","bekon"]),
    "deniz":     _c("Dəniz məhsulları",  ["krevet","midiya","kalamar","kürü","xərçəng"]),
    "baliq":     _c("Balıq",             ["balıq","tuna","skumbriya","losos","siyənək"]),
    "toyuq":     _c("Toyuq",             ["toyuq","cücə","broylyer","bud","qanad","tabaka"]),
    "dana_ati":  _c("Dana əti",          ["dana"]),
    "qoyun_ati": _c("Qoyun, quzu əti",   ["qoyun","quzu"]),
    "hindi":     _c("Hindi",             ["hindi"]),
    "et_diger":  _c("Digər ət məhsulları",["kotlet","küftə"]),
    # süd məhsulları
    "pendir":    _c("Pendir",            ["pendir"]),
    "kere_yagi": _c("Kərə yağı",         ["kərə yağ","butter","spred","marqarin","margarin","əridilmiş yağ","eridilmish yag"]),
    "xama":      _c("Xama",              ["xama","smetana"]),
    "qaymaq":    _c("Qaymaq",            ["qaymaq"]),
    "kesmik":    _c("Kəsmik",            ["kəsmik"]),
    "sirok":     _c("Sırok və desert",   ["sırok","desert"]),
    "yoqurt":    _c("Yoqurt",            ["yoqurt","yogurt"], ["içki","şirə"]),
    "qatiq":     _c("Qatıq",             ["qatıq","qatığı"]),
    "kefir":     _c("Kefir və ayran",    ["kefir","ayran"]),
    "sud":       _c("Süd",               ["süd","şor"], ["kakao","soya"]),
    "yumurta":   _c("Yumurta",           ["yumurta"]),
    "qoz":       _c("Qoz-fındıq, quru meyvə",["fındıq","qoz","badam","fıstıq","kişmiş","qurudulmuş","çərəz","püstə","kaju","xurma","quru ərik","innab","araxis","antep","noğul","toxumu"]),
    # tərəvəz
    "kartof":    _c("Kartof",            ["kartof"]),
    "pomidor":   _c("Pomidor",           ["pomidor","tomat"]),
    "xiyar":     _c("Xiyar",             ["xiyar"]),
    "soyan":     _c("Soğan",             ["soğan","soyan"]),
    "kelem":     _c("Kələm",             ["kələm","kapusta"]),
    "yerkoyu":   _c("Yerkökü",           ["yerkökü","morkov"]),
    "cuqundur":  _c("Çuğundur",          ["çuğundur","svekla"]),
    "badimcan":  _c("Badımcan",          ["badımcan"]),
    "biber":     _c("Bibər",             ["bibər"]),
    "sarimsaq":  _c("Sarımsaq",          ["sarımsaq"]),
    "goyerti":   _c("Göyərti",           ["göyərti","cəfəri","şüyüd","reyhan","ispanaq","kərəviz"]),
    "gobelek":   _c("Göbələk",           ["göbələk"]),
    "balqabaq":  _c("Balqabaq, kabak",   ["balqabaq","kabak"]),
    # meyvə
    "alma":      _c("Alma",              ["alma"], ["sirkə"]),
    "armud":     _c("Armud",             ["armud","heyva"]),
    "saftal":    _c("Şaftalı, ərik",     ["şaftalı","nektarin","ərik","gavalı"]),
    "gilas":     _c("Gilas, albalı",     ["gilas","albalı"]),
    "uzum":      _c("Üzüm",              ["üzüm"], ["sirkə","şərab","kişmiş"]),
    "banan":     _c("Banan",             ["banan"]),
    "kivi":      _c("Kivi",              ["kivi"]),
    "limon":     _c("Limon",             ["limon"]),
    "portaqal":  _c("Portağal",          ["portağal","portakal"]),
    "mandarin":  _c("Mandarin, qreypfrut",["mandarin","qreypfrut","naringi"]),
    "nar":       _c("Nar",               ["nar"]),
    "ekzotik":   _c("Ekzotik meyvə",     ["ananas","avokado","avakado","mango","kokos","papaya","pitaya"]),
    "gile":      _c("Giləmeyvə",         ["çiyələk","moruq","qaragilə","böyürtkən","əzgil"]),
    "qarpiz":    _c("Qarpız, yemiş",     ["qarpız","yemiş"]),
    # bakaliya
    "duyu":      _c("Düyü",              ["düyü","pirinc","sella","basmati"]),
    "merci":     _c("Mərcimək",          ["mərcimək"]),
    "noxud":     _c("Noxud",             ["noxud"]),
    "fasulya":   _c("Lobya, fasulya",    ["fasulya","lobya"]),
    "qarabashaq":_c("Qarabaşaq",         ["qarabaşaq","grechka"]),
    "yulaf":     _c("Yulaf",             ["yulaf","ovsyanka"]),
    "bulgur":    _c("Bulğur",            ["bulğur","bulqur","manna","yarma"]),
    "un":        _c("Un",                ["buğda unu","ali növ un","birinci növ un","çovdar unu","qarğıdalı unu","unu","un"]),
    "seher":     _c("Səhər yeməyi, müsli",["müsli","qranola","corn flakes","səhər yemək","lopa","səhər yeməyi","nesquik","gerkules"]),
    "duz":       _c("Duz",               ["duz","xörək duzu"]),
    "sekerqum":  _c("Şəkər",             ["şəkər","qənd"]),
    "istiot":    _c("İstiot və ədviyyat",["istiot","ədviyyat","zirə","darçın","mixək","kəkik","sarıkök","zəfəran","paprika","pul bibər","acı biber","aci biber","kara biber","qarabibər","keşniş","qabartma tozu","vanilin","kraxmal","maya"]),
    "bulyon":    _c("Bulyon",            ["bulyon"]),
    # digər
    "saglam":    _c("Sağlam və diyet qida",["dietik","diyet","diabetik","protein","qlütensiz","glutensiz","vitadiet","fitnes","fitness"]),
    "mesis":     _c("Mətbəx və məişət əşyaları",["stəkan","boşqab","qaşıq","çəngəl","tava","qazan","süpürgə","əlcək","kibrit","batareya","lampa","plastik","paket","süngər","fincan","saxlama","mətbəx","qab ","şüşə qab","ləyən","organayzer","asılqan","piknik","bıçaq","süzgəc","kley","mop","fırça","daraq","tərlik","bəzək","stol","ütü","çanta","qabı","dəsti","şüşə ","bez ","torbası","ventilyator","çamadan","tük toplayıcı","örtüyü","doğrama","blender","dograyici","filter","butulkası","matara","şam ","keramika","termos","portatif","dibçək","buz qəlibi","skoç","yeni il","işığı","torpaq"]),
    "oyuncaq":   _c("Oyuncaq",           ["oyuncaq","konstruktor","pazl","kukla","oyuncağ","şar ","oyun ","puzzle","fiqur","stadion"]),
    "dereterlik":_c("Dəftərxana",        ["dəftər","qələm","karandaş","marker","albom","qayçı"]),
    "avto":      _c("Avtomobil məhsulları",["maşın üçün","avtomobil","avto "]),
    # yalnız mağaza kateqoriyasına görə
    "sebze_diger":_c("Digər tərəvəz", ["aysberq","kahı"]),
    "meyve_diger":_c("Digər meyvə"),
    "dondurulmus":_c("Dondurulmuş məhsul", ["dondurulmuş","donmus","donmuş","fry me","donuq"]),
    "bakliyyat": _c("Taxıl, bakliyyat", ["irmik","mannı"]),
    "sous_diger":_c("Digər sous", ["narşərab"]),
    "diger":     _c("Digər məhsullar"),
}

# Saytda göstərilən ümumi kateqoriyalar (alt növlər = yuxarıdakı kateqoriyalar)
GROUPS = [
    {"id":"meyve",    "name":"Meyvə",                 "cats":["alma","armud","saftal","gilas","uzum","portaqal","mandarin","limon","banan","kivi","nar","ekzotik","gile","qarpiz","meyve_diger"]},
    {"id":"sebze",    "name":"Tərəvəz",               "cats":["kartof","pomidor","xiyar","soyan","kelem","yerkoyu","cuqundur","badimcan","biber","sarimsaq","goyerti","gobelek","balqabaq","sebze_diger"]},
    {"id":"sud",      "name":"Süd məhsulları və yumurta","cats":["sud","yoqurt","qatiq","kefir","xama","qaymaq","kesmik","sirok","pendir","kere_yagi","yumurta"]},
    {"id":"et",       "name":"Ət, balıq, kolbasa",    "cats":["toyuq","hindi","dana_ati","qoyun_ati","et_diger","kolbasa","sosis","hise","baliq","deniz"]},
    {"id":"corek",    "name":"Çörək və unlu məmulat", "cats":["corek"]},
    {"id":"bakaliya", "name":"Taxıl, makaron, un",    "cats":["duyu","merci","noxud","fasulya","qarabashaq","yulaf","bulgur","bakliyyat","makaron","eriste","un","seher"]},
    {"id":"sirniyyat","name":"Şirniyyat və desert",   "cats":["sokolad","konfet","halva","pecenye","vafli","keks","tort","dondurma","bal","murebbe","krem_pasta"]},
    {"id":"hazir",    "name":"Qəlyanaltı və hazır yemək","cats":["cips","tum","qoz","hazir_yemek","dondurulmus","susi"]},
    {"id":"konserv",  "name":"Konserv və turşu",      "cats":["konserv","zeytun","tursu","pomidor_pasta"]},
    {"id":"iceckiler","name":"İçkilər",               "cats":["su","qazli_su","kola","limonad","soyuq_cay","sire","energetik","cay","qehve"]},
    {"id":"yag_sous", "name":"Yağ, sous, ədviyyat",   "cats":["zeytun_yagi","bitki_yagi","mayonez","ketcup","xardal","sous_diger","sirke","duz","sekerqum","istiot","bulyon"]},
    {"id":"usaq",     "name":"Uşaq məhsulları",       "cats":["usaq_qida","usaq_baxim"]},
    {"id":"gigiyena", "name":"Gigiyena və baxım",     "cats":["beden_baximi","deo","etir","tras","kosmetika","sac_baximi","sac_boya","dis_baximi","qadin_gig","kagiz"]},
    {"id":"ev",       "name":"Ev və məişət",          "cats":["qabyuyan","yuyucu","temizlik","zibil","bisirme","mesis"]},
    {"id":"heyvan",   "name":"Heyvan yemi",           "cats":["pisik_yemi","it_yemi","heyvan_diger"]},
    {"id":"oyuncaq",  "name":"Oyuncaq və dəftərxana", "cats":["oyuncaq","dereterlik","avto"]},
    {"id":"spirtli",  "name":"Spirtli içkilər",       "cats":["pive","araq","viski","serab","likor"]},
    {"id":"tutun",    "name":"Tütün məhsulları",      "cats":["siqaret"]},
    {"id":"saglam",   "name":"Sağlam və diyet qida",   "cats":["saglam"]},
    {"id":"geyim",    "name":"Geyim və tekstil",       "cats":["geyim","ayaqqabi","tekstil"]},
    {"id":"diger",    "name":"Digər məhsullar",       "cats":["diger"]},
]
_missing = {c for g in GROUPS for c in g["cats"]} ^ set(CATEGORIES)
assert not _missing, _missing

ALL_STORES = ["Bravo","OBA","Araz","Neptun","Tamstore","Rahat","Bazarstore"]

# Hər mağaza üçün bir neçə Wolt filialı: ilk işləyən istifadə olunur.
# Mühit dəyişəni ilə əvəz etmək olar: WOLT_SLUG_NEPTUN=... (vergüllə bir neçə)
WOLT_SLUGS = {
    "Bravo":  ["bravo-supermarket-globus-centre", "bravo-supermarket-28-may",
               "bravo-supermarket-narimanov"],
    "OBA":    ["oba-market-nerimanov-1", "oba-market-narimanov", "oba-market-yasamal"],
    "Araz":   ["araz-supermarket-20-yanvarr", "araz-supermarket-narimanov", "araz-supermarket-yasamal",
               "araz-supermarket-28-may"],
    "Tamstore": ["tamstore-narimanov-1", "tamstore-papanin"],
    "Rahat":  ["rahat-supermarket-yasamal"],
    "Neptun": ["neptun-supermarket-narimanovv", "neptun-supermarket-28", "neptun-supermarket-narimanov",
               "neptun-supermarket-nizami"],
}

def wolt_slugs(store):
    env = os.environ.get("WOLT_SLUG_" + store.upper(), "")
    extra = [x.strip() for x in env.split(",") if x.strip()]
    return extra + WOLT_SLUGS.get(store, [])

JUICE_WORDS = ["şirəsi","suyu","nektarı","mors","şərbəti","kompot","içkisi","limonadı","sandora","cappy","pfanner","tropicana","fruktoviy","fruktovy","zolotoy sad"]
_WATER = re.compile(_f(r"mineral su|içməli su|mənbə suyu|qazlı su"))

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
    n = _f(name)
    return any(_f(w) in n for w in JUICE_WORDS)

def _kw_re(words):
    # söz əvvəlində uyğunluq: "nar" -> "Nar", amma "Qarnar"/"Narzan" yox
    # qısa açar sözlər (nar, bal, su, un) tam söz kimi axtarılır
    parts = [re.escape(_f(w)) + (r"(?!\w)" if not w.endswith(" ") and (len(w) <= 3 or _f(w) in ("nar", "bal", "duz")) else "")
             for w in words]
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + ")")

_CAT_RE = {
    cid: (_kw_re(info["kw"]), _kw_re(info["excl"]) if info.get("excl") else None)
    for cid, info in CATEGORIES.items() if info["kw"]
}

_ADJ = re.compile(r"l[iu]$")   # "limonlu", "pendirli" -> dad bildirən sifət, məhsulun özü deyil
# təbii məhsul kateqoriyaları: "dadlı/aromalı/konserv" olanlar bura aid deyil
_MEAT = {"toyuq","hindi","dana_ati","qoyun_ati","baliq"}
_STRICT = {c for g in GROUPS if g["id"] in ("meyve","sebze") for c in g["cats"]} | _MEAT
_STRICT_EXCL = _kw_re(["şirə","suyu","sous","pasta","konserv","turşu","mürəbbə","cem","kompot","çip",
                       "dadlı","aromalı","ətirli","ləzzətli","qurusu","kürü","duzu","povidla","tablet","cleaner",
                       "pürə","yoqurt","yogurt","mirinda","spr","qurudulmuş","pastila","gel","krem"])
_PET = _kw_re(["yem","pişik","itlər","bulyon","əriştə","kub"])
_LIQUID = re.compile(r"\d\s*(?:ml|l|lt|litr)(?!\w)")

def assign_cat(name):
    n = _f(name)
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
            if pos > ((4 if cid == "baliq" else 3) if cid in _MEAT else 1) or (cid in _MEAT and _PET.search(n)):
                continue
        word = re.match(r"\w+", n[m.start():]).group()
        if len(word) > len(m.group()) and _ADJ.search(word):
            continue
        return cid
    return "diger"

# Mağazanın öz kateqoriya adı (Wolt/Araz/OBA) -> bizim alt növ. Yol "Üst > Alt > Yarpaq" seqmentlərə bölünür və
# ƏN DƏRİN seqmentdən yuxarıya doğru yoxlanılır; ilk uyğun qayda qalib gəlir. "~" = ümumi (üst səviyyə) qayda:
# bu halda eyni qrupdan məhsul adı üzrə daha dəqiq nəticə varsa ona üstünlük verilir.
_PATH_SPEC = [
    ("siqaret", r"tütün|siqaret|alışqan|terea|ploom|heets|qızdırılan"),
    ("kola", r"spirtsiz piv|alkoqolsuz piv"),
    ("pive", r"piv"), ("araq", r"araq|vodka"), ("viski", r"viski|burbon"), ("serab", r"şərab|şampan|vermut"),
    ("likor", r"konyak|brendi|likör|tekila|rakı|\brom\b|\bcin\b|alkoqollu|spirtli|elit içki|alkoqollu"),
    ("energetik", r"enerji|energetik|red bull|sport içki"),
    ("sire", r"şirə|nektar|kompot|qazsız içki"), ("soyuq_cay", r"soyuq çay|ice tea"),
    ("qazli_su", r"qazlı su|mineral"), ("su", r"qazsız su|içməli su|sağlam su|xxl su|^su$|sular"),
    ("limonad", r"limonad"), ("kola", r"cola|soda|qazlı içki|^kola"),
    ("qehve", r"qəhvə|kofe|kakao|süd tozu|kapsul"), ("cay", r"çay|dəmləmə|bitki çay"),
    # dondurulmuş (məhsul növünə görə), sonra ət/balıq
    ("dondurulmus", r"dondurulmuş (meyvə|tərəvəz|kartof|börək|mantı|milföy|yarımfabrikat|xəmir|qida)|donmuş (meyvə|tərəvəz|qida)|xəmir məhsul|yarımfabrikat"),
    ("dondurma", r"dondurma|donmuş desert"),
    ("susi", r"suşi|sushi|asiya mətbəxi"), ("baliq", r"balıq"), ("deniz", r"dəniz məhsul|krevet|midiya|kalamar|kürü"),
    ("toyuq", r"toyuq|cücə|broyler"), ("hindi", r"hindi"), ("qoyun_ati", r"qoyun|quzu"), ("dana_ati", r"dana|mal əti|qırmızı ət"),
    ("hise", r"hisə verilmiş"), ("sosis", r"sosis"), ("kolbasa", r"kolbasa|delikates|qastronom|emal olunmuş ət|salam"),
    # süd məhsulları
    ("mayonez", r"mayonez"), ("pendir", r"pendir|pendır|labne"), ("xama", r"xama|smetana"), ("qaymaq", r"qaymaq"),
    ("kesmik", r"kəsmik"), ("sirok", r"sırok"), ("yoqurt", r"yoqurt|yogurt|kokteyl"), ("kefir", r"kefir|ayran|dovğa"), ("qatiq", r"qatıq"),
    ("yumurta", r"yumurta"), ("zeytun_yagi", r"zeytun yağ"),
    ("bitki_yagi", r"günəbaxan|qarğıdalı yağ|duru yağ|digər yağ|^yağlar$|ayçiçəyi|duru və əridilmiş yağ"),
    ("kere_yagi", r"kərə yağ|kərə və|spred|bitki tərkibli yağ"),
    ("sud", r"pasterizə|uzunömürlü|qatılaşdırılmış süd|südlər|^süd$|gündəlik süd|süd və süd məhsulları ?-"),
    # meyvə / tərəvəz
    ("goyerti", r"göyərti"), ("gobelek", r"göbələk"), ("balqabaq", r"balqabaq|kabak"), ("cuqundur", r"çuğundur"),
    ("kelem", r"kələm"), ("sarimsaq", r"sarımsaq"), ("kartof", r"^kartof"), ("soyan", r"^soğan"), ("badimcan", r"badımcan"),
    ("biber", r"^bibər"), ("xiyar", r"^xi?yar|^xıyar"), ("pomidor", r"^pomidor"), ("yerkoyu", r"^kök$|yerkökü"),
    ("ekzotik", r"ananas|ekzotik|kokos|avokado|avakado"), ("mandarin", r"mandarin|qreypfrut"), ("portaqal", r"^portağal"),
    ("limon", r"^limon"), ("alma", r"^alma"), ("armud", r"^armud"), ("banan", r"^banan"), ("kivi", r"^kivi"), ("nar", r"^nar$"),
    ("uzum", r"^üzüm"), ("saftal", r"^şaftalı|^ərik|^gavalı"), ("gilas", r"^gilas|^albalı"), ("gile", r"giləmeyvə"), ("qarpiz", r"qarpız|yemiş"),
    # konserv
    ("zeytun", r"zeytun"), ("tursu", r"turşu"), ("pomidor_pasta", r"pomidor pasta|^pastalar$"),
    ("konserv", r"konserv"),
    # şirniyyat
    ("krem_pasta", r"krem şokolad|əzmə|krem pasta|şokolad yağ"), ("murebbe", r"mürəbbə|^cem$|povidla|bal, cem"), ("bal", r"^bal$"),
    ("halva", r"halva|lokum|kozinak"), ("pecenye", r"peçenye|biskvit|kraker|bisküvit"), ("vafli", r"vafli|gofret"),
    ("keks", r"keks|kruasan|oven|rulet"), ("tort", r"tort|pirojna"), ("sokolad", r"şokolad"),
    ("konfet", r"konfet|jele|şəkərləmə|saqqız|fərəhləndirici|uşaq şirniyyat|meyvəli bar|nanəli|çəkili şirniyyat|şirniyyat çəki|şirniyyat ədəd|şirin ləzzət|marmelad|şirniyyat"),
    # qəlyanaltı
    ("cips", r"çips|chips|ekstruder|xıtır"), ("tum", r"^tum|tumlar|ləpə|araxis|püstə"), ("qoz", r"qoz|fındıq|çərəz|quru meyvə"),
    ("hazir_yemek", r"hazır yemək|hazır qida|şorba|hazır sup|tez hazırlanan|ketrinq"),
    # bakaliya
    ("makaron", r"makaron|spagetti|vermişel|vermeşel|vermesel"), ("eriste", r"əriştə"), ("duyu", r"düyü"), ("merci", r"mərci"), ("noxud", r"noxud"),
    ("fasulya", r"lobya|fasulya"), ("qarabashaq", r"qarabaşaq"), ("yulaf", r"yulaf"), ("bulgur", r"bulğur|manna|yarma"),
    ("seher", r"səhər yemək|müsli|sıyıq|qranola|taxıl məhsul"), ("bakliyyat", r"dənli|paxlalı|bakliyyat"),
    ("un", r"buğda un|ali növ|^un$|^un |un və un|ağ un|quru un"), ("corek", r"çörək|lavaş|xəmir|mayalı|un məmulat|bişinti"),
    # yağ, sous, ədviyyat
    ("ketcup", r"ketçup|ketchup"), ("xardal", r"xardal|xrən|acika"), ("sirke", r"sirkə"),     ("bulyon", r"bulyon"), ("duz", r"^duz$|duz və"), ("sekerqum", r"şəkər|qənd|noğul"), ("istiot", r"ədviyyat"),
    # uşaq / gigiyena / ev
    ("usaq_baxim", r"uşaq (bez|şampun|yağ|sabun|duş|baxım|gigiyen|ləvazimat|krem|salfet)|körpə bez"), ("usaq_qida", r"uşaq|körpə|mama|ana və"),
    ("sac_boya", r"saç boyası"), ("sac_baximi", r"saç|şampun|balzam"), ("dis_baximi", r"diş|ağız"),
    ("qadin_gig", r"qadınlar üçün gigiyen|qadın gigiyen|qoruyucu|molped"), ("deo", r"dezodor|dezodar|deodor"), ("tras", r"təraş"),
    ("etir", r"parfüm|ətir|kaloniya"), ("kosmetika", r"makiyaj|dırnaq|manikür|bəzək|kosmetik məhsul"),
    ("kagiz", r"kağız məhsul|tualet kağız|salfet|dəsmal|kağız və salfet|kağız"),
    ("qabyuyan", r"qabyuyan|qab yuyan"), ("yuyucu", r"yuyucu|paltar|çamaşır|yumşaldıcı|ağardıcı"),
    ("zibil", r"zibil"), ("bisirme", r"bişirmə|folqa|streç"),
    ("temizlik", r"təmizlik vasitə|təmizləyici|döşəmə|şüşə təmiz|tualet təmiz|toz təmiz|xalça|boru|aerozol|ümumi təmizlik|həşərat|hava təravət|ev təmizliyi|təmizlik"),
    ("mesis", r"xırdavat|məişət|mətbəx|ləvazimat|süngər|bezlər|əlcək|birdəfə|saxlama"),
    ("beden_baximi", r"sabun|duş|bədən|dəri|\büz\b|üz və|krem|günəş|qulluq vasitə|gigiyena məhsul|kişilər üçün gig|pambıq|baxım"),
    ("pisik_yemi", r"pişik"), ("it_yemi", r"it qida|itlər|it yem|it və"), ("heyvan_diger", r"heyvan|aksesuar|zoo ?shop"),
    ("oyuncaq", r"oyuncaq|hobbi"), ("dereterlik", r"dəftərxana|məktəb|ofis|qələm|karandaş|dəftər"), ("avto", r"avto|maşın"),
]
# ümumi (üst səviyyə) qaydalar: yalnız dərin seqmentlər uyğun gəlməyəndə
_PATH_GEN = [
    ("sud", r"süd məhsul|süd və süd|yoqurt və kəsmik|süd və emal"), ("meyve_diger", r"meyvə"), ("sebze_diger", r"tərəvəz"),
    ("et_diger", r"ət məhsul|təzə ət|ağ ət|^ət$"), ("kola", r"spirtsiz|alkoqolsuz|içki"), ("konfet", r"unlu və şirniyyat"),
    ("cay", r"çay"), ("hazir_yemek", r"hazır"), ("konserv", r"konserv"), ("dondurulmus", r"dondurulmuş|donmuş"),
    ("bitki_yagi", r"yağ"), ("istiot", r"duz"), ("sekerqum", r"şəkər"),
    ("saglam", r"sağlam qida|sağlam yaşam|dietik|diabetik|qlütensiz|glutensiz|protein"), ("bakliyyat", r"quru qida"),
    ("tekstil", r"tekstil|geyim"), ("heyvan_diger", r"zoo"),
    ("mesis", r"manqal|dekorasiya|elektronika|səyahət|mebel|işıqlandırma|dəmirçi|take away|istirahət|bio məhsul|hobbi|bağ|bəzək"),
    ("sous_diger", r"sous|dadlandırıcı"), ("beden_baximi", r"kosmetik|təmizlik və|şəxsi baxım|hamam"), ("mesis", r"ev və bağ|ev əşya"),
]
_PATH_SPEC = [(c, re.compile(_f(r), re.I)) for c, r in _PATH_SPEC]
_PATH_GEN = [(c, re.compile(_f(r), re.I)) for c, r in _PATH_GEN]
CAT2GROUP = {c: g["id"] for g in GROUPS for c in g["cats"]}

def cat_from_path(path):
    """(alt növ, ümumi?) və ya (None, False)."""
    segs = [x.strip() for x in _f(path).split(">") if x.strip()]
    for sg in reversed(segs):
        for cid, rx in _PATH_SPEC:
            if rx.search(sg): return cid, False
    for sg in reversed(segs):
        for cid, rx in _PATH_GEN:
            if rx.search(sg): return cid, True
    return None, False

# Mağazanın çox ümumi (üst səviyyə) kateqoriyaları, məs. OBA: "Şirniyyat", "Spirtli içkilər" — alt növü ad üzrə təyin olunur
_COARSE = {_f(x) for x in ["Şirniyyat","Təmizlik","Spirtli içkilər","Konserva və dəniz məhsulları","Heyvan qidaları",
                           "Un məmulatları","Kosmetika","Ev əşyaları","İçkilər","Süd məhsulları","Meyvə-tərəvəz"]}
_WEAK = {"bakliyyat", "dondurulmus", "konserv", "mesis", "beden_baximi", "kosmetika", "temizlik", "hazir_yemek"}

def classify(name, path=""):
    """Mağazanın öz kateqoriyası (varsa) + məhsul adı. Mağaza kateqoriyası dəqiqdirsə ona üstünlük verilir;
    ümumi (üst səviyyə) və ya "digər" tipli olduqda eyni qrupdan ad üzrə nəticə daha dəqiq sayılır."""
    nc = assign_cat(name)
    if not path: return nc
    pc, gen = cat_from_path(path)
    if pc is None or pc == "diger": return nc   # mağaza kateqoriyası məlumat vermirsə ("Sağlam qida" və s.) ada görə
    if nc == "diger": return pc
    if _f(path).strip() in _COARSE: gen = True
    # ümumi və ya "qarışıq" kateqoriya adı: məhsul adı üzrə daha dəqiq nəticə varsa ona üstünlük
    if gen or pc.endswith("_diger") or pc in _WEAK: return nc
    return pc

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

# ── BAZARSTORE — bazarstore.az (nopCommerce, HTML) ───────────────────────
def _title(name):
    """"ALISHAAN BASMATI DÜYÜ 2 KQ" -> "Alishaan Basmati Düyü 2 Kq" (İ/I düzgün)."""
    return " ".join(w[:1].upper() + _low(w[1:]) if w[:1].isalpha() else _low(w) for w in name.split())

def scrape_bazarstore_flat():
    """"Ehtiyat üsul: "Bütün məhsullar" siyahısı (1 səhifə = 10 məhsul), orderby=5 (ada görə) ilə sabit sıralama."""
    import html as _html
    ses = _session()
    ses.headers.pop("Content-Type", None)
    ses.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "az"})
    url = "https://bazarstore.az/b%C3%BCt%C3%BCn-m%C9%99hsullar"
    item_rx = re.compile(r'class="product-item" data-productid="(\d+)" data-bzdl-item=\'([^\']*)\'(.*?)</div>\s*</div>\s*</div>', re.S)
    img_rx = re.compile(r'data-lazyloadsrc="([^"]+)"')

    def page(p):
        for attempt in range(4):
            try:
                r = ses.get(url, params={"orderby": 5, "pagenumber": p}, timeout=60)
                if r.status_code == 200: return r.text
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
        return None

    first = page(1)
    if not first:
        print("  [Bazarstore] ✗ saytdan cavab yoxdur")
        return None
    last = max([int(x) for x in re.findall(r'data-page="(\d+)"', first)] or [1])
    print(f"  [Bazarstore] {last} səhifə", flush=True)
    results = {c: [] for c in CATEGORIES}
    seen, failed = set(), 0
    def ingest(h):
        n = 0
        for pid, j, body in item_rx.findall(h):
            if pid in seen: continue
            try: d = json.loads(_html.unescape(j))
            except Exception: continue
            name = _html.unescape(d.get("item_name") or "").strip()
            price = clean_price(d.get("price"))
            if not name or price is None or name.replace(" ", "").isdigit(): continue   # adı yalnız kod olan məhsullar
            seen.add(pid); n += 1
            e = {"name": _title(name), "price": price}
            m = img_rx.search(body)
            if m and "default-image" not in m.group(1): e["img"] = m.group(1)
            results[classify(name, d.get("item_category") or "")].append(e)
        return n
    ingest(first)
    with ThreadPoolExecutor(max_workers=16) as ex:
        for h in ex.map(page, range(2, last + 1)):
            if h is None: failed += 1; continue
            ingest(h)
    total = len(seen)
    print(f"  [Bazarstore] ✓ {total} məhsul" + (f"; {failed} səhifə alınmadı" if failed else ""), flush=True)
    return results if total else None

def _bazar_menu(html_text):
    """Baş səhifənin 3 səviyyəli menyusundan [(url, "Kök > Alt > Yarpaq")] çıxarır."""
    from html.parser import HTMLParser
    import html as _html
    class P(HTMLParser):
        def __init__(self):
            super().__init__(); self.depth = 0; self.stack = []; self.cur = None; self.names = {}; self.out = []; self.in_menu = False
        def handle_starttag(self, tag, attrs):
            a = dict(attrs); cls = a.get("class") or ""
            if tag == "ul" and "mega-menu" in cls: self.in_menu = True
            if not self.in_menu: return
            if tag == "ul": self.stack.append("sub" if "sublist" in cls else "ul"); self.depth += 1 if "sublist" in cls else 0
            if tag == "a" and a.get("href", "").startswith("/"):
                self.cur = {"href": a["href"], "level": self.depth, "last": "lastLevelCategory" in cls, "sub": "with-subcategories" in cls, "text": ""}
        def handle_endtag(self, tag):
            if not self.in_menu: return
            if tag == "ul" and self.stack:
                if self.stack.pop() == "sub": self.depth -= 1
            if tag == "a" and self.cur:
                c = self.cur; self.cur = None
                t = _html.unescape(re.sub(r"[^\w\s,&.()/-]", "", c["text"])).strip()
                self.names[c["level"]] = t
                for k in [k for k in self.names if k > c["level"]]: del self.names[k]
                if c["last"] or not c["sub"]:
                    path = " > ".join(self.names[k] for k in sorted(self.names) if k <= c["level"])
                    self.out.append((c["href"], path))
        def handle_data(self, data):
            if self.cur is not None: self.cur["text"] += data
    p = P(); p.feed(html_text)
    seen, res = set(), []
    for u, path in p.out:
        if u not in seen and not u.startswith("/blog"): seen.add(u); res.append((u, path))
    return res

def scrape_bazarstore():
    """Kateqoriya menyusunu gəzir: hər yarpaq kateqoriya səhifəsi (10 məhsul/səhifə) + kateqoriya yolu ilə təsnif.
    Menyu alınmasa "Bütün məhsullar" siyahısına (kateqoriyasız) qayıdır."""
    import html as _html
    ses = _session()
    ses.headers.pop("Content-Type", None)
    ses.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "az"})
    base = "https://bazarstore.az"
    try:
        home = ses.get(base + "/", timeout=60).text
        leaves = _bazar_menu(home)
    except Exception as e:
        print(f"  [Bazarstore] ✗ menyu alınmadı: {e}"); leaves = []
    if len(leaves) < 20:
        print("  [Bazarstore] menyu tapılmadı → ümumi siyahı"); return scrape_bazarstore_flat()
    print(f"  [Bazarstore] {len(leaves)} kateqoriya", flush=True)
    item_rx = re.compile(r'class="product-item" data-productid="(\d+)" data-bzdl-item=\'([^\']*)\'(.*?)</div>\s*</div>\s*</div>', re.S)
    img_rx = re.compile(r'data-lazyloadsrc="([^"]+)"')

    def page(job):
        url, path, p = job
        for attempt in range(4):
            try:
                r = ses.get(base + url, params={"orderby": 5, "pagenumber": p} if p > 1 else {"orderby": 5}, timeout=60)
                if r.status_code == 200: return path, r.text
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
        return path, None

    results = {c: [] for c in CATEGORIES}
    seen, failed = set(), 0
    def ingest(path, h):
        new = 0
        for pid, j, body in item_rx.findall(h):
            if pid in seen: continue
            try: d = json.loads(_html.unescape(j))
            except Exception: continue
            name = _html.unescape(d.get("item_name") or "").strip()
            price = clean_price(d.get("price"))
            if not name or price is None or name.replace(" ", "").isdigit(): continue
            seen.add(pid); new += 1
            e = {"name": _title(name), "price": price}
            m = img_rx.search(body)
            if m and "default-image" not in m.group(1): e["img"] = m.group(1)
            results[classify(name, path)].append(e)
        return new
    # kateqoriyalar çox üst-üstə düşür: növbəti səhifə yalnız əvvəlki səhifə yeni məhsul verən kateqoriyalar üçün çəkilir
    with ThreadPoolExecutor(max_workers=24) as ex:
        firsts = list(ex.map(page, [(u, pth, 1) for u, pth in leaves]))
        active = []
        for (u, pth), (_, h) in zip(leaves, firsts):
            if h is None: failed += 1; continue
            n = ingest(pth, h)
            last = max([int(x) for x in re.findall(r'data-page="(\d+)"', h)] or [1])
            if n > 0 and last > 1: active.append((u, pth, last))
        pg, requests_n = 2, len(leaves)
        while active and pg < 200:
            jobs = [(u, pth, pg) for u, pth, last in active if pg <= last]
            requests_n += len(jobs)
            nxt = []
            for (u, pth, pg_), (_, h) in zip(jobs, ex.map(page, jobs)):
                if h is None: failed += 1; continue
                if ingest(pth, h) > 0:
                    nxt.append(next(x for x in active if x[0] == u))
            active = nxt; pg += 1
        print(f"  [Bazarstore] {requests_n} sorğu", flush=True)
        # tamlıq: heç bir kateqoriyada tapılmayan məhsullar "Bütün məhsullar" siyahısından (kateqoriyasız, ad üzrə təsnif)
        flat = "/b%C3%BCt%C3%BCn-m%C9%99hsullar"
        _, h1 = page((flat, "", 1))
        if h1:
            ingest("", h1)
            lastp = max([int(x) for x in re.findall(r'data-page="(\d+)"', h1)] or [1])
            before = len(seen)
            for _, h in ex.map(page, [(flat, "", pg) for pg in range(2, lastp + 1)]):
                if h is None: failed += 1; continue
                ingest("", h)
            print(f"  [Bazarstore] ümumi siyahıdan əlavə {len(seen) - before} məhsul", flush=True)
    total = len(seen)
    print(f"  [Bazarstore] ✓ {total} məhsul" + (f"; {failed} səhifə alınmadı" if failed else ""), flush=True)
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
    def collect(trail, items):
        for item in items:
            uid = item.get("id") or item.get("name")
            if uid in seen: continue
            seen.add(uid)
            r = _wolt_entry(item, trail)
            if r: results[r[0]].append(r[1])
    with ThreadPoolExecutor(max_workers=8) as ex:
        for trail, items in ex.map(fetch, leaves):
            collect(trail, items)

    # Wolt GitHub IP-lərinə 429 verir: alınmayan kateqoriyalar bir-bir, uzun fasilə ilə təkrar yoxlanır
    if failed:
        bad = {cs for cs, _ in failed}
        todo = [lf for lf in leaves if lf[0] in bad]
        failed.clear()
        for rnd in range(3):
            time.sleep(15 * (rnd + 1))
            still = []
            for lf in todo:
                before = len(failed)
                trail, items = fetch(lf)
                if len(failed) > before: still.append(lf)
                else: collect(trail, items)
                time.sleep(1)
            failed.clear()
            todo = still
            if not todo: break
        failed.extend((lf[0], "təkrar uğursuz") for lf in todo)
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
    wolt_only = store in ("Bravo", "Neptun", "Tamstore", "Rahat")
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
    RENAMED = {"gigiyena": "beden_baximi", "ayran": "kefir", "spirtli": "likor", "kola": "kola", "ketcup": "ketcup"}   # silinmiş kateqoriya -> yeni
    for oid, c in old.items():
        for store, items in c["stores"].items():
            for it in items:
                cid = assign_cat(it["name"])
                if cid == "diger":   # mağaza kateqoriyası artıq saxlanmır: köhnə təyinatı itirmə
                    cid = RENAMED.get(oid, oid) if RENAMED.get(oid, oid) in CATEGORIES else "diger"
                key = (store, cid, it["name"].lower())
                if key not in seen:
                    seen.add(key)
                    new[cid]["stores"].setdefault(store, []).append(it)
    data["categories"] = new
    data["groups"] = GROUPS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recategorize", action="store_true")
    ap.add_argument("--store", choices=["bravo","oba","araz","neptun","tamstore","rahat","bazarstore","all"], default="all")
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
        if not args.recategorize:   # recategorize köhnə kateqoriyaları özü yenidən paylayır
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

    name_map = {"bravo":"Bravo","oba":"OBA","araz":"Araz","neptun":"Neptun","tamstore":"Tamstore","rahat":"Rahat","bazarstore":"Bazarstore"}
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
            elif sname == "Bazarstore":
                own_res = scrape_bazarstore() or {}

        # Wolt
        if not args.own_only and sname != "Bazarstore":   # Bazarstore Wolt-da yoxdur
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
