import { ViewModelBase } from './ViewModelBase.js';

export class ConfigViewModel extends ViewModelBase {
    constructor() {
        super();
        this.modelName = 'glm-5.2';
        this.modelPrefix = 'zhipu';
        this.apiBase = '';
        this.apiKey = '';
        this.hasApiKey = false;
    }

    async loadFromStorage() {
        try {
            const res = await fetch('/api/config');
            if (res.ok) {
                const data = await res.json();
                this.modelName = data.modelName ?? this.modelName;
                this.modelPrefix = data.modelPrefix ?? this.modelPrefix;
                this.apiBase = data.apiBase ?? this.apiBase;
                this.hasApiKey = data.hasApiKey || false;
            }
        } catch (e) {
            console.error('Erro ao carregar config do backend:', e);
        }
        this.dispatchEvent(new CustomEvent('change', {
            detail: {
                modelName: this.modelName,
                modelPrefix: this.modelPrefix,
                apiBase: this.apiBase,
                apiKey: this.apiKey,
            }
        }));
    }

    async saveToStorage() {
        try {
            const payload = {};
            if (this.modelName) payload.modelName = this.modelName;
            if (this.modelPrefix) payload.modelPrefix = this.modelPrefix;
            if (this.apiBase) payload.apiBase = this.apiBase;
            if (this.apiKey) payload.apiKey = this.apiKey;

            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
        } catch (e) {
            console.error('Erro ao salvar config no backend:', e);
            throw e;
        }
        this.dispatchEvent(new CustomEvent('saved', {
            detail: {
                modelName: this.modelName,
                modelPrefix: this.modelPrefix,
                apiBase: this.apiBase,
                apiKey: this.apiKey,
            }
        }));
    }

    getDefaults() {
        return {
            modelName: 'glm-5.2',
            modelPrefix: 'zhipu',
            apiBase: '',
            apiKey: '',
            hasApiKey: false,
        };
    }

    async restoreDefaults() {
        const defaults = this.getDefaults();
        this.modelName = defaults.modelName;
        this.modelPrefix = defaults.modelPrefix;
        this.apiBase = defaults.apiBase;
        this.apiKey = defaults.apiKey;
        this.hasApiKey = false;
        await this.saveToStorage();
        this.dispatchEvent(new CustomEvent('change', {
            detail: { ...defaults }
        }));
    }

    async clearStorage() {
        try {
            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ modelName: '', modelPrefix: '', apiBase: '', apiKey: '' }),
            });
        } catch (e) {
            console.error('Erro ao limpar config no backend:', e);
        }
    }
}