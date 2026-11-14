# Analog Atlas — Devir Promptu (Claude için)

> **Kullanım:** Bu dosyanın tamamını kopyalayıp Claude'a ilk mesaj olarak yapıştır. **Claude Code** kullanmanı öneririm (Pro aboneliğine dahil; claude.ai/code, masaüstü uygulamasının Code sekmesi ya da terminalde `claude`). Çünkü bu iş komut çalıştırmayı, test etmeyi ve dosya düzenlemeyi gerektiriyor. Önce `AnalogAtlas_handoff.zip` dosyasını bir klasöre aç ve Claude Code'u o klasörde başlat.

---

## 0. Senin rolün ve bu mesajın amacı

Sen, NASA Space Apps Challenge 2026'ya katılan bir takımın projesini devralan kıdemli bir yazılım ve veri bilimi mühendisisin. Projenin ilk yarısı başka bir oturumda yapıldı; bu mesaj sana o oturumda verilen **tüm kararları, mevcut durumu ve kalan işleri** aktarıyor. **Teslime yaklaşık 2 gün (48 saat) kaldı.** Amaç: çalışan, anlatılabilir ve bilimsel olarak dürüst bir ürün teslim etmek.

Çalışma kuralların:
- Kodu değiştirmeden önce ilgili dosyayı oku. Çalışan parçaları baştan yazma; üzerine ekle.
- Her anlamlı değişiklikten sonra testleri çalıştır (`python -m unittest discover -s tests -v`, `backend/` içinde). Kırılan testi düzeltmeden ilerleme.
- Yapmadığın ya da doğrulamadığın bir şeyi yapılmış gibi raporlama. Bir adım çalışmadıysa hata çıktısıyla birlikte söyle.
- Aşağıdaki **"Değişmez kararlar"** bölümündekileri kullanıcıya sormadan değiştirme.
- Kullanıcıya karar bırakılan konularda (bölüm 6) kendin seçme, sor.
- Kullanıcıyla Türkçe konuş. Kod yorumları, README ve teslim metinleri İngilizce olsun (jüri uluslararası).

---

## 1. Challenge

**Başlık:** *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*
Sayfa: https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/?tab=details

Özet:
- NASA ve diğer ajansların açık Earth/Moon/Mars verileriyle, kalıcı Ay üssü aday bölgelerine ve Mars iniş/keşif bölgelerine benzeyen **yeni, az bilinen** Dünya analoglarını bulmak ve karakterize etmek. Çıktı bir harita, görselleştirme ya da araç olacak.
- **"Amaç bilinen analogları yeniden keşfetmek değil."** Antarctica, Atacama, Iceland ve Hawaii zaten çok çalışılmış.
- **Analoji boyutları:** jeoloji ve mineraloji, topografya, sıcaklık ve aydınlanma, su ve buz, toz ve atmosfer süreçleri, biyoloji ve habitabilite, mağara ve yeraltı, operasyon koşulları.
- **Her analog için üç soru:** ne benziyor, ne kadar benziyor, nerede bozuluyor?
- **Dünya'nın sınırları kabul edilmeli:** yerçekimi, vakum, ince atmosfer ve radyasyon taklit edilemez.
- **"Surprise us":** beklenmedik bir yer ya da yeni bir yöntem bekleniyor.

Resources sekmesindeki veriler:
- **NASA:** Earthdata Search, Worldview, PDS, LRO (LOLA, LROC, Diviner, LEND, Mini-RF)
- **CSA:** RADARSAT-1, RCM ve SAR Python tutorial
- **ESA:** Copernicus Data Space, Open Science Catalog
- **JAXA:** G-Portal

Space Apps jüri kriterleri: Impact, Creativity, Validity, Relevance, Presentation.

---

## 2. Proje: "Analog Atlas"

Kullanıcı Ay veya Mars'ta bir bölge seçiyor. Sistem o bölgeyi 25 özellikli, gezegenden bağımsız bir vektöre çeviriyor ve Dünya'daki adayları **fiziksel benzerlik skoru (SI, 0–100)** ile sıralıyor. Her sonuç için şunlar gösteriliyor:
- en güçlü iki aile
- analojinin bozulduğu özellikler ("Breaks on")
- kaynaklar
- Dünya'nın taklit edemediği sabit farklar (yerçekimi, basınç, radyasyon, gün uzunluğu); bunlar skora girmiyor

**Takımın sosyal etki tezi:** NASA'nın analog sahaları büyük ölçüde yüksek gelirli ülkelerde (ABD, Kanada, Batı Avrupa, Şili, Antarktika). Gelişmekte olan ülkeler (Global South) **filtre olarak değil, öncelik olarak** öne çıkarılıyor.

Takımın sunum çerçevesi **"Anchor & Discover"**:
- **Anchor (çapa):** Literatürde bilinen analogları doğru sıralayarak yöntemin çalıştığını kanıtlamak.
- **Discover (keşif):** Aynı özelliklere sahip ama az çalışılmış, tercihen Global South'taki bölgeleri öne çıkarmak.

---

## 3. Zip içeriği

```
p2.html                      Frontend (tek dosya, ~2.3 MB; base64 gezegen dokuları gömülü)
HANDOFF_PROMPT.md            Bu dosya
backend/
  README.md                  Backend mimarisi ve komutlar
  requirements.txt
  config/
    features.json            ★ Tek doğruluk kaynağı: 25 feature, sabit aralıklar, aileler,
                               profiller, veri seviyeleri (tier), veri kaynakları, landform affinity
    priority.json            Global South bonus kuralları
    targets.json             7 Ay/Mars hedefi (değerler literatür tahmini)
    anchors.json             ★ Literatür kaynaklı doğrulama çapaları (DONDURULMUŞ)
  data/
    catalog_sites.json       16 bilinen Dünya analoğu (frontend'deki analog-db'den üretildi)
    income_groups.csv        Dünya Bankası gelir grupları (217 ülke)
  analog_atlas/
    config.py                Konfigürasyon yükleme
    features.py              Feature vektörü oluşturma, sabit aralıkla normalizasyon, güneş açısı
    scoring.py               Vektörize benzerlik motoru (milyonlarca satır), explain()
    priority.py              Global South önceliği, opportunity skoru
    pipeline.py              rank(), validate(), JSON çıktı
    grid.py                  Yaklaşık eşit alanlı global grid
    countries.py             Hücreye ülke kodu atama (Natural Earth + shapely)
    extract/earth_gee.py     Google Earth Engine veri çekme + postprocess
    cli.py                   Komut satırı
    api.py                   FastAPI
  tests/test_core.py         15 test
```

### 3.1 Frontend (`p2.html`) nasıl çalışıyor
- Tek HTML dosyası, saf JavaScript ES modülü. Cesium 3D globe kullanıyor; Cesium yüklenemezse 2D şematik görünüme düşüyor. Tailwind CDN'den geliyor.
- **Gömülü JSON blokları:**
  - `#analog-db`: 16 site
  - `#citation-db`: 87 APA referans
  - `#map-textures`: gezegen dokuları
- **Akış:**
  1. Gezegen seçimi (Earth/Moon/Mars).
  2. Bölge seçimi: nokta, dikdörtgen, poligon ya da hazır preset (Ay: Imbrium, Marius, Shackleton; Mars: Jezero, Gale, Cerberus, Tharsis).
  3. Bölge değerleri `resolveRegion()` ile belirleniyor: preset ise literatür değerleri, Dünya'da bilinen bir siteye yakınsa o sitenin değerleri, başka bir yerse IDW interpolasyonu.
  4. "Run match" → `regionFeatures()` → Web Worker (`WORKER_SOURCE`) → sonuç kartları.
  5. Compare görünümünde parametre tablosu ve veri seviyesi rozetleri (M/D/P) var.
- **Önemli sınırlamalar:**
  - Moon/Mars rölyefi seed'li **sentetik** bir DEM'den geliyor; eğim değerleri bu yüzden gerçek değil.
  - Katmanlar (thermal, climate, mineral) model çıktısı.
  - Serbest seçilen bölgelerde IDW az sayıda kontrol noktasından interpole ediyor; Ay'da −47° enlemde buz 0.55 gibi gerçek dışı değerler çıkabiliyor.
  - Gerçek NASA verisi şu an yalnızca görüntü karoları (Trek WAC / Viking).
- **Frontend'deki ilgili sabitler:** `FAMILIES`, `PROFILES`, `FEATURES` (aralık ve kaynaklarıyla), `FEATURE_TIERS`, `BODY_CONSTANTS`, `FIXED_GAPS`, `LANDFORMS`, `LANDFORM_AFFINITY`, `PRESETS`, `CONFIG`. Bunlar `backend/config/features.json` ile **aynı olmak zorunda.** Birini değiştirirsen diğerini de güncelle.
- **Yerelde açmak için** (proje kökünde):
  ```bash
  python -m http.server 8765
  ```
  Ardından tarayıcıda http://localhost:8765/p2.html adresini aç. `file://` ile açmak bazı özellikleri bozar.

### 3.2 Feature seti v2 (25 feature, 8 aile)
| Aile | Feature'lar |
|---|---|
| topography | slope_mean, slope_std, roughness, relief_local (5 km), crater_density |
| surface | albedo, ti_rel (termal inertianın kendi gezegenindeki yüzdeliği), rock_abundance |
| environment | temp_min, diurnal_range, frost_fraction, sun_elev_noon (enlem + eksen eğikliğinden hesaplanır) |
| water | aridity, ground_ice |
| mineralogy | olivine, pyroxene, plagioclase, evaporite, hematite (Fe-oksit), phyllosilicate (kil), carbonate |
| processes | dust_activity, vegetation_cover |
| subsurface | cave_index |
| landform | landform_class (kategorik + affinity matrisi; `impact_crater` dahil) |

**Metrik:** Δ_k = norm(hedef_k) − norm(aday_k). Normalizasyon **sabit fiziksel aralıklarla** yapılıyor; aralıklar `features.json` içinde.

**SI = 100 · (1 − √(Σ w·Δ² / Σ w))**
- Landform için Δ = 1 − affinity.
- Aile ağırlığı, ailedeki feature'lara eşit bölünüyor.
- NaN olan feature hem paydan hem paydadan düşüyor; `coverage` kolonu verinin ne kadarının mevcut olduğunu gösteriyor.
- `rank()` fonksiyonu `coverage < 0.5` olan hücreleri sıralamıyor.

**Profiller:** landing, resource, habitat, science.

**Veri seviyeleri:**
- **measured:** doğrudan ölçüm
- **derived:** formülle türetilmiş
- **proxy:** global harita yok, yaklaşık değer

### 3.3 Global South önceliği (`priority.py`, `priority.json`)
**opportunity = SI + income_bonus + novelty_bonus**
- Bonuslar: LIC +10, LMC +7, UMC +4, HIC/NA 0.
- **Bonus yalnızca SI ≥ 60 olan adaylara** uygulanıyor.
- SI her zaman ayrı ve değişmeden raporlanıyor.
- Bonus puan cinsinden: bir aday, ancak kendisinden en fazla `bonus` puan daha iyi olan bir adayı geçebilir.
- `novelty_bonus` şimdilik 0; veri seti yok.
- Bu kuralların hepsi testlerle güvence altında.

### 3.4 Doğrulama (`anchors.json`, `cli validate`)
**Çapalar** (literatürden, kaynaklı, ilk çalıştırmadan **önce** donduruldu):
- Jezero → Salda Gölü (c079, c080)
- Cerberus → McCartys (c001) ve İzlanda/Laki (c087)
- Gale → Mauna Kea hematit sırtı (c009, c010)
- Shackleton → Haughton (c086)
- Marius → San Francisco Volcanic Field (c008)

Imbrium ve Tharsis için katalogda kaynaklı bir çapa yok; doğrulamadan bilerek çıkarıldılar.

**Son sonuç** (16 site, saf SI ile): hit@5 değeri landing, resource ve habitat profillerinde **5/5**, science profilinde **4/5** (Gale → Mauna Kea 7. sırada). Rastgele seçimde beklenen oran ≈ %31. MRR 0.61–0.74.

**Dürüst uyarı:** Hedef ve site değerleri literatür tahminleri ve katalog küçük. Bu bir akıl sağlığı kontrolü; güçlü bir kanıt değil. Gerçek grid verisiyle tekrarlanmalı.

---

## 4. Durum tablosu
| Parça | Durum |
|---|---|
| Frontend v2 feature seti, kartlar ("Strongest / Breaks on"), compare tablosu, sabit farklar, tier rozetleri, 4 profil | ✅ çalışıyor, tarayıcıda test edildi, konsolda hata yok |
| 16 sitelik katalog (yeni: Salda/Türkiye, Lonar/Hindistan, Dallol/Etiyopya, Haughton/Kanada) + 9 yeni kaynak (DOI'leri Crossref'te doğrulandı) | ✅ |
| Backend skor motoru, öncelik, açıklama, validate, demo CLI | ✅ çalışıyor, 15 test geçiyor |
| 10 km global grid | ✅ (okyanus dahil 5.08 M hücre; `data/grid.parquet` zip'te yok, yeniden üretilir) |
| Dünya Bankası gelir verisi | ✅ |
| `countries.py` (shapely) | ⚠️ yazıldı, **hiç çalıştırılmadı** |
| `extract/earth_gee.py` | ⚠️ yazıldı, **hiç çalıştırılmadı**. Hatalar beklenir (asset ID'leri, band adları, zaman aşımı, birimler) |
| `api.py` (FastAPI) | ⚠️ yazıldı, **hiç çalıştırılmadı** |
| GEE export CSV'lerini birleştiren komut | ❌ yok, yazılması gerekiyor |
| Anchor/Discover iki liste, kümeleme, yenilik, erişilebilirlik | ❌ yok |
| Frontend ↔ API bağlantısı | ❌ yok |
| Ay/Mars gerçek veri çekme (LOLA/MOLA) | ❌ yok; zaman kalırsa sadece preset'ler için yapılabilir |

---

## 5. Değişmez kararlar (sormadan değiştirme)
1. **Gezegenden bağımsız feature seti.** Mutlak yükseklik yok. Termal inertia kendi gezegenindeki yüzdelik olarak kullanılıyor.
2. **Sabit fiziksel aralıklarla normalizasyon.** Katalog ya da grid'e göre min-max **yapma**. Bir sitenin skoru, başka siteler eklendi diye değişmemeli; bunun için test var.
3. **Ağırlıklı Öklid/RMS mesafesi. Kosinüs benzerliği KULLANMA.** Kosinüs vektörün büyüklüğünü yok sayar; 0–1 ölçekli verilerde (0.1, 0.1) ile (0.9, 0.9) birebir aynı sayılır.
4. **Öncelik formülü bölüm 3.3'teki gibi kalacak.** `SI×0.7 + Yenilik×0.2 + Erişim×0.1` gibi çarpımsal karışımlar önerilebilir ama reddedildi. Sebebi: SI'sı 30 puan düşük bir adayın, yenilik ve erişim puanıyla 1. sıraya çıkmasına izin veriyorlar, ayrıca Global South önceliğini tamamen kaldırıyorlar. Yeni bonuslar (yenilik, erişim) **aynı mantıkla eklenecek:** puan cinsinden, üst sınırlı, sadece SI ≥ 60 için.
5. **Global South bir filtre değil, öncelik.** Hiçbir ülke sonuçlardan elenmez.
6. **SI her yerde opportunity'nin yanında gösterilir.** Politika tercihi ve fizik ayrı kalır.
7. **`anchors.json` donduruldu.** Doğrulama skoru daha iyi çıksın diye çapa listesini veya site/hedef değerlerini **değiştirme**; bu, doğrulamayı döngüsel ve anlamsız hale getirir. Yeni çapa eklenecekse, kaynağı literatürde olan bir çapa eklenir, eklenme tarihi not edilir ve sonuç ne çıkarsa olduğu gibi raporlanır.
8. **Proxy değerler her yerde "PROXY" olarak etiketli kalacak.** Jüriye dürüstçe anlatılacak.
9. **Bilimsel kaynak eklerken DOI'yi Crossref'te doğrula** (`https://api.crossref.org/works/<doi>`). Uydurma kaynak kesinlikle yok.
10. **Feature seti için tek doğruluk kaynağı `backend/config/features.json`.** Frontend'deki `FEATURES` ve `FEATURE_TIERS` bununla uyumlu tutulacak.

---

## 6. Kullanıcıya sorulacak açık kararlar
1. **Bonus mu, kota mı?**
   - **Sorun:** 1.5 M rastgele hücreyle yapılan testte ilk 50 sonucun hepsi LIC/LMC çıktı. Milyonlarca hücrede üst sıradaki SI'lar birbirine çok yakın olduğu için +7/+10'luk bonus sıralamayı belirliyor.
   - **Seçenek A:** Bonusu olduğu gibi bırakmak.
   - **Seçenek B:** Kota; örneğin ilk 20'nin en az yarısı Global South olsun, kalan yerler saf SI'ya göre dolsun.
   - Adım 3'ten önce kullanıcıya sor.
2. **Google Earth Engine proje ID'si.** Kullanıcı açıp verecek. Gerekirse adımları anlat:
   1. console.cloud.google.com'da proje oluştur.
   2. code.earthengine.google.com'da projeyi ticari olmayan kullanım için kaydet.
   3. Şu iki komutu çalıştır:
      ```bash
      pip install earthengine-api
      ```
      ```bash
      earthengine authenticate
      ```
3. **Yayına alma tercihi:** Frontend için GitHub Pages; API için Render, Railway ya da Hugging Face Spaces gibi bir hizmet.

---

## 7. Yapılacak işler (sırayla, kabul kriterleriyle)

### Adım A — Ortamı kur ve mevcut durumu doğrula (30 dk)
`backend/` içinde şu komutları sırayla çalıştır:

```bash
pip install numpy pandas pyarrow requests shapely fastapi uvicorn earthengine-api
```

```bash
python -m unittest discover -s tests -v
```

```bash
python -m analog_atlas.cli validate
```

```bash
python -m analog_atlas.cli demo --profile landing --top 8
```

**Kabul:**
- 15 testin hepsi geçiyor.
- `validate` çıktısı bölüm 3.4'teki tabloyla aynı.
- Frontend http.server ile açılıyor; Jezero + Science + Run Match yapınca Salda 1. çıkıyor.

### Adım B — Earth Engine ile gerçek veri (öncelik: EN YÜKSEK, en uzun süren iş)
1. **Küçük alanla duman testi.** Önce Türkiye çevresinde küçük bir bbox ile `sample` modunda çalıştır:
   ```bash
   python -m analog_atlas.cli build-grid --km 25 --bbox 26 36 31 39 --countries
   ```
   ```bash
   python -m analog_atlas.cli extract-earth --project <ID> --mode sample
   ```
   Hata çıkarsa `earth_gee.py`'yi düzelt. Kontrol edilecek asset'ler:
   - `NASA/NASADEM_HGT/001`
   - `MODIS/061/MOD11A2`, `MODIS/061/MCD43A3`, `MODIS/061/MOD13A2`, `MODIS/061/MOD16A2`
   - `NASA/GPM_L3/IMERG_MONTHLY_V07`
   - `NASA/GSFC/MERRA/aer/2` (saatlik ve ağır; gerekirse tarih aralığını kısalt)
   - `NASA/ASTER_GED/AG100_003`
   - `COPERNICUS/S2_SR_HARMONIZED` (global ölçekte ağır; kaba taramada çıkarılabilir, NaN kalır)
2. **Değerlerin akıl sağlığı kontrolü.** Salda Gölü'nün (37.55N, 29.68E) bulunduğu hücrenin değerlerini katalogdaki tahminlerle karşılaştır: eğim birkaç derece, albedo 0.15–0.3, temp_min −10…0 °C civarı, NDVI düşük-orta. Birimler tutarsızsa (MODIS ölçek faktörleri, IMERG mm/saat, MOD16 PET birimi) düzelt.
3. **Erişilebilirlik bandı.** `Oxford/MAP/accessibility_to_cities_2015_v1_0` (dakika cinsinden şehre seyahat süresi) bandını `raw_stack()`'e ekle. `postprocess()` içinde `access_minutes` kolonu olarak sakla; bu bir feature **değil**, Adım C'de bonus için kullanılacak.
4. **Global kaba tarama (50 km).**
   ```bash
   python -m analog_atlas.cli build-grid --km 50 --countries
   ```
   - Grid okyanusu da içeriyor. Export öncesi kara hücrelerini ayıklamak için `countries.py`'nin `iso3` atamadığı hücreleri çıkar (Antarktika ve açık deniz dikkat: Antarktika'nın ISO kodu ATA, onu tut).
   - İstemci tarafında oluşturulan büyük FeatureCollection'lar GEE'nin istek boyutu sınırına takılabilir. Görev başına ≤5000 hücre olacak şekilde parçala; ya da grid'i bir GEE asset'i olarak yükleyip oradan çalış.
   - `--mode export` ile Drive'a CSV olarak aktar. Görevlerin durumunu `ee.batch.Task.list()` ile takip et.
5. **Eksik komut:** `merge-exports` komutunu yaz. Drive'dan indirilen CSV'leri birleştirsin, `grid.parquet` ile lat/lon/iso3 bilgisini eklesin, `postprocess()`'ten geçirsin ve `data/earth_features.parquet` dosyasını yazsın. Yeni komut için test ekle.
6. **Opsiyonel, zaman kalırsa:**
   - GLiM (küresel litoloji haritası, PANGAEA) ve WOKAM (dünya karst haritası, BGR) ile `cave_index`, `mineral_evaporite` ve `landform_class` proxy'lerini doldur.
   - Zaman yoksa bu alanlar NaN kalsın; motor zaten atlıyor.

**Kabul:** `python -m analog_atlas.cli score --target cerberus --source grid --top 30` gerçek hücrelerden sonuç döndürüyor. Hem kaba sonuçlar hem çapa sitelerine yakın hücrelerin sırası raporlanıyor.

**Risk yönetimi:** GEE export'ları saatler sürebilir. Bu adımı **ilk gün** başlat, bekleme sürelerinde Adım C ve D'nin iskeletini katalog verisiyle kur.

### Adım C — Anchor & Discover + yenilik + erişilebilirlik (backend)
1. **API iki liste döndürsün** (`/score` ya da yeni bir `/find-analogs` endpoint'i):
   - **anchors:** katalogdaki 16 sitenin sırası (doğrulama amaçlı)
   - **discoveries:** grid adayları
2. **Kümeleme.** Yüksek skorlu hücreler bölgelere toplanmalı; aynı lav sahasından 30 hücre listeyi doldurmasın. Basit çözüm: opportunity'ye göre sıralayıp açgözlü seçim yap, seçilen her adayın 150 km yarıçapındaki diğer hücreleri listeden at (non-maximum suppression). Her bölge için en iyi hücre, bölgedeki hücre sayısı ve ortalama SI raporlansın.
3. **"Zaten biliniyor" işareti.** Katalog sitelerine veya kampanya listesine 50 km'den yakın adaylar `known_nearby` olarak işaretlensin.
4. **Yenilik puanı (OpenAlex KULLANMA, hızlı ve sağlam yol):**
   - Elle bir `data/campaigns.csv` derle: geçmiş NASA/ESA analog saha kampanyaları.
     - **Kolonlar:** name, lat, lon, country, agency, program, source_url.
     - **Örnek kampanyalar:** HMP/Devon, Desert RATS/Black Point & SP Crater, PISCES/Hawaii, HI-SEAS, FINESSE/Craters of the Moon, NEEMO/Florida, ARADS/Atacama, MARTE/Río Tinto, AMASE/Svalbard, Apollo eğitimi (İzlanda, Ries, Sudbury), Mojave/Death Valley, Pavilion Lake, Mars 2020/Salda.
     - Her satıra bir kaynak URL'si ekle.
   - **Hesap:** novelty = clip(en yakın kampanyaya uzaklık_km / 500, 0, 1). Bu değer `priority.py`'deki `novelty_col` üzerinden en fazla `max_bonus` (5) puan bonus verir.
   - Aynı CSV, sunumdaki "NASA'nın analog sahaları nerede, gelir grubuna göre dağılım" grafiğinin de verisi olacak.
5. **Erişilebilirlik bonusu.**
   - `access_minutes` küçükse küçük bir bonus ver; öneri en fazla +3 puan. Değer `priority.json`'a yazılsın.
   - 48 saatten uzak adaylar elenmesin, sadece "zor erişim" olarak işaretlensin.
   - Kurallar diğer bonuslarla aynı: puan cinsinden, üst sınırlı, SI ≥ 60.
6. **Testleri genişlet.** Kümeleme, `known_nearby` işareti, yeni bonusların sınırları ve "bonus açıkça daha iyi bir analoğu geçemez" kuralı test edilsin.
7. **Bölüm 6.1'deki bonus/kota kararını uygula.**

**Kabul:** Cerberus sorgusunda yanıt hem anchors listesinde McCartys'i, hem de discoveries listesinde gerekçeli (en güçlü aileler, bozulduğu feature'lar, gelir grubu, yenilik ve erişim bilgisiyle) az çalışılmış adayları içeriyor.

### Adım D — Frontend'i backend'e bağla
1. **Run Match akışı.**
   - `CONFIG.API_BASE` ayarı ekle; boşsa API devre dışı.
   - Butona basılınca `regionFeatures(region)` sonucu ve aile ağırlıkları API'ye POST edilsin (4 saniyelik timeout).
   - **API'ye ulaşılamazsa mevcut yerel Web Worker motoru çalışsın.** Jüri sunumunda internet giderse demo çökmemeli.
2. **Kartlar.**
   - İki bölüm: **"Validation anchors"** ve **"New discoveries"**.
   - Rozetler: Global South (+N), novelty, access, `known_nearby`.
   - SI ve opportunity yan yana gösterilsin.
3. **Globe.** Discoveries globe üzerinde işaretlensin; "Locate" butonu oraya uçursun. Isı haritası opsiyonel: preset hedefler için önceden üretilmiş bir PNG ya da nokta katmanı yeterli.
4. **Çevrimdışı yedek.** 7 preset × 4 profil için API sonuçlarını önceden üret, JSON olarak `p2.html` içine göm (ya da yanına koy). Böylece sunucu kapalıyken bile preset'ler gerçek sonuç gösterir.
5. **Tutarlılık.** `FEATURES` / `FEATURE_TIERS` ile `features.json` uyumlu kalmalı. Methodology metni güncel olmalı (şu an "16 catalog sites" ve doğrulama sonuçları yazıyor; grid gelince güncelle).
6. **Yayına alma.**
   - Frontend: GitHub Pages.
   - API: ücretsiz bir hizmet; CORS zaten açık.

**Kabul:** Mars'ta Jezero seçiliyor, Run Match'e basılıyor; Salda çapa olarak, yeni adaylar da rozetleri ve gerekçeleriyle geliyor. API kapatılınca demo hâlâ çalışıyor.

### Adım E — Son 12 saat: yeni özellik YOK
- **README (İngilizce):**
  - problem
  - yöntem: feature seti, sabit aralıklar, metrik
  - Anchor & Discover
  - doğrulama tablosu
  - Global South önceliği ve kuralları
  - veri kaynakları ve seviyeleri
  - sınırlamalar: proxy'ler, sentetik Ay/Mars DEM'i, katalog değerlerinin tahmin olması
  - kurulum ve komutlar
- **Space Apps proje sayfası, sunum slaytları ve demo videosu.** Önerilen akış:
  1. NASA sahalarının dağılım grafiği
  2. Jezero → Salda doğrulaması
  3. Cerberus → yeni bir Global South keşfi
  4. "Breaks on" ve Dünya'nın sınırları
- **GitHub'a push.** `data/grid.parquet` ve büyük ara dosyalar `.gitignore`'a eklensin.

---

## 8. Saat planı (öneri)
| Saat | İş |
|---|---|
| 0–1 | Adım A. Kullanıcıdan GEE proje ID'sini ve bonus/kota kararını iste |
| 1–6 | Adım B.1–B.3 (duman testi, düzeltmeler, erişilebilirlik bandı) |
| 6–8 | Adım B.4: global export görevlerini başlat (arka planda saatler sürer) |
| 8–20 | Export beklerken: Adım C (katalog verisiyle) + campaigns.csv |
| 20–24 | Adım B.5: export'ları birleştir, grid sonuçlarıyla C'yi doğrula |
| 24–36 | Adım D + çevrimdışı JSON + yayına alma |
| 36–48 | Adım E (dondurma: README, video, slaytlar, teslim) |

---

## 9. Bilinen tuzaklar
- **Windows konsolu:** cp1252 varsayılanı yüzünden `·` ve `ö` gibi karakterler bozulabiliyor. CLI'da `sys.stdout.reconfigure(encoding="utf-8")` var; yeni script'lerde de kullan.
- **Doğrulama profil bağımlılığı:** `validate` saf SI kullanıyor, opportunity kullanmıyor. Bu kasıtlı; değiştirme.
- **JSON çıktısı:** `pipeline._plain()` numpy tiplerini JSON'a uygun Python tiplerine çeviriyor. Yeni alan eklerken JSON'a yazmadan önce bundan geçir.
- **Grid hücre kimliği:** `cell_id` "bant_sütun" formatında; parquet ve CSV birleştirmelerinde anahtar olarak bu kullanılıyor.
- **Frontend localStorage:** ağırlık anahtarı `aa.weights.v2`. Aile sayısı değişirse anahtarı tekrar artır.
- **`p2.html` çok büyük (2.3 MB):** Düzenlemeleri dar ve hedefli yap (Edit ya da küçük Python script'leri). Dosyayı baştan yazma; base64 dokuları bozulur.

İlk mesajında: zip'i açtığını doğrula, Adım A'yı çalıştır ve sonucunu raporla. Ardından kullanıcıdan GEE proje ID'sini ve bonus/kota kararını iste.
