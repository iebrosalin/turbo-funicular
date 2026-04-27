// static/js/filter-helpers.js
/**
 * Система умных подсказок для фильтрации активов на дашборде.
 * Представляет контекстные предложения полей и значений в зависимости от оператора.
 */

// Конфигурация полей и операторов
const FILTER_FIELDS = {
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
        source: '/api/groups', // Endpoint для получения списка групп
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

let currentSuggestions = [];
let selectedIndex = -1;
let activeInput = null;
let suggestionBox = null;
let cache = {}; // Кэш для динамических данных

/**
 * Инициализация автодополнения для поля фильтра
 * @param {HTMLInputElement} inputElement - Поле ввода
 */
function initFilterAutocomplete(inputElement) {
    if (!inputElement) return;
    activeInput = inputElement;

    // Создание контейнера подсказок
    if (!suggestionBox) {
        suggestionBox = document.createElement('div');
        suggestionBox.className = 'autocomplete-suggestions';
        suggestionBox.style.cssText = `
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
        document.body.appendChild(suggestionBox);

        // Закрытие при клике вне
        document.addEventListener('click', (e) => {
            if (!suggestionBox.contains(e.target) && e.target !== inputElement) {
                hideSuggestions();
            }
        });
        
        // Скрытие при скролле
        window.addEventListener('scroll', hideSuggestions, true);
    }

    // Обработчики событий
    inputElement.addEventListener('input', handleFilterInput);
    inputElement.addEventListener('keydown', handleFilterKeydown);
    inputElement.addEventListener('focus', () => {
        if (inputElement.value.trim().length > 0) {
            handleFilterInput({ target: inputElement });
        } else {
            // Показать подсказку по полям при фокусе на пустом поле
            showFieldSuggestions(inputElement);
        }
    });
}

/**
 * Обработка ввода текста
 */
function handleFilterInput(e) {
    const input = e.target;
    const value = input.value.trim();
    
    if (!value) {
        showFieldSuggestions(input);
        return;
    }

    // Анализ текущей стадии ввода: "поле:оператор:значение"
    // Поддерживаем форматы: "ip=192", "os:Linux", "port > 80"
    const parts = parseFilterQuery(value);
    
    if (!parts.field) {
        // Ввод имени поля
        showFieldSuggestions(input, parts.rawField);
    } else if (!parts.operator) {
        // Поле выбрано, ввод оператора
        showOperatorSuggestions(input, parts.field);
    } else {
        // Ввод значения
        showValueSuggestions(input, parts.field, parts.operator, parts.rawValue);
    }
}

/**
 * Парсинг строки запроса
 * Возвращает { rawField, field, operator, rawValue }
 */
function parseFilterQuery(query) {
    // Регулярка для разбора: field[operator]value
    // Операторы: =, !=, :, like, contains, >, <, in, not_in
    const regex = /^([a-zA-Z_]+)\s*(=|!=|:|like|contains|>|<|in|not_in|\[\])?\s*(.*)$/i;
    const match = query.match(regex);

    if (match) {
        const fieldName = match[1].toLowerCase();
        // Нормализация имени поля (множественное число -> единственное)
        let normalizedField = fieldName;
        if (fieldName.endsWith('s') && !['status', 'dns'].includes(fieldName)) {
             // Простая эвристика, можно улучшить
             if (FILTER_FIELDS[fieldName.slice(0, -1)]) {
                 normalizedField = fieldName.slice(0, -1);
             }
        }
        
        // Проверка существования поля
        if (FILTER_FIELDS[normalizedField] || Object.keys(FILTER_FIELDS).some(k => k.startsWith(normalizedField))) {
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
function showFieldSuggestions(input, query = '') {
    const queryLower = query.toLowerCase();
    const suggestions = Object.keys(FILTER_FIELDS)
        .filter(key => FILTER_FIELDS[key].label.toLowerCase().includes(queryLower) || key.includes(queryLower))
        .map(key => ({
            key: key,
            label: FILTER_FIELDS[key].label,
            type: 'field',
            desc: `Пример: ${key}=${FILTER_FIELDS[key].example || '...'}`
        }))
        .slice(0, 8);

    renderSuggestions(suggestions, input, (item) => {
        input.value = `${item.key}:`;
        input.focus();
        handleFilterInput({ target: input });
    });
}

/**
 * Показ подсказок операторов
 */
function showOperatorSuggestions(input, fieldName) {
    const fieldConfig = FILTER_FIELDS[fieldName];
    if (!fieldConfig) return;

    const suggestions = fieldConfig.operators.map(op => ({
        key: op,
        label: getOperatorLabel(op),
        type: 'operator',
        desc: `Синтаксис: ${fieldName}${op}...`
    }));

    renderSuggestions(suggestions, input, (item) => {
        // Сохраняем имя поля и добавляем оператор
        const currentVal = input.value;
        const base = currentVal.split(/[:=!=<>]/)[0]; // Берем часть до оператора
        input.value = `${base}${item.key}`;
        // Если оператор не требует пробела после (как :), можно сразу ждать значение
        input.focus();
        handleFilterInput({ target: input });
    });
}

/**
 * Показ подсказок значений
 */
async function showValueSuggestions(input, fieldName, operator, query) {
    const fieldConfig = FILTER_FIELDS[fieldName];
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
        const data = await fetchDynamicData(fieldConfig.source);
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
            // Для текста просто показываем то, что введено, как валидное значение
            suggestions = [{ key: query, label: `Значение "${query}"`, type: 'value' }];
        }
    }

    renderSuggestions(suggestions.slice(0, 8), input, (item) => {
        const parts = parseFilterQuery(input.value);
        // Формируем финальную строку: field:operator:value
        let finalVal = `${parts.field}${parts.operator}${item.key}`;
        
        // Если оператор множественный (in), можно добавить запятую
        if (parts.operator === 'in' || parts.operator === 'not_in') {
             // Логика для добавления запятой может быть расширена
        }
        
        input.value = finalVal;
        hideSuggestions();
    });
}

/**
 * Получение динамических данных с кэшированием
 */
async function fetchDynamicData(url) {
    if (cache[url]) return cache[url];
    
    try {
        const resp = await fetch(url);
        if (resp.ok) {
            const data = await resp.json();
            cache[url] = data;
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
function renderSuggestions(items, input, onSelect) {
    currentSuggestions = items.map(i => ({...i, onSelect}));
    selectedIndex = -1;
    
    if (!suggestionBox || items.length === 0) {
        hideSuggestions();
        return;
    }

    suggestionBox.innerHTML = '';
    
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
        if (idx === selectedIndex) div.style.backgroundColor = '#e3f2fd';
        
        div.onmouseover = () => { selectedIndex = idx; renderSuggestions(items, input, onSelect); };
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
        suggestionBox.appendChild(div);
    });

    // Позиционирование
    const rect = input.getBoundingClientRect();
    suggestionBox.style.top = `${rect.bottom + window.scrollY + 2}px`;
    suggestionBox.style.left = `${rect.left + window.scrollX}px`;
    suggestionBox.style.width = `${Math.max(rect.width, 300)}px`;
    suggestionBox.style.display = 'block';
}

function hideSuggestions() {
    if (suggestionBox) suggestionBox.style.display = 'none';
    currentSuggestions = [];
    selectedIndex = -1;
}

function handleFilterKeydown(e) {
    if (!suggestionBox || suggestionBox.style.display === 'none') return;
    
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % currentSuggestions.length;
        // Перерисовка для подсветки
        const items = suggestionBox.querySelectorAll('.autocomplete-item');
        items.forEach((el, i) => el.style.backgroundColor = i === selectedIndex ? '#e3f2fd' : 'white');
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + currentSuggestions.length) % currentSuggestions.length;
        const items = suggestionBox.querySelectorAll('.autocomplete-item');
        items.forEach((el, i) => el.style.backgroundColor = i === selectedIndex ? '#e3f2fd' : 'white');
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedIndex >= 0 && currentSuggestions[selectedIndex]) {
            currentSuggestions[selectedIndex].onSelect(currentSuggestions[selectedIndex]);
        }
    } else if (e.key === 'Escape') {
        hideSuggestions();
    }
}

function getOperatorLabel(op) {
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

// Экспорт функций через ES6 export
export { initFilterAutocomplete };