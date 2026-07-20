import { el } from '../dom.js';
import { showToast } from '../utils/toast.js';

export class ConfigView {
    constructor(viewModel) {
        this.vm = viewModel;
        this._saveIndicatorTimer = null;
        this.initEvents();
        this.bindViewModel();
    }

    /** Exibe o indicador "Salvo ✓" com fade-out após 2s */
    _showSavedIndicator() {
        if (el.saveIndicator) {
            el.saveIndicator.style.display = 'inline-flex';
            el.saveIndicator.style.animation = 'none';
            // Força reflow para reiniciar a animação
            void el.saveIndicator.offsetWidth;
            el.saveIndicator.style.animation = 'saveIndicatorFadeIn 0.3s ease forwards';

            clearTimeout(this._saveIndicatorTimer);
            this._saveIndicatorTimer = setTimeout(() => {
                el.saveIndicator.style.animation = 'saveIndicatorFadeOut 0.5s ease forwards';
                this._saveIndicatorTimer = setTimeout(() => {
                    el.saveIndicator.style.display = 'none';
                }, 500);
            }, 2000);
        }
    }

    initEvents() {
        // Toggle Key Visibility
        el.btnToggleKey.addEventListener('click', () => {
            const isPassword = el.apiKey.type === 'password';
            el.apiKey.type = isPassword ? 'text' : 'password';
            el.btnToggleKey.querySelector('i').className = isPassword ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
            const newLabel = isPassword ? 'Ocultar chave de API' : 'Mostrar chave de API';
            el.btnToggleKey.setAttribute('aria-label', newLabel);
            el.btnToggleKey.setAttribute('title', newLabel);
        });

        // Toggle Config Panel Expanded/Collapsed
        el.btnToggleConfig.addEventListener('click', () => {
            const isHidden = el.configFields.classList.toggle('hidden');
            el.btnToggleConfig.classList.toggle('collapsed');
            const isExpanded = !isHidden;
            el.btnToggleConfig.setAttribute('aria-expanded', isExpanded);
            const newLabel = isExpanded ? 'Recolher painel de configuração' : 'Expandir painel de configuração';
            el.btnToggleConfig.setAttribute('aria-label', newLabel);
            el.btnToggleConfig.setAttribute('title', newLabel);
        });

        // Sincronizar inputs em tempo real com o ViewModel (sem salvar automaticamente)
        el.modelName.addEventListener('input', () => {
            this.vm.modelName = el.modelName.value.trim();
        });

        el.modelPrefix.addEventListener('input', () => {
            this.vm.modelPrefix = el.modelPrefix.value.trim();
        });

        el.apiBase.addEventListener('input', () => {
            this.vm.apiBase = el.apiBase.value.trim();
        });

        el.apiKey.addEventListener('input', () => {
            this.vm.apiKey = el.apiKey.value.trim();
        });

        // Botão Salvar Configurações
        el.btnSaveConfig.addEventListener('click', async () => {
            el.btnSaveConfig.disabled = true;
            this.vm.modelName = el.modelName.value.trim();
            this.vm.modelPrefix = el.modelPrefix.value.trim();
            this.vm.apiBase = el.apiBase.value.trim();
            this.vm.apiKey = el.apiKey.value.trim();
            try {
                await this.vm.saveToStorage();
                this._showSavedIndicator();
                showToast('Configurações salvas com sucesso!', 'success');
            } catch (e) {
                showToast('Erro ao salvar configurações.', 'error');
            } finally {
                el.btnSaveConfig.disabled = false;
            }
        });
    }

    bindViewModel() {
        this.vm.addEventListener('change', (e) => {
            const data = e.detail;
            el.modelName.value = data.modelName || '';
            el.modelPrefix.value = data.modelPrefix || '';
            el.apiBase.value = data.apiBase || '';
            el.apiKey.value = data.apiKey || '';
        });

        this.vm.addEventListener('saved', () => {
            this._showSavedIndicator();
        });
    }
}
