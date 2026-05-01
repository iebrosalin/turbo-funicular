/**
 * FilterBuilder - Единый модуль конструктора фильтров
 * Используется на дашборде и в модальных окнах динамических групп
 */

class FilterBuilder {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container #${containerId} not found`);
            return;
        }

        this.options = {
            mode: options.mode || 'dashboard', // 'dashboard' | 'modal'
            onApply: options.onApply || null,  // Callback для применения
            onTest: options.onTest || null,    // Callback для теста
            initialRules: options.initialRules || []
        };

        this.rules = [...this.options.initialRules];
        this.fields = [
            { id: 'ip', label: 'IP Адрес', type: 'text' },
            { id: 'hostname', label: 'Hostname', type: 'text' },
            { id: 'os', label: 'ОС', type: 'text' },
            { id: 'ports', label: 'Порты', type: 'text' },
            { id: 'group_id', label: 'Группа', type: 'select', options: [] }, // Заполняется динамически
            { id: 'source', label: 'Источник', type: 'select', options: [
                { value: 'manual', label: 'Ручной' },
                { value: 'scanning', label: 'Сканирование' }
            ]},
            { id: 'status', label: 'Статус', type: 'select', options: [
                { value: 'active', label: 'Активен' },
                { value: 'inactive', label: 'Неактивен' }
            ]}
        ];

        this.operations = [
            { value: 'eq', label: '=' },
            { value: 'neq', label: '≠' },
            { value: 'contains', label: 'Содержит' },
            { value: 'in', label: 'В списке' }
        ];

        this.init();
    }

    init() {
        this.render();
        this.attachEvents();
        
        // Если есть начальные правила, рендерим их
        if (this.rules.length > 0) {
            this.rules.forEach(rule => this.addRuleRow(rule));
        } else {
            this.addRuleRow(); // Добавить одно пустое правило по умолчанию
        }

        // Загрузить список групп для фильтра
        this.loadGroups();
    }

    async loadGroups() {
        try {
            const groups = await Utils.apiRequest('/api/groups');
            const groupField = this.fields.find(f => f.id === 'group_id');
            if (groupField) {
                groupField.options = groups.map(g => ({ value: g.id.toString(), label: g.name }));
                // Перерисовать существующие селекты групп если они уже есть
                this.container.querySelectorAll('select[data-field="group_id"]').forEach(select => {
                    const currentVal = select.value;
                    select.innerHTML = '<option value="">Выберите группу</option>' + 
                        groupField.options.map(o => `<option value="${o.value}">${o.label}</option>`).join('');
                    if (currentVal) select.value = currentVal;
                });
            }
        } catch (e) {
            console.error('Failed to load groups for filter', e);
        }
    }

    render() {
        this.container.innerHTML = `
            <div class="filter-rules mb-3">
                <!-- Сюда добавляются строки правил -->
            </div>
            <div class="d-flex gap-2 align-items-center flex-wrap">
                <button class="btn btn-sm btn-outline-success" id="btn-add-rule">
                    <i class="bi bi-plus-lg"></i> Добавить условие
                </button>
                <div class="vr mx-2"></div>
                <button class="btn btn-sm btn-primary" id="btn-apply-filters">
                    <i class="bi bi-check-lg"></i> Применить
                </button>
                <button class="btn btn-sm btn-info text-white" id="btn-test-filters">
                    <i class="bi bi-eye"></i> Проверить (<span id="test-count">0</span>)
                </button>
                <button class="btn btn-sm btn-secondary" id="btn-reset-filters">
                    <i class="bi bi-arrow-counterclockwise"></i> Сброс
                </button>
                ${this.options.mode === 'modal' ? '<span class="text-muted small ms-2">Нажмите "Проверить", чтобы увидеть количество активов</span>' : ''}
            </div>
        `;
    }

    attachEvents() {
        // Добавить правило
        this.container.addEventListener('click', (e) => {
            if (e.target.closest('#btn-add-rule')) {
                e.preventDefault();
                this.addRuleRow();
            }
            if (e.target.closest('.btn-remove-rule')) {
                e.preventDefault();
                const row = e.target.closest('.filter-rule-row');
                row.remove();
            }
        });

        // Применить
        const btnApply = this.container.querySelector('#btn-apply-filters');
        if (btnApply) {
            btnApply.addEventListener('click', () => this.handleApply());
        }

        // Тестировать
        const btnTest = this.container.querySelector('#btn-test-filters');
        if (btnTest) {
            btnTest.addEventListener('click', () => this.handleTest());
        }

        // Сброс
        const btnReset = this.container.querySelector('#btn-reset-filters');
        if (btnReset) {
            btnReset.addEventListener('click', () => this.handleReset());
        }
    }

    addRuleRow(ruleData = {}) {
        const rulesContainer = this.container.querySelector('.filter-rules');
        const rowId = 'rule-' + Date.now() + Math.random().toString(36).substr(2, 9);
        
        const row = document.createElement('div');
        row.className = 'filter-rule-row d-flex gap-2 mb-2 align-items-end';
        row.dataset.rowId = rowId;

        // Поле
        const fieldSelect = document.createElement('select');
        fieldSelect.className = 'form-select form-select-sm';
        fieldSelect.style.width = '180px';
        fieldSelect.dataset.field = 'field';
        fieldSelect.innerHTML = '<option value="">Выберите поле</option>' + 
            this.fields.map(f => `<option value="${f.id}">${f.label}</option>`).join('');
        if (ruleData.field) fieldSelect.value = ruleData.field;

        // Операция
        const opSelect = document.createElement('select');
        opSelect.className = 'form-select form-select-sm';
        opSelect.style.width = '100px';
        opSelect.dataset.field = 'operation';
        opSelect.innerHTML = this.operations.map(o => `<option value="${o.value}">${o.label}</option>`).join('');
        if (ruleData.operation) opSelect.value = ruleData.operation;

        // Значение
        const valueInput = document.createElement('input');
        valueInput.type = 'text';
        valueInput.className = 'form-control form-control-sm';
        valueInput.style.width = '200px';
        valueInput.dataset.field = 'value';
        valueInput.placeholder = 'Значение';
        if (ruleData.value) valueInput.value = ruleData.value;

        // Кнопка удаления
        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn btn-sm btn-outline-danger';
        removeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
        removeBtn.classList.add('btn-remove-rule');
        removeBtn.title = 'Удалить условие';

        row.appendChild(fieldSelect);
        row.appendChild(opSelect);
        row.appendChild(valueInput);
        row.appendChild(removeBtn);

        // Логика изменения типа инпута в зависимости от поля (упрощенно)
        fieldSelect.addEventListener('change', () => {
            const selectedField = this.fields.find(f => f.id === fieldSelect.value);
            if (selectedField && selectedField.type === 'select' && selectedField.options) {
                // Превращаем input в select
                const newSelect = document.createElement('select');
                newSelect.className = 'form-select form-select-sm';
                newSelect.style.width = '200px';
                newSelect.dataset.field = 'value';
                newSelect.innerHTML = '<option value="">Любое</option>' + 
                    selectedField.options.map(o => `<option value="${o.value}">${o.label}</option>`).join('');
                if (ruleData.value) newSelect.value = ruleData.value;
                valueInput.replaceWith(newSelect);
            } else if (!valueInput.tagName || valueInput.tagName !== 'INPUT') {
                // Возвращаем input если был select
                const newInput = document.createElement('input');
                newInput.type = 'text';
                newInput.className = 'form-control form-control-sm';
                newInput.style.width = '200px';
                newInput.dataset.field = 'value';
                newInput.placeholder = 'Значение';
                if (ruleData.value) newInput.value = ruleData.value;
                // Найти текущий элемент значения и заменить
                const currentValueEl = row.querySelector('[data-field="value"]');
                if (currentValueEl) currentValueEl.replaceWith(newInput);
            }
        });

        // Триггерим change если поле уже выбрано при инициализации
        if (ruleData.field) {
            fieldSelect.dispatchEvent(new Event('change'));
        }

        rulesContainer.appendChild(row);
    }

    getRules() {
        const rules = [];
        this.container.querySelectorAll('.filter-rule-row').forEach(row => {
            const field = row.querySelector('select[data-field="field"]').value;
            const operation = row.querySelector('select[data-field="operation"]').value;
            const valueEl = row.querySelector('[data-field="value"]');
            const value = valueEl ? valueEl.value : '';

            if (field && value) {
                rules.push({ field, operation, value });
            }
        });
        return rules;
    }

    async handleApply() {
        const rules = this.getRules();
        if (this.options.mode === 'dashboard' && this.options.onApply) {
            this.options.onApply(rules);
        } else if (this.options.mode === 'modal') {
            // В модалке просто сохраняем правила в форму или вызываем коллбек
            if (this.options.onApply) this.options.onApply(rules);
        }
    }

    async handleTest() {
        const rules = this.getRules();
        const countSpan = this.container.querySelector('#test-count');
        if (!countSpan) return;

        countSpan.textContent = '...';
        
        try {
            // Отправляем запрос на сервер для подсчета
            const response = await Utils.apiRequest('/api/assets/count', {
                method: 'POST',
                body: JSON.stringify({ rules })
            });
            countSpan.textContent = response.count || 0;
            
            // Визуальный эффект успеха
            const btn = this.container.querySelector('#btn-test-filters');
            btn.classList.remove('btn-info');
            btn.classList.add('btn-success');
            setTimeout(() => {
                btn.classList.remove('btn-success');
                btn.classList.add('btn-info');
            }, 1000);

        } catch (error) {
            console.error('Error testing filters:', error);
            countSpan.textContent = 'Err';
        }
    }

    handleReset() {
        this.container.querySelector('.filter-rules').innerHTML = '';
        this.rules = [];
        const countSpan = this.container.querySelector('#test-count');
        if (countSpan) countSpan.textContent = '0';
        
        this.addRuleRow(); // Добавить одно пустое
        
        if (this.options.mode === 'dashboard' && this.options.onApply) {
            this.options.onApply([]); // Сбросить фильтр на дашборде
        }
    }
}

// Экспорт для использования в других модулях
export { FilterBuilder };

// Делаем класс глобально доступным (для обратной совместимости)
window.FilterBuilder = FilterBuilder;
