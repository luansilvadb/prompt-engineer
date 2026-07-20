/**
 * Keyboard Shortcuts — Atalhos de teclado para operações frequentes.
 *
 * Mapeamento:
 *   Ctrl+Enter   → Iniciar otimização
 *   Ctrl+S       → Salvar/Copiar skill otimizada
 *   Escape       → Fechar modais abertos
 *   ?            → Exibir overlay de ajuda (quando nenhum input focado)
 *   Ctrl+H       → Abrir histórico
 */

let isHelpVisible = false;
let helpOverlay = null;


/**
 * Cria o overlay de ajuda de atalhos de teclado (exibido com `?`).
 */
function createHelpOverlay() {
    if (helpOverlay) return helpOverlay;

    helpOverlay = document.createElement('div');
    helpOverlay.id = 'shortcuts-help-overlay';
    helpOverlay.className = 'modal-overlay';
    helpOverlay.style.display = 'none';
    helpOverlay.innerHTML = `
      <div class="modal glass shortcuts-modal-content" style="max-width: 480px;">
        <div class="modal-header">
          <h3><i class="fa-solid fa-keyboard"></i> Atalhos de Teclado</h3>
          <button type="button" class="btn-close-modal" id="btn-close-shortcuts" aria-label="Fechar" title="Fechar">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="modal-body" style="display: flex; flex-direction: column; gap: 12px;">
          <div class="shortcut-row">
            <kbd class="shortcut-key">Ctrl</kbd> + <kbd class="shortcut-key">Enter</kbd>
            <span>Iniciar otimização MCTS</span>
          </div>
          <div class="shortcut-row">
            <kbd class="shortcut-key">Ctrl</kbd> + <kbd class="shortcut-key">S</kbd>
            <span>Copiar skill otimizada</span>
          </div>
          <div class="shortcut-row">
            <kbd class="shortcut-key">Escape</kbd>
            <span>Fechar modais e overlays</span>
          </div>
          <div class="shortcut-row">
            <kbd class="shortcut-key">Ctrl</kbd> + <kbd class="shortcut-key">H</kbd>
            <span>Abrir histórico de execuções</span>
          </div>
          <div class="shortcut-row">
            <kbd class="shortcut-key">?</kbd>
            <span>Exibir / ocultar esta ajuda</span>
          </div>
        </div>
      </div>
    `;

    // CSS inline para os kbd
    const style = document.createElement('style');
    style.textContent = `
      .shortcut-row {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: var(--color-text-secondary, #aaa);
      }
      .shortcut-key {
        display: inline-block;
        min-width: 28px;
        padding: 4px 8px;
        background: var(--color-bg-input, #0d0d1a);
        border: 1px solid var(--color-border, #2a2a4a);
        border-radius: 4px;
        font-family: var(--font-mono, 'JetBrains Mono', monospace);
        font-size: 11px;
        color: var(--color-text-primary, #e0e0e0);
        text-align: center;
        text-transform: uppercase;
      }
      .shortcut-row span {
        flex: 1;
        margin-left: 8px;
      }
    `;
    document.head.appendChild(style);

    helpOverlay.addEventListener('click', (e) => {
        if (e.target === helpOverlay) hideHelp();
    });
    helpOverlay.querySelector('#btn-close-shortcuts').addEventListener('click', hideHelp);

    document.body.appendChild(helpOverlay);
    return helpOverlay;
}


function showHelp() {
    const overlay = createHelpOverlay();
    overlay.style.display = 'flex';
    isHelpVisible = true;
}


function hideHelp() {
    if (helpOverlay) {
        helpOverlay.style.display = 'none';
        isHelpVisible = false;
    }
}


/**
 * Verifica se o foco está em um elemento de entrada de texto (input, textarea, select, contenteditable).
 * Se sim, atalhos de tecla única (como `?`) são ignorados para não interferir na digitação.
 */
function isInputFocused() {
    const el = document.activeElement;
    if (!el) return false;
    const tag = el.tagName.toLowerCase();
    return (
        tag === 'input' ||
        tag === 'textarea' ||
        tag === 'select' ||
        el.isContentEditable
    );
}


/**
 * Inicializa os listeners de teclado para atalhos globais.
 * @param {Object} handlers - Objeto com funções de callback para cada ação
 * @param {Function} handlers.onStartOptimization - Callback para Ctrl+Enter
 * @param {Function} handlers.onCopyResult - Callback para Ctrl+S
 * @param {Function} handlers.onOpenHistory - Callback para Ctrl+H
 * @param {Function} handlers.closeAllModals - Callback para Escape
 */
export function initShortcuts(handlers = {}) {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Enter → Iniciar otimização
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (handlers.onStartOptimization) {
                handlers.onStartOptimization();
            }
            return;
        }

        // Ctrl+S → Copiar resultado
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            if (handlers.onCopyResult) {
                handlers.onCopyResult();
            }
            return;
        }

        // Ctrl+H → Abrir histórico
        if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
            e.preventDefault();
            if (handlers.onOpenHistory) {
                handlers.onOpenHistory();
            }
            return;
        }

        // ? → Exibir ajuda (apenas quando foco não está em input)
        if (e.key === '?' && !isInputFocused() && !e.ctrlKey && !e.metaKey && !e.altKey) {
            e.preventDefault();
            if (isHelpVisible) {
                hideHelp();
            } else {
                showHelp();
            }
            return;
        }

        // Escape → Fechar modais
        if (e.key === 'Escape') {
            if (isHelpVisible) {
                hideHelp();
                return;
            }
            if (handlers.closeAllModals) {
                handlers.closeAllModals();
            }
        }
    });

    // Adiciona hint visual de atalhos no footer ou como tooltip
    console.debug('[Shortcuts] Keyboard shortcuts initialized. Press ? for help.');
}