# Devir güncellemesi #3 (Claude'a yapıştır)

Bu zip'teki dosyaları proje köküne, aynı yollara kopyala; var olanların üzerine yazılır. Güncelleme #2'yi de içerir, ayrıca #2'yi uygulamana gerek yok. Sonra `backend/` içinde `python -m unittest discover -s tests -v` çalıştır: **16 test** geçmeli.

## Neler değişti
| Dosya | Değişiklik |
|---|---|
| `backend/data/campaigns.csv` | 33 → **41 kampanya.** Eklenenler: Pinacate/Meksika (Apollo), Çin'den 5 kampanya (CUG Qaidam, Jinchang, PKU Jingpo lav tüpleri, Hainan lav mağaraları, astronot mağara eğitimi), Japonya Tottori, Kanada CanMars ve CanMoon. Yeni kolon: `source_lang` (kaynağın bulunduğu dil). |
| `docs/campaigns_summary.md` | Güncel istatistik (NASA 19/22 yüksek gelirli) + **tarama kapsamı tablosu**: hangi dillerde ve hangi ajanslarda arandı, neler bilerek dışarıda bırakıldı, neler doğrulanamadığı için eklenmedi. |
| `backend/config/discovery_checklist.json` | Orijinal 10 aday **değişmedi.** Üç yeni bölüm eklendi: `amendments` (Jingpo), `batch_2` (Çince ve Rusça taramada uygun yeni aday çıkmadı) ve `watch_list` (testin parçası olmayan 6 bölge). |
| `backend/analog_atlas/pipeline.py` | `check_discoveries()` artık `known_after_freeze` kolonunu ve özet tabloda `novel_candidates` / `novel_passed` değerlerini üretiyor. |

## Kurallar
- **Jingpo:** Kontrol listesi dondurulduktan sonra, ama grid sonucu henüz yokken, Pekin Üniversitesi'nin 2025'te Jingpo'da bir lav tüpü üssü kurduğu öğrenildi. Bu yüzden Jingpo "yeni keşif" sayılmıyor.
  - Listeden **silinmiyor**; dondurulmuş liste düzenlenmez.
  - Sonuçlarda ayrı raporlanır ve "novel" sayıma girmez.
  - Sunum cümlesi: "9 yeni adaydan N'i ilk %10'da."
- **`watch_list`** bir test değil. Literatürde bu bölgeleri analog olarak tanımlayan bir makale bulunamadı. Global tarama bunları üst sıralarda gösterirse, bu gerçekten yeni bir öneri olur; sunumda ayrıca anlatılabilir.
- **Adım C, yeni bilinen yerlerle birlikte çalışmalı.** Kampanya listesi genişlediği için yenilik puanı Çin'deki çalışılmış bölgeleri (Qaidam, Jingpo, Hainan) artık "bilinen" sayacak. Bu doğru davranış; değiştirme.
