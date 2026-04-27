/**
 * Центральный экспорт всех модулей приложения
 * Используется для удобного импорта функций в других файлах
 */

// Хранилище состояния
export { default as store } from '../store.js';

// Модуль управления активами
export {
    initAssetSelection,
    renderAssets,
    showAssetModal,
    saveAsset,
    confirmBulkDelete,
    executeBulkDelete,
    confirmBulkMove,
    executeBulkMove,
    clearSelection,
    initFilterFieldDatalist
} from './assets.js';

// Модуль управления деревом групп
export {
    refreshGroupTree,
    loadAssets,
    filterByGroup,
    initTreeTogglers,
    initGroupTreeStaticListeners,
    renderTree
} from './tree.js';

// Модуль сканирований
export {
    viewScanResults,
    showScanError,
    updateScanHistory,
    pollActiveScans
} from './scans.js';

// Модуль управления группами
export {
    showCreateGroupModal,
    toggleGroupMode,
    addDynamicRule,
    showRenameModal,
    saveGroup,
    showDeleteModal,
    confirmDeleteGroup,
    showMoveGroupModal,
    moveGroup,
    initContextMenu,
    initGroupModeListeners
} from './groups.js';

// Модуль темы
export {
    initTheme,
    toggleTheme
} from './theme.js';

// Модуль утилит
export {
    populateParentSelect,
    closeModalById
} from './utils.js';
