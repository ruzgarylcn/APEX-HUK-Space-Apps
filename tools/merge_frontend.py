"""Build the single deliverable frontend: p2.html (v2 engine) + the Cesium LOD globe of index.html
+ priority badges, Anchor & Discover section and API wiring. Narrow, asserted edits only.

usage: python -I merge_frontend.py <p2.html> <index_lod.html> <backend dir> <out index.html>
"""
import csv
import json
import re
import sys

p2_path, ix_path, backend, dst = sys.argv[1:5]
s = open(p2_path, encoding="utf-8").read()
ix = open(ix_path, encoding="utf-8").read()
PR = json.load(open(f"{backend}/config/priority.json", encoding="utf-8"))
AN = json.load(open(f"{backend}/config/anchors.json", encoding="utf-8"))
INC = list(csv.DictReader(open(f"{backend}/data/income_groups.csv", encoding="utf-8"), ))
CAMP = list(csv.DictReader(open(f"{backend}/data/campaigns.csv", encoding="utf-8")))


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, f"expected {count}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


def section(text, start, end):
    i = text.find(start)
    j = text.find(end, i)
    assert i >= 0 and j > i and text.count(start) == 1, start
    return i, j


def js(o):
    return json.dumps(o, ensure_ascii=False)


# ---------------------------------------------------------------- 1. LOD globe: CONFIG, globe block, textures
def cfg_bounds(text):
    i = text.find("const CONFIG = Object.freeze({")
    return i, text.find("\n});", i) + len("\n});")


ci, cj = cfg_bounds(ix)
cfg = ix[ci:cj]
p2_cfg = s[slice(*cfg_bounds(s))]
gap_line = re.search(r"^  GAP_THRESHOLD:.*$", p2_cfg, re.M).group(0)
storage_line = re.search(r"^  STORAGE:.*$", p2_cfg, re.M).group(0)
cfg = re.sub(r"^  MIN_VAR:.*$\n", "", cfg, flags=re.M)                 # v1 variance floor: unused in v2
cfg = re.sub(r"^  MAX_RESULTS:.*$", "  MAX_RESULTS: 16,                     // all 16 catalog sites = the validation-anchor list", cfg, flags=re.M)
cfg = re.sub(r"^  STORAGE:.*$", storage_line, cfg, flags=re.M)
cfg = cfg.replace("  SITE_MATCH_DEG:", gap_line + "\n  SITE_MATCH_DEG:", 1)
cfg = cfg.replace("  FAVORITES_MAX:", "  // Backend API (FastAPI). Empty = local engine only; override with ?api=https://host\n"
                  "  API_BASE: new URLSearchParams(location.search).get('api') || '',\n"
                  "  API_TIMEOUT_MS: 4000,                // spec: give up on the API after 4 s and stay local\n"
                  "  FAVORITES_MAX:", 1)
assert "GAP_THRESHOLD" in cfg and "API_BASE" in cfg and "aa.weights.v2" in cfg
pi, pj = cfg_bounds(s)
s = s[:pi] + cfg + s[pj:]

gi, gj = section(ix, "// ===== GLOBE (CesiumJS", "// ===== SELECTION (")
si, sj = section(s, "// ===== GLOBE (CesiumJS", "// ===== SELECTION (")
s = s[:si] + ix[gi:gj] + s[sj:]

tex_ix = re.search(r'(<script type="application/json" id="map-textures">)(.*?)(</script>)', ix, re.S)
m = re.search(r'(<script type="application/json" id="map-textures">)(.*?)(</script>)', s, re.S)
s = s[:m.start(2)] + tex_ix.group(2) + s[m.end(2):]

# iso3 per catalog site (backend/data/catalog_sites.json) so the browser can apply the same income bonus
CAT = {c["id"]: c["iso3"] for c in json.load(open(f"{backend}/data/catalog_sites.json", encoding="utf-8"))}
m = re.search(r'(<script type="application/json" id="analog-db">)(.*?)(</script>)', s, re.S)
db = json.loads(m.group(2))
for site in db:
    site.setdefault("iso3", CAT[site["id"]])
s = s[:m.start(2)] + "\n" + js(db) + "\n" + s[m.end(2):]

# ---------------------------------------------------------------- 2. priority data + offline snapshot blocks
priority_db = {
    "cfg": {"min_si": PR["min_si_for_bonus"], "income_bonus": PR["income_bonus"], "income_label": PR["income_label"],
            "novelty": PR["novelty"], "access": PR["access"], "cluster": PR["cluster"], "selection": PR["selection"]},
    "income": {r["iso3"]: r["income"] for r in INC},
    "country": {r["iso3"]: r["name"] for r in INC},
    "campaigns": [{"name": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"])} for r in CAMP],
    "anchors": {t: [e["site"] for e in v] for t, v in AN["anchors"].items()},
}
rep('<script type="module">',
    '<!-- ===== PRIORITY DATA (World Bank income groups, 41 analog field campaigns, frozen anchors; mirrors backend) ===== -->\n'
    '<script type="application/json" id="priority-db">\n' + js(priority_db) + "\n</script>\n"
    '<!-- ===== OFFLINE DISCOVERIES (backend `export-offline --embed`; used when the API is unreachable) ===== -->\n'
    '<script type="application/json" id="offline-results">\n{}\n</script>\n<script type="module">')

rep("const CITE_BY_ID = Object.fromEntries(CITATIONS.map((c) => [c.id, c]));", """const CITE_BY_ID = Object.fromEntries(CITATIONS.map((c) => [c.id, c]));

// ===== PRIORITY (mirror of backend priority.py + pipeline.add_novelty; Global South = priority, never a filter) =====
const PRIORITY = JSON.parse($('#priority-db').textContent);
let OFFLINE_RESULTS = {};
try { OFFLINE_RESULTS = JSON.parse($('#offline-results').textContent); } catch (e) { OFFLINE_RESULTS = {}; }
/** Great-circle distance in km. @returns {number} */
function haversineKm(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180, a = Math.sin((lat2 - lat1) * r / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin((lon2 - lon1) * r / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(Math.min(1, a)));
}
/** Income + novelty bonus for a catalog site (same rules as the backend). @param {object} site @param {number} si @returns {object} */
function priorityFor(site, si) {
  const cfg = PRIORITY.cfg, group = PRIORITY.income[site.iso3] || 'NA';
  let near = null, km = Infinity;
  for (const c of PRIORITY.campaigns) { const d = haversineKm(site.lat, site.lon, c.lat, c.lon); if (d < km) { km = d; near = c; } }
  const eligible = si >= cfg.min_si;
  const incomeBonus = eligible ? (cfg.income_bonus[group] || 0) : 0;
  const noveltyBonus = eligible ? cfg.novelty.max_bonus * Math.min(1, Math.max(0, km / cfg.novelty.full_novelty_km)) : 0;
  return { group, incomeBonus, noveltyBonus, accessBonus: 0, campaign: near && near.name, campaignKm: km,
    opportunity: si + incomeBonus + noveltyBonus, eligible };
}""")

# ---------------------------------------------------------------- 3. engine -> priority + discoveries
rep("""      entries: msg.results.map((r) => ({ ...r, site: SITE_BY_ID[r.id] })),
    };""", """      entries: msg.results.map((r) => ({ ...r, site: SITE_BY_ID[r.id], priority: priorityFor(SITE_BY_ID[r.id], r.si) })),
    };""")
rep("""    App.ui.completeRun(workerMs);
  },""", """    App.ui.completeRun(workerMs);
    App.discover.fetch(region);
  },""")

# ---------------------------------------------------------------- 4. cards: SI next to opportunity + badges
rep("""      ${diag}
      <p class="rationale">${text}</p>""", """      ${diag}
      ${App.ui.priorityLine(en.si, en.priority || priorityFor(s, en.si), { anchor: (PRIORITY.anchors[App.state.selections[region.planet]?.presetId] || []).includes(s.id) })}
      <p class="rationale">${text}</p>""")
rep("""    $('#results-count').textContent = res ? `${res.entries.length} of ${SITES.length} sites` : '';""",
    """    $('#results-count').textContent = res ? `${res.entries.length} catalog sites · pure SI order` : '';""")
i, j = section(s, "  renderResults() {", "  /** Skeleton cards while the worker computes.")
block = s[i:j]
old = "    area.innerHTML = res.entries.map((en, i) => this.cardHTML(en, i, res.region)).join('');\n  },"
assert block.count(old) == 1
block = block.replace(old, """    area.innerHTML = this.fixedGapsHTML(res.region.planet)
      + `<h3 class="sec-h">${icon('i-check', 13)} Validation anchors <small>16 literature sites, ranked by pure SI</small></h3>`
      + res.entries.map((en, i) => this.cardHTML(en, i, res.region)).join('')
      + `<section id="discoveries" aria-live="polite">${App.discover.html()}</section>`;
  },
  /** Conditions Earth cannot reproduce: shown once above the results, never scored. @param {string} planet @returns {string} */
  fixedGapsHTML(planet) {
    if (planet === 'earth' || !BODY_CONSTANTS[planet]) return '';
    const b = BODY_CONSTANTS[planet], e = BODY_CONSTANTS.earth;
    return `<div class="fixed-gaps">${icon('i-warn', 12)} <b>Earth cannot reproduce</b> <i>(never scored)</i>:
      ${FIXED_GAPS.map((g) => `<span><b>${g.label.replace('Surface ', '').toLowerCase()}</b> ${fmt(b[g.key], g.dp)} <i>vs Earth</i> ${fmt(e[g.key], g.dp)} ${g.unit}</span>`).join('')}</div>`;
  },
  /** SI next to opportunity plus priority badges (same layout for anchors and discoveries). @returns {string} */
  priorityLine(si, pr, o = {}) {
    const cfg = PRIORITY.cfg, b = [];
    if (o.anchor) b.push(`<span class="bdg bdg-anchor" data-tip="Literature anchor for this target (backend/config/anchors.json, frozen before the first run)">literature anchor</span>`);
    if (pr.incomeBonus > 0) b.push(`<span class="bdg bdg-gs" data-tip="${esc(cfg.income_label[pr.group] || pr.group)} (World Bank). Bonus only when SI ≥ ${cfg.min_si}">Global South ${pr.group} +${fmt(pr.incomeBonus)}</span>`);
    if (pr.noveltyBonus > 0.05) b.push(`<span class="bdg bdg-nov" data-tip="Nearest past analog field campaign: ${esc(pr.campaign || '')} (${fmt(pr.campaignKm)} km)">novelty +${pr.noveltyBonus.toFixed(1)}</span>`);
    if (pr.accessBonus > 0.05) b.push(`<span class="bdg bdg-acc" data-tip="Travel time to the nearest city (Oxford MAP 2015)">access +${pr.accessBonus.toFixed(1)}</span>`);
    if (pr.hardAccess) b.push(`<span class="bdg bdg-warn" data-tip="More than 48 h to the nearest city: flagged, never removed">hard access</span>`);
    if (o.known) b.push(`<span class="bdg bdg-known" data-tip="Within ${cfg.novelty.known_nearby_km} km of a past campaign or catalog site: ${esc(o.known)}">known nearby</span>`);
    if (!pr.eligible) b.push(`<span class="bdg" data-tip="Priority bonuses only apply when SI ≥ ${cfg.min_si}">no bonus (SI &lt; ${cfg.min_si})</span>`);
    return `<div class="v2-scores"><span data-tip="Similarity index: pure physics, 0–100">SI <b>${fmt(si, 1)}</b></span><span data-tip="Opportunity = SI + bounded Global South, novelty and access bonuses (only when SI ≥ ${cfg.min_si})">opportunity <b>${fmt(pr.opportunity, 1)}</b></span>${b.join('')}</div>`;
  },""")
s = s[:i] + block + s[j:]
rep("""    $('#run-hint').textContent = has ? 'R · score 16 Earth analogs in a worker' : 'Select a region to begin';""",
    """    $('#run-hint').textContent = has ? 'R · 16 anchors locally + Earth-grid discoveries via the API' : 'Select a region to begin';""")

# ---------------------------------------------------------------- 5. discoveries module, markers, body switch
rep("// ===== FAVORITES (spec B) =====", """// ===== DISCOVERIES (Anchor & Discover: backend API, 4 s timeout, offline snapshot fallback) =====
App.discover = {
  state: { status: 'idle', source: null, items: [], note: '' },
  seq: 0,
  /** Ask the API for Earth-grid discoveries; fall back to the embedded snapshot; never block the local engine. @param {object} region @returns {Promise<void>} */
  async fetch(region) {
    const my = ++this.seq;
    const presetId = App.state.selections[region.planet]?.presetId || null;
    const profile = App.state.customWeights ? 'custom' : App.state.profile;
    if (region.planet === 'earth') { this.set({ status: 'n/a', items: [], note: 'Discoveries search Earth for a Moon or Mars target. Pick a Moon or Mars region.' }); return; }
    this.set({ status: 'loading', items: [], note: '' });
    if (CONFIG.API_BASE) {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), CONFIG.API_TIMEOUT_MS);
      try {
        const body = { profile: profile === 'custom' ? 'science' : profile, top: 12,
          weights: App.state.customWeights ? App.engine.familyWeights() : null,
          ...(presetId ? { target_id: presetId } : { features: { ...regionFeatures(region), planet: region.planet } }) };
        const r = await fetch(CONFIG.API_BASE.replace(/\\/$/, '') + '/find-analogs', { method: 'POST',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal });
        clearTimeout(timer);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const j = await r.json();
        if (my !== this.seq) return;
        this.set({ status: 'done', source: 'api', items: j.discoveries || [], mode: j.selection_mode,
          note: j.discovery_source === 'grid' ? `${fmt(j.cells_scored)} Earth grid cells scored by the API.` : 'The API answered but has no Earth grid loaded yet.' });
        return;
      } catch (e) { clearTimeout(timer); log('API unavailable, using the offline snapshot', e); }
    }
    if (my !== this.seq) return;
    const off = presetId && OFFLINE_RESULTS[`${presetId}|${profile}`];
    if (off) this.set({ status: 'done', source: 'offline', items: off.discoveries || [], mode: off.selection_mode,
      note: `Offline snapshot (${off.generated || 'build'}, ${fmt(off.cells_scored)} cells). The live API is not reachable.` });
    else this.set({ status: 'none', items: [], note: presetId ? 'The API is not reachable and there is no offline snapshot for this preset and profile yet.'
      : 'Custom regions need the live API (the Earth grid lives on the server).' });
  },
  set(st) { this.state = st; const el = $('#discoveries'); if (el) el.innerHTML = this.html(); },
  /** Section HTML. @returns {string} */
  html() {
    const st = this.state;
    const src = st.source === 'api' ? 'live API' : st.source === 'offline' ? 'offline snapshot' : '';
    const head = `<h3 class="sec-h">${icon('i-globe', 13)} New discoveries <small>${src}${st.mode ? ' · selection: ' + esc(st.mode) : ''}</small></h3>`;
    if (st.status === 'loading') return head + '<p class="hint">Querying the Earth grid…</p>';
    if (!st.items || !st.items.length) return head + `<p class="hint">${esc(st.note || 'Run a match on a Moon or Mars region.')}</p>`;
    return head + `<p class="hint">${esc(st.note)}</p>` + st.items.map((d, i) => this.cardHTML(d, i)).join('');
  },
  /** One discovery card. @param {object} d API record @param {number} i @returns {string} */
  cardHTML(d, i) {
    const ex = d.explanation || { strongest: [], breaks_on: [] };
    const famLabel = (f) => FAMILIES.find((x) => x.id === (f.family || f))?.label || f.family || f;
    const strong = (ex.strongest || []).map((f) => `${famLabel(f)}${f.score != null ? ' ' + fmt(f.score) + '%' : ''}`).join(' · ');
    const gaps = (ex.breaks_on || []).map((g) => {
      const F = FEATURE_BY_KEY[g.feature];
      if (!F) return esc(g.feature);
      const u = F.unit && !['idx', 'frac', 'pct'].includes(F.unit) ? ' ' + F.unit : '';
      return F.categorical ? `${F.label} (${esc(LANDFORM_LABEL[g.target] || g.target || '—')} vs ${esc(LANDFORM_LABEL[g.candidate] || g.candidate || 'unknown')})`
        : `${F.label} (${fmt(g.target, F.dp)} vs ${fmt(g.candidate, F.dp)}${u})`;
    }).join(' · ');
    const pr = { group: d.income_group, incomeBonus: d.income_bonus || 0, noveltyBonus: d.novelty_bonus || 0, accessBonus: d.access_bonus || 0,
      hardAccess: !!d.hard_access, campaign: d.nearest_campaign, campaignKm: d.campaign_km, opportunity: d.opportunity, eligible: d.si >= PRIORITY.cfg.min_si };
    const known = d.known_nearby ? `${d.known_site_km <= d.campaign_km ? d.nearest_known_site : d.nearest_campaign} (${fmt(Math.min(d.known_site_km, d.campaign_km))} km)` : null;
    const country = PRIORITY.country[d.iso3] || d.iso3 || 'Unassigned';
    const slot = d.slot === 'global_south_quota' ? 'Global South quota slot' : d.slot === 'pure_si' ? 'pure-SI slot' : 'opportunity order';
    return `<article class="card disc" style="margin-bottom:10px;--i:${i}">
      <div class="card-top"><span class="rank">${i + 1}</span>
        <div class="card-name"><b>${esc(country)} · ${fmtCoord(d.lon, d.lat)}</b>
          <span>${d.region_cells} cells within ${PRIORITY.cfg.cluster.radius_km} km · mean SI ${fmt(d.region_mean_si, 1)} · top ${fmt(Math.max(0, 100 - d.si_percentile), 2)} % of land · ${slot}</span></div>
        <div class="si-wrap si-plain" role="img" aria-label="Similarity index ${fmt(d.si)} percent"><span class="si-num">${fmt(d.si)}<small>%</small></span></div>
      </div>
      <p class="diag"><span class="diag-ok">Strongest:</span> ${esc(strong || '—')}${gaps ? `<br><span class="diag-gap">Breaks on:</span> ${gaps}` : ''}</p>
      ${App.ui.priorityLine(d.si, pr, { known })}
      <p class="hint">Access: ${d.access_minutes == null ? 'n/a' : fmt(d.access_minutes / 60, 1) + ' h to the nearest city'} · nearest past analog campaign: ${esc(d.nearest_campaign || '—')} (${fmt(d.campaign_km)} km)</p>
      <div class="card-actions"><button class="btn btn-sm btn-ghost" data-locate-pt="${d.lon},${d.lat}" data-tip="Fly the Earth globe to this candidate">${icon('i-pin', 13)} Locate</button></div>
    </article>`;
  },
  /** Fly to a discovery and mark all current discoveries. @returns {Promise<void>} */
  async locate(lon, lat) {
    if (App.state.body !== 'earth') await App.ui.switchBody('earth');
    App.globe.setMarkers('left', this.state.items.map((d) => [d.lon, d.lat]));
    App.globe.flyToBBox('left', { west: lon - 1.2, south: lat - 1.2, east: lon + 1.2, north: lat + 1.2 });
  },
};
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-locate-pt]');
  if (!b) return;
  const [lon, lat] = b.dataset.locatePt.split(',').map(Number);
  App.discover.locate(lon, lat);
});

// ===== FAVORITES (spec B) =====""")
rep("""  /** Set or clear a raster layer overlay on a pane.""", """  /** Discovery markers (Cesium; the 2D fallback only flies). @param {string} pane @param {Array<[number,number]>|null} pts @returns {void} */
  setMarkers(pane, pts) {
    if (this.mode !== 'cesium' || !this.viewers[pane]) return;
    const v = this.viewers[pane], C = window.Cesium;
    this.markerEntities = this.markerEntities || { left: [], right: [] };
    for (const e of this.markerEntities[pane]) v.entities.remove(e);
    this.markerEntities[pane] = [];
    for (const [lon, lat] of pts || []) {
      this.markerEntities[pane].push(v.entities.add({ position: C.Cartesian3.fromDegrees(lon, lat, 0),
        point: { pixelSize: 11, color: C.Color.fromCssColorString('#22d3ee'), outlineColor: C.Color.WHITE, outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY } }));
    }
  },

  /** Set or clear a raster layer overlay on a pane.""")
rep("""    await App.globe.setBody(body, { fly: true });""", """    if (body !== 'earth') App.globe.setMarkers('left', null);
    await App.globe.setBody(body, { fly: true });""")

# ---------------------------------------------------------------- 6. text + CSS
rep("""data-tip="Score this region against all 16 Earth analogs in a Web Worker (shortcut R)">""",
    """data-tip="Rank the 16 literature anchors locally and ask the API for new Earth-grid discoveries (shortcut R)">""")
rep("</style>", """/* ===== Anchor & Discover ===== */
.sec-h{display:flex;align-items:center;gap:6px;margin:14px 2px 8px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.sec-h small{text-transform:none;letter-spacing:0;color:var(--muted-2);font-weight:400}
.v2-scores{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:6px 0 2px;font-size:11px;color:var(--muted)}
.v2-scores b{color:var(--text);font-size:13px}
.bdg{display:inline-flex;align-items:center;padding:1px 7px;border-radius:999px;font-size:10.5px;border:1px solid var(--ring);color:var(--muted)}
.bdg-gs{border-color:#f59e0b;color:#fbbf24}.bdg-nov{border-color:#22d3ee;color:#67e8f9}.bdg-acc{border-color:#a3e635;color:#bef264}
.bdg-known{border-color:#94a3b8;color:#cbd5e1}.bdg-warn{border-color:#f87171;color:#fca5a5}.bdg-anchor{border-color:var(--accent);color:var(--accent)}
.fixed-gaps{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;padding:8px 10px;margin:4px 0 6px;border:1px dashed var(--ring);border-radius:10px;font-size:11px;color:var(--muted)}
.fixed-gaps i{color:var(--muted-2);font-style:normal}
.si-plain{width:52px;height:52px;position:relative;display:grid;place-items:center}
</style>""")

# ---------------------------------------------------------------- 7. text accuracy (FEATURES has 24 numeric + landform)
rep("a Web Worker normalizes a 23-feature vector", "a Web Worker normalizes a 25-feature vector")
rep("<b>22 numeric features + 1 landform class</b>", "<b>24 numeric features + 1 landform class</b>")
rep("olivine · pyroxene · plagioclase · evaporite/sulfate · Fe-oxide · clay</td>",
    "olivine · pyroxene · plagioclase · evaporite/sulfate · Fe-oxide · clay · carbonate</td>")

open(dst, "w", encoding="utf-8").write(s)
print("merged ->", dst, f"{len(s):,} chars")
