# Where have planetary analog campaigns taken place?

Data: `backend/data/campaigns.csv` — **41 natural-site field campaigns** compiled 2026-11-14, one cited source per row
(agency pages, NTRS, USGS, peer-reviewed DOIs, national news agencies, or Wikipedia where no primary page was reachable).
Column `source_lang` records the language the source was found in. Income groups: World Bank classification
(`backend/data/income_groups.csv`).

## Headline (for the opening slide)

**19 of 22 NASA-involved analog campaigns (86 %) took place in high-income countries.
Only two were in developing countries — both upper-middle income: Apollo geology training at Pinacate, Mexico
(1965, 1970) and the Mars 2020 team's 2019 study at Lake Salda, Türkiye.
None took place in a lower-middle- or low-income country.**

Second sentence for the same slide: **Other agencies and organisations go elsewhere — 10 of their 19 campaigns are in
middle-income countries (6 of them in China) — but no space agency has run a field analog campaign in a low-income country.**

| Income group | NASA-involved (n=22) | Other agencies (n=19) | All (n=41) |
|---|---|---|---|
| High income | 19 (86.4 %) | 8 (42.1 %) | 27 (65.9 %) |
| Upper-middle | 2 (9.1 %) | 7 (36.8 %) | 9 (22.0 %) |
| Lower-middle | 0 | 3 (15.8 %) | 3 (7.3 %) |
| Low income | 0 | 0 | 0 |
| Antarctica (unclassified) | 1 (4.5 %) | 1 (5.3 %) | 2 (4.9 %) |

NASA-involved campaigns by country: USA 10 · Canada 4 · Iceland, Germany, Chile, Spain, Norway, Türkiye, Mexico,
Antarctica 1 each.
Other campaigns by country: China 6 · USA 2 · Spain 2 · India 2 · Italy, Antarctica, Morocco, Oman, Israel, Armenia,
Japan 1 each.

## Search coverage — what was and was not searched

| Scope | Searched | Result |
|---|---|---|
| NASA | English, systematically (programs, NTRS, USGS, JPL, Apollo history) | 22 campaigns |
| ESA, Austrian Space Forum, ISRO | English | 9 campaigns |
| China (CNSA, CAS, CUG, PKU, CMSA) | **Chinese** + English | 6 campaigns — 4 found only or mainly through Chinese sources (CUG Qaidam research, PKU Jingpo lava-tube base, Hainan lava caves, Chinese astronaut cave training) |
| Russia (Roscosmos, IBMP, GEOKHI, FMBA) | **Russian** + English | **0 natural-site campaigns verified** (see below) |
| Japan (JAXA) | **Japanese** | 1 (Tottori Sand Dunes lunar field) |
| Canada (CSA) | English | 2 (CanMars in Utah, CanMoon on Lanzarote) |
| Korea (KASA, KARI, KICT) | English | 0 field sites — only indoor test chambers |
| UAE (MBRSC) | English | 0 field sites — UAE crews took part in indoor studies abroad (SIRIUS in Moscow, HERA in Houston) |
| Not searched | Spanish, Portuguese, Arabic, French, Korean-language sources; Brazil (AEB), Argentina (CONAE), Türkiye (TUA), Iran | — |

### Deliberately excluded (not natural field sites)
Indoor isolation habitats and constructed test yards are not field analogs of a planetary surface:
Mars-500 and SIRIUS (IBMP, Moscow), HERA (NASA, Houston), the Soviet Lunokhod "lunodrome" (constructed 1968 near
Simferopol, Crimea), the CAST Mars yard and Tianwen-1 landing test field (China), KICT's dirty thermal-vacuum chamber
(Korea), JAXA's indoor Space Exploration Field (Sagamihara).

### Found but not added (could not verify, or not yet operational)
- **Tolbachik, Kamchatka** — popular Russian sources say Soviet Lunokhods were tested on the volcano; no primary
  source could confirm it.
- **Kolyma permafrost** — long-running Russian microbiology on permafrost bacteria with Mars relevance; only press
  coverage found, no campaign-level primary source.
- **MARS-V, Gobi (Mongolia)** — non-profit analog habitat planned for 2029; not yet operating.
- **FMBA lunar polygon (Russia)** — announced, not built.

## Caveats (say these out loud — they make the claim stronger, not weaker)

- **Not exhaustive.** A compiled list of well-documented campaigns, not a census. Apollo training alone had ~200 field
  exercises, almost all in the USA; smaller NASA-funded university fieldwork is under-represented. Adding either would
  most likely add more US sites, not fewer.
- **The non-NASA column depends on languages searched.** Adding Chinese sources moved it from 11 to 19 campaigns.
  Spanish- and Portuguese-language searches would likely add Latin American work.
- **One row per campaign/site,** not weighted by duration, budget or number of papers.
- **Coordinates:** `coord_precision = site` for a specific locality, `region` where only the region is documented
  (±50–100 km). Good enough for the novelty distance (`novelty = clip(distance_km / 500)`).
- **Three sources returned HTTP 403 to an automated check** (Wiley DOI page, two JPL news pages) because those sites
  block scripts; all three were confirmed through search results. All other URLs returned HTTP 200 on 2026-11-14.

## Correction log
- Pinacate (Mexico) added after the first version → NASA headline 19/21 (90 %) became 19/22 (86 %).
- Chinese, Japanese and Canadian campaigns added after the multilingual search → "other agencies" 11 → 19.
- The discovery-checklist candidate **Jingpo Lake** turned out to host a Peking University lunar lava-tube base (2025).
  It is flagged `reclassified_known` in `config/discovery_checklist.json` and excluded from the "novel" pass count.

## How the backend uses this file

Step C of the handoff plan: distance from each candidate to the nearest campaign → `novelty` (0–1) →
up to +5 opportunity points (only when SI ≥ 60). Candidates within 50 km of a campaign get `known_nearby = true`.
