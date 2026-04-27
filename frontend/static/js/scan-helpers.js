// static/js/scan-helpers.js
/**
 * Система умных подсказок для форм сканирования (Nmap, Rustscan, Dig)
 * Предоставляет контекстные подсказки аргументов, групп, активов и примеров
 */

import { apiRequest } from './modules/utils.js';

/**
 * Класс управления автодополнением для сканов
 */
export class ScanAutocompleteManager {
  constructor() {
    this.knowledgeBase = {
      nmap: {
        args: [
          { value: '-sS', label: 'TCP SYN Scan', type: 'arg', desc: 'Скрытное сканирование (полусоединение)' },
          { value: '-sT', label: 'TCP Connect Scan', type: 'arg', desc: 'Полное TCP соединение' },
          { value: '-sU', label: 'UDP Scan', type: 'arg', desc: 'Сканирование UDP портов' },
          { value: '-sV', label: 'Version Detection', type: 'arg', desc: 'Определение версий сервисов' },
          { value: '-O', label: 'OS Detection', type: 'arg', desc: 'Определение операционной системы' },
          { value: '-A', label: 'Aggressive Scan', type: 'arg', desc: 'OS + Version + Script + Traceroute' },
          { value: '-p-', label: 'All Ports', type: 'arg', desc: 'Сканировать все 65535 портов' },
          { value: '--top-ports 1000', label: 'Top 1000 Ports', type: 'arg', desc: 'Сканировать топ-1000 портов' },
          { value: '-T4', label: 'Timing T4', type: 'arg', desc: 'Агрессивный тайминг (быстрее)' },
          { value: '-T2', label: 'Timing T2', type: 'arg', desc: 'Вежливый тайминг (медленнее)' },
          { value: '--script=default', label: 'Default Scripts', type: 'arg', desc: 'Запуск скриптов по умолчанию' },
          { value: '--script=vuln', label: 'Vuln Scripts', type: 'arg', desc: 'Скрипты поиска уязвимостей' },
          { value: '-oN output.txt', label: 'Normal Output', type: 'arg', desc: 'Сохранить в обычном формате' },
          { value: '-oX output.xml', label: 'XML Output', type: 'arg', desc: 'Сохранить в XML формате' },
          { value: '-Pn', label: 'No Ping', type: 'arg', desc: 'Пропустить проверку доступности хоста' }
        ]
      },
      rustscan: {
        args: [
          { value: '-a', label: 'Address', type: 'arg', desc: 'IP адрес или диапазон (обязательно)' },
          { value: '-p', label: 'Ports', type: 'arg', desc: 'Диапазон портов (например, 1-1000)' },
          { value: '--top', label: 'Top Ports', type: 'arg', desc: 'Топ N портов (например, --top 1000)' },
          { value: '-t', label: 'Threads', type: 'arg', desc: 'Количество потоков (по умолчанию 2500)' },
          { value: '--batch-size', label: 'Batch Size', type: 'arg', desc: 'Размер пакета для сканирования' },
          { value: '--timeout', label: 'Timeout', type: 'arg', desc: 'Таймаут в миллисекундах' },
          { value: '--tries', label: 'Retries', type: 'arg', desc: 'Количество попыток' },
          { value: '--grepable', label: 'Grepable Output', type: 'arg', desc: 'Вывод в формате для grep' },
          { value: '--no-nmap', label: 'Skip Nmap', type: 'arg', desc: 'Не запускать Nmap после сканирования' },
          { value: '-- -sC -sV', label: 'Nmap Args', type: 'arg', desc: 'Аргументы для последующего Nmap (после --)' }
        ]
      },
      dig: {
        args: [
          { value: '@8.8.8.8', label: 'Custom DNS', type: 'arg', desc: 'Использовать указанный DNS сервер' },
          { value: '@1.1.1.1', label: 'Cloudflare DNS', type: 'arg', desc: 'Использовать DNS Cloudflare' },
          { value: '@77.88.8.8', label: 'Yandex DNS', type: 'arg', desc: 'Использовать DNS Яндекса' },
          { value: 'ANY', label: 'Any Record', type: 'arg', desc: 'Запрос всех типов записей' },
          { value: 'A', label: 'A Record', type: 'arg', desc: 'IPv4 адрес' },
          { value: 'AAAA', label: 'AAAA Record', type: 'arg', desc: 'IPv6 адрес' },
          { value: 'MX', label: 'MX Record', type: 'arg', desc: 'Почтовые сервера' },
          { value: 'TXT', label: 'TXT Record', type: 'arg', desc: 'Текстовые записи (SPF, DKIM)' },
          { value: 'NS', label: 'NS Record', type: 'arg', desc: 'Сервера имен' },
          { value: 'CNAME', label: 'CNAME Record', type: 'arg', desc: 'Псевдонимы доменов' },
          { value: 'SOA', label: 'SOA Record', type: 'arg', desc: 'Информация о зоне' },
          { value: 'PTR', label: 'PTR Record', type: 'arg', desc: 'Обратное разрешение (IP -> Domain)' },
          { value: 'SRV', label: 'SRV Record', type: 'arg', desc: 'Сервисные записи' },
          { value: '+short', label: 'Short Output', type: 'arg', desc: 'Краткий вывод' },
          { value: '+noall +answer', label: 'Answer Only', type: 'arg', desc: 'Показать только ответ' },
          { value: '+trace', label: 'Trace', type: 'arg', desc: 'Трассировка разрешения от корня' }
        ]
      }
    };

    this.currentSuggestions = [];
    this.selectedIndex = -1;
    this.activeInput = null;
    this.suggestionBox = null;
  }

  /**
   * Инициализация автодополнения для поля ввода
   * @param {HTMLInputElement} inputElement - Поле ввода
   * @param {string} scanType - Тип сканера (nmap, rustscan, dig)
   */
  init(inputElement, scanType) {
    if (!inputElement || !this.knowledgeBase[scanType]) return;

    this.activeInput = inputElement;
    
    // Создаем контейнер подсказок, если его нет
    if (!this.suggestionBox) {
      this.suggestionBox = document.createElement('div');
      this.suggestionBox.className = 'autocomplete-suggestions';
      this.suggestionBox.style.cssText = `
        position: absolute;
        background: white;
        border: 1px solid #ddd;
        border-radius: 4px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        max-height: 300px;
        overflow-y: auto;
        z-index: 1000;
        display: none;
        width: ${inputElement.offsetWidth}px;
      `;
      document.body.appendChild(this.suggestionBox);
      
      // Закрытие при клике вне
      document.addEventListener('click', (e) => {
        if (!this.suggestionBox.contains(e.target) && e.target !== inputElement) {
          this.hide();
        }
      });
    }

    // Обработчики событий
    inputElement.addEventListener('input', (e) => this.#handleInput(e));
    inputElement.addEventListener('keydown', (e) => this.#handleKeydown(e));
    inputElement.addEventListener('focus', () => {
      if (inputElement.value.length > 0) {
        this.#handleInput({ target: inputElement });
      }
    });
    
    // Обновление ширины при ресайзе окна
    window.addEventListener('resize', () => {
      if (this.suggestionBox && this.activeInput === inputElement) {
        this.suggestionBox.style.width = `${inputElement.offsetWidth}px`;
      }
    });
  }

  /**
   * Обработка ввода текста
   */
  #handleInput(e) {
    const input = e.target;
    const value = input.value;
    const scanType = input.dataset.scanType || 'nmap';
    
    if (!value || value.length < 1) {
      this.hide();
      return;
    }

    // Определяем контекст (аргумент, группа, актив, IP)
    const context = this.#detectContext(value, scanType);
    
    // Получаем подсказки на основе контекста
    const suggestions = this.#getSuggestions(context, scanType);
    
    if (suggestions.length > 0) {
      this.#showSuggestions(suggestions, input);
    } else {
      this.hide();
    }
  }

  /**
   * Определение контекста ввода
   */
  #detectContext(value, scanType) {
    const trimmed = value.trim();
    
    // Если начинается с @, это DNS сервер для dig
    if (scanType === 'dig' && trimmed.startsWith('@')) {
      return { type: 'dns_server', value: trimmed };
    }
    
    // Если содержит пробелы, проверяем последние слова
    const parts = trimmed.split(/\s+/);
    const lastPart = parts[parts.length - 1];
    const previousPart = parts.length > 1 ? parts[parts.length - 2] : '';
    
    // Проверка на аргументы
    if (lastPart.startsWith('-') || lastPart.startsWith('--') || lastPart.startsWith('@')) {
      return { type: 'arg', value: lastPart };
    }
    
    // Проверка на IP/CIDR
    if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(\/\d{1,2})?$/.test(lastPart)) {
      return { type: 'ip', value: lastPart };
    }
    
    // Проверка на домен
    if (/^[a-zA-Z0-9][a-zA-Z0-9\-\.]*\.[a-zA-Z]{2,}$/.test(lastPart)) {
      return { type: 'domain', value: lastPart };
    }
    
    // Если предыдущее слово было аргументом, требующим значения
    if (previousPart.startsWith('-') && !previousPart.startsWith('--')) {
      // Простые флаги без значений
      const noValueArgs = ['-sS', '-sT', '-sU', '-sV', '-O', '-A', '-Pn', '-n', '--top-ports', '--top'];
      if (!noValueArgs.some(arg => previousPart.includes(arg))) {
        return { type: 'arg_value', arg: previousPart, value: lastPart };
      }
    }
    
    // По умолчанию ищем аргументы
    return { type: 'arg', value: lastPart };
  }

  /**
   * Получение списка подсказок
   */
  #getSuggestions(context, scanType) {
    const base = this.knowledgeBase[scanType];
    if (!base) return [];
    
    let suggestions = [];
    
    if (context.type === 'arg' || context.type === 'arg_value') {
      // Фильтрация аргументов
      const query = context.value.toLowerCase();
      suggestions = base.args
        .filter(item => item.value.toLowerCase().includes(query) || item.label.toLowerCase().includes(query))
        .slice(0, 10);
    } else if (context.type === 'dns_server') {
      // Подсказки DNS серверов для dig
      const dnsServers = [
        { value: '@8.8.8.8', label: 'Google DNS', type: 'arg', desc: 'Публичный DNS Google' },
        { value: '@1.1.1.1', label: 'Cloudflare DNS', type: 'arg', desc: 'Публичный DNS Cloudflare' },
        { value: '@77.88.8.8', label: 'Yandex DNS', type: 'arg', desc: 'Публичный DNS Яндекса' }
      ];
      const query = context.value.toLowerCase();
      suggestions = dnsServers.filter(s => s.value.toLowerCase().includes(query)).slice(0, 5);
    } else if (context.type === 'ip' || context.type === 'domain') {
      // Динамическая подгрузка активов и групп (через API)
      // Здесь можно добавить fetch запрос к API для получения реальных данных
      // Для примера возвращаем заглушки
      suggestions = [
        { value: '192.168.1.1', label: 'Локальный шлюз', type: 'ip', desc: 'Пример IP' },
        { value: 'example.com', label: 'Пример домена', type: 'domain', desc: 'Пример домена' }
      ].filter(s => s.value.toLowerCase().includes(context.value.toLowerCase())).slice(0, 5);
    }
    
    // Добавляем примеры использования
    if (context.type === 'arg' && context.value === '') {
      suggestions.push({ value: '--help', label: 'Show Help', type: 'example', desc: 'Показать справку' });
    }
    
    return suggestions;
  }

  /**
   * Отображение подсказок
   */
  #showSuggestions(suggestions, inputElement) {
    this.currentSuggestions = suggestions;
    this.selectedIndex = -1;
    
    if (!this.suggestionBox) return;
    
    this.suggestionBox.innerHTML = '';
    
    suggestions.forEach((item, index) => {
      const div = document.createElement('div');
      div.className = 'autocomplete-item';
      div.dataset.index = index;
      div.style.cssText = `
        padding: 8px 12px;
        cursor: pointer;
        border-bottom: 1px solid #f0f0f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      `;
      div.onmouseover = () => this.#selectItem(index);
      div.onclick = () => this.#applySuggestion(index);
      
      // Иконка типа подсказки
      let icon = '📝';
      if (item.type === 'arg') icon = '⚙️';
      if (item.type === 'ip') icon = '🌐';
      if (item.type === 'domain') icon = '🔗';
      if (item.type === 'group') icon = '📁';
      if (item.type === 'asset') icon = '💻';
      if (item.type === 'example') icon = '💡';
      
      div.innerHTML = `
        <span><strong>${icon} ${item.value}</strong> <small style="color: #666;">${item.label}</small></span>
        <small style="color: #999; font-size: 0.8em;">${item.desc || ''}</small>
      `;
      
      this.suggestionBox.appendChild(div);
    });
    
    // Позиционирование
    const rect = inputElement.getBoundingClientRect();
    this.suggestionBox.style.top = `${rect.bottom + window.scrollY + 2}px`;
    this.suggestionBox.style.left = `${rect.left + window.scrollX}px`;
    this.suggestionBox.style.width = `${rect.width}px`;
    this.suggestionBox.style.display = 'block';
  }

  /**
   * Скрытие подсказок
   */
  hide() {
    if (this.suggestionBox) {
      this.suggestionBox.style.display = 'none';
    }
    this.currentSuggestions = [];
    this.selectedIndex = -1;
  }

  /**
   * Выбор элемента клавиатурой
   */
  #selectItem(index) {
    this.selectedIndex = index;
    const items = this.suggestionBox.querySelectorAll('.autocomplete-item');
    items.forEach((item, i) => {
      if (i === index) {
        item.style.backgroundColor = '#e3f2fd';
      } else {
        item.style.backgroundColor = 'white';
      }
    });
  }

  /**
   * Применение выбранной подсказки
   */
  #applySuggestion(index) {
    if (index < 0 || index >= this.currentSuggestions.length || !this.activeInput) return;
    
    const suggestion = this.currentSuggestions[index];
    const input = this.activeInput;
    const value = input.value;
    
    // Заменяем последнее введенное слово на подсказку
    const parts = value.split(/\s+/);
    const lastPart = parts[parts.length - 1];
    
    // Если это аргумент с дефисом, заменяем точно
    if (lastPart.startsWith('-') || lastPart.startsWith('@')) {
      parts[parts.length - 1] = suggestion.value;
    } else {
      // Иначе просто добавляем
      if (value.endsWith(' ') || value === '') {
        parts.push(suggestion.value);
      } else {
        parts[parts.length - 1] = suggestion.value;
      }
    }
    
    input.value = parts.join(' ');
    this.hide();
    input.focus();
    
    // Событие для обновления состояния (если нужно)
    input.dispatchEvent(new Event('input'));
  }

  /**
   * Обработка нажатий клавиш
   */
  #handleKeydown(e) {
    if (!this.suggestionBox || this.suggestionBox.style.display === 'none') return;
    
    const itemsCount = this.currentSuggestions.length;
    
    switch(e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.selectedIndex = (this.selectedIndex + 1) % itemsCount;
        this.#selectItem(this.selectedIndex);
        break;
      case 'ArrowUp':
        e.preventDefault();
        this.selectedIndex = (this.selectedIndex - 1 + itemsCount) % itemsCount;
        this.#selectItem(this.selectedIndex);
        break;
      case 'Enter':
        e.preventDefault();
        if (this.selectedIndex >= 0) {
          this.#applySuggestion(this.selectedIndex);
        } else {
          this.hide();
        }
        break;
      case 'Escape':
        this.hide();
        break;
    }
  }
}

// Экспорт синглтона
export const scanAutocomplete = new ScanAutocompleteManager();
