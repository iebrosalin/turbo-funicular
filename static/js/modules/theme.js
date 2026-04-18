// static/js/modules/theme.js
export function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
    updateThemeIcon(savedTheme);
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

function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;
    const moon = toggle.querySelector('.bi-moon');
    const sun = toggle.querySelector('.bi-sun');
    if(moon) moon.style.display = theme === 'dark' ? 'none' : 'block';
    if(sun) sun.style.display = theme === 'dark' ? 'block' : 'none';
}