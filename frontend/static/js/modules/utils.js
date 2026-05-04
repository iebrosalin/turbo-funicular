// static/js/modules/utils.js

export class Utils {
  /**
   * Заполняет выпадающие списки родительских групп с визуальной иерархией.
   * @param {Array} excludeIds - Массив ID для исключения
   * @param {number|null} selectedId - Выбранный ID
   * @param {boolean} forDeleteModal - Флаг для модального окна удаления (добавляет опцию удаления активов)
   * @param {boolean} forMoveModal - Флаг для модального окна перемещения (показывает только корень, если нет других групп)
   */
  static async populateParentSelect(excludeIds = [], selectedId = null, forDeleteModal = false, forMoveModal = false) {
    try {
      const res = await fetch('/api/groups/tree');
      if (!res.ok) throw new Error('Failed to fetch tree');
      const data = await res.json();
      
      if (!data.flat) return;

      // Фильтрация групп для модального окна перемещения
      let groups = data.flat;
      if (forMoveModal) {
        // Исключаем саму перемещаемую группу из списка
        groups = groups.filter(g => !excludeIds.includes(String(g.id)));
        
        // Если нет других групп кроме корневых, показываем только опцию корня
        const hasNonRootGroups = groups.some(g => g.parent_id !== null);
        if (!hasNonRootGroups) {
          // Показываем только опцию корня
          const selectors = [
            '#edit-group-parent',   
            '#move-group-parent'
          ];
          
          if (forDeleteModal) {
            selectors.push('#delete-move-assets');
          }
          
          selectors.forEach(sel => {
            const el = document.querySelector(sel);
            if (el) {
              el.innerHTML = '<option value="">-- Корень --</option>';
              el.classList.add('hierarchy-select');
              el.style.fontFamily = "'Consolas', 'Monaco', 'Courier New', monospace";
              el.value = "";
              el.setAttribute('data-last-value', "");
            }
          });
          return;
        }
      }

      // Построение дерева
      const buildTree = (parentId) => {
        return groups
          .filter(g => g.parent_id == parentId)
          .map(g => ({
            ...g,
            children: buildTree(g.id)
          }));
      };
      const tree = buildTree(null);

      // Генерация опций
      const generateOptions = (nodes, level = 0) => {
        let options = '';
        nodes.forEach(node => {
          if (excludeIds.includes(String(node.id))) return;

          // Используем символы тире для визуализации иерархии, так как CSS padding не работает в <option>
          const prefix = level > 0 ? '— '.repeat(level) : '';
          const label = prefix + node.name;
          
          const option = document.createElement('option');
          option.value = node.id;
          option.text = label; 
          if (selectedId !== null && String(node.id) === String(selectedId)) {
            option.selected = true;
          }
          
          options += option.outerHTML;
          
          if (node.children && node.children.length > 0) {
            options += generateOptions(node.children, level + 1);
          }
        });
        return options;
      };

      const baseOption = '<option value="">-- Корень --</option>';
      const optionsContent = baseOption + generateOptions(tree);

      const selectors = [
        '#edit-group-parent',   
        '#move-group-parent'
      ];

      // Для модального окна удаления используем отдельный селектор
      if (forDeleteModal) {
        selectors.push('#delete-move-assets');
      }  

      selectors.forEach(sel => {
        const el = document.querySelector(sel);
        if (el) {
          // 1. Сначала очищаем и заполняем контент
          el.innerHTML = optionsContent;
          
          // 2. Явно добавляем класс для стилей (важно для всех страниц)
          el.classList.add('hierarchy-select');
          
          // 3. Принудительно задаем стиль через JS, если CSS по какой-то причине не применился
          el.style.fontFamily = "'Consolas', 'Monaco', 'Courier New', monospace";
          
          // 4. Восстанавливаем выбор
          const currentVal = selectedId !== null ? selectedId : el.getAttribute('data-last-value') || el.value;
          if (currentVal) {
            el.value = currentVal;
          } else {
            el.value = ""; // Сброс на "-- Корень --" если ничего не выбрано
          }
          
          // Сохраняем текущее значение для возможного следующего открытия
          el.setAttribute('data-last-value', el.value);
        }
      });

    } catch (e) {
      console.error('Ошибка загрузки дерева групп:', e);
    }
  }

  /**
   * Закрытие модального окна по ID
   * @param {string} modalId 
   */
  static closeModalById(modalId) {
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return;

    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    
    if (modalInstance) {
      modalInstance.hide();
    } else {
      modalEl.classList.remove('show');
      modalEl.removeAttribute('aria-modal');
      modalEl.removeAttribute('role');
      modalEl.style.display = '';
      
      const backdrop = document.querySelector('.modal-backdrop');
      if (backdrop) backdrop.remove();
      
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
    }

    const form = modalEl.querySelector('form');
    if (form) form.reset();
  }

  /**
   * Универсальная функция для API запросов
   * @param {string} url 
   * @param {object} options 
   * @returns {Promise<any>}
   */
  static async apiRequest(url, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    const config = {
      method: options.method || 'GET',
      ...options,
      headers
    };
    if (options.body && typeof options.body === 'object') {
      config.body = JSON.stringify(options.body);
    }

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP Error: ${response.status}`);
      }

      if (response.status === 204) return null;

      return await response.json();
    } catch (error) {
      console.error(`API Request failed (${url}):`, error);
      throw error;
    }
  }

  /**
   * Форматирование даты
   * @param {string} dateString 
   * @returns {string}
   */
  static formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  }

  /**
   * Показ уведомлений (алиас для showFlashMessage)
   * @param {string} message 
   * @param {string} type 
   */
  static showNotification(message, type = 'info') {
    const container = document.getElementById('notifications-container') || document.body;
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.role = 'alert';
    alert.style.cssText = `
      position: relative;
      max-width: 800px;
      word-wrap: break-word;
      white-space: pre-wrap;
      overflow-wrap: break-word;
      hyphens: auto;
      margin-bottom: 1rem;
    `;
    
    // Для ошибок добавляем кнопку копирования
    let extraButtons = '';
    if (type === 'danger') {
      extraButtons = `
      <div class="mt-2">
        <button class="btn btn-sm btn-outline-secondary copy-error-btn me-2" data-error-text="${message.replace(/"/g, '&quot;').replace(/\n/g, '&#10;')}">
          <i class="bi bi-clipboard"></i> Копировать
        </button>
      </div>
      `;
    }
    
    alert.innerHTML = `
      <div style="word-break: break-word; white-space: pre-wrap;">${message}</div>
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      ${extraButtons}
    `;
    
    container.prepend(alert);
    
    // Добавляем обработчик копирования для ошибок
    if (type === 'danger') {
      const copyBtn = alert.querySelector('.copy-error-btn');
      if (copyBtn) {
        copyBtn.addEventListener('click', function() {
          const errorText = this.getAttribute('data-error-text') || message;
          
          // Проверяем поддержку Clipboard API
          if (!navigator.clipboard || !navigator.clipboard.writeText) {
            // Fallback для старых браузеров или небезопасного контекста
            const textarea = document.createElement('textarea');
            textarea.value = errorText;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {
              document.execCommand('copy');
              const originalHTML = copyBtn.innerHTML;
              copyBtn.innerHTML = '<i class="bi bi-check"></i> Скопировано';
              setTimeout(() => {
                copyBtn.innerHTML = originalHTML;
              }, 2000);
            } catch (err) {
              console.error('Ошибка копирования (fallback):', err);
            }
            document.body.removeChild(textarea);
            return;
          }
          
          navigator.clipboard.writeText(errorText).then(() => {
            const originalHTML = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i class="bi bi-check"></i> Скопировано';
            setTimeout(() => {
              copyBtn.innerHTML = originalHTML;
            }, 2000);
          }).catch(err => {
            console.error('Ошибка копирования:', err);
          });
        });
      }
    }
    
    // Уведомления НЕ исчезают автоматически - пользователь закрывает их сам
    // Это позволяет прочитать и скопировать ошибку
  }

  /**
   * Показ всплывающих сообщений (Flash messages)
   * @param {string} type - 'success', 'error', 'warning', 'info'
   * @param {string} message - Текст сообщения
   */
  static showFlashMessage(type, message) {
    // Маппинг типов для Bootstrap alert классов
    const typeMap = {
      'success': 'success',
      'error': 'danger',
      'warning': 'warning',
      'info': 'info'
    };
    
    const bsType = typeMap[type] || 'info';
    this.showNotification(message, bsType);
  }
}

// Отдельные экспорты функций для удобства импорта
export const populateParentSelect = Utils.populateParentSelect.bind(Utils);
export const closeModalById = Utils.closeModalById.bind(Utils);
export const apiRequest = Utils.apiRequest.bind(Utils);
export const formatDate = Utils.formatDate.bind(Utils);
export const showNotification = Utils.showNotification.bind(Utils);