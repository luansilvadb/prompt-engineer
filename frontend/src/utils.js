export function parseLogLine(rawText) {
    let text = rawText.trim();
    if (!text) return null;

    let type = 'info';
    let icon = 'fa-solid fa-circle-info';

    if (text.startsWith('[*]')) {
        type = 'info';
        icon = 'fa-solid fa-circle-info';
        text = text.replace('[*]', '').trim();
    } else if (text.startsWith('[+]')) {
        type = 'success';
        icon = 'fa-solid fa-circle-check';
        text = text.replace('[+]', '').trim();
    } else if (text.startsWith('[!]')) {
        type = 'error';
        icon = 'fa-solid fa-triangle-exclamation';
        text = text.replace('[!]', '').trim();
    } else if (text.includes('[Simulação]') || text.startsWith('[Simulação]')) {
        type = 'simulation';
        icon = 'fa-solid fa-gauge-high';
        text = text.replace('[Simulação]', '').trim();
    } else if (text.includes('[Crítica]') || text.startsWith('[Crítica]')) {
        type = 'critica';
        icon = 'fa-solid fa-comments';
        text = text.replace('[Crítica]', '').trim();
        if (text.startsWith(':')) text = text.substring(1).trim();
    } else if (text.startsWith('---') && text.endsWith('---')) {
        type = 'header';
        icon = 'fa-solid fa-layer-group';
        text = text.replace(/---/g, '').trim();
    } else if (text.startsWith('===') || text.includes('OTIMIZAÇÃO CONCLUÍDA')) {
        type = 'header';
        icon = 'fa-solid fa-flag-checkered';
        text = 'Otimização Concluída';
    }

    return { text, type, icon };
}

export function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

export function computeDiff(original, modified) {
    const originalLines = original.split('\n');
    const modifiedLines = modified.split('\n');
    let diffHtml = '';
    
    let i = 0, j = 0;
    while (i < originalLines.length || j < modifiedLines.length) {
        if (i < originalLines.length && j < modifiedLines.length) {
            if (originalLines[i] === modifiedLines[j]) {
                diffHtml += `<div class="diff-line">  ${escapeHtml(originalLines[i])}</div>`;
                i++;
                j++;
            } else {
                let foundMatch = false;
                for (let look = 1; look <= 5; look++) {
                    if (i + look < originalLines.length && originalLines[i + look] === modifiedLines[j]) {
                        for (let k = 0; k < look; k++) {
                            diffHtml += `<div class="diff-line removed">- ${escapeHtml(originalLines[i + k])}</div>`;
                        }
                        i += look;
                        foundMatch = true;
                        break;
                    }
                    if (j + look < modifiedLines.length && originalLines[i] === modifiedLines[j + look]) {
                        for (let k = 0; k < look; k++) {
                            diffHtml += `<div class="diff-line added">+ ${escapeHtml(modifiedLines[j + k])}</div>`;
                        }
                        j += look;
                        foundMatch = true;
                        break;
                    }
                }
                if (!foundMatch) {
                    diffHtml += `<div class="diff-line removed">- ${escapeHtml(originalLines[i])}</div>`;
                    diffHtml += `<div class="diff-line added">+ ${escapeHtml(modifiedLines[j])}</div>`;
                    i++;
                    j++;
                }
            }
        } else if (i < originalLines.length) {
            diffHtml += `<div class="diff-line removed">- ${escapeHtml(originalLines[i])}</div>`;
            i++;
        } else if (j < modifiedLines.length) {
            diffHtml += `<div class="diff-line added">+ ${escapeHtml(modifiedLines[j])}</div>`;
            j++;
        }
    }
    return diffHtml;
}

export function parseMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="modal-text-block monospace">$1</pre>');
    html = html.replace(/`([^`]+)`/g, '<code class="monospace">$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
    html = html.replace(/^\* (.*?)$/gm, '<li>$1</li>');
    html = html.replace(/^- (.*?)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/g, '<ul>$1</ul>');
    html = html.replace(/<\/ul>\s*<ul>/g, '');
    html = html.replace(/\n\n/g, '</p><p>');
    return '<p>' + html + '</p>';
}
