const $ = (selector) => document.querySelector(selector);
const state = { events: [], currentEvent: null, brief: null };

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || `Request failed: ${response.status}`);
  return response.json();
}
function escapeHtml(value = '') { return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char])); }
function tier(tier) { return `<span class="tier tier-${tier}">TIER ${tier}</span>`; }
function empty() { return $('#empty-template').content.cloneNode(true); }

function renderMetrics(health) {
  $('#metrics').innerHTML = [
    [health.events, 'active events'], [health.items, 'ingested articles'], [health.ledger_entries, 'canonical ledger nodes'], [health.sources, 'registered sources'],
  ].map(([number, label]) => `<article class="metric"><b>${number}</b><span>${label}</span></article>`).join('');
  $('#status-text').textContent = `${health.items} items indexed · ${health.zero_cost_mode ? 'zero cost' : 'metered'}`;
  $('#ops-status').textContent = `${health.status.toUpperCase()} · ${health.events} canonical events · ${health.ledger_entries} ledger nodes · ${health.sources} registered sources`;
}
function renderBrief(brief) {
  state.brief = brief;
  $('#brief-title').textContent = brief.neutral_headline;
  const badge = $('#diversity-badge');
  badge.textContent = brief.diversity_compliant ? 'DIVERSITY COMPLIANT' : 'DIVERSITY NOTICE';
  badge.classList.toggle('warning', !brief.diversity_compliant);
  const facts = $('#brief-facts'); facts.innerHTML = '';
  if (!brief.core_facts.length) facts.append(empty());
  brief.core_facts.forEach(fact => facts.insertAdjacentHTML('beforeend', `<article class="fact"><p>${escapeHtml(fact.text || fact.original_text || 'No rendered text')}</p><footer>${tier(fact.tier)} · ${fact.independent_source_count} independent ${fact.independent_source_count === 1 ? 'origin' : 'origins'}${fact.attribution_speaker ? ` · attributed to ${escapeHtml(fact.attribution_speaker)}` : ''}</footer></article>`));
  const timeline = $('#timeline'); timeline.innerHTML = '';
  if (!brief.timeline.length) timeline.append(empty());
  brief.timeline.forEach(item => { if (typeof item === 'string') timeline.insertAdjacentHTML('beforeend', `<li><p>${escapeHtml(item)}</p></li>`); else timeline.insertAdjacentHTML('beforeend', `<li><div class="time">${escapeHtml(item.timestamp_str || 'UNSTAMPED')}</div><p>${escapeHtml(item.description)}</p><small>${tier(item.tier)} · ${item.source_ids.length} source anchors</small></li>`); });
  const disputes = $('#dispute-list'); disputes.innerHTML = '';
  if (!brief.disputed_points.length) disputes.append(empty());
  brief.disputed_points.forEach(item => { const isText = typeof item === 'string'; disputes.insertAdjacentHTML('beforeend', `<article class="dispute"><h3>${escapeHtml(isText ? 'Unresolved point' : item.topic)}</h3><p>${escapeHtml(isText ? item : item.explanation)}</p></article>`); });
}
function renderLedger(entries) {
  $('#ledger-summary').textContent = `${entries.length} canonical nodes`;
  const body = $('#ledger-rows'); body.innerHTML = '';
  if (!entries.length) body.append(empty());
  entries.forEach(entry => body.insertAdjacentHTML('beforeend', `<tr><td>${escapeHtml(entry.canonical_claim)}</td><td>${tier(entry.confidence_tier)}</td><td>${entry.independent_origin_count}</td><td>${entry.contradictions.length ? `<span class="tier tier-4">${entry.contradictions.length} flagged</span>` : '<span class="muted">None</span>'}</td></tr>`));
}
function renderClaims(claims) {
  const container = $('#claims'); container.innerHTML = '';
  if (!claims.length) container.append(empty());
  claims.forEach(claim => container.insertAdjacentHTML('beforeend', `<article class="claim"><header><span>${escapeHtml(claim.id)}</span><span>${escapeHtml(claim.claim_type)}</span></header><h3>${escapeHtml(claim.what || claim.neutralized_wording || claim.original_wording)}</h3><p><b>Source span:</b> ${escapeHtml(claim.passage_id)}${claim.attribution_speaker ? ` · ${escapeHtml(claim.attribution_speaker)}` : ''}</p><div class="diff"><div><label>ORIGINAL</label>${escapeHtml(claim.original_wording)}</div><div><label>NEUTRALIZED</label>${escapeHtml(claim.neutralized_wording || claim.original_wording)}</div></div></article>`));
}
function renderSources(sources) {
  $('#source-count').textContent = `${sources.length} monitored origins`;
  $('#source-rows').innerHTML = sources.map(source => `<tr><td>${escapeHtml(source.name)}<br><span class="muted">${escapeHtml(source.id)}</span></td><td>${escapeHtml(source.tier)}</td><td>${escapeHtml(source.region)}</td><td>${escapeHtml(source.ownership)}</td><td>${escapeHtml(source.status)}</td></tr>`).join('');
}
async function loadEvent(id) {
  state.currentEvent = id;
  $('#event-select').value = id;
  $('#export-md').href = `/api/exports/${encodeURIComponent(id)}.md`;
  $('#export-html').href = `/api/exports/${encodeURIComponent(id)}.html`;
  const [brief, ledger, claims] = await Promise.all([api(`/api/events/${encodeURIComponent(id)}/brief`), api(`/api/ledger?event=${encodeURIComponent(id)}`), api(`/api/events/${encodeURIComponent(id)}/claims`)]);
  renderBrief(brief); renderLedger(ledger); renderClaims(claims);
}
async function boot() {
  try {
    const [health, events, sources] = await Promise.all([api('/api/health'), api('/api/events'), api('/api/sources')]);
    state.events = events.filter(event => event.id !== 'all');
    renderMetrics(health); renderSources(sources);
    const select = $('#event-select');
    select.innerHTML = state.events.map(event => `<option value="${escapeHtml(event.id)}">${escapeHtml(event.label)} · ${event.claim_count} claims</option>`).join('');
    if (!state.events.length) throw new Error('No processed events are available. Run the pipeline first.');
    select.addEventListener('change', event => loadEvent(event.target.value).catch(showError));
    await loadEvent(state.events[0].id);
  } catch (error) { showError(error); }
}
function showError(error) { $('#brief-title').textContent = 'The editorial workspace could not load'; $('#brief-facts').innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`; console.error(error); }
$('#menu-button').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
$('#refresh-button').addEventListener('click', () => window.location.reload());
boot();
