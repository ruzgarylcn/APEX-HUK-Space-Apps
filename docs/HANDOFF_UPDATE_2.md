# Devir güncellemesi #2 (Claude'a yapıştır)

Bu zip'teki dosyaları proje köküne, aynı yollara kopyala (var olanların üzerine yazılır). Sonra `backend/` içinde
`python -m unittest discover -s tests -v` çalıştır: **16 test** geçmeli.

## Yeni / değişen dosyalar
| Dosya | Ne |
|---|---|
| `backend/data/campaigns.csv` | **YENİ.** 33 analog saha kampanyası (NASA, ESA, OeWF, ISRO, Çin): koordinat, `coord_precision`, kurum, `nasa_involved`, yıllar, hedef, faaliyet, gelir grubu, kaynak URL'si. Adım C'deki yenilik puanı ve `known_nearby` işareti için **hazır veri**. Kampanya listesini yeniden derleme. |
| `docs/campaigns_summary.md` | **YENİ.** Sunumdaki açılış grafiğinin verisi: NASA kampanyalarının 19/22'si (%86) yüksek gelirli ülkelerde, 0'ı alt-orta veya düşük gelirli ülkelerde. |
| `backend/config/discovery_checklist.json` | **YENİ, DONDURULMUŞ.** Literatürde Mars/Ay analoğu olarak adı geçen, katalogda ve kampanya listesinde olmayan 10 aday (Çad, İran, Libya, Hindistan ×3, Gana, Mısır, Namibya, Çin). DOI'lerin hepsi Crossref'te doğrulandı. |
| `backend/analog_atlas/pipeline.py` | `check_discoveries()` eklendi. |
| `backend/analog_atlas/cli.py` | `check-discoveries` komutu eklendi. |
| `backend/tests/test_core.py` | Sentetik grid ile kontrol listesi testi eklendi. |

## Kurallar (değişmez kararlara ek)
- **`discovery_checklist.json` donduruldu.** Global grid sonuçlarını gördükten sonra adayları, hedefleri, yarıçapları veya protokolü **değiştirme**. Sonradan aday eklenecekse yeni bir `frozen_on` tarihiyle eklenir ve ayrı raporlanır.
- **Protokol:**
  - Her aday için, beklenen hedefe göre saf SI hesaplanır (bonus yok).
  - Adayın yarıçapı içindeki en iyi hücrenin, tüm kara hücreleri arasındaki yüzdeliğine bakılır.
  - Yüzdelik ≥ 90 ise **geçti**, ≥ 99 ise **güçlü geçti**.
  - Birincil profil: science.
  - Rastgele noktalarla aynı yarıçapta bir taban çizgisi de hesaplanır ve sonuçla birlikte raporlanır.
- **Sittampundi bilerek eklenen zor bir vaka.** Mineral olarak Ay yaylalarına benziyor ama sıcak bir bölgede; büyük olasılıkla Shackleton'a göre **kalacak**. Kalırsa bu bir hata değil, sonuçtur; olduğu gibi raporla.

## Ne zaman çalıştırılacak
Adım B bitip `data/earth_features.parquet` oluşunca:
```bash
python -m analog_atlas.cli check-discoveries
```
Çıktı `out/discovery_check_*.csv` dosyalarına yazılır. Sunum cümlesi: "Sonuçları görmeden önce dondurduğumuz 10 literatür adayından N'i ilk %10'da; rastgele noktalarda bu oran %X."

## Adım C için kampanya verisinin kullanımı
- `novelty = clip(en yakın kampanyaya uzaklık_km / 500, 0, 1)`: en fazla +5 bonus (`priority.json` → `novelty.max_bonus`), yalnızca SI ≥ 60 için.
- `known_nearby`: kampanyaya veya katalog sitesine 50 km'den yakın.
- `_haversine_km()` fonksiyonu `pipeline.py` içinde hazır; tekrar yazma.
