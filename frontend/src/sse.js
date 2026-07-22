import { el } from './dom.js';
import { parseMarkdown, computeDiff } from './utils.js';
import { showToast } from './utils/toast.js';

/**
 * ReconnectingSSE — wrapper com backoff exponencial sobre EventSource.
 *
 * Estrategia:
 *   - Backoff: 1s → 2s → 4s → 8s → 16s (max 30s)
 *   - Maximo de 5 tentativas antes de desistencia permanente
 *   - Reset do backoff apos conexao bem-sucedida
 *   - Eventos 'end' encerram o ciclo permanentemente (nao reconecta)
 *   - Preserva estado da arvore e logs durante reconexao
 */
class ReconnectingSSE {
    constructor(url, handlers) {
        this._url = url;
        this._handlers = handlers;
        this._eventSource = null;
        this._retryCount = 0;
        this._maxRetries = 5;
        this._baseDelay = 1000; // 1s
        this._maxDelay = 30000; // 30s
        this._ended = false;    // true apos evento 'end' — nao reconectar
        this._connect();
    }

    _connect() {
        if (this._ended) return;

        this._eventSource = new EventSource(this._url);

        this._eventSource.onopen = () => {
            this._retryCount = 0; // reset backoff
            if (this._handlers.onOpen) {
                this._handlers.onOpen();
            }
        };

        this._eventSource.onmessage = (e) => {
            if (this._handlers.onMessage) {
                this._handlers.onMessage(e);
            }
        };

        // Eventos nomeados
        const namedEvents = ['node', 'result', 'end', 'cost'];
        namedEvents.forEach(eventName => {
            this._eventSource.addEventListener(eventName, (e) => {
                if (eventName === 'end') {
                    this._ended = true;
                }
                if (this._handlers[eventName]) {
                    this._handlers[eventName](e);
                }
            });
        });

        this._eventSource.onerror = (err) => {
            console.error('SSE Error (tentativa ' + (this._retryCount + 1) + '/' + this._maxRetries + '):', err);

            if (this._ended) {
                this.close();
                return;
            }

            this._eventSource.close();
            this._retryCount++;

            if (this._retryCount > this._maxRetries) {
                console.error('SSE: maximo de tentativas excedido. Desistindo.');
                if (this._handlers.onPermanentFailure) {
                    this._handlers.onPermanentFailure();
                }
                return;
            }

            const delay = Math.min(this._baseDelay * Math.pow(2, this._retryCount - 1), this._maxDelay);
            console.log('SSE: reconectando em ' + (delay / 1000) + 's...');
            if (this._handlers.onReconnecting) {
                this._handlers.onReconnecting(this._retryCount, delay);
            }
            setTimeout(() => this._connect(), delay);
        };
    }

    close() {
        this._ended = true;
        if (this._eventSource) {
            this._eventSource.close();
            this._eventSource = null;
        }
    }
}

export function connectSSE(jobId, treeVm, consoleVm, onResult, onEnd, updateStatus, setUIRunning, configVm) {
    const url = `/api/stream/${jobId}`;

    const sse = new ReconnectingSSE(url, {
        onOpen: () => {
            updateStatus('running', 'Otimizando...');
        },

        onMessage: (e) => {
            const data = JSON.parse(e.data);
            if (data.text) {
                consoleVm.addLog(data.text);

                if (data.text.includes('Iteração MCTS')) {
                    const match = data.text.match(/Iteração MCTS (\d+)\/(\d+)/);
                    if (match) {
                        const current = parseInt(match[1]);
                        const total = parseInt(match[2]);
                        const percent = Math.min(95, Math.round((current / total) * 100));
                        el.progressBarFill.style.width = `${percent}%`;

                        // Atualiza título do painel de progresso com iteração real
                        const panelHeader = el.progressPanel?.querySelector('.panel-header h2');
                        if (panelHeader) {
                            panelHeader.innerHTML = `<i class="fa-solid fa-terminal"></i> Console de Execução <small>(${current}/${total})</small>`;
                        }
                    }
                }
            }
        },

        node: (e) => {
            const node = JSON.parse(e.data);
            treeVm.addNode(node);

            // Atualiza métricas em tempo real no header da árvore MCTS
            const stats = treeVm.getStats();
            if (stats) {
                if (el.mctsNodeCount) el.mctsNodeCount.textContent = stats.nodeCount;
                if (el.mctsDagHits) el.mctsDagHits.textContent = stats.dagHits || 0;
                if (el.mctsBestScore) {
                    el.mctsBestScore.textContent = (stats.bestScore * 100).toFixed(1) + '%';
                }
            }
        },

        result: (e) => {
            const result = JSON.parse(e.data);
            const optimizedSkill = result.optimized;
            onResult(optimizedSkill);
        },

        cost: (e) => {
            // Item 13: metricas de custo por iteracao
            const costData = JSON.parse(e.data);
            if (costData.iteration && costData.llm_calls) {
                consoleVm.addLog(
                    `    [Custo] Iteracao ${costData.iteration}: ${costData.llm_calls} chamadas LLM` +
                    (costData.estimated_tokens ? `, ~${costData.estimated_tokens} tokens` : '')
                );
            }
        },

        end: (e) => {
            const finalStatus = e.data;
            sse.close();

            setUIRunning(false);
            onEnd(finalStatus);

            if (finalStatus === 'completed') {
                updateStatus('completed', 'Concluído');
                consoleVm.addLog('[+] PROCESSO CONCLUÍDO COM SUCESSO!');
                showToast('Otimização concluída com sucesso!', 'success');
            } else if (finalStatus === 'cancelled') {
                updateStatus('idle', 'Cancelado');
                consoleVm.addLog('[!] OTIMIZAÇÃO CANCELADA PELO USUÁRIO OU SERVIDOR.');
                showToast('Otimização cancelada.', 'warning');
            } else if (finalStatus === 'timeout') {
                updateStatus('error', 'Timeout');
                consoleVm.addLog('[!] TIMEOUT - A otimização excedeu o tempo máximo configurado.');
                showToast('Timeout: otimização excedeu o tempo máximo.', 'error', 8000);
            } else {
                updateStatus('error', 'Erro');
                consoleVm.addLog('[!] FALHA NA EXECUÇÃO - VERIFIQUE AS CONFIGURAÇÕES.');
                showToast('Falha na execução da otimização.', 'error', 6000);
            }
        },

        onReconnecting: (attempt, delay) => {
            updateStatus('running', `Reconectando (${attempt}/${sse._maxRetries})...`);
            consoleVm.addLog(`[*] Conexao perdida. Reconectando em ${(delay / 1000).toFixed(0)}s... (tentativa ${attempt}/${sse._maxRetries})`);
            showToast(`Conexao perdida. Reconectando... (${attempt}/${sse._maxRetries})`, 'warning', delay);
        },

        onPermanentFailure: () => {
            updateStatus('error', 'Conexão perdida');
            consoleVm.addLog('[!] FALHA PERMANENTE DE CONEXAO. A otimizacao pode ter sido interrompida.');
            showToast('Conexao SSE perdida permanentemente. Recarregue a pagina.', 'error', 10000);
            setUIRunning(false);
        },
    });

    return sse;
}
