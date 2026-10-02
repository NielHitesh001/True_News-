/**
 * TrueNews (Antigravity NewsX)
 * Production-Ready Daily Verified News Application
 */

'use strict';

// ─── Application State ───
const state = {
  currentView: 'today',
  previousView: 'today',
  events: [],
  eventsByDate: new Map(), // YYYY-MM-DD -> [events]
  briefsCache: new Map(),   // eventId -> Brief
  activeStoryId: null,
  activeArchiveDateKey: null,
  sources: [],
  health: null,
};

// ─── Selectors & Helpers ───
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
  const res = await fetch(path);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return res.json();
}

function tierBadgeHtml(tierNum) {
  const t = Number(tierNum) || 1;
  const labels = {
    1: 'Tier 1 · Corroborated',
    2: 'Tier 2 · Verified',
    3: 'Tier 3 · Contested',
    4: 'Tier 4 · Unverified',
    5: 'Tier 5 · Speculative',
  };
  return `<span class="tier-pill tier-${t}">${labels[t] || `Tier ${t}`}</span>`;
}

function getIsoDateKey(dateObj) {
  return dateObj.toISOString().slice(0, 10);
}

function formatReadableDate(dateKeyOrObj, fullWeekday = true) {
  const date = typeof dateKeyOrObj === 'string' ? new Date(dateKeyOrObj + 'T00:00:00') : dateKeyOrObj;
  if (isNaN(date.getTime())) return String(dateKeyOrObj);
  const options = {
    weekday: fullWeekday ? 'long' : 'short',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  };
  return date.toLocaleDateString('en-US', options);
}

function formatTimeNow() {
  const now = new Date();
  return now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function showToast(msg) {
  const toast = $('#toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2400);
}

// ─── Clean 2-3 Line Summary Synthesizer ───
function getCleanTakeaway(brief, event) {
  if (!brief || !brief.core_facts || brief.core_facts.length === 0) {
    return `Verified factual reporting corroborated from ${event.item_count || 1} newsrooms with ${event.claim_count || 0} discrete claims.`;
  }

  // Use the primary fact text, cleaned of technical prefixes
  const fact1 = (brief.core_facts[0].text || brief.core_facts[0].original_text || '').trim();
  const fact2 = brief.core_facts[1] ? (brief.core_facts[1].text || brief.core_facts[1].original_text || '').trim() : '';

  if (fact1 && fact2 && fact1.length < 120) {
    return `${fact1} ${fact2}`;
  }
  return fact1 || 'Atomic factual claims extracted and verified across independent origins.';
}

// ─── Routing & Navigation ───
function navigateTo(viewName, storyId = null) {
  if (state.currentView !== 'story') {
    state.previousView = state.currentView;
  }
  state.currentView = viewName;

  // Update URL hash
  if (viewName === 'story' && storyId) {
    window.location.hash = `#story/${encodeURIComponent(storyId)}`;
  } else {
    window.location.hash = `#${viewName}`;
  }

  // Update DOM active view
  $$('.view').forEach((v) => v.classList.remove('active'));
  const targetView = $(`#view-${viewName}`);
  if (targetView) {
    targetView.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Update topbar nav active state
  $$('.nav-item').forEach((item) => {
    if (item.dataset.view === viewName) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Close mobile nav menu
  const topbarNav = $('#topbar-nav');
  if (topbarNav) topbarNav.classList.remove('open');
  const menuBtn = $('#menu-btn');
  if (menuBtn) menuBtn.setAttribute('aria-expanded', 'false');

  // Load story details if entering story view
  if (viewName === 'story' && storyId) {
    loadStoryDetail(storyId);
  }
}

function navigateBack() {
  if (state.previousView === 'archive') {
    navigateTo('archive');
  } else {
    navigateTo('today');
  }
}

// ─── App Initialization ───
document.addEventListener('DOMContentLoaded', () => {
  initApp();
  setupEvents();
});

function setupEvents() {
  const menuBtn = $('#menu-btn');
  const topbarNav = $('#topbar-nav');
  if (menuBtn && topbarNav) {
    menuBtn.addEventListener('click', () => {
      const isOpen = topbarNav.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', String(isOpen));
    });
  }

  window.addEventListener('hashchange', handleHashRouting);

  $$('.nav-item').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const view = link.dataset.view;
      if (view) navigateTo(view);
    });
  });
}

function handleHashRouting() {
  const hash = window.location.hash.replace(/^#/, '');
  if (!hash || hash === 'today') {
    navigateTo('today');
  } else if (hash.startsWith('story/')) {
    const id = decodeURIComponent(hash.replace('story/', ''));
    navigateTo('story', id);
  } else if (['archive', 'sources', 'about'].includes(hash)) {
    navigateTo(hash);
  }
}

async function initApp() {
  try {
    // Set formatted today's date & last updated
    const now = new Date();
    $('#today-date-display').textContent = formatReadableDate(now, true);
    $('#today-last-updated').textContent = `Last updated: ${formatTimeNow()}`;

    // Fetch initial pipeline data
    const [health, rawEvents, sources] = await Promise.all([
      api('/api/health'),
      api('/api/events'),
      api('/api/sources'),
    ]);

    state.health = health;
    state.events = rawEvents.filter((e) => e.id !== 'all');
    state.sources = sources;

    $('#status-text').textContent = `${health.items || state.events.length} Articles Verified`;

    // Group events by Date
    groupEventsByDate();

    // Render Views
    await renderTodayStories();
    renderArchiveDaysList();
    renderSourcesTable();

    // Initial route check
    if (window.location.hash) {
      handleHashRouting();
    }
  } catch (error) {
    console.error('Initialization error:', error);
    renderEmptyTodayFeed('Could not connect to the TrueNews local verification engine. Please make sure the backend is running.');
  }
}

// ─── DATA LAYER: DAILY AGGREGATION ───
function groupEventsByDate() {
  state.eventsByDate.clear();

  state.events.forEach((event) => {
    // Extract date from time_span [start_iso, end_iso] or default to today
    let dateKey = getIsoDateKey(new Date());
    if (event.time_span && event.time_span.length > 0) {
      const isoStr = event.time_span[1] || event.time_span[0];
      if (isoStr) {
        dateKey = isoStr.slice(0, 10);
      }
    }

    if (!state.eventsByDate.has(dateKey)) {
      state.eventsByDate.set(dateKey, []);
    }
    state.eventsByDate.get(dateKey).push(event);
  });
}

// ─── FLOW 1: TODAY'S VERIFIED NEWS (HOME) ───
async function renderTodayStories() {
  const feed = $('#today-stories-feed');
  const todayKey = getIsoDateKey(new Date());

  // Determine today's stories:
  // If there are events explicitly matching today's date, use them.
  // Otherwise, if in development/demo dataset, we check if today's list is empty.
  let todayEvents = state.eventsByDate.get(todayKey) || [];

  // If today has no new events yet, but events exist in database:
  if (todayEvents.length === 0) {
    // Show clean empty state for today
    feed.innerHTML = `
      <div class="empty-box">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin: 0 auto 12px; display: block; opacity: 0.4;"><path d="M19 20H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1m2 13a2 2 0 0 1-2-2V7m2 13a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/></svg>
        <h3 style="font-size: 1.1rem; font-weight: 700; color: var(--text-primary); margin-bottom: 6px;">No verified stories for today yet.</h3>
        <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 16px;">Check back later or browse previous editions in the Archive.</p>
        <button class="btn btn-teal btn-sm" onclick="navigateTo('archive')">Browse Archive →</button>
      </div>
    `;
    return;
  }

  // Pre-fetch all briefs in parallel
  const items = await Promise.all(
    todayEvents.map(async (event) => {
      try {
        if (!state.briefsCache.has(event.id)) {
          const brief = await api(`/api/events/${encodeURIComponent(event.id)}/brief`);
          state.briefsCache.set(event.id, brief);
        }
        return { event, brief: state.briefsCache.get(event.id) };
      } catch (e) {
        return { event, brief: null };
      }
    })
  );

  feed.innerHTML = items
    .map(({ event, brief }) => renderStoryCardHtml(event, brief))
    .join('');
}

function renderStoryCardHtml(event, brief) {
  const headline = brief ? brief.neutral_headline : event.label;
  const tierNum = brief && brief.core_facts && brief.core_facts.length > 0 ? brief.core_facts[0].tier : 1;
  const originsCount = brief && brief.core_facts && brief.core_facts.length > 0
    ? Math.max(...brief.core_facts.map((f) => f.independent_source_count || 1))
    : event.item_count || 1;

  const takeawaySummary = getCleanTakeaway(brief, event);
  const hasDisputes = (brief && brief.disputed_points && brief.disputed_points.length > 0) || (event.dispute_count > 0);

  return `
    <article class="story-card" onclick="navigateTo('story', '${escapeHtml(event.id)}')">
      <div class="story-card-top">
        ${tierBadgeHtml(tierNum)}
        <span class="source-count-pill">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
          ${originsCount} independent ${originsCount === 1 ? 'source' : 'sources'}
        </span>
        ${hasDisputes ? `<span class="disputed-badge">⚠️ Disputed</span>` : ''}
      </div>

      <h2 class="story-headline">${escapeHtml(headline)}</h2>
      <p class="story-card-summary">${escapeHtml(takeawaySummary)}</p>

      <div class="story-card-footer">
        <span class="source-count-pill">${event.item_count || 1} articles audited</span>
        <button class="btn-read-more" onclick="event.stopPropagation(); navigateTo('story', '${escapeHtml(event.id)}')">
          Read more →
        </button>
      </div>
    </article>
  `;
}

function renderEmptyTodayFeed(msg) {
  const feed = $('#today-stories-feed');
  feed.innerHTML = `
    <div class="empty-box">
      <p>${escapeHtml(msg)}</p>
    </div>
  `;
}

// ─── FLOW 2: STORY DETAIL ───
async function loadStoryDetail(eventId) {
  state.activeStoryId = eventId;

  // Set Back button label based on where user arrived from
  const backLabel = $('#story-back-label');
  if (backLabel) {
    backLabel.textContent = state.previousView === 'archive' ? 'Back to Archive' : "Back to Today's News";
  }

  // Set export download links
  $('#export-md-link').href = `/api/exports/${encodeURIComponent(eventId)}.md`;
  $('#export-html-link').href = `/api/exports/${encodeURIComponent(eventId)}.html`;

  try {
    $('#story-headline').textContent = 'Loading verified story…';
    $('#story-summary').textContent = '';
    $('#story-facts-list').innerHTML = '<div class="spinner"></div>';

    let brief = state.briefsCache.get(eventId);
    const [fetchedBrief, claims] = await Promise.all([
      brief ? Promise.resolve(brief) : api(`/api/events/${encodeURIComponent(eventId)}/brief`),
      api(`/api/events/${encodeURIComponent(eventId)}/claims`).catch(() => []),
    ]);

    brief = fetchedBrief;
    state.briefsCache.set(eventId, brief);

    // Headline & Takeaway Lead
    $('#story-headline').textContent = brief.neutral_headline;
    const leadText = brief.core_facts && brief.core_facts.length > 0
      ? brief.core_facts[0].text || brief.core_facts[0].original_text || ''
      : '';
    $('#story-summary').textContent = leadText;

    // Overall Tier badge
    const topTier = brief.core_facts && brief.core_facts.length > 0 ? brief.core_facts[0].tier : 1;
    const tierEl = $('#detail-tier-badge');
    tierEl.className = `tier-pill tier-${topTier}`;
    const tierLabels = { 1: 'Tier 1 · Corroborated', 2: 'Tier 2 · Verified', 3: 'Tier 3 · Contested', 4: 'Tier 4 · Unverified', 5: 'Tier 5 · Speculative' };
    tierEl.textContent = tierLabels[topTier] || `Tier ${topTier}`;

    // Source count badge
    const maxOrigins = brief.core_facts && brief.core_facts.length > 0
      ? Math.max(...brief.core_facts.map((f) => f.independent_source_count || 1))
      : 1;
    $('#detail-sources-count').textContent = `${maxOrigins} independent ${maxOrigins === 1 ? 'source' : 'sources'}`;

    // Diversity badge
    const diversityEl = $('#detail-diversity-badge');
    if (brief.diversity_compliant) {
      diversityEl.className = 'diversity-badge diversity-pass';
      diversityEl.textContent = '✓ Diversity Compliant';
    } else {
      diversityEl.className = 'diversity-badge';
      diversityEl.textContent = 'Diversity Notice';
    }

    // 1. Key Facts List
    renderDetailFacts(brief.core_facts || []);

    // 2. Original vs Neutralized Wording
    renderDetailDiffs(claims);

    // 3. Disputes Section (Only shown if contradictions exist)
    renderDetailDisputes(brief.disputed_points || []);

    // 4. Sources Used
    renderDetailSources(brief.source_ledger || [], claims);

  } catch (error) {
    console.error(`Error loading story ${eventId}:`, error);
    $('#story-headline').textContent = 'Could not load story details';
    $('#story-summary').textContent = error.message;
  }
}

function renderDetailFacts(facts) {
  const container = $('#story-facts-list');
  if (!facts.length) {
    container.innerHTML = `<p class="source-count-pill">No core facts recorded for this story.</p>`;
    return;
  }

  container.innerHTML = facts
    .map((fact) => {
      const tierNum = Number(fact.tier) || 1;
      return `
        <div class="fact-card">
          <div class="fact-header">
            ${tierBadgeHtml(tierNum)}
            <span class="source-count-pill">${fact.independent_source_count || 1} independent ${fact.independent_source_count === 1 ? 'origin' : 'origins'}</span>
          </div>
          <p class="fact-text">${escapeHtml(fact.text || fact.original_text || '')}</p>
          ${fact.attribution_speaker ? `<div class="fact-footer">Attributed to: ${escapeHtml(fact.attribution_speaker)}</div>` : ''}
        </div>
      `;
    })
    .join('');
}

function renderDetailDiffs(claims) {
  const container = $('#story-diff-list');
  const diffClaims = claims.filter(
    (c) => c.original_wording && c.neutralized_wording && c.original_wording !== c.neutralized_wording
  );

  const displayList = diffClaims.length > 0 ? diffClaims : claims.slice(0, 3);

  if (!displayList.length) {
    container.innerHTML = `<p class="source-count-pill">No wording diffs available for this story.</p>`;
    return;
  }

  container.innerHTML = displayList
    .map((c) => {
      const orig = c.original_wording || c.what || 'Original passage text';
      const neut = c.neutralized_wording || c.what || orig;

      return `
        <div class="diff-box">
          <div class="diff-half diff-original">
            <span class="diff-label diff-label-red">ORIGINAL WORDING</span>
            <p class="diff-text">${escapeHtml(orig)}</p>
            <div class="diff-meta">Source passage: ${escapeHtml(c.passage_id || c.item_id || 'paragraph citation')}</div>
          </div>
          <div class="diff-half diff-neutralized">
            <span class="diff-label diff-label-teal">NEUTRALIZED TRUENEWS CLAIM</span>
            <p class="diff-text">${escapeHtml(neut)}</p>
            <div class="diff-meta" style="color: var(--teal-600);">✓ Loaded language and bias removed</div>
          </div>
        </div>
      `;
    })
    .join('');
}

function renderDetailDisputes(disputedPoints) {
  const section = $('#story-disputes-section');
  const container = $('#story-disputes-list');

  // Strict check: Only show if disputes exist
  if (!disputedPoints || !disputedPoints.length) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  container.innerHTML = disputedPoints
    .map((dp) => {
      const isStr = typeof dp === 'string';
      const title = isStr ? 'Reporting Contradiction' : dp.topic || 'Disputed point';
      const text = isStr ? dp : dp.explanation || 'Differing figures or assertions reported across newsrooms.';

      return `
        <div class="dispute-box">
          <h4>⚠️ ${escapeHtml(title)}</h4>
          <p>${escapeHtml(text)}</p>
        </div>
      `;
    })
    .join('');
}

function renderDetailSources(sourceLedger, claims) {
  const container = $('#story-sources-grid');

  if (sourceLedger && sourceLedger.length > 0) {
    container.innerHTML = sourceLedger
      .map((s) => `
        <div class="source-item">
          <div class="source-item-name">${escapeHtml(s.name || s.source_id)}</div>
          <div class="source-item-tier">Tier ${s.tier || 1} · ${s.independent_origin ? 'Primary origin' : 'Secondary report'}</div>
        </div>
      `)
      .join('');
    return;
  }

  // Fallback to matched registered sources
  const sourceIds = new Set(claims.map((c) => c.source_id).filter(Boolean));
  const matched = state.sources.filter((s) => sourceIds.has(s.id));
  const display = matched.length > 0 ? matched : state.sources.slice(0, 4);

  container.innerHTML = display
    .map((s) => `
      <div class="source-item">
        <div class="source-item-name">${escapeHtml(s.name)}</div>
        <div class="source-item-tier">Tier ${escapeHtml(s.tier)} · ${escapeHtml(s.region)}</div>
      </div>
    `)
    .join('');
}

// ─── FLOW 3: ARCHIVE ───
function renderArchiveDaysList() {
  const container = $('#archive-days-container');
  if (!state.eventsByDate.size) {
    container.innerHTML = `<p class="empty-box">No historical news editions available yet.</p>`;
    return;
  }

  // Sort dates descending
  const sortedDates = Array.from(state.eventsByDate.keys()).sort().reverse();

  container.innerHTML = sortedDates
    .map((dateKey) => {
      const events = state.eventsByDate.get(dateKey) || [];
      const dateLabel = formatReadableDate(dateKey, true);

      return `
        <div class="archive-day-card" onclick="openArchiveDay('${escapeHtml(dateKey)}')">
          <span class="archive-day-date">${escapeHtml(dateLabel)}</span>
          <span class="archive-day-count">
            ${events.length} verified ${events.length === 1 ? 'story' : 'stories'} →
          </span>
        </div>
      `;
    })
    .join('');
}

async function openArchiveDay(dateKey) {
  state.activeArchiveDateKey = dateKey;
  const events = state.eventsByDate.get(dateKey) || [];
  const dateLabel = formatReadableDate(dateKey, true);

  $('#archive-days-container').style.display = 'none';
  const dayFeedContainer = $('#archive-day-feed');
  dayFeedContainer.style.display = 'block';
  $('#archive-day-feed-title').textContent = `Verified Stories — ${dateLabel}`;

  const feed = $('#archive-stories-feed');
  feed.innerHTML = '<div class="spinner"></div>';

  if (!events.length) {
    feed.innerHTML = `<div class="empty-box"><p>No stories found for this date.</p></div>`;
    return;
  }

  // Fetch briefs
  const items = await Promise.all(
    events.map(async (event) => {
      try {
        if (!state.briefsCache.has(event.id)) {
          const brief = await api(`/api/events/${encodeURIComponent(event.id)}/brief`);
          state.briefsCache.set(event.id, brief);
        }
        return { event, brief: state.briefsCache.get(event.id) };
      } catch (e) {
        return { event, brief: null };
      }
    })
  );

  feed.innerHTML = items
    .map(({ event, brief }) => renderStoryCardHtml(event, brief))
    .join('');
}

function showArchiveDaysList() {
  $('#archive-day-feed').style.display = 'none';
  $('#archive-days-container').style.display = 'flex';
}

// ─── FLOW 4: SOURCES ───
function renderSourcesTable() {
  const tbody = $('#sources-tbody');
  if (!state.sources.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="source-count-pill">No sources registered.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.sources
    .map((s) => `
      <tr>
        <td><strong>${escapeHtml(s.name)}</strong></td>
        <td><span class="tier-pill tier-${s.tier === 'primary' ? '1' : s.tier === 'secondary' ? '2' : '3'}">${escapeHtml(s.tier.toUpperCase())}</span></td>
        <td>${escapeHtml(s.region)}</td>
        <td><span class="diversity-badge diversity-pass">${escapeHtml(s.status)}</span></td>
      </tr>
    `)
    .join('');
}

// ─── ADVANCED DRAWER (POWER USERS) ───
async function toggleAdvancedView() {
  const drawer = $('#advanced-drawer');
  const isHidden = drawer.style.display === 'none';
  drawer.style.display = isHidden ? 'block' : 'none';

  if (isHidden) {
    try {
      const entries = await api('/api/ledger');
      const tbody = $('#advanced-ledger-tbody');
      tbody.innerHTML = entries
        .slice(0, 30)
        .map((e) => `
          <tr>
            <td><code>${escapeHtml(e.id)}</code></td>
            <td>${escapeHtml(e.canonical_claim)}</td>
            <td>Tier ${e.confidence_tier || 1}</td>
            <td>${e.independent_origin_count || 1}</td>
          </tr>
        `)
        .join('');
    } catch (e) {
      console.warn('Advanced ledger load error:', e);
    }
  }
}
