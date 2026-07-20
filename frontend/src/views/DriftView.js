import { el } from '../dom.js';

/**
 * Painel de resultado de drift — substitui alert() bloqueante.
 * Renderiza métricas detalhadas do DriftReport em um modal rico.
 */
export class DriftView {
    constructor() {
        this._bindModal();
    }

    _bindModal() {
        if (el.btnCloseDrift) {
            el.btnCloseDrift.addEventListener('click', () => this.hide());
        }
        if (el.driftModalOverlay) {
            el.driftModalOverlay.addEventListener('click', (e) => {
                if (e.target === el.driftModalOverlay) this.hide();
            });
        }
    }

    /**
     * Exibe o resultado de drift no modal.
     * @param {object} result - Resposta completa da API { status, report, circuit_breaker }
     */
    show(result) {
        if (!el.driftModalOverlay) return;

        if (result.status === 'no_golden') {
            this._renderNoGolden(result.message);
        } else if (result.status === 'error') {
            this._renderError(result.message);
        } else if (result.report) {
            this._renderReport(result.report, result.circuit_breaker);
        }

        el.driftModalOverlay.classList.add('active');
    }

    hide() {
        if (el.driftModalOverlay) {
            el.driftModalOverlay.classList.remove('active');
        }
    }

    // ── Render helpers ──────────────────────────────────────────────

    _renderNoGolden(msg) {
        el.driftModalTitle.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Sem Golden Set';
        el.driftModalBody.innerHTML = `
            <div class="drift-status drift-status-warning">
                <i class="fa-solid fa-circle-exclamation"></i>
                <span>${msg || 'Golden set ausente. Nenhuma medição disponível.'}</span>
            </div>`;
    }

    _renderError(msg) {
        el.driftModalTitle.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> Erro na Verificação';
        el.driftModalBody.innerHTML = `
            <div class="drift-status drift-status-danger">
                <i class="fa-solid fa-bug"></i>
                <span>${msg || 'Falha ao medir drift.'}</span>
            </div>`;
    }

    _renderReport(report, cb) {
        const spearman = (report.spearman_composite * 100).toFixed(1);
        const offset = report.offset_scale.toFixed(2);
        const missed = report.missed_violations;
        const falseRej = report.false_rejections;
        const variance = report.mean_variance?.toFixed(2) || '0.00';
        const ts = report.measured_at
            ? new Date(report.measured_at * 1000).toLocaleString('pt-BR')
            : '-';

        // Status visual
        let statusClass = 'drift-status-ok';
        let statusIcon = 'fa-circle-check';
        let statusText = 'Juiz Saudável';
        if (!cb.accept) {
            statusClass = 'drift-status-danger';
            statusIcon = 'fa-shield-halved';
            statusText = 'Circuit Breaker Disparado';
        } else if (missed > 0) {
            statusClass = 'drift-status-warning';
            statusIcon = 'fa-circle-exclamation';
            statusText = 'Atenção — Violações Detectadas';
        }

        el.driftModalTitle.innerHTML = '<i class="fa-solid fa-shield-halved"></i> Resultado da Verificação de Drift';

        // MAE por dimensão
        const dimLabels = {
            nota_clareza: 'Clareza', nota_formatacao: 'Formatação',
            nota_robustez: 'Robustez', nota_densidade_informacional: 'Densidade Informacional',
            nota_acionabilidade: 'Acionabilidade', nota_anti_fragilidade: 'Anti-fragilidade'
        };
        let maeRows = '';
        if (report.mae_per_dimension) {
            maeRows = report.mae_per_dimension.map(d => `
                <tr>
                    <td>${dimLabels[d.dimension] || d.dimension}</td>
                    <td>${d.mae.toFixed(2)}</td>
                </tr>`).join('');
        }

        el.driftModalBody.innerHTML = `
            <div class="drift-status ${statusClass}">
                <i class="fa-solid ${statusIcon}"></i>
                <span>${statusText}</span>
            </div>

            <div class="drift-metrics-grid">
                <div class="drift-metric">
                    <span class="drift-metric-label">Spearman (Ranking)</span>
                    <span class="drift-metric-value ${spearman >= 80 ? 'good' : spearman >= 60 ? 'warn' : 'bad'}">${spearman}%</span>
                </div>
                <div class="drift-metric">
                    <span class="drift-metric-label">Offset de Escala</span>
                    <span class="drift-metric-value">${offset}</span>
                </div>
                <div class="drift-metric">
                    <span class="drift-metric-label">Violações Aprovadas</span>
                    <span class="drift-metric-value ${missed === 0 ? 'good' : 'bad'}">${missed}</span>
                </div>
                <div class="drift-metric">
                    <span class="drift-metric-label">Excesso de Rigor</span>
                    <span class="drift-metric-value">${falseRej}</span>
                </div>
                <div class="drift-metric">
                    <span class="drift-metric-label">Variância Média</span>
                    <span class="drift-metric-value">${variance}</span>
                </div>
                <div class="drift-metric">
                    <span class="drift-metric-label">Medido em</span>
                    <span class="drift-metric-value drift-timestamp">${ts}</span>
                </div>
            </div>

            ${maeRows ? `
            <div class="drift-section">
                <h4><i class="fa-solid fa-table"></i> MAE por Dimensão</h4>
                <table class="drift-mae-table">
                    <thead><tr><th>Dimensão</th><th>MAE</th></tr></thead>
                    <tbody>${maeRows}</tbody>
                </table>
            </div>` : ''}

            <div class="drift-section">
                <h4><i class="fa-solid fa-gavel"></i> Decisão</h4>
                <div class="drift-decision ${cb.accept ? 'accept' : 'reject'}">
                    <i class="fa-solid ${cb.accept ? 'fa-check' : 'fa-xmark'}"></i>
                    <span>${cb.reason}</span>
                </div>
            </div>`;
    }
}