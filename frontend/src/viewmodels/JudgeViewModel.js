import { ViewModelBase } from './ViewModelBase.js';

export class JudgeViewModel extends ViewModelBase {
    constructor() {
        super();
    }

    async trainJudge() {
        this.dispatchEvent(new CustomEvent('trainingStarted'));
        try {
            const res = await fetch('/api/train-judge', { method: 'POST' });
            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || 'Treinamento falhou.');
            }

            this.dispatchEvent(new CustomEvent('trainingFinished', {
                detail: {
                    success: true,
                    status: data.status,
                    message: data.message || data.warning
                }
            }));
            return data;
        } catch (err) {
            this.dispatchEvent(new CustomEvent('trainingFinished', {
                detail: {
                    success: false,
                    message: err.message
                }
            }));
            throw err;
        }
    }

    /**
     * Check drift via POST /api/check-drift (medição fresh + CB).
     * Dispara evento com resposta completa para renderização no DriftView.
     *
     * P0-C1: AbortController com timeout de 120s garante que o botão sempre
     * sai do spinner, mesmo se o backend não responder. Alinhado ao timeout
     * do backend (100s): frontend ganha por margem de 20s para renderizar
     * erro limpo.
     */
    async checkDrift() {
        const DRIFT_CHECK_TIMEOUT_MS = 120000;  // 120s (backend: 100s + 20s margem)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), DRIFT_CHECK_TIMEOUT_MS);

        this.dispatchEvent(new CustomEvent('driftCheckStarted'));
        try {
            const res = await fetch('/api/check-drift', {
                method: 'POST',
                signal: controller.signal,
            });

            // HTTP 504 (timeout do backend P1-C2): mensagem específica.
            if (res.status === 504) {
                throw new Error('Verificação de drift excedeu o tempo máximo (timeout no servidor). Verifique conectividade e chave de API.');
            }

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.message || data.detail || 'Verificação falhou.');
            }

            this.dispatchEvent(new CustomEvent('driftCheckFinished', {
                detail: {
                    success: true,
                    data: data
                }
            }));
            return data;
        } catch (err) {
            // AbortError: frontend abortou por timeout — mensagem específica.
            const isTimeout = err.name === 'AbortError';
            const message = isTimeout
                ? 'Verificação de drift excedeu o tempo limite (120s) e foi cancelada.'
                : err.message;

            this.dispatchEvent(new CustomEvent('driftCheckFinished', {
                detail: {
                    success: false,
                    message: message,
                    timeout: isTimeout,
                }
            }));
            throw err;
        } finally {
            clearTimeout(timeoutId);
        }
    }

    /**
     * Poll do status de drift via GET /api/drift-status (cache, sem medição).
     * Usado pelo badge de saúde no header.
     */
    async fetchDriftStatus() {
        try {
            const res = await fetch('/api/drift-status');
            const data = await res.json();
            this.dispatchEvent(new CustomEvent('driftStatusUpdated', {
                detail: { data }
            }));
            return data;
        } catch (err) {
            // Silencioso — o badge mantém o último estado conhecido
            return null;
        }
    }
}