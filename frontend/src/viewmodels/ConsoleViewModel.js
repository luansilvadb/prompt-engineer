import { ViewModelBase } from './ViewModelBase.js';
import { parseLogLine } from '../utils.js';

export class ConsoleViewModel extends ViewModelBase {
    constructor() {
        super();
        this.queue = [];
        this.logsList = []; // Histórico completo dos logs parseados
    }

    addLog(rawText) {
        if (!rawText) return;
        const lines = rawText.split('\n');
        const newItems = [];
        lines.forEach(line => {
            const parsed = parseLogLine(line);
            if (parsed) {
                newItems.push(parsed);
                this.logsList.push(parsed);
            }
        });

        if (newItems.length > 0) {
            this.dispatchEvent(new CustomEvent('logsAdded', {
                detail: {
                    items: newItems,
                    totalPending: this.logsList.length
                }
            }));
        }
    }

    addLogsInstant(logsArray) {
        this.clear();
        if (!logsArray || !Array.isArray(logsArray)) return;
        logsArray.forEach(logLine => {
            const parsed = parseLogLine(logLine);
            if (parsed) {
                this.logsList.push(parsed);
            }
        });
        this.dispatchEvent(new CustomEvent('logsReset', {
            detail: {
                items: this.logsList
            }
        }));
    }

    clear() {
        this.queue = [];
        this.logsList = [];
        this.dispatchEvent(new CustomEvent('consoleCleared'));
    }
}
