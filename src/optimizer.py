"""
Optimizer — MCTS Evolutivo com Self-Play

Evolução do core inspirada nos princípios de David Silver (AlphaGo/AlphaZero):

- Progressive Widening: nós promissores ganham mais filhos (vs. max_children fixo)
- Backpropagation com γ discount: nós próximos à folha recebem mais crédito
- Thompson Sampling na seleção final: exploração residual proporcional à incerteza
- Integração com Experience Store (Dyna-2 long-term memory)
- Integração com Value Estimator (bootstrap para pré-filtragem)
- Mutation Strategies com Multi-Armed Bandit (policy diversification)
- Delta Reward Shaping (temporal-difference sobre reward absoluto)
"""

import re
import time
import uuid
from typing import Tuple

from src.domain.agent_interfaces import (
    IAvaliadorModoB,
    IMutadorCognitivoAgent,
    ISelfReflectiveAgent,
    IStrategyDiscoverer,
)
from src.domain.config import MCTSConfig
from src.domain.events import IJobEventEmitter, NodeEventPayload
from src.domain.store_interfaces import IExperienceStore
from src.domain.mcts import MCTSNode
from src.mutation_strategies.bandit_interfaces import IMutationBandit, IStrategyRegistry
from src.signatures import calcular_delta_reward, MutadorCognitivoOutput, _validate_raciocinio, funcao_de_recompensa
from src.experience_store import Experience, hash_instruction
from src.value_estimator import ValueEstimator
from src.mutation_strategies.api import get_strategy_description
from src.semantic_evaluator import calculate_semantic_penalty
from src.heuristic_evaluator import evaluate_heuristics
from src.density_evaluator import calculate_density_multiplier


class Optimizer:
    def __init__(
        self,
        skill_original: str,
        config: MCTSConfig,
        emitter: IJobEventEmitter,
        strategy_discoverer: IStrategyDiscoverer,
        agent: ISelfReflectiveAgent,
        agent_cognitivo: IMutadorCognitivoAgent,
        avaliador_modo_b: IAvaliadorModoB,
        experience_store: IExperienceStore,
        bandit: IMutationBandit,
        strategy_registry: IStrategyRegistry,
        regras_adicionais: str = "",
    ) -> None:
        self.skill_original = skill_original
        self.config = config
        self.strategy_discoverer = strategy_discoverer
        self.agent = agent
        self.agent_cognitivo = agent_cognitivo
        self.avaliador_modo_b = avaliador_modo_b
        self._emitter = emitter
        self.regras_adicionais = regras_adicionais

        self.job_id = uuid.uuid4().hex[:8]
        strategy_registry.set_job_id(self.job_id)
        self._strategy_registry = strategy_registry

        self.experience_store = experience_store
        self.value_estimator = ValueEstimator(learning_rate=config.value_lr)
        self.mutation_bandit = bandit

        strategy_stats = self.experience_store.get_strategy_stats()
        if strategy_stats:
            self.mutation_bandit.load_priors(strategy_stats)
            self._emitter.emit_log(
                f'[*] Memória experiencial carregada: {len(self.experience_store.experiences)} experiências, '
                f'{len(strategy_stats)} estratégias conhecidas.'
            )

        cognitivo_prior = {
            'mutador_cognitivo': {
                'count': config.cognitivo_prior_count,
                'mean_delta': config.cognitivo_prior_mean_delta,
            }
        }
        self.mutation_bandit.load_priors(cognitivo_prior)
        self._emitter.emit_log(
            f'[*] Mutador Cognitivo prior boosting: {config.cognitivo_prior_count} virtual count, '
            f'delta={config.cognitivo_prior_mean_delta}'
        )

    def selection(self, node: MCTSNode) -> MCTSNode:
        """Seleção UCB com progressive widening."""
        cfg = self.config
        while node.children and len(node.children) >= node.max_children_allowed(cfg.progressive_c, cfg.progressive_alpha):
            if self._emitter.is_cancelled():
                return node
            best = node.best_child_ucb(cfg.c_param)
            if best is None:
                return node
            node = best
        return node

    def simulation(self, instruction: str) -> Tuple[float, str]:
        if self._emitter.is_cancelled():
            return 0.0, 'Cancelado pelo usuário.'
        try:
            reward, feedback = funcao_de_recompensa(
                avaliador_modo_b=self.avaliador_modo_b,
                skill_original=self.skill_original,
                skill_otimizada=instruction,
                regras_adicionais=self.regras_adicionais
            )
            if reward == 0.0:
                self._emitter.emit_error(f"    [Simulação] Recompensa 0.00! Motivo: {feedback}")
            else:
                self._emitter.emit_log(f"    [Simulação] Recompensa obtida: {reward:.2f}")

            self.value_estimator.update(instruction, reward)

            return float(reward), feedback
        except Exception as e:
            self._emitter.emit_error(f"[!] Erro na simulação: {e}")
            return 0.0, f"Erro na simulação: {str(e)}"

    def _should_prune(self, instruction: str) -> bool:
        if self.value_estimator.confidence < 0.3:
            return False

        estimated = self.value_estimator.estimate(instruction)
        if estimated < self.config.value_threshold:
            self._emitter.emit_log(f"    [Poda] Value estimator: {estimated:.2f} < threshold {self.config.value_threshold}. Podando.")
            return True
        return False

    def notify_node(self, node: MCTSNode):
        try:
            payload = NodeEventPayload(
                id=node.node_id,
                parent_id=node.parent.node_id if node.parent else None,
                instruction=node.instruction,
                feedback=node.feedback,
                critica=node.critica,
                q_value=node.q_value,
                visits=node.visits,
                score=float(node.q_value / max(1, node.visits)),
                mutation_strategy=node.mutation_strategy,
                depth=node.depth,
                job_id=self.job_id,
            )
            self._emitter.emit_node(payload)
        except Exception as e:
            self._emitter.emit_error(f"[!] Erro ao notificar nó do MCTS: {e}")

    def backpropagation(self, node: MCTSNode, reward: float):
        """
        Backpropagation com γ discount.

        Silver: temporal-difference — nós mais próximos da folha
        recebem mais crédito que nós distantes.
        """
        current = node
        depth_from_leaf = 0
        while current is not None:
            if self._emitter.is_cancelled():
                break
            discounted_reward = reward * (self.config.gamma ** depth_from_leaf)
            current.q_value += discounted_reward
            current.visits += 1
            self.notify_node(current)
            current = current.parent
            depth_from_leaf += 1

    def _discover_strategy(self, leaf: MCTSNode) -> str:
        self._emitter.emit_log('[*] Bandit escolheu __DISCOVER__. Inventando nova heurística de mutação...')
        try:
            estrategias_conhecidas = ", ".join([
                self._strategy_registry.get_name(k)
                for k in self._strategy_registry.get_all_keys()
                if k != '__DISCOVER__'
            ])
            if not estrategias_conhecidas:
                estrategias_conhecidas = "Nenhuma. Você é livre para criar a primeira heurística (Tabula Rasa)."

            nova_estrat = self.strategy_discoverer(
                skill_atual=leaf.instruction,
                feedbacks_recentes=leaf.feedback or "Nenhum feedback ainda. Invente algo inovador.",
                estrategias_conhecidas=estrategias_conhecidas
            )

            key_raw = nova_estrat.nome_estrategia.lower()
            key = re.sub(r'[^a-z0-9_]', '_', key_raw)[:30] + '_' + str(uuid.uuid4())[:4]

            self._strategy_registry.add_strategy(key, nova_estrat.nome_estrategia, nova_estrat.prompt_estrategia)
            self._emitter.emit_log(f'[+] Nova estratégia descoberta! {nova_estrat.nome_estrategia}')
            return key
        except Exception as e:
            self._emitter.emit_error(f'[!] Falha ao inventar estratégia: {e}. Usando fallback.')
            return '__DISCOVER__'

    def _get_lessons_context(self, feedback: str) -> str:
        similar_experiences = self.experience_store.query_similar(feedback, top_k=3)
        if similar_experiences:
            lessons = [f"- Estratégia '{exp.mutation_strategy}': delta={exp.delta_reward:+.2f}"
                       for exp in similar_experiences if exp.delta_reward != 0]
            if lessons:
                return '\nLições de otimizações passadas:\n' + '\n'.join(lessons[:3])
        return ''

    def _validate_cognitive_output(self, predicao) -> None:
        """Valida as seções obrigatórias da saída do agente cognitivo."""
        try:
            _validate_raciocinio(predicao.raciocinio_estruturado)
        except Exception as e:
            self._emitter.emit_error(f'[!] raciocinio_estruturado invalido: {e}')
        try:
            MutadorCognitivoOutput(nova_instrucao=predicao.nova_instrucao)
        except Exception as e:
            self._emitter.emit_error(f'[!] nova_instrucao secoes cognitivas invalidas: {e}')

    def _handle_empty_candidate(self, critica: str) -> Tuple[str, str, bool]:
        """Fallback quando a candidata gerada é nula ou idêntica."""
        self._emitter.emit_error('    [!] Instrução gerada nula ou idêntica. Mudando abordagem...')
        nova_critica = f'{critica}\nInstrução idêntica ou nula. Teste uma mudança radical.'
        return '', nova_critica, False

    def _try_generate_mutation(
        self,
        leaf: MCTSNode,
        strategy: str,
        strategy_prompt: str,
        feedback_completo: str,
        nota: str,
        critica: str
    ) -> Tuple[str, str, bool]:
        try:
            if strategy == 'mutador_cognitivo':
                predicao = self.agent_cognitivo(
                    instrucao_anterior=leaf.instruction,
                    nota_anterior=nota,
                    feedback_juiz=feedback_completo,
                    estrategia_mutacao=strategy_prompt,
                )
                self._validate_cognitive_output(predicao)
            else:
                predicao = self.agent(
                    instrucao_anterior=leaf.instruction,
                    nota_anterior=nota,
                    feedback_juiz=feedback_completo,
                    estrategia_mutacao=strategy_prompt,
                )
            candidata = predicao.nova_instrucao
            if candidata and candidata.strip() and candidata.strip() != leaf.instruction.strip():
                if self._should_prune(candidata):
                    self._emitter.emit_log('    [!] Candidata podada pelo value estimator. Tentando novamente...')
                    nova_critica = f'{critica}\nA última tentativa gerou uma skill de baixa qualidade estimada. Mude radicalmente a abordagem.'
                    return '', nova_critica, False

                self._emitter.emit_log(f'    [Crítica]: {predicao.critica}')
                return candidata, predicao.critica, True
            else:
                return self._handle_empty_candidate(critica)
        except Exception as e:
            self._emitter.emit_error(f'    [!] Erro técnico na geração: {str(e)}')
            nova_critica = f'{critica}\nErro técnico ({e}). Tente uma reescrita mais simples.'
            return '', nova_critica, False

    def _expand_node(self, leaf: MCTSNode) -> MCTSNode:
        strategy = self.mutation_bandit.select()

        if strategy == '__DISCOVER__':
            strategy = self._discover_strategy(leaf)

        strategy_prompt = self._strategy_registry.get_prompt(strategy)
        strategy_desc = self._strategy_registry.get_name(strategy)

        experience_context = self._get_lessons_context(leaf.feedback)

        critica = leaf.feedback
        nova_instrucao = leaf.instruction

        for tentativa in range(3):
            if self._emitter.is_cancelled():
                break
            if tentativa > 0:
                time.sleep(2 * tentativa)

            nota = str(leaf.q_value / max(1, leaf.visits))
            self._emitter.emit_log(f'[*] Expandindo nó (Tentativa {tentativa + 1}/3) | Estratégia: {strategy_desc} | Nota: {nota}')

            feedback_completo = critica
            if experience_context:
                feedback_completo += experience_context

            candidata, nova_critica, sucesso = self._try_generate_mutation(
                leaf, strategy, strategy_prompt, feedback_completo, nota, critica
            )
            critica = nova_critica
            if sucesso:
                nova_instrucao = candidata
                break
        else:
            self._emitter.emit_error('[!] Falha em gerar nova instrução após 3 tentativas. Usando variação mínima.')
            nova_instrucao = f'{leaf.instruction}\n '
            critica = 'Fallback automático.'

        child = MCTSNode(
            nova_instrucao,
            parent=leaf,
            feedback='',
            critica=critica,
            mutation_strategy=strategy,
            depth=leaf.depth + 1,
        )
        leaf.children.append(child)
        self.notify_node(child)
        return child

    def _evaluate_and_prune(self, child: MCTSNode) -> Tuple[bool, dict]:
        """Returns (is_pruned, heuristic_result)"""
        cfg = self.config
        heuristic_result = evaluate_heuristics(
            child.instruction,
            density_min=cfg.lexical_density_min,
            penalty_factor=cfg.verbosity_penalty_factor,
            buzzword_threshold=cfg.buzzword_threshold,
        )
        if heuristic_result.get("prune"):
            self._emitter.emit_log(f"    [Poda Heurística] {heuristic_result.get('reason')}")
            child.feedback = heuristic_result.get("reason")
            child.last_reward = 0.0
            self.backpropagation(child, 0.0)
            return True, heuristic_result
        return False, heuristic_result

    def _apply_heuristic_multiplier(self, reward: float, heuristic_result: dict) -> float:
        multiplier = heuristic_result.get("penalty_multiplier", 1.0)
        if multiplier < 1.0:
            self._emitter.emit_log(f"    [Penalidade Heurística] Fator de decaimento: {multiplier:.2f}")
        return reward * multiplier

    def _apply_semantic_penalty(self, child: MCTSNode, reward: float) -> float:
        parent_instruction = child.parent.instruction if child.parent else self.skill_original
        penalty = calculate_semantic_penalty(
            child.instruction,
            parent_instruction,
            threshold=self.config.semantic_sim_threshold
        )
        if penalty < 1.0:
            self._emitter.emit_log(f"    [Penalidade Semântica] Fator de decaimento: {penalty:.2f}")
        return reward * penalty

    def _apply_density_multiplier(self, child: MCTSNode, reward: float) -> float:
        """
        RN-05: Aplica multiplicador de densidade com guard clauses

        Retorna reward inalterado (multiplicador 1.0) se:
        - Threshold de densidade está desabilitado (lexical_density_min == 0.0)
        - Parent ausente (nó raiz)
        - Instruções têm tamanho idêntico (sem mudança estrutural)
        """
        if not child.parent:
            return reward

        cfg = self.config
        if cfg.lexical_density_min == 0.0:
            return reward

        parent_instruction = child.parent.instruction
        if len(parent_instruction) == len(child.instruction):
            return reward

        density_mult = calculate_density_multiplier(
            child_instruction=child.instruction,
            parent_instruction=parent_instruction,
            mutation_strategy=child.mutation_strategy,
            density_threshold=cfg.density_threshold,
            density_multiplier_min=cfg.density_multiplier_min,
            density_multiplier_max=cfg.density_multiplier_max,
            structured_bonus=cfg.density_structured_bonus,
            min_density=cfg.lexical_density_min,
        )
        if density_mult != 1.0:
            direction = "Bonus por Densidade" if density_mult > 1.0 else "Penalidade por Densidade"
            self._emitter.emit_log(f"    [{direction}] Fator: {density_mult:.2f}")
        return reward * density_mult

    def _run_mcts_iteration(self, root: MCTSNode) -> Tuple[bool, float]:
        """
        RN-06: Verifica cancelamento em 3 checkpoints obrigatórios.

        Returns (should_break, reward).
        """
        cfg = self.config
        if self._emitter.is_cancelled():
            return True, 0.0

        leaf = self.selection(root)
        if len(leaf.children) >= leaf.max_children_allowed(cfg.progressive_c, cfg.progressive_alpha):
            child = leaf
        else:
            child = self._expand_node(leaf)

        if self._emitter.is_cancelled():
            return True, 0.0

        is_pruned, heuristic_result = self._evaluate_and_prune(child)
        if is_pruned:
            return False, 0.0

        if self._emitter.is_cancelled():
            return True, 0.0

        reward, feedback = self.simulation(child.instruction)

        reward = self._apply_heuristic_multiplier(reward, heuristic_result)
        reward = self._apply_semantic_penalty(child, reward)
        reward = self._apply_density_multiplier(child, reward)

        child.feedback = feedback
        child.last_reward = reward

        parent_reward = child.parent.last_reward if child.parent else 0.0
        shaped_reward = calcular_delta_reward(reward, parent_reward)

        self.backpropagation(child, shaped_reward)

        if child.mutation_strategy:
            self.mutation_bandit.update(child.mutation_strategy, shaped_reward)

        self.experience_store.add(Experience(
            skill_hash=hash_instruction(self.skill_original),
            mutation_strategy=child.mutation_strategy,
            delta_reward=reward - parent_reward,
            absolute_reward=reward,
            feedback=feedback[:500],
            parent_instruction_hash=hash_instruction(child.parent.instruction) if child.parent else '',
            instruction=child.instruction,
            parent_instruction=child.parent.instruction if child.parent else self.skill_original
        ))

        return False, reward

    def _get_all_nodes(self, node: MCTSNode) -> list[MCTSNode]:
        nodes = [node]
        for child in node.children:
            if self._emitter.is_cancelled():
                break
            nodes.extend(self._get_all_nodes(child))
        return nodes

    def _run_single_iteration(
        self,
        root: MCTSNode,
        i: int,
        consecutive_zeros: int,
        consecutive_api_errors: int
    ) -> Tuple[bool, int, int]:
        self._emitter.emit_log(f'\n--- Iteração MCTS {i + 1}/{self.config.max_iterations} ---')
        try:
            should_break, iter_reward = self._run_mcts_iteration(root)
            if should_break:
                return True, consecutive_zeros, consecutive_api_errors

            if iter_reward == 0.0:
                consecutive_zeros += 1
            else:
                consecutive_zeros = 0

            consecutive_api_errors = 0

            if consecutive_zeros >= 5:
                self._emitter.emit_error('\n[!] ALERTA: 5 iterações consecutivas com recompensa 0.0. Abortando por plateau.')
                return True, consecutive_zeros, consecutive_api_errors
        except Exception as e:
            consecutive_api_errors += 1
            self._emitter.emit_error(f'[!] Erro inesperado na iteração {i + 1}: {e}')
            if consecutive_api_errors >= 3:
                self._emitter.emit_error('[!] Falhas técnicas persistentes. Abortando.')
                return True, consecutive_zeros, consecutive_api_errors
        return False, consecutive_zeros, consecutive_api_errors

    def _log_bandit_stats(self):
        stats = self.experience_store.get_strategy_stats()
        if stats:
            self._emitter.emit_log('[*] Performance das estratégias de mutação:')
            for strategy, s in sorted(stats.items(), key=lambda x: x[1].get('mean_delta', 0), reverse=True):
                desc = get_strategy_description(strategy)
                self._emitter.emit_log(f'    {desc}: Δ médio={s["mean_delta"]:+.3f}, usos={int(s["count"])}')

    def _select_and_log_best_node(self, root: MCTSNode) -> str:
        all_nodes = self._get_all_nodes(root)
        best_node = max(all_nodes, key=lambda n: n.q_value / max(1, n.visits))

        score = best_node.q_value / max(1, best_node.visits)
        if best_node == root:
            self._emitter.emit_log(f'[+] Raiz mantida como melhor resultado (nenhuma otimização superou): score={score:.3f}, visits={best_node.visits}')
        else:
            self._emitter.emit_log(f'[+] Melhor nó selecionado: score={score:.3f}, visits={best_node.visits}, strategy={get_strategy_description(best_node.mutation_strategy)}')

        return best_node.instruction

    def optimize(self) -> str:
        cfg = self.config
        self._emitter.emit_log('\n[+] Inicializando o pipeline MCTS RL customizado com refinamentos...')
        self._emitter.emit_log(f'    Config: γ={cfg.gamma}, C_ucb={cfg.c_param}, α_pw={cfg.progressive_alpha}, threshold={cfg.value_threshold}')

        root = MCTSNode(self.skill_original, critica='Rascunho Inicial')
        self.notify_node(root)

        self._emitter.emit_log('[*] Avaliando a instrução original (raiz)...')
        reward, feedback = self.simulation(root.instruction)
        root.feedback = feedback
        root.last_reward = reward
        self.backpropagation(root, reward)

        consecutive_zeros = 0
        consecutive_api_errors = 0

        for i in range(cfg.max_iterations):
            if self._emitter.is_cancelled():
                self._emitter.emit_log('\n[!] OTIMIZAÇÃO INTERROMPIDA PELO USUÁRIO.')
                break

            should_break, consecutive_zeros, consecutive_api_errors = self._run_single_iteration(
                root, i, consecutive_zeros, consecutive_api_errors
            )
            if should_break:
                break

        self.experience_store.save()
        self._emitter.emit_log(f'[*] {len(self.experience_store.experiences)} experiências salvas na memória de longo prazo.')

        self._log_bandit_stats()

        self._emitter.emit_log('\n=======================================================\n                OTIMIZAÇÃO CONCLUÍDA                   \n=======================================================\n')

        return self._select_and_log_best_node(root)