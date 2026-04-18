// static/js/main.js
import { initTheme, toggleTheme } from './modules/theme.js';
import { populateParentSelect, closeModalById } from './modules/utils.js';
import {
    showCreateGroupModal, toggleGroupMode, addDynamicRule, showRenameModal,
    saveGroup, showDeleteModal, confirmDeleteGroup, showMoveGroupModal, moveGroup, initContextMenu
} from './modules/groups.js';
import {
    initAssetSelection, confirmBulkDelete, executeBulkDelete,
    initFilterFieldDatalist, renderAssets
} from './modules/assets.js';
import { viewScanResults, showScanError, updateScanHistory, pollActiveScans } from './modules/scans.js';
import { initWazuhFilter, saveWazuhConfig, testWazuhConnection } from './modules/wazuh.js';
// ✅ Импорт всей логики дерева из одного источника
import { refreshGroupTree, loadAssets, filterByGroup, initTreeTogglers } from './modules/tree.js';

(function() {
    // 🔒 Guard против повторной инициализации
    if (window.__MAIN_JS_LOADED) return;
    window.__MAIN_JS_LOADED = true;

    // 🌐 Глобальные переменные состояния
    window.currentGroupId = null;
    window.contextMenu = null;
    window.editModal = null;
    window.createModal = null;
    window.moveModal = null;
    window.deleteModal = null;
    window.bulkDeleteModalInstance = null;
    window.lastSelectedIndex = -1;
    window.selectedAssetIds = new Set();

    document.addEventListener('DOMContentLoaded', () => {
        // 🎨 Тема
        initTheme();

        // 🔍 Фильтры
        initFilterFieldDatalist();

        // 📋 Выбор активов
        initAssetSelection();

        // 🛡️ Wazuh
        initWazuhFilter();

        // 🖱️ Контекстное меню
        initContextMenu();

        // 📝 Обработчик формы редактирования/создания группы
        const groupEditForm = document.getElementById('groupEditForm');
        if (groupEditForm) {
            groupEditForm.addEventListener('submit', (e) => {
                e.preventDefault();
                saveGroup();
            });
        }

        // 🔄 Обработчик формы перемещения группы
        const groupMoveForm = document.getElementById('groupMoveForm');
        if (groupMoveForm) {
            groupMoveForm.addEventListener('submit', (e) => {
                e.preventDefault();
                moveGroup();
            });
        }
        // 🔗 Ссылка на контекстное меню
        window.contextMenu = document.getElementById('group-context-menu');

        // 🔄 Поллинг активных сканирований
        pollActiveScans();
        setInterval(pollActiveScans, 5000);

        // 🌳 Инициализация дерева групп (строго после DOM)
        refreshGroupTree()
            .then(() => {
                initTreeTogglers();
            })
            .catch(err => {
                console.error('❌ Ошибка инициализации дерева групп:', err);
            });

        // ⌨️ Горячие клавиши (Ctrl+A для выделения всех)
        document.addEventListener('keydown', e => {
            if (e.ctrlKey && e.key === 'a' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
                e.preventDefault();
                document.querySelectorAll('#assets-body .asset-checkbox').forEach(cb => {
                    cb.checked = true;
                    const row = cb.closest('tr');
                    if (row) row.classList.add('selected');
                    window.selectedAssetIds.add(cb.value);
                });
                const tb = document.getElementById('bulk-toolbar');
                if (tb) {
                    tb.style.display = window.selectedAssetIds.size > 0 ? 'flex' : 'none';
                    const countEl = document.getElementById('selected-count');
                    if (countEl) countEl.textContent = window.selectedAssetIds.size;
                }
            }
        });

        // 🌍 Глобальные экспорты для onclick-обработчиков в HTML
        window.toggleTheme = toggleTheme;
        window.showCreateGroupModal = showCreateGroupModal;
        window.toggleGroupMode = toggleGroupMode;
        window.addDynamicRule = addDynamicRule;
        window.showRenameModal = showRenameModal;
        window.saveGroup = saveGroup;
        window.showDeleteModal = showDeleteModal;
        window.confirmDeleteGroup = confirmDeleteGroup;
        window.showMoveGroupModal = showMoveGroupModal;
        window.moveGroup = moveGroup;
        window.confirmBulkDelete = confirmBulkDelete;
        window.executeBulkDelete = executeBulkDelete;
        window.refreshGroupTree = refreshGroupTree;
        window.loadAssets = loadAssets;
        window.filterByGroup = filterByGroup;
        window.renderAssets = renderAssets; // ✅ Добавлено: нужен для tree.js
        window.initTreeTogglers = initTreeTogglers; // ✅ Добавлено: для повторной инициализации
        window.saveWazuhConfig = saveWazuhConfig;
        window.testWazuhConnection = testWazuhConnection;
        window.closeModalById = closeModalById; // ✅ Добавлено: утилита закрытия модалок
        window.populateParentSelect = populateParentSelect; // ✅ Добавлено: для динамических селектов
    });
})();