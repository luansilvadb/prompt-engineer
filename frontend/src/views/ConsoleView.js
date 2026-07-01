import { el } from '../dom.js';

export class ConsoleView {
    constructor(viewModel) {
        this.vm = viewModel;
        this.queue = [];
        this.isProcessing = false;
        this.activeCursorSpan = null;
        
        this.bindViewModel();
    }

    bindViewModel() {
        this.vm.addEventListener('logsAdded', (e) => {
            const { items } = e.detail;
            const skipTyping = items.length > 10 || this.queue.length > 10;
            
            items.forEach(item => {
                this.queue.push({ item, skipTyping });
            });
            this.processQueue();
        });

        this.vm.addEventListener('logsReset', (e) => {
            this.clearDOM();
            e.detail.items.forEach(item => {
                this.renderLineInstant(item);
            });
        });

        this.vm.addEventListener('consoleCleared', () => {
            this.clearDOM();
        });
    }

    clearDOM() {
        this.queue = [];
        this.isProcessing = false;
        if (this.activeCursorSpan) {
            this.activeCursorSpan.classList.remove('console-cursor');
            this.activeCursorSpan = null;
        }
        el.consoleOutput.innerHTML = '';
    }

    async processQueue() {
        if (this.isProcessing) return;
        this.isProcessing = true;

        while (this.queue.length > 0) {
            const current = this.queue.shift();
            // Se o tamanho restante da fila cresceu, força pular o efeito de digitação
            const forceSkip = this.queue.length > 5 || current.skipTyping;
            await this.renderLine(current.item, forceSkip);
        }

        this.isProcessing = false;
    }

    renderLine(item, skipTyping) {
        return new Promise((resolve) => {
            if (this.activeCursorSpan) {
                this.activeCursorSpan.classList.remove('console-cursor');
            }

            const lineDiv = document.createElement('div');
            lineDiv.className = `console-line console-line-${item.type}`;

            const icon = document.createElement('i');
            icon.className = item.icon;

            const textSpan = document.createElement('span');

            lineDiv.appendChild(icon);
            lineDiv.appendChild(textSpan);
            el.consoleOutput.appendChild(lineDiv);

            el.consoleOutput.scrollTop = el.consoleOutput.scrollHeight;

            if (skipTyping) {
                textSpan.textContent = item.text;
                resolve();
            } else {
                textSpan.classList.add('console-cursor');
                this.activeCursorSpan = textSpan;

                let idx = 0;
                const charDelay = 8; // Um pouco mais rápido para melhor fluidez

                const typeChar = () => {
                    if (idx < item.text.length) {
                        textSpan.textContent += item.text.charAt(idx);
                        idx++;
                        el.consoleOutput.scrollTop = el.consoleOutput.scrollHeight;
                        setTimeout(typeChar, charDelay);
                    } else {
                        resolve();
                    }
                };
                typeChar();
            }
        });
    }

    renderLineInstant(item) {
        const lineDiv = document.createElement('div');
        lineDiv.className = `console-line console-line-${item.type}`;
        
        const icon = document.createElement('i');
        icon.className = item.icon;
        
        const textSpan = document.createElement('span');
        textSpan.textContent = item.text;
        
        lineDiv.appendChild(icon);
        lineDiv.appendChild(textSpan);
        el.consoleOutput.appendChild(lineDiv);
        el.consoleOutput.scrollTop = el.consoleOutput.scrollHeight;
    }
}
