// static/js/main.js
// Модульная версия - импортирует функциональность из отдельных модулей

import { initTheme, toggleTheme, initTreeTogglers, filterByGroup } from './modules/theme.js';
import { populateParentSelect, closeModalById } from './modules/utils.js';
import { 
    showCreateGroupModal, 
    toggleGroupMode, 
    addDynamicRule, 
    showRenameModal, 
    saveGroup, 
    showDeleteModal, 
    confirmDeleteGroup,
    showMoveGroupModal,
    moveGroup,
    initContextMenu 
} from './modules/groups.js';
import { 
    initAssetSelection, 
    confirmBulkDelete, 
    executeBulkDelete, 
    initFilterFieldDatalist, 
    renderAssets 
} from './modules/assets.js';
import { viewScanResults, showScanError, updateScanHistory, pollActiveScans } from './modules/scans.js';
import { initWazuhFilter, saveWazuhConfig, testWazuhConnection } from './modules/wazuh.js';
import { refreshGroupTree, loadAssets } from './modules/tree.js';

// ═══════════════════════════════════════════════════════════════
// ЗАЩИТА ОТ ПОВТОРНОГО ВЫПОЛНЕНИЯ
// ═══════════════════════════════════════════════════════════════
(function() {
    if (window.__MAIN_JS_LOADED) {
        console.warn('main.js уже был загружен, пропускаем повторную инициализацию.');
        return;
    }
    window.__MAIN_JS_LOADED = true;

    // ═══════════════════════════════════════════════════════════════
    // ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
    // ═══════════════════════════════════════════════════════════════
    var currentGroupId = null; 
    var contextMenu = null;
    var editModal, createModal, moveModal, deleteModal, bulkDeleteModalInstance;
    var lastSelectedIndex = -1; 
    var selectedAssetIds = new Set();

    // Экспорт глобальных переменных для доступа из модулей
    window.currentGroupId = currentGroupId;
    window.selectedAssetIds = selectedAssetIds;

    // ═══════════════════════════════════════════════════════════════
    // ИНИЦИАЛИЗАЦИЯ
    // ═══════════════════════════════════════════════════════════════
    document.addEventListener('DOMContentLoaded', () => {
        initTheme(); 
        initFilterFieldDatalist(); 
        initTreeTogglers(); 
        initAssetSelection();
        initWazuhFilter();
        initContextMenu();
        
        contextMenu = document.getElementById('group-context-menu');
        
        setInterval(pollActiveScans, 5000);
        pollActiveScans();

        // Обработчик Ctrl+A для выделения всех активов
        document.addEventListener('keydown', e => { 
            if(e.ctrlKey && e.key==='a' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) { 
                e.preventDefault(); 
                document.querySelectorAll('#assets-body .asset-checkbox').forEach(cb => { 
                    cb.checked=true; 
                    const row = cb.closest('tr');
                    if(row) row.classList.add('selected');
                    selectedAssetIds.add(cb.value); 
                }); 
                const tb = document.getElementById('bulk-toolbar');
                if(tb) {
                    tb.style.display = selectedAssetIds.size > 0 ? 'flex' : 'none';
                    const countEl = document.getElementById('selected-count');
                    if(countEl) countEl.textContent = selectedAssetIds.size;
                }
            } 
        });

        // Глобальные обработчики для кнопок
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
        window.saveWazuhConfig = saveWazuhConfig;
        window.testWazuhConnection = testWazuhConnection;
    });
})();
