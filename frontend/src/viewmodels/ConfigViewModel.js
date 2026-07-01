import { ViewModelBase } from './ViewModelBase.js';

export class ConfigViewModel extends ViewModelBase {
    constructor() {
        super();
        this.modelName = 'glm-5.2';
        this.modelPrefix = 'zhipu';
        this.apiBase = '';
        this.apiKey = '';
        this.regrasAdicionais = [];
    }

    loadFromStorage() {
        try {
            const modelName = localStorage.getItem('so_modelName');
            const modelPrefix = localStorage.getItem('so_modelPrefix');
            const apiBase = localStorage.getItem('so_apiBase');
            const apiKey = localStorage.getItem('so_apiKey');
            const regras = localStorage.getItem('so_regrasAdicionais');

            if (modelName !== null) this.modelName = modelName;
            if (modelPrefix !== null) this.modelPrefix = modelPrefix;
            if (apiBase !== null) this.apiBase = apiBase;
            if (apiKey !== null) this.apiKey = apiKey;
            if (regras !== null) {
                this.regrasAdicionais = JSON.parse(regras);
            }
        } catch (e) {
            console.error('Erro ao carregar do localStorage:', e);
        }
        this.dispatchEvent(new CustomEvent('change', {
            detail: {
                modelName: this.modelName,
                modelPrefix: this.modelPrefix,
                apiBase: this.apiBase,
                apiKey: this.apiKey,
                regrasAdicionais: this.regrasAdicionais
            }
        }));
    }

    saveToStorage() {
        try {
            localStorage.setItem('so_modelName', this.modelName);
            localStorage.setItem('so_modelPrefix', this.modelPrefix);
            localStorage.setItem('so_apiBase', this.apiBase);
            localStorage.setItem('so_apiKey', this.apiKey);
            localStorage.setItem('so_regrasAdicionais', JSON.stringify(this.regrasAdicionais));
        } catch (e) {
            console.error('Erro ao salvar no localStorage:', e);
        }
    }

    addRule(ruleText) {
        const text = ruleText.trim();
        if (text) {
            this.regrasAdicionais.push(text);
            this.saveToStorage();
            this.dispatchEvent(new CustomEvent('rulesChanged', {
                detail: this.regrasAdicionais
            }));
        }
    }

    removeRule(index) {
        if (index >= 0 && index < this.regrasAdicionais.length) {
            this.regrasAdicionais.splice(index, 1);
            this.saveToStorage();
            this.dispatchEvent(new CustomEvent('rulesChanged', {
                detail: this.regrasAdicionais
            }));
        }
    }
}
