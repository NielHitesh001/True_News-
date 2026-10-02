/**
 * TrueNews (Antigravity NewsX)
 * Pure Vanilla JavaScript · 5 Core Reader Flows
 */

'use strict';

// ─── State ───
const state = {
  currentView: 'today',
  events: [],
  briefsCache: new Map(),
  activeStoryId: null,
  sources: [],
  health: null,
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

function showToast(msg) {
  const toast = $('#toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}

// ─── Navigation ───
function navigateTo(viewName, storyId = null) {
  state.currentView = viewName;

  // Update URL hash
  if (viewName === 'story' && storyId) {
    window.location.hash = `#story/${encodeURIComponent(storyId)}`;
  } else {
    window.location.hash = `#${viewName}`;
  }

  // Switch view section
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

  // If entering story view with ID, load the story detail
  if (viewName === 'story' && storyId) {
    loadStoryDetail(storyId);
  }
}

// ─── App Init ───
document.addEventListener('DOMContentLoaded', () => {
  initApp();
  setupEvents();
});

function setupEvents() {
  // Mobile menu toggle
  const menuBtn = $('#menu-btn');
  const topbarNav = $('#topbar-nav');
  if (menuBtn && topbarNav) {
    menuBtn.addEventListener('click', () => {
      const isOpen = topbarNav.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', String(isOpen));
    });
  }

  // Hash-based routing
  window.addEventListener('hashchange', handleHashRouting);

  // Topbar nav links
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
    // Set date display
    const today = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    $('#today-date-display').textContent = today.toLocaleDateString('en-US', options);

    // Fetch pipeline data
    const [health, events, sources] = await Promise.all([
      api('/api/health'),
      api('/api/events'),
      api('/api/sources'),
    ]);

    state.health = health;
    state.events = events.filter((e) => e.id !== 'all');
    state.sources = sources;

    $('#status-text').textContent = `${health.items || 0} Articles Verified`;

    // Render all core views
    await renderTodayStories();
    renderArchiveDays();
    renderSourcesTable();

    // Initial route handling
    if (window.location.hash) {
      handleHashRouting();
    }
  } catch (error) {
    console.error('Initialization error:', error);
    renderEmptyTodayFeed('Could not connect to the TrueNews local verification engine. Please check that the server is running.');
  }
}

// ─── FLOW 1: TODAY'S VERIFIED NEWS (HOME) ───
async function renderTodayStories() {
  const feed = $('#today-stories-feed');
  if (!state.events.length) {
    renderEmptyTodayFeed('No verified stories for today yet. Check back later.');
    return;
  }

  // Fetch all briefs
  const items = await Promise.all(
    state.events.map(async (event) => {
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
    .map(({ event, brief }) => {
      const headline = brief ? brief.neutral_headline : event.label;
      const tierNum = brief && brief.core_facts && brief.core_facts.length > 0 ? brief.core_facts[0].tier : 1;
      const originsCount = brief && brief.core_facts && brief.core_facts.length > 0
        ? Math.max(...brief.core_facts.map((f) => f.independent_source_count || 1))
        : event.item_count || 1;

      // 2-3 line summary
      const summary = brief && brief.core_facts && brief.core_facts.length > 0
        ? (brief.core_facts[0].text || brief.core_facts[0].original_text || '')
        : `Verified event synthesized from ${event.item_count || 1} sources with ${event.claim_count || 0} atomic factual claims.`;

      // Check if disputes exist
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
          <p class="story-card-summary">${escapeHtml(summary)}</p>

          <div class="story-card-footer">
            <span class="source-count-pill">${event.item_count || 1} articles audited</span>
            <button class="btn-read-more" onclick="event.stopPropagation(); navigateTo('story', '${escapeHtml(event.id)}')">
              Read more →
            </button>
          </div>
        </article>
      `;
    })
    .join('');
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

    // Headline & Lead
    $('#story-headline').textContent = brief.neutral_headline;
    $('#story-summary').textContent = brief.core_facts && brief.core_facts.length > 0
      ? brief.core_facts[0].text || brief.core_facts[0].original_text || ''
      : '';

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

    // 3. Disputes Section
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
            <div class="diff-meta">Source: ${escapeHtml(c.passage_id || c.item_id || 'Reporting passage')}</div>
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

  // Fallback to matched sources from registry
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
function renderArchiveDays() {
  const container = $('#archive-days-container');
  if (!state.events.length) {
    container.innerHTML = `<p class="empty-box">No historical news editions available yet.</p>`;
    return;
  }

  // Group events by date (or present today + past simulated dates)
  const today = new Date();
  const options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' };

  // For demonstration and realistic archives, group available events
  const days = [
    {
      dateLabel: today.toLocaleDateString('en-US', options),
      storyCount: state.events.length,
      events: state.events,
    },
  ];

  container.innerHTML = days
    .map((day, idx) => `
      <div class="archive-day-card" onclick="openArchiveDay(${idx})">
        <span class="archive-day-date">${escapeHtml(day.dateLabel)}</span>
        <span class="archive-day-count">
          ${day.storyCount} verified ${day.storyCount === 1 ? 'story' : 'stories'} →
        </span>
      </div>
    `)
    .join('');
}

function openArchiveDay(dayIdx) {
  const today = new Date();
  const options = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' };
  const dateStr = today.toLocaleDateString('en-US', options);

  $('#archive-days-container').style.display = 'none';
  const dayFeedContainer = $('#archive-day-feed');
  dayFeedContainer.style.display = 'block';
  $('#archive-day-feed-title').textContent = `Verified Stories — ${dateStr}`;

  const feed = $('#archive-stories-feed');
  feed.innerHTML = state.events
    .map((event) => {
      const brief = state.briefsCache.get(event.id);
      const headline = brief ? brief.neutral_headline : event.label;
      const tierNum = brief && brief.core_facts && brief.core_facts.length > 0 ? brief.core_facts[0].tier : 1;
      const originsCount = event.item_count || 1;
      const summary = brief && brief.core_facts && brief.core_facts.length > 0
        ? (brief.core_facts[0].text || brief.core_facts[0].original_text || '')
        : `Verified event containing ${event.claim_count || 0} claims.`;

      return `
        <article class="story-card" onclick="navigateTo('story', '${escapeHtml(event.id)}')">
          <div class="story-card-top">
            ${tierBadgeHtml(tierNum)}
            <span class="source-count-pill">${originsCount} sources</span>
          </div>
          <h2 class="story-headline">${escapeHtml(headline)}</h2>
          <p class="story-card-summary">${escapeHtml(summary)}</p>
          <div class="story-card-footer">
            <span class="source-count-pill">${event.claim_count || 0} claims verified</span>
            <button class="btn-read-more" onclick="event.stopPropagation(); navigateTo('story', '${escapeHtml(event.id)}')">
              Read more →
            </button>
          </div>
        </article>
      `;
    })
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

// ─── ADVANCED DRAWER (FOR POWER USERS) ───
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
