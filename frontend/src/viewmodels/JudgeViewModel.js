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

    async checkDrift() {
        this.dispatchEvent(new CustomEvent('driftCheckStarted'));
        try {
            const res = await fetch('/api/check-drift', { method: 'POST' });
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
            this.dispatchEvent(new CustomEvent('driftCheckFinished', {
                detail: {
                    success: false,
                    message: err.message
                }
            }));
            throw err;
        }
    }
}
