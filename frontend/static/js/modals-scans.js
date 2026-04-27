// static/js/modals-scans.js
/**
 * Логика работы модальных окон сканирования (Импорт, Результаты, Ошибки)
 */

import { ModalManager } from './modules/modals.js';
import { Utils } from './modules/utils.js';

export class ScanModalManager {
  constructor() {
    this.modalManager = new ModalManager();
    this.#initListeners();
  }

  #initListeners() {
    // Инициализация формы импорта сканирования
    const form = document.getElementById('scanImportForm');
    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.#handleImportSubmit(e.target);
    });

    // Загрузка групп при открытии модального окна импорта XML
    document.getElementById('scanImportModal')?.addEventListener('show.bs.modal', () => {
      this.#loadGroupsForImport();
    });
  }

  async #handleImportSubmit(form) {
    const fileInput = document.getElementById('import-file');
    const groupSelect = document.getElementById('import-group-id');
    const progressDiv = document.getElementById('import-progress');
    const submitBtn = form.querySelector('button[type="submit"]');

    if (!fileInput?.files.length) {
      Utils.showNotification('Пожалуйста, выберите файл.', 'warning');
      return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    if (groupSelect?.value) {
      formData.append('group_id', groupSelect.value);
    }

    // UI обновления
    submitBtn.disabled = true;
    progressDiv.style.display = 'block';
    
    try {
      const response = await fetch('/api/scans/import', { 
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (response.ok) {
        this.modalManager.close('scanImportModal');
        Utils.showNotification(`Импорт успешно завершен! Обработано активов: ${result.count || 0}`, 'success');
        setTimeout(() => location.reload(), 1000);
      } else {
        this.showScanError(result.error || 'Неизвестная ошибка при импорте');
      }
    } catch (error) {
      console.error('Import error:', error);
      this.showScanError('Ошибка соединения: ' + error.message);
    } finally {
      submitBtn.disabled = false;
      progressDiv.style.display = 'none';
    }
  }

  /**
   * Показать модальное окно с ошибкой сканирования
   * @param {string} message - Текст ошибки
   */
  showScanError(message) {
    const contentDiv = document.getElementById('scan-error-content');
    if (contentDiv) {
      contentDiv.innerHTML = `<div class="alert alert-danger">${message}</div>`;
    }
    
    const modalEl = document.getElementById('scanErrorModal');
    if (modalEl) {
      this.modalManager.open('scanErrorModal');
    }
  }

  /**
   * Показать модальное окно с результатами сканирования
   * @param {string} htmlContent - HTML контент результатов
   * @param {string|null} errorText - Текст ошибки (если есть)
   */
  showScanResults(htmlContent, errorText = null) {
    const contentDiv = document.getElementById('scan-results-content');
    const errorAlert = document.getElementById('scan-error-alert');
    const errorTextPre = document.getElementById('scan-error-text');

    if (contentDiv) {
      contentDiv.innerHTML = htmlContent;
    }

    if (errorText && errorTextPre) {
      errorTextPre.textContent = errorText;
      errorAlert?.style.setProperty('display', 'block');
    } else {
      errorAlert?.style.setProperty('display', 'none');
    }

    const modalEl = document.getElementById('scanResultsModal');
    if (modalEl) {
      this.modalManager.open('scanResultsModal');
    }
  }

  /**
   * Динамическое обновление списка групп в модалке импорта
   */
  async #loadGroupsForImport() {
    const groupSelect = document.getElementById('import-group-id');
    if (!groupSelect) return;
    
    const currentValue = groupSelect.value;
    groupSelect.innerHTML = '<option value="">Без группы</option>';
    groupSelect.disabled = true;
    
    try {
      const response = await fetch('/api/groups/tree');
      if (response.ok) {
        const data = await response.json();
        const flatGroups = Array.isArray(data?.flat) ? data.flat : [];
        
        flatGroups.forEach(g => {
          const option = document.createElement('option');
          option.value = g.id;
          const depth = g.depth || 0;
          let prefix = '', icon = '📁 ';
          if (depth > 0) {
            for (let i = 0; i < depth; i++) prefix += '    ';
            prefix += '└─ '; 
            icon = '📂 ';
          }
          option.textContent = `${prefix}${icon}${g.name}`;
          groupSelect.appendChild(option);
        });
        
        if (currentValue && flatGroups.some(g => g.id == currentValue)) {
          groupSelect.value = currentValue;
        }
      }
    } catch (error) { 
      console.error('Ошибка загрузки групп:', error); 
    } finally { 
      groupSelect.disabled = false; 
    }
  }
}