import { el } from '../dom.js';
import { escapeHtml } from '../utils.js';

export class TreeView {
    constructor(viewModel) {
        this.vm = viewModel;
        this.nodeElements = new Map(); // nodeId -> childrenContainer element
        this.isDown = false;
        this.startX = 0;
        this.startY = 0;
        this.canvasX = 0;
        this.canvasY = 0;
        this.currentZoom = 1.0;

        this.initCanvasEvents();
        this.initModalEvents();
        this.bindViewModel();
    }

    initCanvasEvents() {
        const btnRecenter = document.getElementById('btn-recenter-tree');
        if (btnRecenter) {
            btnRecenter.addEventListener('click', () => this.recenterTree());
        }

        el.treeContainer.addEventListener('mousedown', (e) => {
            this.isDown = true;
            this.startX = e.pageX - this.canvasX;
            this.startY = e.pageY - this.canvasY;
            el.treeContainer.style.cursor = 'grabbing';
        });

        el.treeContainer.addEventListener('mouseleave', () => {
            this.isDown = false;
            el.treeContainer.style.cursor = 'grab';
        });

        el.treeContainer.addEventListener('mouseup', () => {
            this.isDown = false;
            el.treeContainer.style.cursor = 'grab';
        });

        el.treeContainer.addEventListener('mousemove', (e) => {
            if (!this.isDown) return;
            e.preventDefault();
            this.canvasX = e.pageX - this.startX;
            this.canvasY = e.pageY - this.startY;
            this.applyCanvasTransform();
        });

        el.treeContainer.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomDelta = e.deltaY > 0 ? -0.1 : 0.1;
            this.currentZoom = Math.max(0.3, Math.min(2.0, this.currentZoom + zoomDelta));
            this.applyCanvasTransform();
        }, { passive: false });
    }

    applyCanvasTransform() {
        el.treeCanvas.style.transform = `translate(${this.canvasX}px, ${this.canvasY}px) scale(${this.currentZoom})`;
    }

    recenterTree() {
        this.canvasX = 0;
        this.canvasY = 0;
        this.currentZoom = 1.0;
        this.applyCanvasTransform();
    }

    initModalEvents() {
        el.btnCloseModal.addEventListener('click', () => this.closeNodeModal());
        el.nodeModal.addEventListener('click', (e) => {
            if (e.target === el.nodeModal) this.closeNodeModal();
        });

        const btnCopyNodeInstruction = document.getElementById('btn-copy-node-instruction');
        if (btnCopyNodeInstruction) {
            btnCopyNodeInstruction.addEventListener('click', () => {
                const textToCopy = el.modalNodeInstruction.textContent;
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const originalHtml = btnCopyNodeInstruction.innerHTML;
                    btnCopyNodeInstruction.innerHTML = '<i class="fa-solid fa-check" style="color: var(--color-success)"></i>';
                    setTimeout(() => {
                        btnCopyNodeInstruction.innerHTML = originalHtml;
                    }, 2000);
                }).catch(err => console.error('Erro ao copiar:', err));
            });
        }
    }

    openNodeModal(nodeId) {
        const node = this.vm.mctsNodes[nodeId];
        if (!node) return;

        el.modalNodeId.textContent = node.id;
        el.modalNodeScore.textContent = `${(node.score * 100).toFixed(1)}%`;
        el.modalNodeVisits.textContent = node.visits;
        el.modalNodeCritica.textContent = node.critica || 'Sem crítica/feedback para a raiz.';
        el.modalNodeInstruction.textContent = node.instruction;

        el.nodeModal.classList.add('active');
    }

    closeNodeModal() {
        el.nodeModal.classList.remove('active');
    }

    bindViewModel() {
        this.vm.addEventListener('nodeAdded', (e) => {
            const { node, nodeCount } = e.detail;
            el.mctsNodeCount.textContent = nodeCount;
            this.addNodeDOM(node);
        });

        this.vm.addEventListener('bestScoreChanged', (e) => {
            const scorePercent = (e.detail.bestScore * 100).toFixed(1);
            el.mctsBestScore.textContent = `${scorePercent}%`;
            this.highlightBestNodes();
        });

        this.vm.addEventListener('treeCleared', () => {
            el.treeCanvas.innerHTML = '';
            el.mctsNodeCount.textContent = '0';
            el.mctsBestScore.textContent = '0.0%';
            this.nodeElements.clear();
            this.recenterTree();
        });
    }

    addNodeDOM(node) {
        // Se o nó já estiver desenhado, ignora ou atualiza
        if (this.nodeElements.has(node.id)) {
            this.updateNodeDOM(node);
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'tree-branch';

        const card = document.createElement('div');
        card.id = `node-card-${node.id}`;
        card.addEventListener('click', () => this.openNodeModal(node.id));

        const scorePercent = (node.score * 100).toFixed(1);
        const isRoot = !node.parent_id;

        let extraClass = '';
        if (isRoot) extraClass = 'root-node';
        else if (node.score === this.vm.bestScore && node.score > 0) extraClass = 'best-node';

        card.className = `node-card ${extraClass}`;
        card.innerHTML = `
            <div class="node-header">
                <div class="node-score-wrapper">
                    <span class="node-score-badge">${scorePercent}%</span>
                    ${isRoot ? '<span class="node-critica-badge"><i class="fa-solid fa-anchor"></i> Raiz</span>' : ''}
                </div>
                <span class="node-visits"><i class="fa-solid fa-eye"></i> ${node.visits} v</span>
            </div>
            <div class="node-instruction-preview">${escapeHtml(node.instruction)}</div>
            <div class="node-footer">
                <span class="node-critica-badge">${node.critica ? 'Refletido' : 'Simulado'}</span>
                <span>${node.id.substring(0, 8)}...</span>
            </div>
        `;

        // Destaque de caminho (hover)
        card.addEventListener('mouseenter', () => {
            let current = node;
            while (current) {
                const parentCard = document.getElementById(`node-card-${current.id}`);
                if (parentCard) parentCard.classList.add('highlight-path');
                current = current.parent_id ? this.vm.mctsNodes[current.parent_id] : null;
            }
        });
        card.addEventListener('mouseleave', () => {
            document.querySelectorAll('.node-card.highlight-path').forEach(c => {
                c.classList.remove('highlight-path');
            });
        });

        wrapper.appendChild(card);

        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'node-children';
        wrapper.appendChild(childrenContainer);

        this.nodeElements.set(node.id, childrenContainer);

        if (isRoot) {
            el.treeCanvas.innerHTML = '';
            el.treeCanvas.appendChild(wrapper);
        } else {
            const parentChildrenContainer = this.nodeElements.get(node.parent_id);
            if (parentChildrenContainer) {
                parentChildrenContainer.appendChild(wrapper);
            } else {
                // Se por acaso o pai não foi renderizado ainda, recria a árvore
                this.renderAll();
            }
        }
    }

    updateNodeDOM(node) {
        const card = document.getElementById(`node-card-${node.id}`);
        if (!card) return;

        const scorePercent = (node.score * 100).toFixed(1);
        const isRoot = !node.parent_id;

        let extraClass = '';
        if (isRoot) extraClass = 'root-node';
        else if (node.score === this.vm.bestScore && node.score > 0) extraClass = 'best-node';

        card.className = `node-card ${extraClass}`;
        
        // Atualiza conteúdo
        card.querySelector('.node-score-badge').textContent = `${scorePercent}%`;
        card.querySelector('.node-visits').innerHTML = `<i class="fa-solid fa-eye"></i> ${node.visits} v`;
        card.querySelector('.node-instruction-preview').textContent = escapeHtml(node.instruction);
        card.querySelector('.node-footer span').textContent = node.critica ? 'Refletido' : 'Simulado';
    }

    highlightBestNodes() {
        Object.values(this.vm.mctsNodes).forEach(node => {
            const card = document.getElementById(`node-card-${node.id}`);
            if (card) {
                const isRoot = !node.parent_id;
                if (!isRoot) {
                    if (node.score === this.vm.bestScore && node.score > 0) {
                        card.classList.add('best-node');
                    } else {
                        card.classList.remove('best-node');
                    }
                }
            }
        });
    }

    renderAll() {
        el.treeCanvas.innerHTML = '';
        this.nodeElements.clear();

        const rootNode = Object.values(this.vm.mctsNodes).find(n => !n.parent_id);
        if (!rootNode) return;

        // Renderiza recursivo ordenado por id para garantir estrutura correta
        const renderQueue = [rootNode];
        while (renderQueue.length > 0) {
            const current = renderQueue.shift();
            this.addNodeDOM(current);
            const children = Object.values(this.vm.mctsNodes).filter(n => n.parent_id === current.id);
            renderQueue.push(...children);
        }
    }
}
