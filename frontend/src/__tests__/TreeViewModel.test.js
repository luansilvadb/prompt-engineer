import { describe, it, expect, beforeEach } from "vitest";
import { TreeViewModel } from "../viewmodels/TreeViewModel.js";

describe("TreeViewModel", () => {
    let vm;

    beforeEach(() => {
        vm = new TreeViewModel();
    });

    it("deve inicializar com árvore vazia e bestScore zero", () => {
        const stats = vm.getStats();
        expect(stats.nodeCount).toBe(0);
        expect(stats.bestScore).toBe(0.0);
    });

    it("addNode deve inserir nó e atualizar nodeCount", () => {
        vm.addNode({ id: "n1", score: 0.5, instruction: "test" });
        expect(vm.getStats().nodeCount).toBe(1);
    });

    it("addNode deve atualizar bestScore quando score maior", () => {
        vm.addNode({ id: "n1", score: 0.3 });
        expect(vm.getStats().bestScore).toBe(0.3);

        vm.addNode({ id: "n2", score: 0.8 });
        expect(vm.getStats().bestScore).toBe(0.8);

        vm.addNode({ id: "n3", score: 0.5 });
        expect(vm.getStats().bestScore).toBe(0.8);
    });

    it("addNode deve ignorar nós sem id", () => {
        vm.addNode({ score: 0.5 });
        vm.addNode(null);
        vm.addNode(undefined);
        expect(vm.getStats().nodeCount).toBe(0);
    });

    it("addNode deve disparar evento nodeAdded", () => {
        let fired = false;
        vm.addEventListener("nodeAdded", () => {
            fired = true;
        });
        vm.addNode({ id: "n1", score: 0.5 });
        expect(fired).toBe(true);
    });

    it("addNode deve disparar bestScoreChanged apenas quando score muda", () => {
        let changeCount = 0;
        vm.addEventListener("bestScoreChanged", () => {
            changeCount++;
        });

        vm.addNode({ id: "n1", score: 0.0 });
        expect(changeCount).toBe(1); // bestScore era 0.0, novo é 0.0 → dispara

        vm.addNode({ id: "n2", score: 0.5 });
        expect(changeCount).toBe(2); // 0.0 → 0.5

        vm.addNode({ id: "n3", score: 0.3 });
        expect(changeCount).toBe(2); // 0.5 não mudou
    });

    it("clearTree deve resetar tudo e disparar eventos", () => {
        vm.addNode({ id: "n1", score: 0.8 });
        vm.addNode({ id: "n2", score: 0.3 });

        let cleared = false;
        let scoreChanged = false;
        vm.addEventListener("treeCleared", () => (cleared = true));
        vm.addEventListener("bestScoreChanged", (e) => {
            scoreChanged = true;
            expect(e.detail.bestScore).toBe(0.0);
        });

        vm.clearTree();
        expect(vm.getStats().nodeCount).toBe(0);
        expect(vm.getStats().bestScore).toBe(0.0);
        expect(cleared).toBe(true);
        expect(scoreChanged).toBe(true);
    });

    it("getStats deve refletir estado atual após múltiplas operações", () => {
        vm.addNode({ id: "a", score: 0.2 });
        vm.addNode({ id: "b", score: 0.7 });
        vm.addNode({ id: "c", score: 0.4 });

        expect(vm.getStats()).toEqual({
            nodeCount: 3,
            dagHits: 0,
            bestScore: 0.7,
        });
    });
});