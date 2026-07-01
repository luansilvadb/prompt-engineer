import { el } from '../dom.js';

export class ConfigView {
    constructor(viewModel) {
        this.vm = viewModel;
        this.initEvents();
        this.bindViewModel();
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

        // Add Rule
        el.btnAddRule.addEventListener('click', () => {
            const ruleText = el.newRuleInput.value.trim();
            if (ruleText) {
                this.vm.addRule(ruleText);
                el.newRuleInput.value = '';
            }
        });

        el.newRuleInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                el.btnAddRule.click();
            }
        });

        // Remove Rule via Delegation
        el.rulesList.addEventListener('click', (e) => {
            const button = e.target.closest('button');
            if (button) {
                const idx = parseInt(button.dataset.index);
                this.vm.removeRule(idx);
            }
        });

        // Sincronizar inputs em tempo real com o ViewModel
        el.modelName.addEventListener('input', () => {
            this.vm.modelName = el.modelName.value.trim();
            this.vm.saveToStorage();
        });

        el.modelPrefix.addEventListener('input', () => {
            this.vm.modelPrefix = el.modelPrefix.value.trim();
            this.vm.saveToStorage();
        });

        el.apiBase.addEventListener('input', () => {
            this.vm.apiBase = el.apiBase.value.trim();
            this.vm.saveToStorage();
        });

        el.apiKey.addEventListener('input', () => {
            this.vm.apiKey = el.apiKey.value.trim();
            this.vm.saveToStorage();
        });
    }

    bindViewModel() {
        this.vm.addEventListener('change', (e) => {
            const data = e.detail;
            el.modelName.value = data.modelName || '';
            el.modelPrefix.value = data.modelPrefix || '';
            el.apiBase.value = data.apiBase || '';
            el.apiKey.value = data.apiKey || '';
            this.renderRules(data.regrasAdicionais);
        });

        this.vm.addEventListener('rulesChanged', (e) => {
            this.renderRules(e.detail);
        });
    }

    renderRules(rules) {
        el.rulesList.innerHTML = '';
        rules.forEach((rule, idx) => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>${rule}</span>
                <button type="button" data-index="${idx}" title="Excluir diretriz" aria-label="Excluir diretriz"><i class="fa-regular fa-trash-can"></i></button>
            `;
            el.rulesList.appendChild(li);
        });
    }
}
