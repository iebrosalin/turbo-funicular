/**
 * Централизованное хранилище состояния приложения (Store)
 * Реализует паттерн Observer для реактивности
 */

class Store {
    constructor() {
        this.state = {
            selectedAssetIds: new Set(),
            lastSelectedIndex: -1,
            currentGroupId: null,
            currentAssets: [],
            contextMenu: null,
            editModal: null,
            createModal: null,
            moveModal: null,
            deleteModal: null,
            bulkDeleteModalInstance: null,
            isAssetsLoading: false,
            isGroupsLoading: false
        };
        
        this.listeners = new Map();
    }

    /**
     * Получить значение из хранилища
     * @param {string} key - Ключ состояния
     * @returns {*} Значение
     */
    get(key) {
        if (!(key in this.state)) {
            console.warn(`Ключ '${key}' не найден в хранилище`);
            return undefined;
        }
        return this.state[key];
    }

    /**
     * Установить значение в хранилище
     * @param {string} key - Ключ состояния
     * @param {*} value - Значение
     * @param {boolean} notify - Уведомить слушателей
     */
    set(key, value, notify = true) {
        if (!(key in this.state)) {
            console.warn(`Попытка записи в несуществующий ключ '${key}'`);
            return;
        }
        
        const oldValue = this.state[key];
        this.state[key] = value;
        
        if (notify && this.listeners.has(key)) {
            this.listeners.get(key).forEach(callback => {
                try {
                    callback(value, oldValue);
                } catch (error) {
                    console.error(`Ошибка в слушателе для ключа '${key}':`, error);
                }
            });
        }
    }

    /**
     * Подписаться на изменения значения
     * @param {string} key - Ключ состояния
     * @param {Function} callback - Функция обратного вызова (newValue, oldValue) => void
     * @returns {Function} Функция для отписки
     */
    subscribe(key, callback) {
        if (!this.listeners.has(key)) {
            this.listeners.set(key, new Set());
        }
        
        this.listeners.get(key).add(callback);
        
        // Возвращаем функцию для отписки
        return () => {
            const listeners = this.listeners.get(key);
            if (listeners) {
                listeners.delete(callback);
                if (listeners.size === 0) {
                    this.listeners.delete(key);
                }
            }
        };
    }

    /**
     * Добавить ID актива в выбранные
     * @param {string} id - ID актива
     */
    addSelectedAsset(id) {
        this.state.selectedAssetIds.add(id);
        this.notifySelectionChange();
    }

    /**
     * Удалить ID актива из выбранных
     * @param {string} id - ID актива
     */
    removeSelectedAsset(id) {
        this.state.selectedAssetIds.delete(id);
        this.notifySelectionChange();
    }

    /**
     * Очистить все выбранные активы
     */
    clearSelectedAssets() {
        this.state.selectedAssetIds.clear();
        this.state.lastSelectedIndex = -1;
        this.notifySelectionChange();
    }

    /**
     * Проверить, выбран ли актив
     * @param {string} id - ID актива
     * @returns {boolean}
     */
    isSelected(id) {
        return this.state.selectedAssetIds.has(id);
    }

    /**
     * Получить массив выбранных ID
     * @returns {Array<string>}
     */
    getSelectedIds() {
        return Array.from(this.state.selectedAssetIds);
    }

    /**
     * Получить Set выбранных активов (для совместимости)
     * @returns {Set}
     */
    getSelectedAssets() {
        return this.state.selectedAssetIds;
    }

    /**
     * Получить количество выбранных активов
     * @returns {number}
     */
    getSelectedCount() {
        return this.state.selectedAssetIds.size;
    }

    /**
     * Получить количество выбранных активов (алиас для совместимости)
     * @returns {number}
     */
    getSelectedAssetsCount() {
        return this.state.selectedAssetIds.size;
    }

    /**
     * Получить последний выбранный индекс
     * @returns {number}
     */
    getLastSelectedIndex() {
        return this.state.lastSelectedIndex;
    }

    /**
     * Установить последний выбранный индекс
     * @param {number} index
     */
    setLastSelectedIndex(index) {
        this.state.lastSelectedIndex = index;
    }

    /**
     * Установить текущие активы
     * @param {Array} assets
     */
    setCurrentAssets(assets) {
        this.state.currentAssets = assets;
    }

    /**
     * Получить текущие активы
     * @returns {Array}
     */
    getCurrentAssets() {
        return this.state.currentAssets;
    }

    /**
     * Уведомить об изменении выделения
     */
    notifySelectionChange() {
        const count = this.state.selectedAssetIds.size;
        if (this.listeners.has('selectedAssetIds')) {
            this.listeners.get('selectedAssetIds').forEach(callback => {
                try {
                    callback(count);
                } catch (error) {
                    console.error('Ошибка в слушателе выделения:', error);
                }
            });
        }
    }

    /**
     * Сбросить всё состояние к начальным значениям
     */
    reset() {
        this.state = {
            selectedAssetIds: new Set(),
            lastSelectedIndex: -1,
            currentGroupId: null,
            currentAssets: [],
            contextMenu: null,
            editModal: null,
            createModal: null,
            moveModal: null,
            deleteModal: null,
            bulkDeleteModalInstance: null,
            isAssetsLoading: false,
            isGroupsLoading: false
        };
        
        // Уведомляем всех слушателей о сбросе
        this.listeners.forEach((callbacks, key) => {
            callbacks.forEach(callback => {
                try {
                    callback(this.state[key], undefined);
                } catch (error) {
                    console.error(`Ошибка в слушателе при сбросе для '${key}':`, error);
                }
            });
        });
    }
}

// Создаем единственный экземпляр хранилища
const store = new Store();

export default store;
