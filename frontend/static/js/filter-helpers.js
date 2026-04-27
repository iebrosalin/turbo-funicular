// static/js/filter-helpers.js
/**
 * Система умных подсказок для фильтрации активов на дашборде.
 * Представляет контекстные предложения полей и значений в зависимости от оператора.
 */

export class FilterAutocompleteManager {
  constructor() {
    this.filterFields = {
      ip: {
        label: 'IP Адрес',
        type: 'text',
        operators: ['=', '!=', 'like', 'in'],
        example: '192.168.1.10, 10.0.0.0/24',
        dynamic: false
      },
      hostname: {
        label: 'Имя хоста',
        type: 'text',
        operators: ['=', '!=', 'like', 'contains'],
        example: 'web-server-01',
        dynamic: false
      },
      fqdn: {
        label: 'FQDN',
        type: 'text',
        operators: ['=', '!=', 'like', 'endswith'],
        example: 'example.com',
        dynamic: false
      },
      os: {
        label: 'ОС (Family)',
        type: 'select',
        operators: ['=', '!=', 'in'],
        options: ['Linux', 'Windows', 'macOS', 'FreeBSD', 'Cisco IOS', 'Unknown'],
        dynamic: false
      },
      type: {
        label: 'Тип устройства',
        type: 'select',
        operators: ['=', '!=', 'in'],
        options: ['server', 'workstation', 'network_device', 'printer', 'iot', 'unknown'],
        dynamic: false
      },
      status: {
        label: 'Статус',
        type: 'select',
        operators: ['=', '!='],
        options: ['active', 'inactive', 'archived', 'maintenance'],
        dynamic: false
      },
      group: {
        label: 'Группа',
        type: 'dynamic_select',
        operators: ['in', 'not_in', '='],
        source: '/api/groups',
        valueField: 'name',
        dynamic: true
      },
      port: {
        label: 'Порт',
        type: 'number',
        operators: ['=', '!=', '>', '<', 'in'],
        example: '22, 80, 443',
        dynamic: false
      },
      dns_name: {
        label: 'DNS Имя',
        type: 'text',
        operators: ['like', 'contains', '=', 'endswith'],
        example: 'mail.example.com',
        dynamic: false
      },
      dns_record_type: {
        label: 'Тип DNS записи',
        type: 'select',
        operators: ['contains', '='],
        options: ['A', 'AAAA', 'MX', 'TXT', 'NS', 'CNAME', 'SOA', 'PTR', 'SRV'],
        dynamic: false
      },
      owner: {
        label: 'Владелец',
        type: 'text',
        operators: ['like', '=', 'contains'],
        dynamic: false
      },
      location: {
        label: 'Локация',
        type: 'text',
        operators: ['like', '=', 'contains'],
        dynamic: false
      }
    };

    this.currentSuggestions = [];
    this.selectedIndex = -1;
    this.activeInput = null;
    this.suggestionBox = null;
    this.cache = {};
  }

  /**
   * Инициализация автодополнения для поля фильтра
   * @param {HTMLInputElement} inputElement - Поле ввода
   */
  init(inputElement) {
    if (!inputElement) return;
    this.activeInput = inputElement;

    // Создание контейнера подсказок
    if (!this.suggestionBox) {
      this.suggestionBox = document.createElement('div');
      this.suggestionBox.className = 'autocomplete-suggestions';
      this.suggestionBox.style.cssText = `
        position: absolute;
        background: white;
        border: 1px solid #ccc;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        max-height: 300px;
        overflow-y: auto;
        z-index: 1050;
        display: none;
        font-size: 0.9rem;
      `;
      document.body.appendChild(this.suggestionBox);

      // Закрытие при клике вне
      document.addEventListener('click', (e) => {
        if (!this.suggestionBox.contains(e.target) && e.target !== inputElement) {
          this.hide();
        }
      });
      
      // Скрытие при скролле
      window.addEventListener('scroll', () => this.hide(), true);
    }

    // Обработчики событий
    inputElement.addEventListener('input', (e) => this.#handleInput(e));
    inputElement.addEventListener('keydown', (e) => this.#handleKeydown(e));
    inputElement.addEventListener('focus', () => {
      if (inputElement.value.trim().length > 0) {
        this.#handleInput({ target: inputElement });
      } else {
        // Показать подсказку по полям при фокусе на пустом поле
        this.#showFieldSuggestions(inputElement);
      }
    });
  }

  /**
   * Обработка ввода текста
   */
  #handleInput(e) {
    const input = e.target;
    const value = input.value.trim();
    
    if (!value) {
      this.#showFieldSuggestions(input);
      return;
    }

    // Анализ текущей стадии ввода: "поле:оператор:значение"
    const parts = this.#parseFilterQuery(value);
    
    if (!parts.field) {
      // Ввод имени поля
      this.#showFieldSuggestions(input, parts.rawField);
    } else if (!parts.operator) {
      // Поле выбрано, ввод оператора
      this.#showOperatorSuggestions(input, parts.field);
    } else {
      // Ввод значения
      this.#showValueSuggestions(input, parts.field, parts.operator, parts.rawValue);
    }
  }

  /**
   * Парсинг строки запроса
   */
  #parseFilterQuery(query) {
    const regex = /^([a-zA-Z_]+)\s*(=|!=|:|like|contains|>|<|in|not_in|\[\])?\s*(.*)$/i;
    const match = query.match(regex);

    if (match) {
      const fieldName = match[1].toLowerCase();
      let normalizedField = fieldName;
      if (fieldName.endsWith('s') && !['status', 'dns'].includes(fieldName)) {
        if (this.filterFields[fieldName.slice(0, -1)]) {
          normalizedField = fieldName.slice(0, -1);
        }
      }
      
      if (this.filterFields[normalizedField] || Object.keys(this.filterFields).some(k => k.startsWith(normalizedField))) {
        return {
          rawField: match[1],
          field: normalizedField,
          operator: match[2] || null,
          rawValue: match[3] || ''
        };
      }
    }
    
    return { rawField: query, field: null, operator: null, rawValue: '' };
  }

  /**
   * Показ подсказок по именам полей
   */
  #showFieldSuggestions(input, query = '') {
    const queryLower = query.toLowerCase();
    const suggestions = Object.keys(this.filterFields)
      .filter(key => this.filterFields[key].label.toLowerCase().includes(queryLower) || key.includes(queryLower))
      .map(key => ({
        key: key,
        label: this.filterFields[key].label,
        type: 'field',
        desc: `Пример: ${key}=${this.filterFields[key].example || '...'}`
      }))
      .slice(0, 8);

    this.#renderSuggestions(suggestions, input, (item) => {
      input.value = `${item.key}:`;
      input.focus();
      this.#handleInput({ target: input });
    });
  }

  /**
   * Показ подсказок операторов
   */
  #showOperatorSuggestions(input, fieldName) {
    const fieldConfig = this.filterFields[fieldName];
    if (!fieldConfig) return;

    const suggestions = fieldConfig.operators.map(op => ({
      key: op,
      label: this.#getOperatorLabel(op),
      type: 'operator',
      desc: `Синтаксис: ${fieldName}${op}...`
    }));

    this.#renderSuggestions(suggestions, input, (item) => {
      const currentVal = input.value;
      const base = currentVal.split(/[:=!=<>]/)[0];
      input.value = `${base}${item.key}`;
      input.focus();
      this.#handleInput({ target: input });
    });
  }

  /**
   * Показ подсказок значений
   */
  async #showValueSuggestions(input, fieldName, operator, query) {
    const fieldConfig = this.filterFields[fieldName];
    if (!fieldConfig) return;

    let suggestions = [];

    // Статические опции
    if (fieldConfig.options) {
      suggestions = fieldConfig.options
        .filter(opt => opt.toLowerCase().includes(query.toLowerCase()))
        .map(opt => ({ key: opt, label: opt, type: 'value' }));
    } 
    // Динамические опции (Группы и т.д.)
    else if (fieldConfig.dynamic) {
      const data = await this.#fetchDynamicData(fieldConfig.source);
      suggestions = data
        .filter(item => {
          const val = item[fieldConfig.valueField] || item.name || item.toString();
          return val.toLowerCase().includes(query.toLowerCase());
        })
        .map(item => {
          const val = item[fieldConfig.valueField] || item.name;
          return { key: val, label: val, type: 'value', desc: item.description || '' };
        });
    } 
    // Текстовые/Числовые поля (примеры)
    else {
      if (query.length < 1) {
        suggestions = [{ key: fieldConfig.example, label: `Пример: ${fieldConfig.example}`, type: 'example' }];
      } else {
        suggestions = [{ key: query, label: `Значение "${query}"`, type: 'value' }];
      }
    }

    this.#renderSuggestions(suggestions.slice(0, 8), input, (item) => {
      const parts = this.#parseFilterQuery(input.value);
      let finalVal = `${parts.field}${parts.operator}${item.key}`;
      input.value = finalVal;
      this.hide();
    });
  }

  /**
   * Получение динамических данных с кэшированием
   */
  async #fetchDynamicData(url) {
    if (this.cache[url]) return this.cache[url];
    
    try {
      const resp = await fetch(url);
      if (resp.ok) {
        const data = await resp.json();
        this.cache[url] = data;
        return data;
      }
    } catch (e) {
      console.error('Ошибка загрузки данных для подсказок:', e);
    }
    return [];
  }

  /**
   * Отрисовка подсказок
   */
  #renderSuggestions(items, input, onSelect) {
    this.currentSuggestions = items.map(i => ({...i, onSelect}));
    this.selectedIndex = -1;
    
    if (!this.suggestionBox || items.length === 0) {
      this.hide();
      return;
    }

    this.suggestionBox.innerHTML = '';
    
    items.forEach((item, idx) => {
      const div = document.createElement('div');
      div.className = 'autocomplete-item';
      div.style.cssText = `
        padding: 8px 12px;
        cursor: pointer;
        border-bottom: 1px solid #f0f0f0;
        display: flex;
        flex-direction: column;
      `;
      if (idx === this.selectedIndex) div.style.backgroundColor = '#e3f2fd';
      
      div.onmouseover = () => { this.selectedIndex = idx; this.#renderSuggestions(items, input, onSelect); };
      div.onclick = () => { item.onSelect(item); };

      let icon = '🔹';
      if (item.type === 'field') icon = '🏷️';
      if (item.type === 'operator') icon = '⚙️';
      if (item.type === 'value') icon = '✅';
      if (item.type === 'example') icon = '💡';

      div.innerHTML = `
        <div><strong>${icon} ${item.label}</strong></div>
        ${item.desc ? `<small style="color:#666; font-size:0.85em">${item.desc}</small>` : ''}
      `;
      this.suggestionBox.appendChild(div);
    });

    // Позиционирование
    const rect = input.getBoundingClientRect();
    this.suggestionBox.style.top = `${rect.bottom + window.scrollY + 2}px`;
    this.suggestionBox.style.left = `${rect.left + window.scrollX}px`;
    this.suggestionBox.style.width = `${Math.max(rect.width, 300)}px`;
    this.suggestionBox.style.display = 'block';
  }

  hide() {
    if (this.suggestionBox) this.suggestionBox.style.display = 'none';
    this.currentSuggestions = [];
    this.selectedIndex = -1;
  }

  #handleKeydown(e) {
    if (!this.suggestionBox || this.suggestionBox.style.display === 'none') return;
    
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.selectedIndex = (this.selectedIndex + 1) % this.currentSuggestions.length;
      const items = this.suggestionBox.querySelectorAll('.autocomplete-item');
      items.forEach((el, i) => el.style.backgroundColor = i === this.selectedIndex ? '#e3f2fd' : 'white');
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.selectedIndex = (this.selectedIndex - 1 + this.currentSuggestions.length) % this.currentSuggestions.length;
      const items = this.suggestionBox.querySelectorAll('.autocomplete-item');
      items.forEach((el, i) => el.style.backgroundColor = i === this.selectedIndex ? '#e3f2fd' : 'white');
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (this.selectedIndex >= 0 && this.currentSuggestions[this.selectedIndex]) {
        this.currentSuggestions[this.selectedIndex].onSelect(this.currentSuggestions[this.selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      this.hide();
    }
  }

  #getOperatorLabel(op) {
    const map = {
      '=': 'Равно',
      '!=': 'Не равно',
      ':': 'Содержит (Like)',
      'like': 'Похоже на',
      'contains': 'Содержит подстроку',
      '>': 'Больше',
      '<': 'Меньше',
      'in': 'В списке',
      'not_in': 'Не в списке',
      '[]': 'В диапазоне'
    };
    return map[op] || op;
  }
}