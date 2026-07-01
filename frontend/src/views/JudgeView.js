import { el } from '../dom.js';

export class JudgeView extends EventTarget {
    constructor(viewModel) {
        super();
        this.vm = viewModel;
        this.initEvents();
        this.bindViewModel();
    }

    initEvents() {
        if (el.btnTrainJudge) {
            el.btnTrainJudge.addEventListener('click', () => {
                if (el.btnTrainJudge.disabled) return;
                this.vm.trainJudge().catch(err => {
                    // Erros já são tratados via eventos do ViewModel
                });
            });
        }

        if (el.btnCheckDrift) {
            el.btnCheckDrift.addEventListener('click', () => {
                if (el.btnCheckDrift.disabled) return;
                this.vm.checkDrift().catch(err => {
                    // Erros já são tratados via eventos do ViewModel
                });
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
                if (status === 'golden_empty_open') {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'error', text: 'Sem Golden Set' }
                    }));
                    alert('⚠️ ATENÇÃO: O golden set está ausente!\n\n' +
                          'O juiz foi recompilado SEM o portão de drift (fail-open).\n' +
                          'Você NÃO está protegido contra drift.\n\n' +
                          'Verifique se o arquivo src/outputs/golden/golden_set.json existe.');
                } else {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'completed', text: 'Juiz Treinado' }
                    }));
                    alert('Avaliador recompilado e validado contra o golden set.');
                }
            } else {
                if (message && message.includes('rejeitado pelo portão')) {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'idle', text: 'Drift Rejeitado' }
                    }));
                    alert('✅ Portão de drift ATIVO.\n\n' +
                          'O candidato a juiz foi rejeitado (pioraria o drift).\n' +
                          'O juiz anterior foi preservado.\n\n' +
                          message);
                } else {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'error', text: 'Falha' }
                    }));
                    alert(`Treinamento falhou. ${message}`);
                }
            }
        });

        // Verificação de Drift
        this.vm.addEventListener('driftCheckStarted', () => {
            this.driftOriginalHtml = el.btnCheckDrift.innerHTML;
            el.btnCheckDrift.disabled = true;
            el.btnCheckDrift.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Verificando...';
            this.dispatchEvent(new CustomEvent('statusChanged', {
                detail: { status: 'running', text: 'Verificando Drift...' }
            }));
        });

        this.vm.addEventListener('driftCheckFinished', (e) => {
            el.btnCheckDrift.disabled = false;
            if (this.driftOriginalHtml) {
                el.btnCheckDrift.innerHTML = this.driftOriginalHtml;
            }

            const { success, data, message } = e.detail;

            if (success) {
                if (data.status === 'no_golden') {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'error', text: 'Sem Golden Set' }
                    }));
                    alert('⚠️ Golden set ausente. Não há como medir drift.\n' +
                          'Verifique src/outputs/golden/golden_set.json.');
                    return;
                }

                const r = data.report;
                const cb = data.circuit_breaker;
                const spearman = (r.spearman_composite * 100).toFixed(1);
                const offset = r.offset_scale.toFixed(2);
                const missed = r.missed_violations;
                const falseRej = r.false_rejections;

                if (!cb.accept) {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'error', text: 'Rollback Aplicado' }
                    }));
                    alert('🛑 CIRCUIT BREAKER DISPAROU.\n\n' +
                          `O juiz atual aprovou ${missed} violação(ões) de regras críticas.\n` +
                          'Rollback automático ao juiz zerado.\n\n' +
                          `Spearman: ${spearman}% | Offset: ${offset}\n` +
                          `Detalhe: ${cb.reason}`);
                } else {
                    this.dispatchEvent(new CustomEvent('statusChanged', {
                        detail: { status: 'completed', text: 'Juiz OK' }
                    }));

                    let alertMsg = '✅ Juiz saudável.\n\n' +
                                   `Spearman (ranking): ${spearman}%\n` +
                                   `Offset de escala: ${offset}\n` +
                                   `Violações aprovadas: ${missed}\n` +
                                   `Excesso de rigor: ${falseRej}`;
                    if (missed > 0) {
                        alertMsg += '\n\n⚠️ Há violações aprovadas — investigar!';
                    }
                    alert(alertMsg);
                }
            } else {
                this.dispatchEvent(new CustomEvent('statusChanged', {
                    detail: { status: 'error', text: 'Falha' }
                }));
                alert(`Verificação falhou. ${message}`);
            }
        });
    }

}
