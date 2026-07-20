import { el } from '../dom.js';
import { DriftView } from './DriftView.js';
import { showToast } from '../utils/toast.js';

export class JudgeView extends EventTarget {
    constructor(viewModel) {
        super();
        this.vm = viewModel;
        this.driftView = new DriftView();
        this.initEvents();
        this.bindViewModel();
    }

    initEvents() {
        if (el.btnTrainJudge) {
            el.btnTrainJudge.addEventListener('click', () => {
                if (el.btnTrainJudge.disabled) return;
                this.vm.trainJudge().catch(() => { });
            });
        }

        if (el.btnCheckDrift) {
            el.btnCheckDrift.addEventListener('click', () => {
                if (el.btnCheckDrift.disabled) return;
                this.vm.checkDrift().catch(() => { });
            });
        }
    }

    bindViewModel() {
        // Treinamento do Juiz
        this.vm.addEventListener('trainingStarted', () => {
            this.trainOriginalHtml = el.btnTrainJudge.innerHTML;
            el.btnTrainJudge.disabled = true;
            el.btnTrainJudge.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Treinando...';
            this.dispatchEvent(new CustomEvent('statusChanged', {
                detail: { status: 'running', text: 'Treinando Juiz...' }
            }));
        });

        this.vm.addEventListener('trainingFinished', (e) => {
            el.btnTrainJudge.disabled = false;
            if (this.trainOriginalHtml) {
                el.btnTrainJudge.innerHTML = this.trainOriginalHtml;
            }

            const { success, status, message } = e.detail;
            if (success) {
                this.dispatchEvent(new CustomEvent('statusChanged', {
                    detail: { status: 'completed', text: 'Juiz Treinado' }
                }));
                showToast('Avaliador recompilado e validado contra o golden set.', 'success');
            } else {
                if (message && message.includes('Golden set ausente')) {
                    // fail-closed: golden set é pré-requisito obrigatório
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'error', text: 'Golden Set Ausente' }
                    }));
                    showToast(
                        '⚠️ Candidato descartado: Golden set ausente. Crie o golden set em src/outputs/golden/golden_set.json antes de treinar o avaliador.',
                        'warning',
                        10000
                    );
                } else if (message && message.includes('rejeitado pelo portão')) {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'idle', text: 'Drift Rejeitado' }
                    }));
                    showToast('Portão de drift ATIVO: candidato rejeitado, juiz anterior preservado.', 'success', 6000);
                } else {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'error', text: 'Falha' }
                    }));
                    showToast(`Treinamento falhou: ${message}`, 'error', 6000);
                }
            }
        });

        // Verificação de Drift — usa DriftView (modal) em vez de alert()
        this.vm.addEventListener('driftCheckStarted', () => {
            // Guard: se já estiver spinando (disabled), ignora para evitar estado inconsistente
            if (el.btnCheckDrift.disabled) return;
            el.btnCheckDrift.disabled = true;
            el.btnCheckDrift.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Verificando...';
            this.dispatchEvent(new CustomEvent('statusChanged', {
                detail: { status: 'running', text: 'Verificando Drift...' }
            }));
        });

        this.vm.addEventListener('driftCheckFinished', (e) => {
            el.btnCheckDrift.disabled = false;
            // Sempre restaura para o HTML canônico — não depende do estado capturado
            el.btnCheckDrift.innerHTML = '<i class="fa-solid fa-shield-halved"></i> Verificar Drift';

            const { success, data, message } = e.detail;

            if (success) {
                // Renderiza resultado rico no modal DriftView
                this.driftView.show(data);

                if (data.circuit_breaker && !data.circuit_breaker.accept) {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'error', text: 'Rollback Aplicado' }
                    }));
                } else {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'completed', text: 'Juiz OK' }
                    }));
                }
            } else {
                this.dispatchEvent(new CustomEvent('statusChanged', {
                    detail: { status: 'error', text: 'Falha' }
                }));
                this.driftView.show({
                    status: 'error',
                    message: message || 'Falha na verificação de drift.'
                });
            }
        });

        // Atualização periódica do badge de saúde (polling)
        this.vm.addEventListener('driftStatusUpdated', (e) => {
            this._updateHealthBadge(e.detail.data);
        });
    }

    /**
     * Atualiza o badge de saúde do juiz no header.
     * Chamado pelo polling periódico e também após checkDrift.
     * @param {object} data - Resposta de GET /api/drift-status
     */
    _updateHealthBadge(data) {
        if (!el.driftHealthBadge) return;

        const badge = el.driftHealthBadge;
        if (data.status === 'no_cache') {
            badge.className = 'drift-health-badge unknown';
            badge.title = 'Nenhuma medição de drift disponível';
            badge.innerHTML = '<i class="fa-solid fa-circle-question"></i> Drift: ?';
            return;
        }

        const r = data.report;
        if (!r) {
            badge.className = 'drift-health-badge unknown';
            badge.title = 'Dados de drift indisponíveis';
            badge.innerHTML = '<i class="fa-solid fa-circle-question"></i> Drift: ?';
            return;
        }

        const spearman = (r.spearman_composite * 100).toFixed(0);
        const missed = r.missed_violations || 0;

        if (r.critical_rules_violated) {
            badge.className = 'drift-health-badge danger';
            badge.title = `CRÍTICO: ${missed} violação(ões) aprovadas — Spearman ${spearman}%`;
            badge.innerHTML = `<i class="fa-solid fa-shield-halved"></i> Drift: 🛑`;
        } else if (missed > 0) {
            badge.className = 'drift-health-badge warning';
            badge.title = `Atenção: ${missed} violação(ões) detectadas — Spearman ${spearman}%`;
            badge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Drift: ${spearman}%`;
        } else {
            badge.className = 'drift-health-badge ok';
            badge.title = `Juiz saudável — Spearman ${spearman}%, Offset ${r.offset_scale?.toFixed(2) || '0'}`;
            badge.innerHTML = `<i class="fa-solid fa-circle-check"></i> Drift: ${spearman}%`;
        }
    }
}