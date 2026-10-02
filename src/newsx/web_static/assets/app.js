/**
 * TrueNews (Antigravity NewsX) — Daily Verified News Application Logic
 * Pure Vanilla JavaScript · Fast · No Frameworks
 */

'use strict';

// ─── Global State ───
const state = {
  currentView: 'today',
  events: [],
  briefsCache: new Map(),
  activeEventId: null,
  sources: [],
  health: null,
  toastTimer: null,
};

// ─── Helpers ───
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

function escapeHtml(str = '') {
  return String(str).replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  }[char]));
}

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Request failed with status ${response.status}`);
  }
  return response.json();
}

function tierBadge(tierNum, showLabel = true) {
  const t = Number(tierNum) || 1;
  const labels = {
    1: 'Tier 1 · Corroborated',
    2: 'Tier 2 · Verified',
    3: 'Tier 3 · Contested',
    4: 'Tier 4 · Unverified',
    5: 'Tier 5 · Speculative',
  };
  return `<span class="tier-pill tier-${t}">${showLabel ? labels[t] || `Tier ${t}` : `T${t}`}</span>`;
}

function showToast(message) {
  const toast = $('#toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
}

// ─── Navigation ───
function navigateTo(viewName, eventId = null) {
  state.currentView = viewName;

  // Update hash without jump
  if (viewName === 'story' && eventId) {
    window.location.hash = `#story/${encodeURIComponent(eventId)}`;
  } else {
    window.location.hash = `#${viewName}`;
  }

  // Update active view DOM
  $$('.view').forEach((el) => el.classList.remove('active'));
  const targetView = $(`#view-${viewName}`);
  if (targetView) {
    targetView.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Update sidebar active link
  $$('.nav-link').forEach((el) => {
    if (el.dataset.view === viewName) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });

  // Close mobile sidebar if open
  closeSidebar();

  // If navigating to story view with an ID, load that story
  if (viewName === 'story') {
    const targetId = eventId || state.activeEventId || (state.events[0] && state.events[0].id);
    if (targetId && targetId !== state.activeEventId) {
      loadStory(targetId);
    }
  }
}

function toggleSidebar() {
  const sidebar = $('#sidebar');
  const overlay = $('#sidebar-overlay');
  const isOpen = sidebar.classList.toggle('open');
  overlay.classList.toggle('open', isOpen);
  $('#menu-button').setAttribute('aria-expanded', String(isOpen));
}

function closeSidebar() {
  const sidebar = $('#sidebar');
  const overlay = $('#sidebar-overlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
  const menuBtn = $('#menu-button');
  if (menuBtn) menuBtn.setAttribute('aria-expanded', 'false');
}

// ─── Initialization ───
document.addEventListener('DOMContentLoaded', () => {
  initApp();
  setupEventListeners();
});

function setupEventListeners() {
  $('#menu-button').addEventListener('click', toggleSidebar);

  // Hash change routing
  window.addEventListener('hashchange', handleHashChange);

  // Sidebar link clicks
  $$('.nav-link').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const view = link.dataset.view;
      if (view) navigateTo(view);
    });
  });
}

function handleHashChange() {
  const hash = window.location.hash.replace(/^#/, '');
  if (!hash) {
    navigateTo('today');
    return;
  }

  if (hash.startsWith('story/')) {
    const eventId = decodeURIComponent(hash.replace('story/', ''));
    navigateTo('story', eventId);
  } else if (['today', 'story', 'archive', 'sources', 'about', 'advanced'].includes(hash)) {
    navigateTo(hash);
  }
}

async function initApp() {
  try {
    // Format edition date
    const today = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const dateStr = today.toLocaleDateString('en-US', options);
    $('#current-edition-date').textContent = `${dateStr}`;

    // Fetch initial pipeline data
    const [health, events, sources] = await Promise.all([
      api('/api/health'),
      api('/api/events'),
      api('/api/sources'),
    ]);

    state.health = health;
    state.events = events.filter((e) => e.id !== 'all');
    state.sources = sources;

    // Update Header / Metrics
    $('#stat-events').textContent = state.events.length;
    $('#stat-articles').textContent = health.items || state.events.reduce((sum, e) => sum + (e.item_count || 0), 0);
    $('#stat-sources').textContent = sources.length;
    $('#nav-stories-count').textContent = state.events.length;
    $('#nav-sources-count').textContent = sources.length;
    $('#status-text').textContent = `${health.items || 0} articles · Zero paid APIs`;

    // Render Views
    await renderTodayNewsFeed();
    renderSourcesTable(sources);
    renderArchiveGrid(state.events);
    renderAdvancedLedger();

    // Populate story dropdown in detail view
    const dropdown = $('#story-select-dropdown');
    dropdown.innerHTML = state.events
      .map((e) => `<option value="${escapeHtml(e.id)}">${escapeHtml(e.label)}</option>`)
      .join('');

    // Handle initial route
    if (window.location.hash) {
      handleHashChange();
    } else if (state.events.length > 0) {
      state.activeEventId = state.events[0].id;
    }
  } catch (error) {
    console.error('Failed to initialize TrueNews app:', error);
    renderErrorState(error);
  }
}

// ─── VIEW 1: TODAY'S VERIFIED NEWS FEED ───
async function renderTodayNewsFeed() {
  const feed = $('#stories-feed');
  if (!state.events.length) {
    feed.innerHTML = `
      <div class="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M19 20H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1m2 13a2 2 0 0 1-2-2V7m2 13a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/></svg>
        <h3>No verified stories for today yet</h3>
        <p>Run the local ingestion pipeline to extract atomic facts and build today's verified edition.</p>
      </div>
    `;
    return;
  }

  $('#feed-count-sub').textContent = `Showing ${state.events.length} verified ${state.events.length === 1 ? 'story' : 'stories'}`;

  // Fetch briefs for all events in parallel
  const briefPromises = state.events.map(async (event) => {
    try {
      if (!state.briefsCache.has(event.id)) {
        const brief = await api(`/api/events/${encodeURIComponent(event.id)}/brief`);
        state.briefsCache.set(event.id, brief);
      }
      return { event, brief: state.briefsCache.get(event.id) };
    } catch (e) {
      return { event, brief: null };
    }
  });

  const storyItems = await Promise.all(briefPromises);

  feed.innerHTML = storyItems
    .map(({ event, brief }) => {
      if (!brief) {
        return `
          <article class="story-card">
            <div class="story-card-top">
              <span class="story-category">General</span>
              ${tierBadge(1)}
            </div>
            <a href="#story/${encodeURIComponent(event.id)}" class="story-headline-link" onclick="navigateTo('story', '${escapeHtml(event.id)}'); return false;">
              ${escapeHtml(event.label)}
            </a>
            <p class="story-summary">Verified event containing ${event.claim_count || 0} claims audited from ${event.item_count || 0} independent articles.</p>
            <div class="story-card-footer">
              <span class="story-source-info">${event.item_count || 1} sources</span>
              <button class="btn-read-story" onclick="navigateTo('story', '${escapeHtml(event.id)}')">Read Story Brief →</button>
            </div>
          </article>
        `;
      }

      // Determine category from event id/label
      let category = 'General';
      const labelLower = (brief.neutral_headline + ' ' + event.id).toLowerCase();
      if (labelLower.includes('rate') || labelLower.includes('rbi') || labelLower.includes('gdp') || labelLower.includes('market') || labelLower.includes('sensex')) {
        category = 'Economy & Finance';
      } else if (labelLower.includes('bridge') || labelLower.includes('infrastructure') || labelLower.includes('collapse') || labelLower.includes('train')) {
        category = 'Public Infrastructure';
      } else if (labelLower.includes('climate') || labelLower.includes('summit') || labelLower.includes('emission') || labelLower.includes('environment')) {
        category = 'Environment & Climate';
      } else if (labelLower.includes('border') || labelLower.includes('treaty') || labelLower.includes('diplomacy') || labelLower.includes('talks')) {
        category = 'Geopolitics';
      }

      // Best tier among core facts
      const primaryTier = brief.core_facts && brief.core_facts.length > 0 ? brief.core_facts[0].tier : 1;
      const totalOrigins = brief.core_facts
        ? Math.max(...brief.core_facts.map((f) => f.independent_source_count || 1), event.item_count || 1)
        : event.item_count || 1;

      // First 2 fact previews
      const factPreviews = (brief.core_facts || []).slice(0, 2);
      const disputeCount = (brief.disputed_points || []).length || event.dispute_count || 0;

      // Summary text from first fact or fallback
      const summaryText = brief.core_facts && brief.core_facts.length > 0
        ? (brief.core_facts[0].text || brief.core_facts[0].original_text || '')
        : 'Atomic fact base extracted and corroborated across independent origin records.';

      return `
        <article class="story-card" data-event-id="${escapeHtml(event.id)}">
          <div class="story-card-top">
            <span class="story-category">${escapeHtml(category)}</span>
            ${tierBadge(primaryTier)}
            ${brief.diversity_compliant ? '<span class="diversity-badge diversity-pass">✓ Diverse Origins</span>' : ''}
            ${disputeCount > 0 ? `<span class="story-dispute-alert">⚠️ ${disputeCount} ${disputeCount === 1 ? 'Dispute' : 'Disputes'} Flagged</span>` : ''}
          </div>

          <a href="#story/${encodeURIComponent(event.id)}" class="story-headline-link" onclick="navigateTo('story', '${escapeHtml(event.id)}'); return false;">
            ${escapeHtml(brief.neutral_headline || event.label)}
          </a>

          <p class="story-summary">${escapeHtml(summaryText)}</p>

          ${factPreviews.length > 0 ? `
            <div class="story-fact-previews">
              ${factPreviews.map((f) => `
                <div class="fact-preview-item">
                  <span class="fact-preview-bullet">•</span>
                  <span>${escapeHtml(f.text || f.original_text || '')}</span>
                </div>
              `).join('')}
            </div>
          ` : ''}

          <div class="story-card-footer">
            <div class="story-source-info">
              <span class="story-sources-count">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
                ${totalOrigins} independent ${totalOrigins === 1 ? 'origin' : 'origins'}
              </span>
              <span>·</span>
              <span>${event.item_count || 1} articles audited</span>
            </div>

            <button class="btn-read-story" onclick="navigateTo('story', '${escapeHtml(event.id)}')">
              Read Story Brief →
            </button>
          </div>
        </article>
      `;
    })
    .join('');
}

// ─── VIEW 2: STORY DETAIL ───
async function loadStory(eventId) {
  if (!eventId) return;
  state.activeEventId = eventId;

  // Sync dropdown
  const dropdown = $('#story-select-dropdown');
  if (dropdown) dropdown.value = eventId;

  // Update Export Links
  $('#export-md-btn').href = `/api/exports/${encodeURIComponent(eventId)}.md`;
  $('#export-html-btn').href = `/api/exports/${encodeURIComponent(eventId)}.html`;

  try {
    // Show loading indicator
    $('#story-headline').textContent = 'Loading verified story brief…';
    $('#story-facts').innerHTML = '<div class="spinner"></div>';

    // Fetch brief and claims in parallel
    let brief = state.briefsCache.get(eventId);
    const [fetchedBrief, claims] = await Promise.all([
      brief ? Promise.resolve(brief) : api(`/api/events/${encodeURIComponent(eventId)}/brief`),
      api(`/api/events/${encodeURIComponent(eventId)}/claims`).catch(() => []),
    ]);

    brief = fetchedBrief;
    state.briefsCache.set(eventId, brief);

    // Populate Header
    $('#story-event-id').textContent = eventId.toUpperCase();
    $('#story-headline').textContent = brief.neutral_headline;

    // Diversity Badge
    const diversityEl = $('#story-diversity-badge');
    if (brief.diversity_compliant) {
      diversityEl.className = 'diversity-badge diversity-pass';
      diversityEl.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> <span>Diversity Compliant</span>`;
    } else {
      diversityEl.className = 'diversity-badge diversity-warn';
      diversityEl.innerHTML = `<span>Diversity Notice</span>`;
    }

    // Top tier & origin count
    const topTier = brief.core_facts && brief.core_facts.length > 0 ? brief.core_facts[0].tier : 1;
    $('#story-tier-pill').className = `tier-pill tier-${topTier}`;
    $('#story-tier-pill').textContent = `Tier ${topTier} · ${topTier <= 2 ? 'Corroborated' : 'Verified'}`;

    const maxOrigins = brief.core_facts && brief.core_facts.length > 0
      ? Math.max(...brief.core_facts.map((f) => f.independent_source_count || 1))
      : 1;
    $('#story-origins-text').textContent = `${maxOrigins} independent ${maxOrigins === 1 ? 'origin' : 'origins'}`;

    // Lead paragraph
    $('#story-lead').textContent = brief.core_facts && brief.core_facts.length > 0
      ? brief.core_facts[0].text || brief.core_facts[0].original_text || ''
      : '';

    // Render Facts
    renderStoryFacts(brief.core_facts || []);

    // Render Timeline
    renderStoryTimeline(brief.timeline || []);

    // Render Neutralization / Diff Cards
    renderStoryDiffs(claims);

    // Render Disputes
    renderStoryDisputes(brief.disputed_points || []);

    // Render Sources for this story
    renderStorySources(brief.source_ledger || [], claims);

  } catch (error) {
    console.error(`Failed to load story ${eventId}:`, error);
    $('#story-headline').textContent = 'Story brief could not be loaded';
    $('#story-facts').innerHTML = `<p class="empty-state">Error: ${escapeHtml(error.message)}</p>`;
  }
}

function renderStoryFacts(facts) {
  const container = $('#story-facts');
  if (!facts.length) {
    container.innerHTML = `<p class="empty-state">No individual core facts recorded.</p>`;
    return;
  }

  container.innerHTML = facts
    .map((fact) => {
      const tierNum = Number(fact.tier) || 1;
      const cardClass = tierNum === 3 ? 'tier-3-card' : tierNum >= 4 ? 'tier-4-card' : '';
      const sources = fact.supporting_source_ids || [];

      return `
        <article class="fact-item-card ${cardClass}">
          <div class="fact-item-header">
            ${tierBadge(tierNum)}
            <span class="origins-tag">
              ${fact.independent_source_count || 1} independent ${fact.independent_source_count === 1 ? 'origin' : 'origins'}
            </span>
          </div>
          <p class="fact-item-text">${escapeHtml(fact.text || fact.original_text || 'No statement available.')}</p>
          <div class="fact-item-footer">
            ${fact.attribution_speaker ? `
              <span class="fact-item-speaker">Attributed: ${escapeHtml(fact.attribution_speaker)}</span>
            ` : ''}
            ${sources.length > 0 ? `
              <div class="fact-sources-inline">
                ${sources.map((s) => `<span class="source-tag">${escapeHtml(s)}</span>`).join('')}
              </div>
            ` : ''}
          </div>
        </article>
      `;
    })
    .join('');
}

function renderStoryTimeline(timeline) {
  const container = $('#story-timeline');
  if (!timeline.length) {
    container.innerHTML = `<li class="story-timeline-item"><p class="story-timeline-text">No chronological timeline entries recorded for this event.</p></li>`;
    return;
  }

  container.innerHTML = timeline
    .map((item) => {
      if (typeof item === 'string') {
        return `
          <li class="story-timeline-item">
            <span class="story-timeline-dot"></span>
            <p class="story-timeline-text">${escapeHtml(item)}</p>
          </li>
        `;
      }

      return `
        <li class="story-timeline-item">
          <span class="story-timeline-dot"></span>
          <div class="story-timeline-time">${escapeHtml(item.timestamp_str || 'SEQUENCED')}</div>
          <p class="story-timeline-text">${escapeHtml(item.description)}</p>
          <div class="story-timeline-meta">
            ${tierBadge(item.tier || 1, false)}
            <span>${(item.source_ids || []).length} source anchors</span>
          </div>
        </li>
      `;
    })
    .join('');
}

function renderStoryDiffs(claims) {
  const container = $('#story-diffs');
  // Filter claims that have both original and neutralized wording
  const diffClaims = claims.filter(
    (c) => c.original_wording && c.neutralized_wording && c.original_wording !== c.neutralized_wording
  );

  const displayClaims = diffClaims.length > 0 ? diffClaims : claims.slice(0, 4);

  if (!displayClaims.length) {
    container.innerHTML = `<p class="empty-state">No claim-level provenance diffs available.</p>`;
    return;
  }

  container.innerHTML = displayClaims
    .map((claim) => {
      const orig = claim.original_wording || claim.what || 'Original passage text';
      const neut = claim.neutralized_wording || claim.what || orig;

      return `
        <div class="diff-card">
          <div class="diff-card-header">
            <code>${escapeHtml(claim.id || 'CLM')}</code>
            <span class="muted">${claim.attribution_speaker ? `Speaker: ${escapeHtml(claim.attribution_speaker)}` : 'Audited reporting'}</span>
          </div>
          <div class="diff-card-body">
            <div class="diff-col diff-col-original">
              <span class="diff-label diff-label-red">ORIGINAL REPORTING</span>
              <p class="diff-content">${escapeHtml(orig)}</p>
              <div class="diff-source-span">Source span: ${escapeHtml(claim.passage_id || claim.item_id || 'paragraph citation')}</div>
            </div>
            <div class="diff-col diff-col-neutral">
              <span class="diff-label diff-label-teal">NEUTRALIZED TRUENEWS CLAIM</span>
              <p class="diff-content">${escapeHtml(neut)}</p>
              <div class="diff-source-span" style="color: var(--teal-600);">✓ Bias &amp; loaded language stripped</div>
            </div>
          </div>
        </div>
      `;
    })
    .join('');
}

function renderStoryDisputes(disputedPoints) {
  const section = $('#story-disputes-section');
  const container = $('#story-disputes');

  if (!disputedPoints || disputedPoints.length === 0) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  container.innerHTML = disputedPoints
    .map((point) => {
      const isString = typeof point === 'string';
      const topic = isString ? 'Contradiction Flagged' : point.topic || 'Disputed point';
      const explanation = isString ? point : point.explanation || 'Differing claims between newsrooms.';

      return `
        <article class="dispute-card">
          <div class="dispute-card-header">
            <span class="dispute-topic">⚠️ ${escapeHtml(topic)}</span>
            <span class="tier-pill tier-3">Contested</span>
          </div>
          <p class="dispute-explanation">${escapeHtml(explanation)}</p>
        </article>
      `;
    })
    .join('');
}

function renderStorySources(sourceLedger, claims) {
  const container = $('#story-sources-grid');

  if (sourceLedger && sourceLedger.length > 0) {
    container.innerHTML = sourceLedger
      .map((s) => `
        <div class="story-source-card">
          <div class="story-source-name">${escapeHtml(s.name || s.source_id)}</div>
          <div class="story-source-meta">
            <span>Tier ${s.tier || 1}</span> · 
            <span>${s.independent_origin ? 'Independent Wire/Origin' : 'Secondary reporting'}</span>
          </div>
        </div>
      `)
      .join('');
    return;
  }

  // Fallback: extract source IDs from claims or registered sources
  const sourceIds = new Set();
  claims.forEach((c) => {
    if (c.source_id) sourceIds.add(c.source_id);
  });

  const matchingSources = state.sources.filter((s) => sourceIds.has(s.id));
  const displaySources = matchingSources.length > 0 ? matchingSources : state.sources.slice(0, 4);

  container.innerHTML = displaySources
    .map((s) => `
      <div class="story-source-card">
        <div class="story-source-name">${escapeHtml(s.name)}</div>
        <div class="story-source-meta">
          <span>Tier ${escapeHtml(s.tier)}</span> · <span>${escapeHtml(s.region)}</span>
        </div>
      </div>
    `)
    .join('');
}

// ─── VIEW 3: ARCHIVE ───
function renderArchiveGrid(events) {
  const container = $('#archive-grid');
  if (!events.length) {
    container.innerHTML = `<p class="empty-state">No past events recorded in the archive.</p>`;
    return;
  }

  container.innerHTML = events
    .map((event) => `
      <article class="archive-card">
        <div class="archive-card-header">
          <code class="meta-tag">${escapeHtml(event.id.toUpperCase())}</code>
          ${tierBadge(1)}
        </div>
        <h3>${escapeHtml(event.label)}</h3>
        <div class="archive-card-stats">
          <span>${event.claim_count || 0} claims</span>
          <span>·</span>
          <span>${event.item_count || 0} sources</span>
          <span>·</span>
          <span>${event.dispute_count ? `${event.dispute_count} disputes` : 'Zero disputes'}</span>
        </div>
        <button class="btn btn-ghost btn-sm archive-card-btn" onclick="navigateTo('story', '${escapeHtml(event.id)}')">
          View Story Brief →
        </button>
      </article>
    `)
    .join('');
}

function filterArchive(keyword) {
  const term = keyword.trim().toLowerCase();
  const filtered = state.events.filter(
    (e) => e.label.toLowerCase().includes(term) || e.id.toLowerCase().includes(term)
  );
  renderArchiveGrid(filtered);
}

// ─── VIEW 4: SOURCES REGISTRY ───
function renderSourcesTable(sources) {
  const tbody = $('#sources-table-body');
  if (!sources || !sources.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="muted">No sources registered.</td></tr>`;
    return;
  }

  tbody.innerHTML = sources
    .map((s) => `
      <tr>
        <td><strong>${escapeHtml(s.name)}</strong></td>
        <td><code>${escapeHtml(s.id)}</code></td>
        <td><span class="source-tag">${escapeHtml(s.tier.toUpperCase())}</span></td>
        <td>${escapeHtml(s.region)}</td>
        <td>${escapeHtml(s.ownership)}</td>
        <td><span class="diversity-badge diversity-pass">${escapeHtml(s.status)}</span></td>
      </tr>
    `)
    .join('');
}

// ─── VIEW 6: ADVANCED LEDGER & AUDIT ───
async function renderAdvancedLedger() {
  try {
    const entries = await api('/api/ledger');
    $('#advanced-ledger-count').textContent = `${entries.length} canonical nodes`;
    const tbody = $('#advanced-ledger-body');

    if (!entries.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">No ledger entries generated yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = entries
      .slice(0, 50)
      .map((entry) => `
        <tr>
          <td><code>${escapeHtml(entry.id)}</code></td>
          <td>${escapeHtml(entry.canonical_claim)}</td>
          <td>${tierBadge(entry.confidence_tier || 1, false)}</td>
          <td>${entry.independent_origin_count || 1}</td>
          <td>${(entry.contradictions || []).length ? `<span class="tier-pill tier-3">${entry.contradictions.length} flagged</span>` : '<span class="muted">—</span>'}</td>
        </tr>
      `)
      .join('');
  } catch (e) {
    console.warn('Could not load advanced ledger:', e);
  }
}

function renderErrorState(error) {
  const feed = $('#stories-feed');
  if (feed) {
    feed.innerHTML = `
      <div class="empty-state">
        <h3>Could not connect to TrueNews Local Engine</h3>
        <p>${escapeHtml(error.message)}</p>
        <p style="margin-top: 12px; font-size: 0.8rem;">Run <code>make web</code> in your terminal to start the local server.</p>
      </div>
    `;
  }
}
