// static/js/modules/theme.js

export class ThemeController {
  constructor() {
    this.htmlEl = document.documentElement;
    this.themeToggle = document.getElementById('themeToggle');
    this.icon = this.themeToggle?.querySelector('i');
    this.#init();
  }

  #init() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    this.#applyTheme(savedTheme);

    this.themeToggle?.addEventListener('click', () => {
      const current = this.htmlEl.getAttribute('data-bs-theme');
      const next = current === 'light' ? 'dark' : 'light';
      this.#applyTheme(next);
    });
  }

  #applyTheme(theme) {
    this.htmlEl.setAttribute('data-bs-theme', theme);
    localStorage.setItem('theme', theme);
    this.#updateIcon(theme);
  }

  #updateIcon(theme) {
    if (!this.icon) return;
    if (theme === 'dark') {
      this.icon.classList.replace('bi-moon-stars-fill', 'bi-sun-fill');
    } else {
      this.icon.classList.replace('bi-sun-fill', 'bi-moon-stars-fill');
    }
  }

  toggle() {
    const current = this.htmlEl.getAttribute('data-bs-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.body.classList.add('theme-transition');
    this.#applyTheme(next);
    setTimeout(() => document.body.classList.remove('theme-transition'), 300);
  }
}

// Создаем и экспортируем экземпляр по умолчанию
export const themeController = new ThemeController();