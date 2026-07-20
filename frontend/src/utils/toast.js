/**
 * Sistema de Toast Notifications — Feedback visual não-bloqueante.
 *
 * Uso:
 *   import { showToast } from './utils/toast.js';
 *   showToast('Otimização iniciada!', 'success');
 *   showToast('Erro ao conectar', 'error');
 *   showToast('Atenção: golden set ausente', 'warning');
 *   showToast('Drift medido com sucesso', 'info');
 */

const TOAST_CONTAINER_ID = 'toast-container';
const MAX_VISIBLE_TOASTS = 3;

/** @type {HTMLElement|null} */
let container = null;


/** Garante que o container de toasts existe no DOM */
function ensureContainer() {
    if (container) return container;

    container = document.getElementById(TOAST_CONTAINER_ID);
    if (!container) {
        container = document.createElement('div');
        container.id = TOAST_CONTAINER_ID;
        container.setAttribute('role', 'status');
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-label', 'Notificações');
        // Estilos inline para garantir posicionamento mesmo sem CSS carregado
        Object.assign(container.style, {
            position: 'fixed',
            top: '80px',
            right: '24px',
            zIndex: '9999',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            pointerEvents: 'none',
        });
        document.body.appendChild(container);
    }
    return container;
}


/** Remove os toasts mais antigos se houver mais que MAX_VISIBLE_TOASTS */
function pruneOldToasts() {
    const toasts = container.querySelectorAll('.toast-notification');
    while (toasts.length > MAX_VISIBLE_TOASTS) {
        const oldest = toasts[0];
        oldest.classList.add('toast-exit');
        oldest.addEventListener('transitionend', () => oldest.remove(), { once: true });
    }
}


/**
 * Exibe um toast notification.
 * @param {string} message - Texto da notificação
 * @param {'success'|'error'|'warning'|'info'} type - Tipo visual
 * @param {number} [duration=4000] - Duração em ms antes do auto-dismiss (0 = permanente)
 */
export function showToast(message, type = 'info', duration = 4000) {
    const container = ensureContainer();

    const icons = {
        success: 'fa-circle-check',
        error: 'fa-circle-exclamation',
        warning: 'fa-triangle-exclamation',
        info: 'fa-circle-info',
    };

    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
      <i class="fa-solid ${icons[type] || icons.info} toast-icon"></i>
      <span class="toast-message">${message}</span>
      <button type="button" class="toast-dismiss" aria-label="Fechar notificação" title="Fechar">
        <i class="fa-solid fa-xmark"></i>
      </button>
    `;

    // Animação de entrada
    toast.style.animation = 'toastSlideIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards';

    // Botão dismiss
    const dismissBtn = toast.querySelector('.toast-dismiss');
    dismissBtn.addEventListener('click', () => dismissToast(toast));

    container.appendChild(toast);
    pruneOldToasts();

    // Auto-dismiss
    if (duration > 0) {
        const timer = setTimeout(() => dismissToast(toast), duration);
        // Cancela o timer se o usuário interagir
        toast.addEventListener('mouseenter', () => clearTimeout(timer));
        toast.addEventListener('mouseleave', () => {
            const remaining = setTimeout(() => dismissToast(toast), Math.min(duration, 2000));
            toast._dismissTimer = remaining;
        });
    }

    return toast;
}


/** Remove um toast com animação de saída */
function dismissToast(toast) {
    if (toast._dismissed) return;
    toast._dismissed = true;

    toast.style.animation = 'toastSlideOut 0.2s ease-in forwards';
    toast.addEventListener('animationend', () => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, { once: true });
}


// ── CSS-in-JS para animações dos toasts ────────────────────────────────────
function injectToastStyles() {
    if (document.getElementById('toast-styles')) return;

    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
      @keyframes toastSlideIn {
        from { opacity: 0; transform: translateX(100px) scale(0.9); }
        to   { opacity: 1; transform: translateX(0) scale(1); }
      }
      @keyframes toastSlideOut {
        from { opacity: 1; transform: translateX(0) scale(1); }
        to   { opacity: 0; transform: translateX(100px) scale(0.9); }
      }

      .toast-notification {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 300px;
        max-width: 480px;
        padding: 12px 16px;
        border-radius: 8px;
        background: var(--color-bg-elevated, #1a1a2e);
        border: 1px solid var(--color-border, #2a2a4a);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        font-family: var(--font-body, 'Manrope', sans-serif);
        font-size: 13px;
        color: var(--color-text-primary, #e0e0e0);
        pointer-events: auto;
        backdrop-filter: blur(12px);
        transition: opacity 0.2s ease, transform 0.2s ease;
      }

      .toast-notification.toast-success {
        border-left: 4px solid var(--color-success, #00c853);
      }
      .toast-notification.toast-error {
        border-left: 4px solid var(--color-error, #ff1744);
      }
      .toast-notification.toast-warning {
        border-left: 4px solid var(--color-warning, #ffab00);
      }
      .toast-notification.toast-info {
        border-left: 4px solid var(--color-accent, #448aff);
      }

      .toast-icon {
        font-size: 16px;
        flex-shrink: 0;
      }
      .toast-success .toast-icon { color: var(--color-success, #00c853); }
      .toast-error   .toast-icon { color: var(--color-error, #ff1744); }
      .toast-warning .toast-icon { color: var(--color-warning, #ffab00); }
      .toast-info    .toast-icon { color: var(--color-accent, #448aff); }

      .toast-message {
        flex: 1;
        line-height: 1.4;
      }

      .toast-dismiss {
        background: none;
        border: none;
        color: var(--color-text-tertiary, #666);
        cursor: pointer;
        padding: 4px;
        border-radius: 4px;
        flex-shrink: 0;
        font-size: 12px;
        transition: color 0.15s;
      }
      .toast-dismiss:hover {
        color: var(--color-text-primary, #e0e0e0);
      }
    `;
    document.head.appendChild(style);
}

// Injeta os estilos ao carregar o módulo
if (typeof document !== 'undefined') {
    injectToastStyles();
}