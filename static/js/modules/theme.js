// static/js/modules/theme.js
export function initTheme() {
    const htmlEl = document.documentElement;
    const themeToggle = document.getElementById('themeToggle');
    const icon = themeToggle?.querySelector('i');
    
    const savedTheme = localStorage.getItem('theme') || 'light';
    htmlEl.setAttribute('data-bs-theme', savedTheme);
    updateIcon(savedTheme, icon);

    themeToggle?.addEventListener('click', () => {
        const current = htmlEl.getAttribute('data-bs-theme');
        const next = current === 'light' ? 'dark' : 'light';
        htmlEl.setAttribute('data-bs-theme', next);
        localStorage.setItem('theme', next);
        updateIcon(next, icon);
    });
}

export function toggleTheme() {
    const html = document.documentElement;
    const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    document.body.classList.add('theme-transition');
    html.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
    setTimeout(() => document.body.classList.remove('theme-transition'), 300);
}

function updateIcon(theme, icon) {
    if (!icon) return;
    if (theme === 'dark') {
        icon.classList.replace('bi-moon-stars-fill', 'bi-sun-fill');
    } else {
        icon.classList.replace('bi-sun-fill', 'bi-moon-stars-fill');
    }
}

function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;
    const moon = toggle.querySelector('.bi-moon');
    const sun = toggle.querySelector('.bi-sun');
    if(moon) moon.style.display = theme === 'dark' ? 'none' : 'block';
    if(sun) sun.style.display = theme === 'dark' ? 'block' : 'none';
}