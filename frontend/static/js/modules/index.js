/**
 * Центральный экспорт всех модулей приложения
 * Используется для удобного импорта функций в других файлах
 */

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
} from './modules/assets.js';

// Модуль управления деревом групп
export {
    refreshGroupTree,
    loadAssets,
    filterByGroup,
    initTreeTogglers,
    initGroupTreeStaticListeners,
    renderTree
} from './modules/tree.js';

// Модуль сканирований
export {
    viewScanResults,
    showScanError,
    updateScanHistory,
    pollActiveScans
} from './modules/scans.js';

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
} from './modules/groups.js';

// Модуль темы
export {
    initTheme,
    toggleTheme
} from './modules/theme.js';

// Модуль утилит
export {
    populateParentSelect,
    closeModalById
} from './modules/utils.js';

// Хранилище состояния
export { default as store } from '../store.js';
