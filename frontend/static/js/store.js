/**
 * Централизованное хранилище состояния приложения (Store)
 * Реализует паттерн Observer для реактивности
 * Стандарт ES2020+: приватные поля #, методы
 */

export class Store {
  #state = {
    selectedAssetIds: new Set(),
    lastSelectedIndex: -1,
    currentGroupId: null,
    currentAssets: [],
    groups: [],  // Добавлено ключ groups
    assets: [],  // Добавлен ключ assets для хранения списка активов
    contextMenu: null,
    editModal: null,
    createModal: null,
    moveModal: null,
    deleteModal: null,
    bulkDeleteModalInstance: null,
    isAssetsLoading: false,
    isGroupsLoading: false
  };

  #listeners = new Map();

  /**
   * Получить значение из хранилища
   * @param {string} [key] - Ключ состояния
   * @returns {*} Значение или всё состояние
   */
  getState(key) {
    if (!key) {
      return { ...this.#state };
    }
    if (!(key in this.#state)) {
      console.warn(`Ключ '${key}' не найден в хранилище`);
      return undefined;
    }
    return this.#state[key];
  }

  /**
   * Установить значение в хранилище
   * @param {string} key - Ключ состояния
   * @param {*} value - Значение
   */
  setState(key, value) {
    if (!(key in this.#state)) {
      console.warn(`Попытка записи в несуществующий ключ '${key}'`);
      return;
    }

    const oldValue = this.#state[key];
    this.#state[key] = value;
    this.#notify(key, value, oldValue);
  }

  /**
   * Подписаться на изменения значения
   * @param {string} key - Ключ состояния
   * @param {Function} callback - Функция обратного вызова
   * @returns {Function} Функция для отписки
   */
  subscribe(key, callback) {
    if (!this.#listeners.has(key)) {
      this.#listeners.set(key, new Set());
    }

    this.#listeners.get(key).add(callback);

    return () => {
      const listeners = this.#listeners.get(key);
      if (listeners) {
        listeners.delete(callback);
        if (listeners.size === 0) {
          this.#listeners.delete(key);
        }
      }
    };
  }

  /**
   * Уведомление подписчиков
   * @private
   */
  #notify(key, newValue, oldValue) {
    if (this.#listeners.has(key)) {
      this.#listeners.get(key).forEach(callback => {
        try {
          callback(newValue, oldValue);
        } catch (error) {
          console.error(`Ошибка в слушателе для ключа '${key}':`, error);
        }
      });
    }
  }

  // --- Специализированные методы для активов ---

  addSelectedAsset(id) {
    this.#state.selectedAssetIds.add(id);
    this.#notifySelectionChange();
  }

  removeSelectedAsset(id) {
    this.#state.selectedAssetIds.delete(id);
    this.#notifySelectionChange();
  }

  clearSelectedAssets() {
    this.#state.selectedAssetIds.clear();
    this.#state.lastSelectedIndex = -1;
    this.#notifySelectionChange();
  }

  isSelected(id) {
    return this.#state.selectedAssetIds.has(id);
  }

  getSelectedIds() {
    return Array.from(this.#state.selectedAssetIds);
  }

  getSelectedCount() {
    return this.#state.selectedAssetIds.size;
  }

  getLastSelectedIndex() {
    return this.#state.lastSelectedIndex;
  }

  setLastSelectedIndex(index) {
    this.#state.lastSelectedIndex = index;
  }

  setCurrentAssets(assets) {
    this.#state.currentAssets = assets;
  }

  getCurrentAssets() {
    return this.#state.currentAssets;
  }

  #notifySelectionChange() {
    const count = this.#state.selectedAssetIds.size;
    this.#notify('selectedAssetIds', count);
  }

  /**
   * Сбросить всё состояние к начальным значениям
   */
  reset() {
    this.#state = {
      selectedAssetIds: new Set(),
      lastSelectedIndex: -1,
      currentGroupId: null,
      currentAssets: [],
      groups: [],
      assets: [],
      contextMenu: null,
      editModal: null,
      createModal: null,
      moveModal: null,
      deleteModal: null,
      bulkDeleteModalInstance: null,
      isAssetsLoading: false,
      isGroupsLoading: false
    };

    this.#listeners.forEach((callbacks, key) => {
      callbacks.forEach(callback => {
        try {
          callback(this.#state[key], undefined);
        } catch (error) {
          console.error(`Ошибка в слушателе при сбросе для '${key}':`, error);
        }
      });
    });
  }
}

// Создаем единственный экземпляр хранилища (Singleton)
export const store = new Store();
