# Analog Atlas — Backend

Ay/Mars hedef bölgelerine en çok benzeyen Dünya bölgelerini **tüm Dünya'yı tarayarak** bulur ve
gelişmekte olan ülkeleri (Global South) **filtre olarak değil, öncelik olarak** öne çıkarır.

## Akış

```
NASA / ESA / JAXA açık verileri                   Ay (LOLA, Diviner…) / Mars (MOLA, TES, CRISM…)
        │  extract/earth_gee.py  (Google Earth Engine)        │  (sonraki adım: PDS extraction)
        ▼                                                     ▼
 10 km global grid ──► 23 feature/hücre  ───────────►  hedef bölge vektörü (config/targets.json)
 (grid.py, ~1.5 M kara hücresi)    (data/earth_features.parquet)
                                   │
                                   ▼
                    scoring.py   SI = 100·(1 − √(Σw·Δ²/Σw))    (sabit fiziksel aralıklar)
                                   │
                                   ▼
                    priority.py  opportunity = SI + gelir bonusu (+ yenilik bonusu)
                                   │
                                   ▼
                    pipeline.py  sıralama + "en güçlü aileler / nerede bozuluyor" açıklaması
                                   │
                         cli.py (çıktı: out/*.json)  ·  api.py (frontend için HTTP)
```

## Global South önceliği nasıl çalışıyor

| Dünya Bankası grubu | Bonus (SI puanı) |
|---|---|
| Low income (LIC) | +10 |
| Lower-middle (LMC) | +7 |
| Upper-middle (UMC) | +4 |
| High income (HIC) / sınıflandırılmamış | 0 |

- **Hiçbir ülke elenmez.** Fiziksel benzerlik (SI) her sonuçta değişmeden raporlanır, `opportunity` yanında durur.
- **Bonus yalnızca SI ≥ 60 olan adaylara uygulanır.** Zayıf bir analog, bulunduğu yer yüzünden öne çıkamaz.
- **Bonus sınırlıdır.** Öncelikli bir aday, ancak kendisinden en fazla `bonus` puan daha iyi olan bir adayı geçebilir. Açıkça daha iyi bir analog yüksek gelirli bir ülkedeyse yine o kazanır.
- Tüm değerler `config/priority.json` içinde ayarlanabilir. Gelir verisi Dünya Bankası API'sinden gelir (CC BY 4.0).

## Kurulum

```bash
pip install -r requirements.txt
```

Sadece demo ve testler için `numpy`, `pandas`, `pyarrow` ve `requests` yeterli.

## Komutlar

```bash
python -m analog_atlas.cli fetch-income
```

```bash
python -m analog_atlas.cli demo --profile landing
```

```bash
python -m analog_atlas.cli build-grid --km 10 --countries
```

```bash
python -m analog_atlas.cli extract-earth --project GCP_PROJE_ID --mode sample
```

```bash
python -m analog_atlas.cli score --target cerberus --profile science --top 50
```

```bash
uvicorn analog_atlas.api:app --reload --port 8000
```

```bash
python -m unittest discover -s tests -v
```

- `demo`: 7 hedefi 12 sitelik literatür kataloğuna karşı skorlar ve sonuçları `out/` klasörüne yazar.
- `build-grid`: global grid'i üretir. `--countries` için `shapely` gerekir; `--bbox W S E N` ile küçük bir test alanı seçilebilir.
- `extract-earth`: Earth Engine ile özellik çıkarır. Önce `earthengine authenticate` çalıştırılmalı. Küresel ölçek için `--mode export` kullanılır (Drive'a aktarım).
- `score`: Grid verisi varsa onu, yoksa kataloğu kullanır.

## Dosyalar

| Dosya | Görev |
|---|---|
| `config/features.json` | v2 feature seti, aralıklar, profiller, her feature'ın veri kaynağı (frontend ile aynı) |
| `config/priority.json` | Global South bonusları ve kuralları |
| `config/targets.json` | Ay/Mars hedefleri (şimdilik literatür tahmini) |
| `data/catalog_sites.json` | 12 bilinen analog — doğrulama ve kalibrasyon için |
| `data/income_groups.csv` | Dünya Bankası gelir grupları (217 ülke) |
| `analog_atlas/scoring.py` | Vektörize benzerlik motoru (milyonlarca hücre) |
| `analog_atlas/priority.py` | Öncelik katmanı |
| `analog_atlas/extract/earth_gee.py` | Earth Engine veri çekme + post-processing |

## Durum

| Parça | Durum |
|---|---|
| Skor motoru, öncelik, açıklama, CLI demo | ✅ çalışıyor, 14 test geçiyor |
| Global grid | ✅ çalışıyor (10 km → 5.08 M hücre, kara maskesi extraction'da) |
| Ülke ataması (`--countries`) | ⚠️ yazıldı, `shapely` kurulu olmadığı için çalıştırılmadı |
| Earth Engine extraction | ⚠️ yazıldı, GEE hesabı olmadan çalıştırılmadı |
| FastAPI | ⚠️ yazıldı, `fastapi` kurulu olmadığı için çalıştırılmadı |
| Ay/Mars extraction (PDS) | ⏳ sonraki adım — hedefler şimdilik literatür tahmini |
| `crater_density`, `rock_abundance`, `cave_index`, `plagioclase`, `evaporite`, `landform_class` (Earth) | ⏳ global kaynak gerekiyor; şimdilik NaN, skor motoru bunları atlıyor |
| Mineral ve zemin buzu değerleri | ⚠️ basit proxy formüller, iyileştirilecek |
| Yenilik (araştırma ilgisi) bonusu | ⏳ veri seti henüz yok |
