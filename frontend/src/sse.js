import { el } from './dom.js';
import { parseMarkdown, computeDiff } from './utils.js';

export function connectSSE(jobId, treeVm, consoleVm, onResult, onEnd, updateStatus, setUIRunning, configVm) {
    const url = `/api/stream/${jobId}`;
    const eventSource = new EventSource(url);

    eventSource.onopen = () => {
        updateStatus('running', 'Otimizando...');
    };

    eventSource.onmessage = (e) => {
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
                }
            }
        }
    };

    eventSource.addEventListener('node', (e) => {
        const node = JSON.parse(e.data);
        treeVm.addNode(node);
    });

    eventSource.addEventListener('result', (e) => {
        const result = JSON.parse(e.data);
        const optimizedSkill = result.optimized;
        onResult(optimizedSkill);
    });

    eventSource.addEventListener('end', (e) => {
        const finalStatus = e.data;
        eventSource.close();
        
        setUIRunning(false);
        onEnd(finalStatus);

        if (finalStatus === 'completed') {
            updateStatus('completed', 'Concluído');
            consoleVm.addLog('[+] PROCESSO CONCLUÍDO COM SUCESSO!');
        } else if (finalStatus === 'cancelled') {
            updateStatus('idle', 'Cancelado');
            consoleVm.addLog('[!] OTIMIZAÇÃO CANCELADA PELO USUÁRIO OU SERVIDOR.');
        } else {
            updateStatus('error', 'Erro');
            consoleVm.addLog('[!] FALHA NA EXECUÇÃO - VERIFIQUE AS CONFIGURAÇÕES.');
        }
    });

    eventSource.onerror = (err) => {
        console.error('SSE Error:', err);
    };

    return eventSource;
}
