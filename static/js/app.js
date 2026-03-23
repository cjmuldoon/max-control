/**
 * Max — App Core
 * Theme switcher and global utilities.
 * "Would you believe... a single-file application controller?"
 */

// ===== Theme Management =====
const ThemeManager = {
    STORAGE_KEY: 'max-theme',
    DEFAULT: 'dark',

    init() {
        const saved = localStorage.getItem(this.STORAGE_KEY) || this.DEFAULT;
        this.apply(saved);
        this.bindButtons();
    },

    apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(this.STORAGE_KEY, theme);

        // Update active button state
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === theme);
        });
    },

    bindButtons() {
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.apply(btn.dataset.theme);
            });
        });
    }
};

// ===== Toast Notifications =====
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = [
        'position:fixed', 'bottom:20px', 'right:20px', 'z-index:9999',
        'padding:8px 14px', 'border-radius:6px', 'font-size:13px',
        'font-weight:500', 'opacity:0', 'transition:opacity 0.25s ease',
        'pointer-events:none',
        type === 'success' ? 'background:#2a6e3f;color:#d4edda;' :
        type === 'error'   ? 'background:#7c2d2d;color:#f8d7da;' :
                             'background:#2c3e50;color:#eee;'
    ].join(';');
    document.body.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = '1'; });
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

// ===== Flash Message Auto-dismiss =====
function initFlashMessages() {
    document.querySelectorAll('.flash').forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-8px)';
            flash.style.transition = 'all 0.3s ease';
            setTimeout(() => flash.remove(), 300);
        }, 5000);
    });
}

// ===== Sidebar Collapse =====
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const collapsed = sidebar.classList.toggle('collapsed');
    localStorage.setItem('max-sidebar-collapsed', collapsed ? '1' : '0');
    const icon = document.getElementById('sidebar-toggle-icon');
    if (icon) icon.innerHTML = collapsed ? '&#x25B6;' : '&#x25C0;';
}

function initSidebar() {
    const collapsed = localStorage.getItem('max-sidebar-collapsed') === '1';
    if (collapsed) {
        document.querySelector('.sidebar').classList.add('collapsed');
        const icon = document.getElementById('sidebar-toggle-icon');
        if (icon) icon.innerHTML = '&#x25B6;';
    }
}

// ===== Lid-Awake Control =====
function lidAwake(action) {
    const badge = document.getElementById('lid-awake-status');
    const label = document.getElementById('lid-awake-label');
    const btnOn = document.getElementById('lid-awake-btn-on');
    const btnOff = document.getElementById('lid-awake-btn-off');
    if (!badge) return;

    function applyLidState(isOn, isOff) {
        badge.classList.remove('running', 'stopped', 'idle');
        if (btnOn) btnOn.classList.remove('btn-success', 'btn-secondary');
        if (btnOff) btnOff.classList.remove('btn-danger', 'btn-secondary');
        if (isOn) {
            badge.classList.add('running');
            if (label) label.textContent = 'Lid: On';
            badge.title = 'Lid-awake active — lid close will not sleep';
            if (btnOn) btnOn.classList.add('btn-success');
            if (btnOff) btnOff.classList.add('btn-secondary');
        } else if (isOff) {
            badge.classList.add('stopped');
            if (label) label.textContent = 'Lid: Off';
            badge.title = 'Lid-awake off — normal sleep behaviour';
            if (btnOn) btnOn.classList.add('btn-secondary');
            if (btnOff) btnOff.classList.add('btn-danger');
        } else {
            badge.classList.add('idle');
            if (label) label.textContent = 'Lid: ?';
            if (btnOn) btnOn.classList.add('btn-secondary');
            if (btnOff) btnOff.classList.add('btn-secondary');
        }
    }

    fetch(`/system/lid-awake/${action}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            const out = (data.output || '').toLowerCase();
            const isOn = out.includes('enabled') || out.includes('on') || out.includes('active');
            const isOff = out.includes('disabled') || out.includes('off') || out.includes('inactive');
            applyLidState(isOn, isOff);
            badge.title = badge.title || data.output || 'Unknown status';
            if (action !== 'status') {
                if (isOn) showToast('Lid-awake ON — Mac stays awake with lid closed', 'success');
                else if (isOff) showToast('Lid-awake OFF — normal sleep restored', 'info');
                else showToast(data.output || 'Lid-awake: unknown state', 'error');
            }
        })
        .catch(() => {
            applyLidState(false, false);
            if (label) label.textContent = 'Lid: ?';
            if (action !== 'status') showToast('Lid-awake: request failed', 'error');
        });
}

// ===== Local Time Conversion =====
// Converts <time data-utc="ISO-string"> elements to the browser's local timezone.
// SQLite stores UTC via datetime.utcnow().isoformat() without a 'Z' suffix — we
// append it so JS treats the value as UTC, not local.
function initLocalTimes() {
    document.querySelectorAll('time[data-utc]').forEach(el => {
        const raw = el.dataset.utc;
        if (!raw) return;
        const utcStr = (raw.endsWith('Z') || raw.includes('+')) ? raw : raw + 'Z';
        const d = new Date(utcStr);
        if (isNaN(d)) return;
        const pad = n => String(n).padStart(2, '0');
        el.textContent = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
        el.title = d.toLocaleString();
    });
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.init();
    initFlashMessages();
    initSidebar();
    lidAwake('status');
    initLocalTimes();
});
