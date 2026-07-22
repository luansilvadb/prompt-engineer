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
import threading
import concurrent.futures
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
from src.domain.mcts import MCTSNode, TranspositionTable
from src.domain.bandit_interfaces import IMutationBandit, IStrategyRegistry
from src.signatures import calcular_delta_reward, MutadorCognitivoOutput, _validate_raciocinio, funcao_de_recompensa
from src.experience_store import Experience, hash_instruction
from src.evaluators import (
    ValueEstimator,
    calculate_density_multiplier,
    calculate_semantic_penalty,
    compute_lexical_density,
    evaluate_heuristics,
)
from src.mutation_strategies.api import get_strategy_description


# ── helpers de poda dinâmica (extraídos de _should_prune) ─────────────────────

def _check_lexical_critical(instruction: str) -> bool:
    """Poda por densidade lexical crítica (< 0.15)."""
    ld = compute_lexical_density(instruction)
    return 0 < ld < 0.15


def _check_density_critical(instruction: str, ref_instruction: str, mutation_strategy: str = "") -> bool:
    """Poda por densidade informacional crítica (< 0.20)."""
    if len(ref_instruction) < 50:
        return False
    dm = calculate_density_multiplier(instruction, ref_instruction, mutation_strategy=mutation_strategy)
    return dm < 0.20


def _check_semantic_critical(instruction: str, parent_instruction: str) -> bool:
    """Poda por penalidade semântica excessiva (< 0.4)."""
    sp = calculate_semantic_penalty(instruction, parent_instruction)
    return sp < 0.4


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

        self._expansion_order: list[dict] = []
        self._expand_count: int = 0
        self._llm_call_count: int = 0    # contador de chamadas LLM da iteração atual
        self._total_llm_calls: int = 0   # acumulado cumulativo da sessão inteira (BUG-2 fix)
        self.best_reward_so_far: float = 0.0  # Rastreamento para poda relativa MCTS
        self._simulation_cache: dict[str, Tuple[float, str]] = {}  # MCTS Expert: cache de simulação deduplicada
        self.transposition_table = TranspositionTable()  # MCTS Expert: Tabela de Transposição para fusão de nós DAG
        self.lock = threading.Lock()

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

    def _count_llm_call(self, n: int = 1) -> None:
        """Registra chamadas LLM para metricas de custo."""
        with self.lock:
            self._llm_call_count += n
            self._total_llm_calls += n  # BUG-2 fix: acumulador cumulativo nunca é zerado

    def _emit_cost_event(self, iteration: int) -> None:
        """Emite evento de custo apos cada iteracao MCTS."""
        from src.domain.events import CostEventPayload
        with self.lock:
            calls = self._llm_call_count
            self._llm_call_count = 0  # reset apenas o contador da iteração atual
        estimated_tokens = calls * 2000  # estimativa conservadora
        self._emitter.emit_cost(CostEventPayload(
            iteration=iteration + 1,
            llm_calls=calls,
            estimated_tokens=estimated_tokens,
            job_id=self.job_id,
        ))

    def selection(self, node: MCTSNode) -> MCTSNode:
        """Seleção MCTS com política configurável (PUCT, UCB1-Tuned ou UCB1) e progressive widening."""
        cfg = self.config
        while node.children and len(node.children) >= node.max_children_allowed(cfg.progressive_c, cfg.progressive_alpha):
            if self._emitter.is_cancelled():
                return node
            
            # Recupera as estatísticas globais das estratégias (RAVE/AMAF)
            bandit_stats = {
                k: v.mean_delta for k, v in self.mutation_bandit.get_stats().items()
            }
            
            policy = getattr(cfg, "selection_policy", "puct")
            if policy == "ucb1_tuned":
                best = node.best_child_ucb_tuned(
                    cfg.c_param,
                    bandit_stats=bandit_stats,
                    rave_k=cfg.rave_k,
                    virtual_loss_weight=cfg.virtual_loss_weight,
                )
            elif policy == "ucb1":
                best = node.best_child_ucb(cfg.c_param)
            else:
                # Padrão PUCT (AlphaZero-style com RAVE e Progressive Bias)
                best = node.best_child_puct(
                    cfg.c_param, 
                    bandit_stats=bandit_stats, 
                    rave_k=cfg.rave_k,
                    virtual_loss_weight=cfg.virtual_loss_weight,
                    c_bias=getattr(cfg, "c_bias", 0.5),
                )

            if best is None:
                return node
            node = best
            node.add_virtual_loss()
        return node

    def simulation(self, instruction: str) -> Tuple[float, str]:
        if self._emitter.is_cancelled():
            return 0.0, 'Cancelado pelo usuário.'
        try:
            # 1. Early Cut-Off Heurístico (MCTS Expert / Heavy Playout Shortcut)
            if not instruction or len(instruction.strip()) < 20:
                self._emitter.emit_log("    [Early Cut-Off Heurístico] Instrução curta ou vazia (< 20 chars). Abortando avaliação LLM.")
                return 0.05, "Early Cut-Off Heurístico: instrução demasiado curta ou corrompida."

            density_mult = calculate_density_multiplier(instruction, self.skill_original)
            if density_mult < 0.20:
                self._emitter.emit_log(f"    [Early Cut-Off Heurístico] Densidade informacional muito baixa ({density_mult:.2f}). Abortando avaliação LLM.")
                return 0.10, "Early Cut-Off Heurístico: baixa densidade informacional."

            # 2. Tabela de Transposição & Simulation Cache Hit
            hash_key = hash_instruction(instruction)
            trans_node = self.transposition_table.get(hash_key)
            if trans_node is not None and trans_node.visits > 0:
                reward = trans_node.q_value / trans_node.visits
                self._emitter.emit_log(f"    [Transposition Table Hit] Nó reaproveitado via DAG. Recompensa: {reward:.2f}")
                return reward, trans_node.feedback

            with self.lock:
                if hash_key in self._simulation_cache:
                    cached_reward, cached_feedback = self._simulation_cache[hash_key]
                    self._emitter.emit_log(f"    [Simulação Cache Hit] Instrução deduplicada. Recompensa: {cached_reward:.2f}")
                    return cached_reward, cached_feedback

            self._count_llm_call()  # 1 chamada LLM (avaliador_modo_b)
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

            res_reward = float(reward)
            with self.lock:
                self._simulation_cache[hash_key] = (res_reward, feedback)

            return res_reward, feedback
        except Exception as e:
            self._emitter.emit_error(f"[!] Erro na simulação: {e}")
            return 0.0, f"Erro na simulação: {str(e)}"

    def _should_prune(self, instruction: str, parent_instruction: str = "", mutation_strategy: str = "") -> bool:
        # Dynamic Action Reduction (MCTS Expert - Swiechowski et al. Sec 3.2)
        if _check_lexical_critical(instruction):
            self._emitter.emit_log(f"    [Poda Dinâmica de Ações] Densidade lexical crítica ({compute_lexical_density(instruction):.2f}).")
            return True
        ref = parent_instruction or self.skill_original
        if _check_density_critical(instruction, ref, mutation_strategy):
            dm = calculate_density_multiplier(instruction, ref, mutation_strategy=mutation_strategy)
            self._emitter.emit_log(f"    [Poda Dinâmica de Ações] Densidade informacional crítica ({dm:.2f}).")
            return True
        if parent_instruction and _check_semantic_critical(instruction, parent_instruction):
            sp = calculate_semantic_penalty(instruction, parent_instruction)
            self._emitter.emit_log(f"    [Poda Dinâmica de Ações] Penalidade semântica excessiva ({sp:.2f}).")
            return True

        if self.value_estimator.confidence < 0.3:
            return False

        estimated = self.value_estimator.estimate(instruction)
        if estimated < self.config.value_threshold:
            self._emitter.emit_log(f"    [Poda Absoluta] Value estimator: {estimated:.2f} < threshold {self.config.value_threshold}. Podando.")
            return True

        if self.best_reward_so_far > 0.6 and (estimated + 0.15) < self.best_reward_so_far:
            self._emitter.emit_log(f"    [Poda Relativa] Estimado ({estimated:.2f} + 0.15) < melhor recompensa ({self.best_reward_so_far:.2f}). Podando.")
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
        Backpropagation com γ discount para MCTS em Grafo Orientado Acíclico (DAG).

        Swiechowski et al. Sec 3.4 / Silver: temporal-difference.
        Propaga o crédito descontado para o nó folha e todos os seus ancestrais no DAG.
        """
        visited = set()
        queue = [(node, 0)]  # (nó, profundidade_relativa)

        while queue:
            if self._emitter.is_cancelled():
                break
            current, depth_from_leaf = queue.pop(0)

            if current.node_id in visited:
                continue
            visited.add(current.node_id)

            with current.lock:
                discounted_reward = reward * (self.config.gamma ** depth_from_leaf)
                current.q_value += discounted_reward
                current.sq_q_value += discounted_reward ** 2
                current.visits += 1

            current.remove_virtual_loss()
            self.notify_node(current)

            parents = getattr(current, 'parents', [])
            if not parents and current.parent:
                parents = [current.parent]

            for p in parents:
                if p and p.node_id not in visited:
                    queue.append((p, depth_from_leaf + 1))

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

            self._count_llm_call()  # 1 chamada LLM (strategy_discoverer)
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
            if "RateLimit" in str(e) or "429" in str(e):
                self._emitter.emit_error('[!] Rate limit atingido na descoberta. Pausando 15s...')
                time.sleep(15)
            else:
                self._emitter.emit_error(f'[!] Falha ao inventar estratégia: {e}. Usando fallback.')
            # Retorna uma estratégia segura real (fallback) para evitar quebrar o loop
            fallback_keys = [k for k in self._strategy_registry.get_all_keys() if k != '__DISCOVER__']
            return fallback_keys[0] if fallback_keys else 'mutador_cognitivo'

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
        for local_attempt in range(3):
            try:
                self._count_llm_call()  # 1 chamada LLM (agent ou agent_cognitivo)
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
                    if self._should_prune(candidata, leaf.instruction, strategy):
                        self._emitter.emit_log('    [!] Candidata podada pelo value estimator / poda dinâmica. Tentando novamente...')
                        nova_critica = f'{critica}\nA última tentativa gerou uma skill de baixa qualidade estimada. Mude radicalmente a abordagem.'
                        return '', nova_critica, False

                    self._emitter.emit_log(f'    [Crítica]: {predicao.critica}')
                    return candidata, predicao.critica, True
                else:
                    return self._handle_empty_candidate(critica)
            except Exception as e:
                if "RateLimit" in str(e) or "429" in str(e):
                    self._emitter.emit_error(f'    [!] Rate Limit atingido. Pausando 15s antes de retentar... ({local_attempt + 1}/3)')
                    time.sleep(15)
                    continue
                self._emitter.emit_error(f'    [!] Erro técnico na geração: {str(e)}')
                nova_critica = f'{critica}\nErro técnico ({e}). Tente uma reescrita mais simples.'
                return '', nova_critica, False

        self._emitter.emit_error('    [!] Falha persistente por Rate Limit ou indisponibilidade da API.')
        return '', f'{critica}\nErro técnico persistente da API.', False

    def _pick_strategy(self, leaf: MCTSNode) -> str:
        strategy = self.mutation_bandit.select()
        return self._discover_strategy(leaf) if strategy == '__DISCOVER__' else strategy

    def _try_fallback_strategy(self, leaf: MCTSNode, failed_strategies: set) -> tuple[str, str, str] | None:
        for _ in range(5):
            strategy = self._pick_strategy(leaf)
            if strategy not in failed_strategies:
                prompt = self._strategy_registry.get_prompt(strategy)
                desc = self._strategy_registry.get_name(strategy)
                return strategy, prompt, desc
        return None

    def _is_candidate_valid(self, candidata: str, leaf: MCTSNode, strategy_desc: str) -> bool:
        if candidata.strip() == leaf.instruction.strip():
            self._emitter.emit_log(f'    [Action Reduction] Candidato de {strategy_desc} é idêntico ao original. Descartando.')
            return False
        if len(candidata.strip()) < 10:
            self._emitter.emit_log(f'    [Action Reduction] Candidato de {strategy_desc} muito curto (<10 chars). Descartando.')
            return False
        return True

    def _create_child_node(self, leaf: MCTSNode, instruction: str, critica: str, strategy: str, strategy_desc: str) -> MCTSNode:
        child = MCTSNode(
            instruction, parent=leaf, feedback='', critica=critica,
            mutation_strategy=strategy, depth=leaf.depth + 1,
            prior=self.value_estimator.estimate(instruction),
        )
        canonical = self.transposition_table.put(hash_instruction(instruction), child)
        if canonical != child:
            self._emitter.emit_log("    [Transposition Merge] Nó alinhado com nó existente em DAG.")
            child = canonical
        with leaf.lock:
            if child not in leaf.children:
                leaf.children.append(child)
        with self.lock:
            self._expand_count += 1
            self._expansion_order.append({
                'expand_num': self._expand_count,
                'strategy_key': strategy,
                'strategy_desc': strategy_desc,
                'depth': child.depth,
                'parent_score': leaf.q_value / max(1, leaf.visits) if leaf != child else 0.0,
            })
        self.notify_node(child)
        return child

    def _expand_node(self, leaf: MCTSNode) -> MCTSNode:
        strategy = self._pick_strategy(leaf)
        strategy_prompt = self._strategy_registry.get_prompt(strategy)
        strategy_desc = self._strategy_registry.get_name(strategy) or strategy
        experience_context = self._get_lessons_context(leaf.feedback)
        critica = leaf.feedback
        failed_strategies: set[str] = set()

        for tentativa in range(3):
            if self._emitter.is_cancelled():
                break
            if tentativa > 0:
                time.sleep(2 * tentativa)

            nota = str(leaf.q_value / max(1, leaf.visits))
            self._emitter.emit_log(f'[*] Expandindo nó (Tentativa {tentativa + 1}/3) | Estratégia: {strategy_desc} | Nota: {nota}')

            feedback_completo = critica + (experience_context if experience_context else '')
            candidata, nova_critica, sucesso = self._try_generate_mutation(
                leaf, strategy, strategy_prompt, feedback_completo, nota, critica
            )
            critica = nova_critica

            if sucesso and self._is_candidate_valid(candidata, leaf, strategy_desc):
                return self._create_child_node(leaf, candidata, critica, strategy, strategy_desc)

            failed_strategies.add(strategy)
            self._emitter.emit_log(f'    [!] Estratégia {strategy_desc} falhou. Selecionando nova estratégia...')
            fallback = self._try_fallback_strategy(leaf, failed_strategies)
            if fallback is None:
                self._emitter.emit_log('    [!] Todas as estratégias falharam. Retornando nó pai sem expansão.')
                return leaf
            strategy, strategy_prompt, strategy_desc = fallback

        self._emitter.emit_error('[!] Falha em gerar nova instrução após 3 tentativas. Retornando nó pai sem expansão.')
        return leaf

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
        """RN-05: Aplica multiplicador de densidade com guard clauses"""
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

    def _is_cancelled(self) -> bool:
        return self._emitter.is_cancelled() or getattr(self, '_abort_flag', False)

    def _expand_child(self, leaf: MCTSNode) -> MCTSNode:
        """Expande ou reutiliza leaf; gerencia virtual loss no finally."""
        cfg = self.config
        if len(leaf.children) >= leaf.max_children_allowed(cfg.progressive_c, cfg.progressive_alpha):
            return leaf
        child = self._expand_node(leaf)
        child.add_virtual_loss()
        return child

    def _apply_reward_multipliers(self, reward: float, heuristic_result: dict, child: MCTSNode) -> float:
        """Aplica multiplicadores de heurística, semântica e densidade + reward floor."""
        reward_before = reward
        reward = self._apply_heuristic_multiplier(reward, heuristic_result)
        reward = self._apply_semantic_penalty(child, reward)
        reward = self._apply_density_multiplier(child, reward)
        if reward < self.config.reward_floor and reward_before >= self.config.reward_floor * 2:
            self._emitter.emit_log(
                f"    [Reward Floor] reward={reward:.3f} < floor={self.config.reward_floor:.2f}. "
                f"Restaurando para {self.config.reward_floor:.2f}"
            )
            reward = self.config.reward_floor
        return reward

    def _commit_iteration(self, child: MCTSNode, reward: float, feedback: str):
        """Persiste resultados da iteração: bandit update e experience store."""
        parent_reward = child.parent.last_reward if child.parent else 0.0
        shaped_reward = calcular_delta_reward(reward, parent_reward)
        self.backpropagation(child, shaped_reward)
        with self.lock:
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

    def _run_mcts_iteration(self, root: MCTSNode) -> Tuple[bool, float]:
        """RN-06: Verifica cancelamento em 3 checkpoints obrigatórios."""
        if self._is_cancelled():
            return True, 0.0

        leaf = self.selection(root)
        try:
            child = self._expand_child(leaf)
        finally:
            if leaf != child:
                leaf.remove_virtual_loss()

        if self._is_cancelled():
            if child != leaf:
                child.remove_virtual_loss()
            return True, 0.0

        # BUG-2 fix: se a expansão falhou e retornou o próprio leaf,
        # não há filho novo para simular. Evita iteração desperdiçada.
        if child == leaf:
            self._emitter.emit_log('    [Iteração Descartada] Nó pai retornado sem filho. Nenhuma estratégia gerou candidato novo.')
            return False, 0.0

        is_pruned, heuristic_result = self._evaluate_and_prune(child)
        if is_pruned:
            return False, 0.0

        if self._is_cancelled():
            return True, 0.0

        reward, feedback = self.simulation(child.instruction)
        reward = self._apply_reward_multipliers(reward, heuristic_result, child)

        child.feedback = feedback
        child.last_reward = reward

        with self.lock:
            if reward > self.best_reward_so_far:
                self.best_reward_so_far = reward

        self._commit_iteration(child, reward, feedback)
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
            self._emit_cost_event(i)  # emite metricas de custo apos a iteracao
            if should_break:
                return True, consecutive_zeros, consecutive_api_errors

            if iter_reward >= self.config.mcts_early_termination_threshold:
                self._emitter.emit_log(f'\n[!] EARLY TERMINATION: Recompensa {iter_reward:.3f} >= {self.config.mcts_early_termination_threshold:.3f}. Abortando busca.')
                return True, consecutive_zeros, consecutive_api_errors

            with self.lock:
                if self.best_reward_so_far >= self.config.mcts_early_termination_threshold:
                    self._emitter.emit_log(
                        f'\n[!] EARLY TERMINATION: Melhor recompensa acumulada ({self.best_reward_so_far:.3f}) '
                        f'alcançou o limiar ({self.config.mcts_early_termination_threshold:.3f}). Abortando busca.'
                    )
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

    def get_expansion_order(self) -> list[dict]:
        """Retorna a ordem cronológica das expansões com estratégias e métricas."""
        return list(self._expansion_order)

    def get_level_one_nodes(self, root: MCTSNode) -> list[dict]:
        """Retorna métricas de todos os nós de profundidade 1 (filhos diretos da raiz)."""
        return [
            {
                'strategy': n.mutation_strategy,
                'score': n.q_value / max(1, n.visits),
                'visits': n.visits,
                'reward': n.last_reward,
                'depth': n.depth,
                'instruction_len': len(n.instruction),
            }
            for n in root.children
        ]

    def _select_and_log_best_node(self, root: MCTSNode) -> MCTSNode:
        """Retorna o melhor nó (por score) para uso em experimentos.

        BUG-3 fix: raiz (depth=0) é excluída da competição. A raiz representa
        a skill original — se ela fosse selecionada significaria que nenhum filho
        superou o ponto de partida. Esse caso já é tratado separadamente em
        _format_best_node via `if best_node == root`. Excluir aqui evita
        que o gamma-discount diluído da raiz (que acumula muitas visitas)
        vença por volume em runs curtos (≤ 5 iterações).
        """
        all_nodes = self._get_all_nodes(root)
        # BUG-3 fix: filtra a raiz; se só existir a raiz, retorna ela como fallback
        candidate_nodes = [n for n in all_nodes if n.depth > 0]
        if not candidate_nodes:
            return root  # fallback: nenhum filho gerado ainda
        best_node = max(candidate_nodes, key=lambda n: (
            n.q_value / max(1, n.visits),
            n.visits,
            n.depth,
        ))
        return best_node

    def _format_best_node(self, root: MCTSNode) -> str:
        best_node = self._select_and_log_best_node(root)

        n_samples = self.config.root_median_samples
        if n_samples > 1 and best_node != root:
            best_rewards = []
            for _ in range(n_samples):
                if self._emitter.is_cancelled():
                    break
                r, _ = self.simulation(best_node.instruction)
                best_rewards.append(r)
            if best_rewards:
                best_rewards.sort()
                best_node.last_reward = best_rewards[len(best_rewards) // 2]
                self._emitter.emit_log(
                    f'    [BestNode] {n_samples} reavaliacoes: '
                    f'{[f"{v:.3f}" for v in best_rewards]}, '
                    f'mediana={best_node.last_reward:.3f}'
                )

        score = best_node.q_value / max(1, best_node.visits)
        if best_node == root:
            self._emitter.emit_log(
                f'[!] ATENCAO: Nenhuma otimizacao superou a skill original. '
                f'O otimizador nao encontrou melhoria significativa. '
                f'score={score:.3f}, visits={best_node.visits}'
            )
        else:
            self._emitter.emit_log(
                f'[+] Melhor no selecionado: score={score:.3f}, visits={best_node.visits}, '
                f'strategy={get_strategy_description(best_node.mutation_strategy)}, '
                f'depth={best_node.depth}'
            )

        return best_node.instruction

    def _evaluate_root(self, root: MCTSNode, n_samples: int) -> None:
        if n_samples == 1:
            self._emitter.emit_log('[*] Avaliando a instrucao original (raiz)...')
            reward, feedback = self.simulation(root.instruction)
        else:
            self._emitter.emit_log(f'[*] Avaliando a instrucao original (raiz) com mediana de {n_samples}...')
            rewards, feedbacks = [], []
            for _ in range(n_samples):
                if self._emitter.is_cancelled():
                    break
                r, f = self.simulation(root.instruction)
                rewards.append(r); feedbacks.append(f)
            rewards.sort()
            idx = len(rewards) // 2
            reward, feedback = rewards[idx], feedbacks[idx]
            self._emitter.emit_log(f'    [Raiz] {n_samples} avaliacoes: {[f"{v:.3f}" for v in rewards]}, mediana={reward:.3f}')
        root.feedback = feedback
        root.last_reward = reward
        self.backpropagation(root, reward)

    def _run_threaded_search(self, root: MCTSNode) -> None:
        cfg = self.config
        consecutive_zeros = 0
        consecutive_api_errors = 0
        self._abort_flag = False

        def run_task(i):
            nonlocal consecutive_zeros, consecutive_api_errors
            if self._emitter.is_cancelled() or self._abort_flag:
                return True
            with self.lock:
                local_zeros = consecutive_zeros
                local_errors = consecutive_api_errors
            should_break, z, e = self._run_single_iteration(root, i, local_zeros, local_errors)
            with self.lock:
                consecutive_zeros = z
                consecutive_api_errors = e
            if should_break:
                self._abort_flag = True
            return should_break

        with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.num_threads) as executor:
            futures = [executor.submit(run_task, i) for i in range(cfg.max_iterations)]
            for future in concurrent.futures.as_completed(futures):
                if self._emitter.is_cancelled():
                    self._emitter.emit_log('\n[!] OTIMIZAÇÃO INTERROMPIDA PELO USUÁRIO.')
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    if future.result():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                except Exception as ex:
                    self._emitter.emit_error(f'[!] Erro fatal em thread: {ex}')

    def _log_final_stats(self) -> None:
        self.experience_store.save()
        self._emitter.emit_log(f'[*] {len(self.experience_store.experiences)} experiências salvas na memória de longo prazo.')
        tt = self.transposition_table
        self._emitter.emit_log(
            f'[*] Tabela de Transposição: {tt.size} nós únicos, '
            f'{tt.hits} hits de {tt.lookups} buscas ({tt.hit_rate:.1%} taxa de reaproveitamento).'
        )
        self._log_bandit_stats()

    def optimize(self) -> str:
        cfg = self.config
        self._emitter.emit_log('\n[+] Inicializando o pipeline MCTS RL customizado com refinamentos...')
        self._emitter.emit_log(f'    Config: γ={cfg.gamma}, C_ucb={cfg.c_param}, α_pw={cfg.progressive_alpha}, threshold={cfg.value_threshold}')

        root = MCTSNode(self.skill_original, critica='Rascunho Inicial')
        self.notify_node(root)
        self._evaluate_root(root, cfg.root_median_samples)

        self._run_threaded_search(root)
        self._log_final_stats()

        self._emitter.emit_log('\n=======================================================\n                OTIMIZAÇÃO CONCLUÍDA                   \n=======================================================\n')
        return self._format_best_node(root)