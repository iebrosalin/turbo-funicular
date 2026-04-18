// static/js/modules/wazuh.js

export function initWazuhFilter() {
    const dsFilter = document.getElementById('data-source-filter');
    if(dsFilter) {
        dsFilter.addEventListener('change', function() {
            const p = new URLSearchParams(window.location.search); 
            p.set('data_source', this.value); 
            window.location.search = p.toString();
        });
    }
}

export async function saveWazuhConfig() {
    const urlInput = document.getElementById('wazuh-url');
    const userInput = document.getElementById('wazuh-user');
    const passInput = document.getElementById('wazuh-pass');
    
    if(!urlInput || !userInput || !passInput) return;
    
    const config = {
        url: urlInput.value.trim(),
        username: userInput.value.trim(),
        password: passInput.value
    };
    
    try {
        const res = await fetch('/api/wazuh/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        if(!res.ok) throw new Error('Ошибка сохранения конфигурации');
        
        alert('Конфигурация Wazuh сохранена');
    } catch(e) {
        console.error('Ошибка сохранения Wazuh:', e);
        alert(e.message);
    }
}

export async function testWazuhConnection() {
    try {
        const res = await fetch('/api/wazuh/test');
        const data = await res.json();
        
        if(data.success) {
            alert('✅ Подключение к Wazuh успешно!');
        } else {
            alert('❌ Ошибка подключения: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('❌ Ошибка подключения: ' + e.message);
    }
}
