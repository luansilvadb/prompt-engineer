import { ViewModelBase } from './ViewModelBase.js';

export class ConfigViewModel extends ViewModelBase {
    constructor() {
        super();
        this.modelName = 'glm-5.2';
        this.modelPrefix = 'zhipu';
        this.apiBase = '';
        this.apiKey = '';
    }

    loadFromStorage() {
        try {
            const modelName = localStorage.getItem('so_modelName');
            const modelPrefix = localStorage.getItem('so_modelPrefix');
            const apiBase = localStorage.getItem('so_apiBase');
            const apiKey = localStorage.getItem('so_apiKey');

            if (modelName !== null) this.modelName = modelName;
            if (modelPrefix !== null) this.modelPrefix = modelPrefix;
            if (apiBase !== null) this.apiBase = apiBase;
            if (apiKey !== null) this.apiKey = apiKey;
        } catch (e) {
            console.error('Erro ao carregar do localStorage:', e);
        }
        this.dispatchEvent(new CustomEvent('change', {
            detail: {
                modelName: this.modelName,
                modelPrefix: this.modelPrefix,
                apiBase: this.apiBase,
                apiKey: this.apiKey
            }
        }));
    }

    saveToStorage() {
        try {
            localStorage.setItem('so_modelName', this.modelName);
            localStorage.setItem('so_modelPrefix', this.modelPrefix);
            localStorage.setItem('so_apiBase', this.apiBase);
            localStorage.setItem('so_apiKey', this.apiKey);
        } catch (e) {
            console.error('Erro ao salvar no localStorage:', e);
        }
    }
}
