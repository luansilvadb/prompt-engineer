import { ViewModelBase } from './ViewModelBase.js';

export class TreeViewModel extends ViewModelBase {
    constructor() {
        super();
        this.mctsNodes = {};
        this.bestScore = 0.0;
    }

    addNode(node) {
        if (!node || !node.id) return;

        this.mctsNodes[node.id] = node;

        let newBestScore = 0.0;
        Object.values(this.mctsNodes).forEach(n => {
            if (n.score > newBestScore) {
                newBestScore = n.score;
            }
        });

        const hasBestScoreChanged = newBestScore !== this.bestScore;
        this.bestScore = newBestScore;

        this.dispatchEvent(new CustomEvent('nodeAdded', {
            detail: {
                node,
                nodeCount: Object.keys(this.mctsNodes).length
            }
        }));

        if (hasBestScoreChanged || newBestScore === 0.0) {
            this.dispatchEvent(new CustomEvent('bestScoreChanged', {
                detail: {
                    bestScore: this.bestScore
                }
            }));
        }
    }

    getStats() {
        return {
            nodeCount: Object.keys(this.mctsNodes).length,
            dagHits: 0, // será populado pelo backend via SSE futuramente
            bestScore: this.bestScore,
        };
    }

    clearTree() {
        this.mctsNodes = {};
        this.bestScore = 0.0;
        this.dispatchEvent(new CustomEvent('treeCleared'));
        this.dispatchEvent(new CustomEvent('bestScoreChanged', {
            detail: {
                bestScore: this.bestScore
            }
        }));
    }
}
