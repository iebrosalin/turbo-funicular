import { Utils } from './modules/utils.js';

export class FilterBuilder {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            mode: options.mode || 'dashboard',
            onApply: options.onApply || (() => {}),
            onCheck: options.onCheck || (() => {}),
            initialRules: options.initialRules || [],
            ...options
        };
        this.schema = [];
        this.inputElement = null;
        this.suggestionsBox = null;
        this.errorElement = null;
        this.selectedSuggestionIndex = -1;
        this.suggestions = [];
        this.rules = []; // Для режима визуальных правил
        
        this.init();
    }
    
    async init() {
        await this.loadSchema();
        this.render();
        this.attachEvents();
        
        // Если есть начальные правила, загружаем их
        if (this.options.initialRules && this.options.initialRules.length > 0) {
            this.rules = this.options.initialRules;
            if (this.options.mode === 'modal') {
                this.renderRules();
            }
        }
    }

    async loadSchema() {
        // Проверка кэша сессии
        const cached = sessionStorage.getItem('asset_schema');
        if (cached) {
            this.schema = JSON.parse(cached);
            return;
        }

        try {
            const response = await Utils.apiRequest('/api/assets/schema');
            this.schema = response.schema || [];
            sessionStorage.setItem('asset_schema', JSON.stringify(this.schema));
        } catch (e) {
            console.error('Failed to load asset schema', e);
            // Fallback схема
            this.schema = [
                { field: 'ip', type: 'string', label: 'IP Address' },
                { field: 'hostname', type: 'string', label: 'Hostname' },
                { field: 'os', type: 'string', label: 'OS' },
                { field: 'ports', type: 'integer', label: 'Ports' },
                { field: 'mac_address', type: 'string', label: 'MAC Address' },
                { field: 'vendor', type: 'string', label: 'Vendor' },
                { field: 'source', type: 'string', label: 'Source' },
                { field: 'group_id', type: 'integer', label: 'Group ID' },
                { field: 'status', type: 'string', label: 'Status' },
                { field: 'notes', type: 'text', label: 'Notes' }
            ];
        }
    }

    render() {
        if (this.options.mode === 'modal') {
            // Режим для модального окна группы - визуальный конструктор правил
            this.container.innerHTML = `
                <div class="filter-rules-container">
                    <div class="filter-rules mb-3" id="filter-rules-list"></div>
                    <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-rule">
                        <i class="bi bi-plus-lg me-1"></i>Добавить правило
                    </button>
                </div>
            `;
            this.rulesContainer = this.container.querySelector('#filter-rules-list');
            this.btnAddRule = this.container.querySelector('#btn-add-rule');
        } else {
            // Режим dashboard - текстовый конструктор запросов
            this.container.innerHTML = `
                <div class="query-builder-wrapper position-relative">
                    <label class="form-label small fw-bold text-muted mb-1">
                        <i class="bi bi-terminal-fill me-1"></i>Конструктор запросов (SQL-like)
                    </label>
                    <div class="input-group has-validation">
                        <span class="input-group-text bg-body-tertiary border-end-0">
                            <i class="bi bi-braces-asterisk text-primary"></i>
                        </span>
                        <input type="text" 
                               id="qb-input" 
                               class="form-control border-start-0 font-monospace shadow-none" 
                               placeholder='Пример: (ip = "192.168.1.1" OR hostname LIKE "%web%") AND ports IN [80, 443]'
                               autocomplete="off" 
                               spellcheck="false"
                               aria-describedby="qb-error">
                    </div>
                    <div id="qb-suggestions" class="position-absolute bg-white border shadow-sm rounded mt-1 d-none" 
                         style="z-index: 1055; max-height: 250px; overflow-y: auto; width: 100%; font-size: 0.9rem;"></div>
                    <div id="qb-error" class="invalid-feedback d-block mt-1 small" style="display: none;"></div>
                    <div class="form-text small mt-2">
                        <span class="badge bg-light text-dark border me-1">AND</span>
                        <span class="badge bg-light text-dark border me-1">OR</span>
                        <span class="badge bg-light text-dark border me-1">()</span>
                        Операторы: <code>=</code>, <code>!=</code>, <code>LIKE</code>, <code>IN [...]</code>, <code>REG_MATCH</code>
                    </div>
                </div>
            `;
            this.inputElement = this.container.querySelector('#qb-input');
            this.suggestionsBox = this.container.querySelector('#qb-suggestions');
            this.errorElement = this.container.querySelector('#qb-error');
        }
    }

    attachEvents() {
        if (this.options.mode === 'modal') {
            // Обработчик для режима модального окна (визуальные правила)
            if (this.btnAddRule) {
                this.btnAddRule.addEventListener('click', () => this.addRuleRow());
            }
            
            // Делегирование событий для кнопок удаления правил
            if (this.rulesContainer) {
                this.rulesContainer.addEventListener('click', (e) => {
                    const btnRemove = e.target.closest('.btn-remove-rule');
                    if (btnRemove) {
                        const ruleRow = btnRemove.closest('.filter-rule-row');
                        if (ruleRow) {
                            ruleRow.remove();
                            this.updateRulesFromDOM();
                        }
                    }
                });
                
                // Обработчики изменений в полях правил
                this.rulesContainer.addEventListener('change', (e) => {
                    if (e.target.classList.contains('rule-field') || 
                        e.target.classList.contains('rule-op') || 
                        e.target.classList.contains('rule-value')) {
                        this.updateRulesFromDOM();
                    }
                });
            }
        } else {
            // Обработчик для режима dashboard (текстовый запрос)
            if (!this.inputElement) return;
            
            this.inputElement.addEventListener('input', (e) => this.handleInput(e));
            this.inputElement.addEventListener('keydown', (e) => this.handleKeydown(e));
            this.inputElement.addEventListener('click', () => this.handleInput({ target: this.inputElement }));
            this.inputElement.addEventListener('blur', () => setTimeout(() => this.hideSuggestions(), 200));

            // Обработка кликов по подсказкам (mousedown чтобы сработал до blur)
            if (this.suggestionsBox) {
                this.suggestionsBox.addEventListener('mousedown', (e) => {
                    const item = e.target.closest('.suggestion-item');
                    if (item) {
                        e.preventDefault();
                        this.selectSuggestion(item.dataset.value);
                    }
                });
            }
        }
    }
    
    /**
     * Добавить строку правила в визуальном конструкторе
     */
    addRuleRow(ruleData = {}) {
        if (!this.rulesContainer) return;
        
        const field = ruleData.field || '';
        const op = ruleData.operation || ruleData.op || 'eq';
        const value = ruleData.value || '';
        
        const row = document.createElement('div');
        row.className = 'filter-rule-row mb-2 d-flex align-items-center gap-2';
        row.innerHTML = `
            <select class="form-select form-select-sm rule-field" style="max-width: 180px;">
                ${this.schema.map(s => `<option value="${s.field}" ${s.field === field ? 'selected' : ''}>${s.label || s.field}</option>`).join('')}
            </select>
            <select class="form-select form-select-sm rule-op" style="max-width: 120px;">
                <option value="eq" ${op === 'eq' ? 'selected' : ''}>=</option>
                <option value="neq" ${op === 'neq' ? 'selected' : ''}>≠</option>
                <option value="contains" ${op === 'contains' ? 'selected' : ''}>содержит</option>
                <option value="in" ${op === 'in' ? 'selected' : ''}>в списке</option>
            </select>
            <input type="text" class="form-control form-control-sm rule-value flex-grow-1" value="${value}" placeholder="Значение">
            <button type="button" class="btn btn-outline-danger btn-sm btn-remove-rule">×</button>
        `;
        
        this.rulesContainer.appendChild(row);
        this.updateRulesFromDOM();
    }
    
    /**
     * Отрисовать все правила из массива rules
     */
    renderRules() {
        if (!this.rulesContainer) return;
        this.rulesContainer.innerHTML = '';
        this.rules.forEach(rule => this.addRuleRow(rule));
    }
    
    /**
     * Обновить массив rules на основе DOM элементов
     */
    updateRulesFromDOM() {
        if (!this.rulesContainer) return;
        
        this.rules = [];
        this.rulesContainer.querySelectorAll('.filter-rule-row').forEach(row => {
            const field = row.querySelector('.rule-field')?.value || '';
            const op = row.querySelector('.rule-op')?.value || 'eq';
            const value = row.querySelector('.rule-value')?.value || '';
            
            if (field && value) {
                this.rules.push({ field, operation: op, value });
            }
        });
    }
    
    /**
     * Получить текущие правила
     */
    getRules() {
        if (this.options.mode === 'modal') {
            this.updateRulesFromDOM();
            return this.rules;
        } else {
            // Для текстового режима парсим запрос
            const query = this.getQuery();
            return query ? this.parseQuery(query) : [];
        }
    }
    
    /**
     * Применить фильтр (вызывает onApply callback)
     */
    apply() {
        if (this.options.mode === 'modal') {
            this.updateRulesFromDOM();
            this.options.onApply(this.rules);
        } else {
            const query = this.getQuery();
            if (this.validateSyntax(query)) {
                const rules = this.parseQuery(query);
                this.options.onApply(rules);
            }
        }
    }
    
    /**
     * Сбросить фильтр
     */
    reset() {
        if (this.options.mode === 'modal') {
            this.rules = [];
            this.renderRules();
            this.options.onApply([]);
        } else {
            this.setQuery('');
            this.options.onApply([]);
        }
    }
    
    /**
     * Парсинг текстового запроса в правила (упрощенная реализация)
     */
    parseQuery(query) {
        // Упрощенный парсер для базовых случаев
        const rules = [];
        if (!query) return rules;
        
        // Пример парсинга: ip = "192.168.1.1"
        const simpleMatch = query.match(/([a-z_]+)\s*=\s*"([^"]+)"/i);
        if (simpleMatch) {
            rules.push({ field: simpleMatch[1], operation: 'eq', value: simpleMatch[2] });
        }
        
        return rules;
    }

    handleInput(e) {
        const cursorPos = this.inputElement.selectionStart;
        const text = this.inputElement.value;
        
        // Валидация синтаксиса
        this.validateSyntax(text);

        // Определение текущего слова для подсказок
        const currentWord = this.getCurrentWord(text, cursorPos);
        
        if (currentWord.text.length >= 1) {
            this.generateSuggestions(currentWord.text, currentWord.start, cursorPos);
        } else {
            this.hideSuggestions();
        }
    }

    getCurrentWord(text, pos) {
        // Ищем начало текущего слова/токена
        let start = pos;
        while (start > 0 && !/[\s\(\)\[\],]/.test(text[start - 1])) {
            start--;
        }
        return {
            text: text.slice(start, pos),
            start: start
        };
    }

    generateSuggestions(word, startPos, cursorPos) {
        const lowerWord = word.toLowerCase();
        this.suggestions = [];
        this.selectedSuggestionIndex = -1;

        // 1. Подсказки по полям (если слово похоже на начало поля и не внутри кавычек/скобок значений)
        const prevChar = this.inputElement.value.slice(startPos - 1, startPos);
        const isValueContext = ['"', "'", '['].includes(prevChar) || /\d/.test(prevChar);
        
        if (!isValueContext && !word.includes('"') && !word.includes('[')) {
            const fieldMatches = this.schema.filter(s => s.field.toLowerCase().startsWith(lowerWord));
            fieldMatches.forEach(f => {
                this.suggestions.push({
                    value: f.field,
                    label: f.label || f.field,
                    type: 'field',
                    icon: 'bi-table'
                });
            });
        }

        // 2. Подсказки по операторам и ключевым словам
        if (!isValueContext) {
            const keywords = ['AND', 'OR', 'NOT', 'LIKE', 'IN', 'REG_MATCH', '=', '!='];
            const kwMatches = keywords.filter(k => k.toLowerCase().startsWith(lowerWord));
            kwMatches.forEach(k => {
                this.suggestions.push({
                    value: k + ' ',
                    label: k,
                    type: 'keyword',
                    icon: 'bi-sign-turn-right'
                });
            });

            // Скобки
            if ('('.startsWith(lowerWord)) {
                this.suggestions.push({ value: '( ', label: '( Открыть скобку', type: 'symbol', icon: 'bi-braces' });
            }
            if (')'.startsWith(lowerWord)) {
                this.suggestions.push({ value: ') ', label: ') Закрыть скобку', type: 'symbol', icon: 'bi-braces' });
            }
        }

        // 3. Подсказки значений для IN (если видно открывающую квадратную скобку в текущем токене)
        if (word.includes('[') || (this.inputElement.value.slice(0, startPos).endsWith('IN [') && word === '')) {
             // Упрощенная логика: предлагаем примеры портов или статусов
             if (lowerWord === '' || lowerWord === '[') {
                 this.suggestions.push({ value: '80, 443', label: 'Пример: 80, 443', type: 'value', icon: 'bi-list-ul' });
             }
        }

        if (this.suggestions.length > 0) {
            this.renderSuggestions();
        } else {
            this.hideSuggestions();
        }
    }

    renderSuggestions() {
        this.suggestionsBox.innerHTML = this.suggestions.map((s, idx) => `
            <div class="suggestion-item d-flex align-items-center px-3 py-2 ${idx === this.selectedSuggestionIndex ? 'bg-primary text-white' : 'hover-bg-light'}" 
                 data-value="${s.value}" 
                 data-index="${idx}"
                 style="cursor: pointer;">
                <i class="bi ${s.icon} me-2 opacity-75"></i>
                <span class="fw-medium">${s.label}</span>
                <span class="ms-auto small opacity-50 text-uppercase" style="font-size: 0.7em;">${s.type}</span>
            </div>
        `).join('');
        
        this.suggestionsBox.classList.remove('d-none');
        
        // Скролл к выбранному элементу
        if (this.selectedSuggestionIndex >= 0) {
            const selectedEl = this.suggestionsBox.querySelector(`[data-index="${this.selectedSuggestionIndex}"]`);
            if (selectedEl) selectedEl.scrollIntoView({ block: 'nearest' });
        }
    }

    hideSuggestions() {
        this.suggestionsBox.classList.add('d-none');
        this.suggestions = [];
        this.selectedSuggestionIndex = -1;
    }

    selectSuggestion(value) {
        const cursorPos = this.inputElement.selectionStart;
        const text = this.inputElement.value;
        const currentWord = this.getCurrentWord(text, cursorPos);
        
        // Заменяем текущее слово на выбранное значение
        const newText = text.slice(0, currentWord.start) + value + text.slice(cursorPos);
        
        this.inputElement.value = newText;
        const newCursorPos = currentWord.start + value.length;
        this.inputElement.focus();
        this.inputElement.selectionStart = newCursorPos;
        this.inputElement.selectionEnd = newCursorPos;
        
        this.hideSuggestions();
        this.validateSyntax(newText);
        
        // Если выбрали поле, можно сразу предложить оператор (опционально)
        if (value.match(/^[a-z_]+$/) && this.schema.find(s => s.field === value)) {
             // Логика авто-добавления пробела и ожидания оператора уже работает через input event
        }
    }

    handleKeydown(e) {
        if (this.suggestions.length === 0) {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.applyQuery();
            }
            return;
        }

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedSuggestionIndex = (this.selectedSuggestionIndex + 1) % this.suggestions.length;
            this.renderSuggestions();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedSuggestionIndex = (this.selectedSuggestionIndex - 1 + this.suggestions.length) % this.suggestions.length;
            this.renderSuggestions();
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            e.preventDefault();
            if (this.selectedSuggestionIndex === -1) this.selectedSuggestionIndex = 0;
            this.selectSuggestion(this.suggestions[this.selectedSuggestionIndex].value);
        } else if (e.key === 'Escape') {
            this.hideSuggestions();
        }
    }

    validateSyntax(text) {
        const openParens = (text.match(/\(/g) || []).length;
        const closeParens = (text.match(/\)/g) || []).length;
        const openBrackets = (text.match(/\[/g) || []).length;
        const closeBrackets = (text.match(/\]/g) || []).length;

        let errorMsg = null;

        if (openParens !== closeParens) {
            errorMsg = `Ошибка скобок: открыто ${openParens}, закрыто ${closeParens}`;
        } else if (openBrackets !== closeBrackets) {
            errorMsg = `Ошибка списков: открыто ${openBrackets}, закрыто ${closeBrackets}`;
        } else if (/^\s*(AND|OR)\s*/i.test(text)) {
             errorMsg = "Запрос не может начинаться с логического оператора";
        }

        if (errorMsg) {
            this.errorElement.textContent = errorMsg;
            this.errorElement.style.display = 'block';
            this.inputElement.classList.add('is-invalid');
            return false;
        } else {
            this.errorElement.style.display = 'none';
            this.inputElement.classList.remove('is-invalid');
            return true;
        }
    }

    applyQuery() {
        const query = this.inputElement.value.trim();
        if (!query) return;
        
        if (this.validateSyntax(query)) {
            this.options.onApply(query);
        }
    }

    getQuery() {
        return this.inputElement.value.trim();
    }

    setQuery(query) {
        this.inputElement.value = query;
        this.validateSyntax(query);
    }
}
