// static/js/main.js
import { initTheme, toggleTheme } from './modules/theme.js';
import { populateParentSelect, closeModalById } from './modules/utils.js';
import {
    showCreateGroupModal, toggleGroupMode, addDynamicRule, showRenameModal,
    saveGroup, showDeleteModal, confirmDeleteGroup, showMoveGroupModal, moveGroup, initContextMenu,
    initGroupModeListeners
} from './modules/groups.js';
import {
    initAssetSelection, confirmBulkDelete, executeBulkDelete,
        confirmBulkMove, executeBulkMove, clearSelection,
    initFilterFieldDatalist, renderAssets, showAssetModal, saveAsset
} from './modules/assets.js';
import { viewScanResults, showScanError, updateScanHistory, pollActiveScans } from './modules/scans.js';
// ✅ Импорт всей логики дерева из одного источника
import { refreshGroupTree, loadAssets, filterByGroup, initTreeTogglers, initGroupTreeStaticListeners } from './modules/tree.js';
import { store } from './modules/index.js';

(function() {
    document.addEventListener('DOMContentLoaded', () => {
        // 🎨 Тема
        initTheme();

        // 🔍 Фильтры
        initFilterFieldDatalist();

        // 📋 Выбор активов
        initAssetSelection();

        // 🖱️ Контекстное меню
        initContextMenu();

        // 🌳 Инициализация обработчиков статических элементов дерева
        // Вызывается после загрузки DOM, а также повторно после refreshGroupTree()

        // --- Логика изменения размера сайдбара ---
        const sidebar = document.getElementById('sidebar');
        const resizer = document.getElementById('sidebarResizer');
        const content = document.getElementById('content');
        
        let isResizing = false;

        // Восстановление ширины из localStorage
        const savedWidth = localStorage.getItem('sidebarWidth');
        if (savedWidth) {
            document.documentElement.style.setProperty('--sidebar-width', savedWidth);
        }

        resizer.addEventListener('mousedown', (e) => {
            isResizing = true;
            resizer.classList.add('resizing');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none'; // Запрет выделения текста
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            let newWidth = e.clientX;
            
            // Ограничения ширины
            const minWidth = 200;
            const maxWidth = 600;
            
            if (newWidth < minWidth) newWidth = minWidth;
            if (newWidth > maxWidth) newWidth = maxWidth;

            document.documentElement.style.setProperty('--sidebar-width', `${newWidth}px`);
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                resizer.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                
                // Сохранение ширины
                const currentWidth = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width').trim();
                localStorage.setItem('sidebarWidth', currentWidth);
            }
        });
        // -----------------------------------------

        // Переключение сайдбара на мобильных
        document.getElementById('sidebarCollapse')?.addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('active');
            document.getElementById('content').classList.toggle('active');
        });

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

        // 🛠️ Обработчик формы создания/редактирования актива
        const assetForm = document.getElementById('assetForm');
        if (assetForm) {
            assetForm.addEventListener('submit', (e) => {
                e.preventDefault();
                saveAsset(e);
            });
        }
        
        // 🎛️ Инициализация обработчиков для переключателей режимов группы
        initGroupModeListeners();

        // 🔄 Поллинг активных сканирований
        pollActiveScans();
        setInterval(pollActiveScans, 5000);

        // 🌳 Инициализация дерева групп (строго после DOM)
        (async () => {
            try {
                await refreshGroupTree();
                initTreeTogglers();
                // initGroupTreeStaticListeners() уже вызывается внутри refreshGroupTree() после renderTree()

                // 🔍 Обработка URL-параметров для фильтрации активов (group_id, ungrouped)
                const urlParams = new URLSearchParams(window.location.search);
                const groupIdParam = urlParams.get('group_id');
                const ungroupedParam = urlParams.get('ungrouped');

                if (ungroupedParam === 'true') {
                    // Фильтр "Без группы"
                    filterByGroup('ungrouped', true, 'assets-body', null);
                } else if (groupIdParam && groupIdParam !== 'all') {
                    // Фильтр по конкретной группе
                    filterByGroup(groupIdParam, false, 'assets-body', null);
                } else {
                    // По умолчанию загружаем все активы
                    filterByGroup('all', false, 'assets-body', null);
                }
            } catch (err) {
                console.error('❌ Ошибка инициализации дерева групп:', err);
            }
        })();

        // ⌨️ Горячие клавиши (Ctrl+A для выделения всех)
        document.addEventListener('keydown', e => {
            if (e.ctrlKey && e.key === 'a' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
                e.preventDefault();
                document.querySelectorAll('#assets-body .asset-checkbox').forEach(cb => {
                    cb.checked = true;
                    const row = cb.closest('tr');
                    if (row) row.classList.add('selected');
                    store.addSelectedAsset(cb.value);
                });
                const tb = document.getElementById('bulk-toolbar');
                if (tb) {
                    tb.style.display = store.getSelectedAssetsCount() > 0 ? 'flex' : 'none';
                    const countEl = document.getElementById('selected-count');
                    if (countEl) countEl.textContent = store.getSelectedAssetsCount();
                }
            }
        });

        // 🌍 Глобальные экспорты удалены - используется ES6 import/export
    });
})();