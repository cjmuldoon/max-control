/**
 * Max — Operations Centre
 * Reconnaissance with search, sort, time grouping, and undercover management.
 * Sort & filter: "CONTROL keeps its agents organised, Chief."
 */

/* ===== Operations Filter & Sort ===== */
const OpsFilter = {
    STORAGE_KEY: 'max-ops-filter',

    /** Load saved preferences from localStorage */
    load() {
        try {
            const saved = JSON.parse(localStorage.getItem(this.STORAGE_KEY));
            if (!saved) return;
            const sortEl = document.getElementById('ops-sort');
            const statusEl = document.getElementById('ops-filter-status');
            const locationEl = document.getElementById('ops-filter-location');
            const searchEl = document.getElementById('ops-search');

            if (sortEl && saved.sort) sortEl.value = saved.sort;
            if (statusEl && saved.status) statusEl.value = saved.status;
            if (locationEl && saved.location) locationEl.value = saved.location;
            if (searchEl && saved.search) searchEl.value = saved.search;
        } catch (e) {
            // Corrupted storage — ignore
        }
    },

    /** Save current preferences to localStorage */
    save() {
        const prefs = {
            sort: document.getElementById('ops-sort')?.value || 'name-asc',
            status: document.getElementById('ops-filter-status')?.value || '',
            location: document.getElementById('ops-filter-location')?.value || '',
            search: document.getElementById('ops-search')?.value || '',
        };
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(prefs));
    },

    /** Apply filters and sort to the project grid */
    apply() {
        const grid = document.getElementById('project-grid');
        if (!grid) return;

        const cards = Array.from(grid.querySelectorAll('.project-card'));
        const searchVal = (document.getElementById('ops-search')?.value || '').toLowerCase().trim();
        const statusVal = document.getElementById('ops-filter-status')?.value || '';
        const locationVal = document.getElementById('ops-filter-location')?.value || '';
        const sortVal = document.getElementById('ops-sort')?.value || 'name-asc';

        // Highlight active filters
        this._markActive('ops-filter-status', statusVal);
        this._markActive('ops-filter-location', locationVal);

        let visibleCount = 0;
        const totalCount = cards.length;

        // Filter
        cards.forEach(card => {
            const name = card.dataset.name || '';
            const status = card.dataset.status || '';
            const location = card.dataset.location || '';
            const desc = (card.querySelector('.project-card-desc')?.textContent || '').toLowerCase();
            const path = (card.querySelector('.project-card-path')?.textContent || '').toLowerCase();

            let visible = true;

            // Search — matches name, description, or path
            if (searchVal && !name.includes(searchVal) && !desc.includes(searchVal) && !path.includes(searchVal)) {
                visible = false;
            }

            // Status filter
            if (statusVal && status !== statusVal) {
                visible = false;
            }

            // Location filter
            if (locationVal && location !== locationVal) {
                visible = false;
            }

            card.classList.toggle('ops-hidden', !visible);
            if (visible) visibleCount++;
        });

        // Sort visible cards
        const statusOrder = { running: 0, error: 1, stopped: 2, no_agent: 3 };
        const sortedCards = cards.slice().sort((a, b) => {
            switch (sortVal) {
                case 'name-asc':
                    return (a.dataset.name || '').localeCompare(b.dataset.name || '');
                case 'name-desc':
                    return (b.dataset.name || '').localeCompare(a.dataset.name || '');
                case 'status': {
                    const sa = statusOrder[a.dataset.status] ?? 99;
                    const sb = statusOrder[b.dataset.status] ?? 99;
                    return sa - sb || (a.dataset.name || '').localeCompare(b.dataset.name || '');
                }
                case 'location':
                    return (a.dataset.location || '').localeCompare(b.dataset.location || '') ||
                           (a.dataset.name || '').localeCompare(b.dataset.name || '');
                case 'updated': {
                    const ua = a.dataset.updated || '';
                    const ub = b.dataset.updated || '';
                    // Descending — most recently updated first
                    return ub.localeCompare(ua) || (a.dataset.name || '').localeCompare(b.dataset.name || '');
                }
                default:
                    return 0;
            }
        });

        // Re-order DOM
        sortedCards.forEach(card => grid.appendChild(card));

        // Update summary
        this._updateSummary(visibleCount, totalCount, searchVal, statusVal, locationVal);

        // Show/hide empty state
        const emptyEl = document.getElementById('ops-empty-filter');
        const formEl = document.getElementById('multi-launch-form');
        if (emptyEl && formEl) {
            const hasFilters = searchVal || statusVal || locationVal;
            emptyEl.style.display = (visibleCount === 0 && hasFilters) ? 'block' : 'none';
            // Keep the form visible so the grid stays in DOM for re-filtering
        }

        this.save();
    },

    /** Reset all filters to defaults */
    reset() {
        const sortEl = document.getElementById('ops-sort');
        const statusEl = document.getElementById('ops-filter-status');
        const locationEl = document.getElementById('ops-filter-location');
        const searchEl = document.getElementById('ops-search');

        if (sortEl) sortEl.value = 'name-asc';
        if (statusEl) statusEl.value = '';
        if (locationEl) locationEl.value = '';
        if (searchEl) searchEl.value = '';

        localStorage.removeItem(this.STORAGE_KEY);
        this.apply();
    },

    /** Mark selects with active-filter class when non-default */
    _markActive(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.classList.toggle('active-filter', !!value);
        }
    },

    /** Update the results summary text */
    _updateSummary(visible, total, search, status, location) {
        const el = document.getElementById('ops-results-summary');
        if (!el) return;

        const hasFilters = search || status || location;
        if (!hasFilters) {
            el.textContent = '';
            return;
        }

        const parts = [];
        if (search) parts.push(`matching "${search}"`);
        if (status) {
            const labels = { running: 'in the field', stopped: 'standing by', error: 'compromised', no_agent: 'no agent' };
            parts.push(labels[status] || status);
        }
        if (location) {
            const labels = { local: 'Local HQ', work: 'Branch Office' };
            parts.push(labels[location] || location);
        }

        if (visible === total) {
            el.textContent = `All ${total} agents shown — ${parts.join(', ')}`;
        } else if (visible === 0) {
            el.textContent = `No agents found — ${parts.join(', ')}. Missed it by that much!`;
        } else {
            el.textContent = `Showing ${visible} of ${total} agents — ${parts.join(', ')}`;
        }
    },

    /** Initialise on page load */
    init() {
        this.load();
        this.apply();
    }
};


/* ===== Card Selection & Multi-Launch ===== */

function handleCardClick(event, card) {
    // Always toggle selection — use the Open button to navigate
    const cb = card.querySelector('input[type="checkbox"]');
    cb.checked = !cb.checked;
    handleCheckboxChange(cb);
}

function handleCheckboxChange(cb) {
    const card = cb.closest('.project-card');
    card.classList.toggle('selected', cb.checked);
}

function toggleAllProjects() {
    // Only toggle visible (non-hidden) cards
    const checkboxes = document.querySelectorAll('.project-card:not(.ops-hidden) input[type="checkbox"]');
    const allChecked = [...checkboxes].every(cb => cb.checked);
    checkboxes.forEach(cb => {
        cb.checked = !allChecked;
        handleCheckboxChange(cb);
    });
    const btn = document.querySelector('[onclick="toggleAllProjects()"]');
    btn.textContent = allChecked ? '\u2611\uFE0F Select All' : '\uD83D\uDD32 Deselect All';
}


/* ===== Reconnaissance Scanner ===== */

async function scanProjects() {
    const btn = document.getElementById('scan-btn');
    const resultsDiv = document.getElementById('scan-results');
    const contentDiv = document.getElementById('scan-results-content');

    btn.disabled = true;
    btn.textContent = 'Scanning...';

    try {
        const response = await fetch('/projects/scan');
        const html = await response.text();

        contentDiv.innerHTML = html;
        resultsDiv.style.display = 'block';

        // Add search/sort bar if not already present
        if (!document.getElementById('recon-controls')) {
            const controls = document.createElement('div');
            controls.id = 'recon-controls';
            controls.className = 'mb-3';
            controls.innerHTML = `
                <div class="flex gap-2 items-center" style="flex-wrap: wrap;">
                    <input type="text" id="recon-search" class="form-input" placeholder="\uD83D\uDD0D Search targets..." style="flex: 1; min-width: 180px;" oninput="filterRecon()">
                    <select id="recon-location" class="form-select" style="width: auto; font-size: 13px;" onchange="filterRecon()">
                        <option value="">All Field Offices</option>
                        <option value="local">\uD83C\uDFE0 Local HQ</option>
                        <option value="work">\uD83C\uDFE2 Branch Office</option>
                    </select>
                    <select id="recon-sort" class="form-select" style="width: auto; font-size: 13px;" onchange="filterRecon()">
                        <option value="modified">\uD83D\uDCC5 Last Modified</option>
                        <option value="name">\uD83D\uDD24 Name</option>
                        <option value="size">\uD83D\uDCCA Size</option>
                    </select>
                    <label class="form-check" style="font-size: 12px; white-space: nowrap;">
                        <input type="checkbox" id="recon-undercover" onchange="filterRecon()">
                        \uD83D\uDD76\uFE0F Show Undercover
                    </label>
                </div>
            `;
            const section = resultsDiv.querySelector('.detail-section');
            const title = section.querySelector('.detail-section-title');
            title.insertAdjacentElement('afterend', controls);
        }
    } catch (err) {
        contentDiv.innerHTML = '<p class="text-sm text-error">Sorry about that, Chief. Reconnaissance failed.</p>';
        resultsDiv.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '\uD83D\uDD0E Reconnaissance';
    }
}

async function filterRecon() {
    const searchEl = document.getElementById('recon-search');
    const locationEl = document.getElementById('recon-location');
    const sortEl = document.getElementById('recon-sort');
    const undercoverEl = document.getElementById('recon-undercover');
    const contentDiv = document.getElementById('scan-results-content');

    const params = new URLSearchParams();
    if (searchEl && searchEl.value) params.set('q', searchEl.value);
    if (locationEl && locationEl.value) params.set('location', locationEl.value);
    if (sortEl && sortEl.value) params.set('sort', sortEl.value);
    if (undercoverEl && undercoverEl.checked) params.set('undercover', '1');

    try {
        const response = await fetch(`/projects/scan?${params.toString()}`);
        const html = await response.text();
        contentDiv.innerHTML = html;
    } catch (err) {
        // Keep existing results on filter failure
    }
}


/* ===== Init on DOM ready ===== */
document.addEventListener('DOMContentLoaded', () => {
    OpsFilter.init();
});
