import { el } from './dom.js';
import { ConfigViewModel } from './viewmodels/ConfigViewModel.js';
import { TreeViewModel } from './viewmodels/TreeViewModel.js';
import { ConsoleViewModel } from './viewmodels/ConsoleViewModel.js';
import { HistoryViewModel } from './viewmodels/HistoryViewModel.js';
import { JudgeViewModel } from './viewmodels/JudgeViewModel.js';

import { ConfigView } from './views/ConfigView.js';
import { TreeView } from './views/TreeView.js';
import { ConsoleView } from './views/ConsoleView.js';
import { HistoryView } from './views/HistoryView.js';
import { JudgeView } from './views/JudgeView.js';

import { connectSSE } from './sse.js';
import { parseMarkdown, computeDiff } from './utils.js';
import { showToast } from './utils/toast.js';
import { initShortcuts } from './shortcuts.js';

// ── Inicializar ViewModels ──────────────────────────────────────────────────
const configVm = new ConfigViewModel();
const treeVm = new TreeViewModel();
const consoleVm = new ConsoleViewModel();
const historyVm = new HistoryViewModel();
const judgeVm = new JudgeViewModel();

// ── Inicializar Views ───────────────────────────────────────────────────────
const configView = new ConfigView(configVm);
const treeView = new TreeView(treeVm);
const consoleView = new ConsoleView(consoleVm);
const historyView = new HistoryView(historyVm);
const judgeView = new JudgeView(judgeVm);

// ── Estado de orquestração local ────────────────────────────────────────────
let activeEventSource = null;
let currentJobId = null;
let stateOriginalSkill = '';
let stateOptimizedSkill = '';

// ── Mensagem inicial no console ─────────────────────────────────────────────
consoleVm.addLogsInstant(['[*] Aguardando início do processo...']);

// ── Carregar configurações do localStorage ──────────────────────────────────
configVm.loadFromStorage();

// ── Health Check: polling a cada 30s ────────────────────────────────────────
async function checkApiHealth() {
    try {
        const res = await fetch('/api/health');
        if (res.ok) {
            const data = await res.json();
            updateStatus('idle', data.llm_configured ? 'LLM pronto' : 'Pronto (sem LLM)');
        } else {
            updateStatus('error', 'API offline');
        }
    } catch {
        updateStatus('error', 'API offline');
    }
}
checkApiHealth();
setInterval(checkApiHealth, 30000);

// ── Iniciar polling do badge de drift (a cada 60s) ─────────────────────────
judgeVm.fetchDriftStatus();
setInterval(() => {
    judgeVm.fetchDriftStatus();
}, 60000);

// ── Funções globais de UI ───────────────────────────────────────────────────
export function updateStatus(status, text) {
    el.globalStatusIndicator.className = `status-indicator ${status}`;
    el.globalStatusText.textContent = text;
}

export function setUIRunning(running) {
    if (running) {
        el.btnStartOpt.classList.add('hidden');
        el.btnStopOpt.classList.remove('hidden');
        el.welcomePanel.style.display = 'none';
        el.progressPanel.style.display = 'flex';
        el.mctsPanel.style.display = 'flex';
        el.resultPanel.style.display = 'none';
        el.progressBarFill.style.width = '5%';

        consoleVm.clear();
        consoleVm.addLog('[*] Conectando ao servidor...');
        treeVm.clearTree();
    } else {
        el.btnStartOpt.classList.remove('hidden');
        el.btnStartOpt.disabled = false;
        el.btnStopOpt.classList.add('hidden');
        el.progressBarFill.style.width = '100%';
    }
}

// ── Escuta por mudanças de status vindas da JudgeView ───────────────────────
judgeView.addEventListener('statusChanged', (e) => {
    updateStatus(e.detail.status, e.detail.text);
});

// ── Tabs do painel de resultados ────────────────────────────────────────────
el.tabBtnOptimized.addEventListener('click', () => {
    el.tabBtnOptimized.classList.add('active');
    el.tabBtnDiff.classList.remove('active');
    el.tabContentOptimized.classList.remove('hidden');
    el.tabContentDiff.classList.add('hidden');
});

el.tabBtnDiff.addEventListener('click', () => {
    el.tabBtnDiff.classList.add('active');
    el.tabBtnOptimized.classList.remove('active');
    el.tabContentDiff.classList.remove('hidden');
    el.tabContentOptimized.classList.add('hidden');
});

el.btnViewDiff.addEventListener('click', () => {
    el.tabBtnDiff.click();
});

// ── Copiar resultado final para a área de transferência ─────────────────────
function copyResultToClipboard() {
    if (!stateOptimizedSkill) {
        showToast('Nenhuma skill otimizada para copiar.', 'warning');
        return;
    }

    navigator.clipboard.writeText(stateOptimizedSkill)
        .then(() => {
            const originalText = el.btnCopyResult.innerHTML;
            el.btnCopyResult.innerHTML = '<i class="fa-solid fa-check"></i> Copiado!';
            el.btnCopyResult.style.borderColor = 'var(--color-success)';
            el.btnCopyResult.style.color = 'var(--color-success)';
            showToast('Skill copiada para a área de transferência!', 'success');
            setTimeout(() => {
                el.btnCopyResult.innerHTML = originalText;
                el.btnCopyResult.style.borderColor = '';
                el.btnCopyResult.style.color = '';
            }, 2000);
        })
        .catch(err => {
            console.error('Failed to copy text: ', err);
            showToast('Falha ao copiar para a área de transferência.', 'error');
        });
}

el.btnCopyResult.addEventListener('click', copyResultToClipboard);

// ── Função para fechar todos os modais abertos ──────────────────────────────
function closeAllModals() {
    // Fecha modal de detalhe de nó
    if (el.nodeModal && el.nodeModal.style.display === 'flex') {
        el.nodeModal.style.display = 'none';
    }
    // Fecha modal de drift
    const driftOverlay = document.getElementById('drift-modal-overlay');
    if (driftOverlay && driftOverlay.style.display === 'flex') {
        driftOverlay.style.display = 'none';
    }
    // Fecha modal de histórico
    const historyModal = document.getElementById('history-modal');
    if (historyModal && historyModal.style.display === 'flex') {
        historyModal.style.display = 'none';
    }
}

// ── Inicializar Keyboard Shortcuts ──────────────────────────────────────────
initShortcuts({
    onStartOptimization: () => {
        // Simula clique no botão de iniciar otimização
        if (!el.btnStartOpt.classList.contains('hidden') && !el.btnStartOpt.disabled) {
            el.btnStartOpt.click();
        } else {
            showToast('Otimização já está em andamento.', 'info');
        }
    },
    onCopyResult: () => {
        copyResultToClipboard();
    },
    onOpenHistory: () => {
        el.btnOpenHistory.click();
    },
    closeAllModals,
});

// ── Escuta job do histórico carregado ───────────────────────────────────────
historyVm.addEventListener('jobDetailsLoaded', (e) => {
    const job = e.detail.job;

    // Parar SSE ativo se houver
    if (activeEventSource) {
        activeEventSource.close();
        activeEventSource = null;
    }

    // 1. Restaurar configurações
    configVm.modelName = job.model_name || '';
    configVm.modelPrefix = job.model_prefix || '';
    configVm.apiBase = job.api_base || '';

    configVm.dispatchEvent(new CustomEvent('change', {
        detail: {
            modelName: configVm.modelName,
            modelPrefix: configVm.modelPrefix,
            apiBase: configVm.apiBase,
            apiKey: configVm.apiKey,
        },
    }));

    // 2. Restaurar Árvore MCTS
    treeVm.clearTree();
    if (job.mcts_nodes && Array.isArray(job.mcts_nodes)) {
        job.mcts_nodes.forEach(n => treeVm.addNode(n));
    }
    treeView.renderAll();

    // 3. Restaurar Logs
    if (job.logs && Array.isArray(job.logs)) {
        consoleVm.addLogsInstant(job.logs);
    } else {
        consoleVm.addLogsInstant(['[!] Sem logs salvos.']);
    }

    // 4. Restaurar inputs visuais e painéis
    stateOriginalSkill = job.original_skill || '';
    el.originalSkillInput.value = stateOriginalSkill;

    el.welcomePanel.style.display = 'none';
    el.progressPanel.style.display = 'flex';
    el.mctsPanel.style.display = 'flex';

    currentJobId = job.id;

    if (job.status === 'completed') {
        el.resultPanel.style.display = 'flex';
        stateOptimizedSkill = job.result || '';
        el.optimizedSkillOutput.innerHTML = parseMarkdown(stateOptimizedSkill);
        el.diffOutputContainer.innerHTML = computeDiff(stateOriginalSkill, stateOptimizedSkill);
        el.progressBarFill.style.width = '100%';

        el.btnStartOpt.classList.remove('hidden');
        el.btnStartOpt.disabled = false;
        el.btnStopOpt.classList.add('hidden');
        showToast('Job carregado do histórico.', 'success');
    } else {
        el.resultPanel.style.display = 'none';
        if (job.status === 'running') {
            el.btnStartOpt.classList.add('hidden');
            el.btnStopOpt.classList.remove('hidden');

            activeEventSource = connectSSE(
                job.id,
                treeVm,
                consoleVm,
                (optimized) => {
                    stateOptimizedSkill = optimized;
                    el.resultPanel.style.display = 'flex';
                    el.optimizedSkillOutput.innerHTML = parseMarkdown(optimized);
                    el.diffOutputContainer.innerHTML = computeDiff(stateOriginalSkill, optimized);
                },
                () => {
                    activeEventSource = null;
                },
                updateStatus,
                setUIRunning,
                configVm,
            );
        } else {
            el.progressBarFill.style.width = '100%';
            el.btnStartOpt.classList.remove('hidden');
            el.btnStartOpt.disabled = false;
            el.btnStopOpt.classList.add('hidden');
        }
    }

    updateStatus(job.status, job.status === 'completed' ? 'Concluído' : job.status);
});

// ── Iniciar Otimização MCTS ─────────────────────────────────────────────────
el.btnStartOpt.addEventListener('click', async () => {
    if (el.btnStartOpt.disabled) return;

    const skill = el.originalSkillInput.value.trim();
    if (!skill) {
        showToast('Por favor, insira a Skill original a ser otimizada.', 'warning');
        return;
    }

    stateOriginalSkill = skill;
    el.btnStartOpt.disabled = true;
    setUIRunning(true);
    updateStatus('running', 'Iniciando...');

    const payload = {
        skillOriginal: skill,
        modelName: configVm.modelName || null,
        modelPrefix: configVm.modelPrefix || null,
        apiBase: configVm.apiBase || null,
        apiKey: configVm.apiKey || null,
    };

    try {
        const res = await fetch('/api/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            const detail = data.detail || `Erro HTTP ${res.status}`;
            throw new Error(detail);
        }

        const data = await res.json();
        currentJobId = data.job_id;

        showToast('Otimização MCTS iniciada!', 'success');

        activeEventSource = connectSSE(
            currentJobId,
            treeVm,
            consoleVm,
            (optimized) => {
                stateOptimizedSkill = optimized;
                el.resultPanel.style.display = 'flex';
                el.optimizedSkillOutput.innerHTML = parseMarkdown(optimized);
                el.diffOutputContainer.innerHTML = computeDiff(stateOriginalSkill, optimized);
            },
            () => {
                activeEventSource = null;
            },
            updateStatus,
            setUIRunning,
            configVm,
        );
    } catch (err) {
        setUIRunning(false);
        updateStatus('error', 'Falha');
        consoleVm.addLog(`[!] Erro na requisição: ${err.message}`);
        showToast(`Falha ao conectar na API: ${err.message}`, 'error', 6000);
    }
});

// ── Parar Execução ──────────────────────────────────────────────────────────
el.btnStopOpt.addEventListener('click', async () => {
    if (!currentJobId) return;

    updateStatus('running', 'Interrompendo...');
    try {
        await fetch(`/api/stop/${currentJobId}`, { method: 'POST' });
        showToast('Sinal de interrupção enviado.', 'info');
    } catch (err) {
        console.error('Error stopping job:', err);
        showToast('Erro ao enviar sinal de interrupção.', 'error');
    }
});