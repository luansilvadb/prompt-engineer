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
import statistics
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
from src.domain.selection_policies import create_selection_policy
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
        self._selection_policy = create_selection_policy(config)

        self._expansion_order: list[dict] = []
        self._expand_count: int = 0
        self._llm_call_count: int = 0    # contador de chamadas LLM da iteração atual
        self._total_llm_calls: int = 0   # acumulado cumulativo da sessão inteira (BUG-2 fix)
        self._llm_latency_ms: float = 0.0  # acumulador de latência da iteração atual
        self.best_reward_so_far: float = 0.0  # Rastreamento para poda relativa MCTS
        self._simulation_cache: dict[str, Tuple[float, str]] = {}  # MCTS Expert: cache de simulação deduplicada
        self.transposition_table = TranspositionTable()  # MCTS Expert: Tabela de Transposição para fusão de nós DAG
        self.lock = threading.Lock()
        self._llm_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)  # pool reutilizável para timeouts LLM

        self._expansion_success: dict[str, int] = {}  # contagem de sucesso por estratégia
        self._expansion_failure: dict[str, int] = {}  # contagem de falha por estratégia
        self._density_floor_history: list[bool] = []
        self._iteration_start_time: float = 0.0
        self._iteration_deadline: float = 0.0
        self._iteration_circuit_broken: bool = False
        self._last_iter_parent_raw: float = 0.0
        self._gates_without_test_cases: int = 0
        self._post_evals_without_test_cases: int = 0
        self._discovered_strategies: set = set()  # rastreia estratégias vindas do __DISCOVER__
        self._incremental_checkpoint: dict | None = None  # checkpoint entre estágios de gate/descoberta
        self._technical_error_count: int = 0  # contador de avaliações que falharam por erro técnico (não score zero real)

        strategy_stats = self.experience_store.get_strategy_stats()
        coalesced: dict | None = None
        if strategy_stats:
            coalesced = self._coalesce_strategy_stats(strategy_stats)
            self.mutation_bandit.load_priors(coalesced)
            self._emitter.emit_log(
                f'[*] Memória experiencial carregada: {len(self.experience_store.experiences)} experiências, '
                f'{len(coalesced)} estratégias conhecidas.'
            )

        # SubTask 5.1: estatística observada de mutador_cognitivo no coalesced
        observed_mean_delta = None
        if coalesced and 'mutador_cognitivo' in coalesced:
            observed_mean_delta = coalesced['mutador_cognitivo'].get('mean_delta')

        # SubTask 5.2: prior boosting condicional — só aplica se não há histórico ou mean_delta > 0
        if observed_mean_delta is None or observed_mean_delta > 0:
            cognitivo_prior = {
                'mutador_cognitivo': {
                    'count': config.cognitivo_prior_count,
                    'mean_delta': config.cognitivo_prior_mean_delta,
                }
            }
            self.mutation_bandit.load_priors(cognitivo_prior)
            # SubTask 5.3: espelha a regra efetiva de load_priors para o log.
            if config.cognitivo_prior_mean_delta < 0:
                effective_virtual_count = 1
            else:
                effective_virtual_count = max(1, min(int(config.cognitivo_prior_count * 0.5), 10))
            self._emitter.emit_log(
                f'[*] Mutador Cognitivo prior boosting: {effective_virtual_count} virtual count, '
                f'delta={config.cognitivo_prior_mean_delta}'
            )
        else:
            self._emitter.emit_log(
                f'[*] Mutador Cognitivo prior boosting suprimido: mean_delta histórico={observed_mean_delta:.3f} <= 0'
            )

    def _count_llm_call(self, n: int = 1, latency_ms: float = 0.0) -> None:
        """Registra chamadas LLM para metricas de custo."""
        with self.lock:
            self._llm_call_count += n
            self._total_llm_calls += n  # BUG-2 fix: acumulador cumulativo nunca é zerado
            self._llm_latency_ms += latency_ms

    def _emit_cost_event(self, iteration: int) -> None:
        """Emite evento de custo apos cada iteracao MCTS."""
        from src.domain.events import CostEventPayload
        with self.lock:
            calls = self._llm_call_count
            latency = self._llm_latency_ms
            self._llm_call_count = 0  # reset apenas o contador da iteração atual
            self._llm_latency_ms = 0.0
            total_expansions = sum(self._expansion_success.values()) + sum(self._expansion_failure.values())
        if total_expansions > 0:
            efficiency = sum(self._expansion_success.values()) / total_expansions
            self._emitter.emit_log(f'    [Eficiência de Expansão] {sum(self._expansion_success.values())}/{total_expansions} ({efficiency:.1%})')
        estimated_tokens = calls * 2000  # estimativa conservadora
        self._emitter.emit_cost(CostEventPayload(
            iteration=iteration + 1,
            llm_calls=calls,
            estimated_tokens=estimated_tokens,
            job_id=self.job_id,
            latency_ms=latency,
        ))

    def selection(self, node: MCTSNode) -> MCTSNode:
        """Seleção MCTS com política configurável (PUCT, UCB1-Tuned ou UCB1) e progressive widening."""
        cfg = self.config
        while node.children and len(node.children) >= node.max_children_allowed(cfg.progressive_c, cfg.progressive_alpha) and node.depth < cfg.max_depth:
            if self._emitter.is_cancelled():
                return node

            if getattr(node, 'is_sufficient', False):
                return node

            # Recupera as estatísticas globais das estratégias (RAVE/AMAF)
            bandit_stats = {
                k: v.mean_delta for k, v in self.mutation_bandit.get_stats().items()
            }

            best = self._selection_policy.select(node, cfg, bandit_stats=bandit_stats)

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

            t0 = time.perf_counter()
            reward, feedback = funcao_de_recompensa(
                avaliador_modo_b=self.avaliador_modo_b,
                skill_original=self.skill_original,
                skill_otimizada=instruction,
                regras_adicionais=self.regras_adicionais
            )
            latency = (time.perf_counter() - t0) * 1000
            self._count_llm_call(latency_ms=latency)  # 1 chamada LLM (avaliador_modo_b)
            if reward == 0.0:
                self._emitter.emit_error(f"    [Simulação] Recompensa 0.00! Motivo: {feedback}")
                # Distingue erro técnico de score zero real
                if feedback.startswith("Erro interno na avaliação"):
                    self._technical_error_count += 1
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

        if self.best_reward_so_far > 0.6 and (estimated + self.config.prune_relative_margin) < self.best_reward_so_far:
            self._emitter.emit_log(f"    [Poda Relativa] Estimado ({estimated:.2f} [raw] + {self.config.prune_relative_margin:.2f}) < melhor recompensa ({self.best_reward_so_far:.2f} [raw]). Podando.")
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
        # Validação: clamp do reward para [0, 1]
        original_reward = reward
        reward = max(0.0, min(1.0, reward))
        if reward != original_reward:
            self._emitter.emit_error(f'[!] [Validação Backprop] Reward inválido ({original_reward:.3f}) clampado para [{reward:.3f}]')

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
                if current.q_value < 0:
                    self._emitter.emit_error(f'[!] [Validação Backprop] Q-value negativo detectado: {current.q_value:.3f} no nó {current.node_id[:8]}')
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

    def _coalesce_strategy_stats(self, stats: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        name_to_key: dict[str, str] = {}
        coalesced: dict[str, dict[str, float]] = {}
        for key, info in stats.items():
            name = self._strategy_registry.get_name(key)
            name_lower = name.lower().strip()
            if name_lower in name_to_key:
                existing_key = name_to_key[name_lower]
                existing = coalesced[existing_key]
                count = info.get("count", 0)
                total_delta = info.get("total_delta", 0)
                existing["count"] = existing.get("count", 0) + count
                existing["total_delta"] = existing.get("total_delta", 0) + total_delta
                existing["total_reward"] = existing.get("total_reward", 0) + info.get("total_reward", 0)
                existing["mean_delta"] = existing["total_delta"] / max(1, existing["count"])
            else:
                name_to_key[name_lower] = key
                coalesced[key] = dict(info)
        return coalesced

    def _discover_strategy(self, leaf: MCTSNode) -> str:
        self._emitter.emit_log('[*] Bandit escolheu __DISCOVER__. Inventando nova heurística de mutação...')
        # Obtém estratégias conhecidas com lock breve — NÃO segura lock durante LLM
        with self.lock:
            estrategias_conhecidas = ", ".join([
                self._strategy_registry.get_name(k)
                for k in self._strategy_registry.get_all_keys()
                if k != '__DISCOVER__'
            ])
        if not estrategias_conhecidas:
            estrategias_conhecidas = "Nenhuma. Você é livre para criar a primeira heurística (Tabula Rasa)."

        try:
            enriched_feedback = (leaf.feedback or "Nenhum feedback ainda. Invente algo inovador.") + f"""

INSTRUÇÃO DE DESCOBERTA: Você deve inventar uma NOVA estratégia de mutação coerente com a skill, cobrindo um EIXO de mutação ainda NÃO explorado pelas estratégias já registradas.

Estratégias já registradas (evite duplicar estes eixos):
{estrategias_conhecidas}

Exemplos de eixos que você pode explorar (não se limite a estes): variação de tom/registro, reestruturação de formato, especificação de contexto de uso, decomposição em passos, adição de justificativas, parametrização de configuração, especialização por perfil de agente, ou qualquer outro eixo coerente.

IMPORTANTE: Gere uma estratégia de um eixo DIFERENTE dos que as estratégias conhecidas já implementam."""
            timeout_s = self._remaining_time(self.config.llm_timeout)
            if timeout_s <= 0:
                self._iteration_circuit_broken = True
                self._emitter.emit_log('    [Circuit Breaker] Deadline já passado, abortando submissão de discovery')
                with self.lock:
                    fallback_keys = [k for k in self._strategy_registry.get_all_keys() if k != '__DISCOVER__']
                return fallback_keys[0] if fallback_keys else 'mutador_cognitivo'

            t0 = time.perf_counter()
            if self._check_iteration_abort():
                with self.lock:
                    fallback_keys = [k for k in self._strategy_registry.get_all_keys() if k != '__DISCOVER__']
                return fallback_keys[0] if fallback_keys else 'mutador_cognitivo'
            future = self._llm_executor.submit(
                self.strategy_discoverer,
                skill_atual=leaf.instruction,
                feedbacks_recentes=enriched_feedback,
                estrategias_conhecidas=estrategias_conhecidas
            )
            try:
                nova_estrat = future.result(timeout=timeout_s)
                if not nova_estrat.nome_estrategia:
                    self._emitter.emit_log('[Discovery] nome_estrategia vazio/None, usando fallback')
                    with self.lock:
                        fallback_keys = [k for k in self._strategy_registry.get_all_keys() if k != '__DISCOVER__']
                    return fallback_keys[0] if fallback_keys else 'mutador_cognitivo'
            except concurrent.futures.TimeoutError:
                self._iteration_circuit_broken = True
                self._emitter.emit_log(
                    f'    [Circuit Breaker] Descoberta excedeu timeout ({timeout_s:.2f}s). '
                    f'Thread em background continuará mas resultado será descartado.'
                )
                with self.lock:
                    fallback_keys = [k for k in self._strategy_registry.get_all_keys() if k != '__DISCOVER__']
                return fallback_keys[0] if fallback_keys else 'mutador_cognitivo'
            latency = (time.perf_counter() - t0) * 1000
            self._count_llm_call(latency_ms=latency)  # 1 chamada LLM (strategy_discoverer)

            key_raw = nova_estrat.nome_estrategia.lower()
            key = re.sub(r'[^a-z0-9_]', '_', key_raw)[:30] + '_' + str(uuid.uuid4())[:4]

            # Lock apenas para operação de registro — thread-safe
            with self.lock:
                existing_key = self._strategy_registry.add_strategy(key, nova_estrat.nome_estrategia, nova_estrat.prompt_estrategia)
            if existing_key:
                self._emitter.emit_log(f'[i] Estratégia "{nova_estrat.nome_estrategia}" já descoberta. Reaproveitando chave existente.')
                self._discovered_strategies.add(existing_key)
                self._save_incremental_checkpoint(
                    stage='discovery',
                    strategy_key=existing_key,
                    strategy_desc=nova_estrat.nome_estrategia,
                )
                return existing_key
            self._emitter.emit_log(f'[+] Nova estratégia descoberta! {nova_estrat.nome_estrategia}')
            self._discovered_strategies.add(key)
            self._save_incremental_checkpoint(
                stage='discovery',
                strategy_key=key,
                strategy_desc=nova_estrat.nome_estrategia,
            )
            return key
        except Exception as e:
            if "RateLimit" in str(e) or "429" in str(e):
                self._emitter.emit_error('[!] Rate limit atingido na descoberta. Pausando 15s...')
                time.sleep(15)
            else:
                self._emitter.emit_error(f'[!] Falha ao inventar estratégia: {e}. Usando fallback.')
            with self.lock:
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
        """Valida as seções obrigatórias da saída do agente cognitivo.

        Se a validação falhar por seções ausentes, tenta auto-reparo injetando
        as seções faltantes. Só emite erro se o reparo também falhar.
        """
        try:
            _validate_raciocinio(predicao.raciocinio_estruturado)
        except Exception as e:
            self._emitter.emit_error(f'[!] raciocinio_estruturado invalido: {e}')
        try:
            output = MutadorCognitivoOutput(nova_instrucao=predicao.nova_instrucao)
            if output.auto_fix:
                self._emitter.emit_log('    [Auto-Reparo] Seções cognitivas ausentes foram injetadas automaticamente.')
                # Atualiza a predicação com a versão reparada
                object.__setattr__(predicao, 'nova_instrucao', output.nova_instrucao)
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
        critica: str,
        current_instruction: str = None,
        timeout_override: int = None,
    ) -> Tuple[str, str, bool]:
        instrucao = current_instruction if current_instruction is not None else leaf.instruction
        effective_timeout = timeout_override if timeout_override is not None else self.config.llm_timeout
        for local_attempt in range(3):
            try:
                if self._check_iteration_abort():
                    return '', critica, False
                timeout_s = self._remaining_time(effective_timeout)
                if timeout_s <= 0:
                    self._iteration_circuit_broken = True
                    self._emitter.emit_log('    [Circuit Breaker] Sem tempo restante para nova chamada LLM. Abortando expansão.')
                    return '', critica, False
                t0 = time.perf_counter()
                if strategy == 'mutador_cognitivo':
                    future = self._llm_executor.submit(
                        self.agent_cognitivo,
                        instrucao_anterior=instrucao,
                        nota_anterior=nota,
                        feedback_juiz=feedback_completo,
                        estrategia_mutacao=strategy_prompt,
                    )
                    predicao = future.result(timeout=timeout_s)
                    self._validate_cognitive_output(predicao)
                else:
                    future = self._llm_executor.submit(
                        self.agent,
                        instrucao_anterior=instrucao,
                        nota_anterior=nota,
                        feedback_juiz=feedback_completo,
                        estrategia_mutacao=strategy_prompt,
                    )
                    predicao = future.result(timeout=timeout_s)
                latency = (time.perf_counter() - t0) * 1000
                self._count_llm_call(latency_ms=latency)  # 1 chamada LLM (agent ou agent_cognitivo)
                candidata = predicao.nova_instrucao
                if candidata and candidata.strip() and candidata.strip() != instrucao.strip():
                    if self._should_prune(candidata, instrucao, strategy):
                        self._emitter.emit_log('    [!] Candidata podada pelo value estimator / poda dinâmica. Tentando novamente...')
                        nova_critica = f'{critica}\nA última tentativa gerou uma skill de baixa qualidade estimada. Mude radicalmente a abordagem.'
                        return '', nova_critica, False

                    self._emitter.emit_log(f'    [Crítica]: {predicao.critica}')
                    return candidata, predicao.critica, True
                else:
                    return self._handle_empty_candidate(critica)
            except concurrent.futures.TimeoutError:
                if timeout_s < effective_timeout:
                    self._iteration_circuit_broken = True
                    self._emitter.emit_log(
                        f'    [Circuit Breaker] Geração excedeu a janela restante ({timeout_s:.2f}s). '
                        f'Thread em background continuará mas resultado será descartado.'
                    )
                    return '', critica, False
                self._emitter.emit_error(
                    f'    [!] Timeout ({timeout_s:.2f}s) na geração. '
                    f'Thread em background continuará. Tentando novamente... ({local_attempt + 1}/3)'
                )
                continue
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

    def _resolve_strategy(self, leaf: MCTSNode, strategy_result, force_known: bool = False) -> str | list[str]:
        """Resolve o resultado do bandit: se for lista (composição), repassa direto;
        se for string, aplica a lógica __DISCOVER__/force_known."""
        if isinstance(strategy_result, list):
            # Composições não usam __DISCOVER__/force_known
            return strategy_result
        # Estratégia isolada
        strategy = strategy_result
        if strategy == '__DISCOVER__':
            if force_known:
                # Primeira expansão do nó: evita __DISCOVER__, usa estratégia conhecida
                known = [k for k in self._strategy_registry.get_all_keys() if k != '__DISCOVER__']
                strategy = known[0] if known else 'mutador_cognitivo'
                self._emitter.emit_log(f'    [FirstExpansion] __DISCOVER__ bloqueado para nó virgem. Usando {strategy}.')
            else:
                strategy = self._discover_strategy(leaf)
        return strategy

    def _pick_strategy(self, leaf: MCTSNode, force_known: bool = False) -> str | list[str]:
        strategy_result = self.mutation_bandit.select()
        return self._resolve_strategy(leaf, strategy_result, force_known)

    def _try_fallback_strategy(self, leaf: MCTSNode, failed_strategies: set) -> tuple[str, str, str] | None:
        for attempt in range(5):
            raw = self._pick_strategy(leaf)
            # Resolve composite para chave única
            if isinstance(raw, list):
                strategy = self._strategy_registry.get_composite_key(raw)
                prompt_fn = lambda: self._strategy_registry.build_composite_prompt(raw)[2]
                desc_fn = lambda: self._strategy_registry.build_composite_prompt(raw)[1]
            else:
                strategy = raw
                prompt_fn = lambda: self._strategy_registry.get_prompt(raw)
                desc_fn = lambda: self._strategy_registry.get_name(raw) or raw
            if strategy not in failed_strategies:
                prompt = prompt_fn()
                desc = desc_fn()
                return strategy, prompt, desc
            name = self._strategy_registry.get_name(strategy)
            self._emitter.emit_log(f'    [Fallback] Estratégia "{name}" já falhou (tentativa {attempt + 1}/5). Selecionando outra...')
        self._emitter.emit_log('    [Fallback] Nenhuma estratégia alternativa disponível após 5 tentativas.')
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

    def _run_ab_gate(self, instruction_original: str, instruction_mutada: str, test_cases: list) -> tuple[bool, float, float]:
        """Gate A/B: avalia original vs mutada contra casos de feedback do experience store.
        
        Returns (approved, score_original, score_mutada).
        Aprova apenas se score_mutada > score_original + ab_margin_min.
        """
        if not test_cases:
            self._emitter.emit_log('    [Gate A/B] ⚠️ Operando sem casos de feedback — incerteza alta. Aprovação condicional (warm-up).')
            with self.lock:
                self._gates_without_test_cases += 1
            return True, 0.0, 0.0
        
        ab_margin = self.config.ab_margin_min
        
        scores_original = []
        scores_mutada = []
        
        for case in test_cases:
            skill_original_case = case.parent_instruction or case.instruction
            regras = case.feedback[:200] if case.feedback else ''
            
            try:
                reward_orig, _ = funcao_de_recompensa(
                    avaliador_modo_b=self.avaliador_modo_b,
                    skill_original=skill_original_case,
                    skill_otimizada=instruction_original,
                    regras_adicionais=regras
                )
                scores_original.append(reward_orig)
            except Exception:
                pass
            
            try:
                reward_mut, _ = funcao_de_recompensa(
                    avaliador_modo_b=self.avaliador_modo_b,
                    skill_original=skill_original_case,
                    skill_otimizada=instruction_mutada,
                    regras_adicionais=regras
                )
                scores_mutada.append(reward_mut)
            except Exception:
                pass
        
        if not scores_original or not scores_mutada:
            self._emitter.emit_log('    [Gate A/B] Falha ao avaliar casos. Aprovando por segurança.')
            return True, 0.0, 0.0
        
        mean_orig = statistics.mean(scores_original)
        mean_mut = statistics.mean(scores_mutada)
        delta = mean_mut - mean_orig
        
        approved = delta >= ab_margin
        
        self._emitter.emit_log(
            f'    [Gate A/B] Original={mean_orig:.3f} | Mutada={mean_mut:.3f} | '
            f'Delta={delta:+.3f} | Margem={ab_margin:.3f} | '
            f'{"APROVADO" if approved else "REJEITADO"}'
        )
        
        # Conta como chamadas LLM (2 por caso)
        self._count_llm_call(len(scores_original) + len(scores_mutada))
        
        return approved, mean_orig, mean_mut

    def _run_post_eval(self, instruction_original: str, instruction_mutada: str, test_cases: list) -> tuple[bool, float, float, float, float]:
        """Avaliação pós-implementação comportamental.
        
        Valida o comportamento real do agente analisando se a instrução mutada
        preserva regras críticas e não introduz novos defeitos comportamentais.
        
        DIFERENTE do Gate A/B: NÃO usa funcao_de_recompensa (simulação MCTS).
        Usa diretamente self.avaliador_modo_b e analisa métricas comportamentais
        (manteve_regras_criticas, defeitos_encontrados).
        
        Returns (approved, mean_orig, mean_mut, avg_defeitos_orig, avg_defeitos_mut).
        """
        if not test_cases:
            self._emitter.emit_log('    [Post-Eval] ⚠️ Operando sem casos de teste — incerteza alta. Aprovação condicional (warm-up).')
            with self.lock:
                self._post_evals_without_test_cases += 1
            return True, 0.0, 0.0, 0.0, 0.0
        
        post_eval_margin = self.config.post_eval_margin_min
        
        scores_original = []
        scores_mutada = []
        defeitos_original = []
        defeitos_mutada = []
        
        for case in test_cases:
            skill_original_case = case.parent_instruction or case.instruction
            regras = case.feedback[:200] if case.feedback else ''
            
            # Avalia instrução original contra este caso de teste
            try:
                resultado_orig = self.avaliador_modo_b(
                    skill_original=skill_original_case,
                    skill_otimizada=instruction_original,
                    regras_adicionais=regras
                )
                if not resultado_orig.manteve_regras_criticas:
                    scores_original.append(0.0)
                else:
                    penalty = min(len(resultado_orig.defeitos_encontrados) * 0.1, 0.5)
                    scores_original.append(max(0.0, 1.0 - penalty))
                defeitos_original.append(len(resultado_orig.defeitos_encontrados))
            except Exception:
                pass
            
            # Avalia instrução mutada contra este caso de teste
            try:
                resultado_mut = self.avaliador_modo_b(
                    skill_original=skill_original_case,
                    skill_otimizada=instruction_mutada,
                    regras_adicionais=regras
                )
                if not resultado_mut.manteve_regras_criticas:
                    scores_mutada.append(0.0)
                else:
                    penalty = min(len(resultado_mut.defeitos_encontrados) * 0.1, 0.5)
                    scores_mutada.append(max(0.0, 1.0 - penalty))
                defeitos_mutada.append(len(resultado_mut.defeitos_encontrados))
            except Exception:
                pass
        
        if not scores_original or not scores_mutada:
            self._emitter.emit_log('    [Post-Eval] Falha ao avaliar casos. Aprovando por segurança.')
            return True, 0.0, 0.0, 0.0, 0.0
        
        mean_orig = statistics.mean(scores_original)
        mean_mut = statistics.mean(scores_mutada)
        avg_def_orig = statistics.mean(defeitos_original) if defeitos_original else 0.0
        avg_def_mut = statistics.mean(defeitos_mutada) if defeitos_mutada else 0.0
        
        delta = mean_mut - mean_orig
        approved = delta > post_eval_margin
        
        self._emitter.emit_log(
            f'    [Post-Eval Comportamental] Orig={mean_orig:.3f} ({avg_def_orig:.1f} def) | '
            f'Mut={mean_mut:.3f} ({avg_def_mut:.1f} def) | '
            f'Delta={delta:+.3f} | Margem={post_eval_margin:.3f} | '
            f'{"APROVADO" if approved else "REJEITADO"}'
        )
        
        # Conta como chamadas LLM (2 por caso: original + mutada)
        self._count_llm_call(len(scores_original) + len(scores_mutada))
        
        return approved, mean_orig, mean_mut, avg_def_orig, avg_def_mut

    def _inject_dynamic_data(self, strategy: str, strategy_prompt: str) -> str:
        """Injeta dados dinâmicos do experience store no prompt da estratégia."""
        if strategy == 'reorganizacao_falha':
            # Extrai frequência de erros do experience store
            feedbacks = self.experience_store.get_feedback_frequency(top_k=5)
            if feedbacks:
                erros_text = '\n'.join(
                    f"- Erro: {f['feedback'][:150]} (delta={f['delta_reward']:+.2f}, "
                    f"ocorrências={f['count']})"
                    for f in feedbacks
                )
                return strategy_prompt + f"\n\nDADOS DE FALHA (erros mais frequentes do sistema):\n{erros_text}\nReordene as regras para que as que resolvem estes erros apareçam PRIIMEIRO no texto."
            return strategy_prompt
        
        elif strategy == 'preservacao_blocos':
            # Extrai blocos eficazes do experience store
            blocos = self.experience_store.get_effective_blocks(top_k=5)
            if blocos:
                blocos_text = '\n---\n'.join(
                    f"[Bloco eficaz, delta={b['delta_reward']:+.2f}]\n{b['instruction'][:300]}"
                    for b in blocos
                )
                return strategy_prompt + f"\n\nBLOCOS DE RACIOCÍNIO EFICAZES (PRESERVAR INTACTOS):\n{blocos_text}\nEstes trechos demonstraram eficácia. Preserve-os literalmente na reescrita."
            return strategy_prompt
        
        return strategy_prompt

    def _expand_node(self, leaf: MCTSNode) -> MCTSNode:
        if leaf.depth >= self.config.max_depth:
            self._emitter.emit_log(f'    [Max Depth] Nó atingiu profundidade máxima ({self.config.max_depth}). Bloqueando expansão.')
            return leaf

        if leaf.is_sufficient:
            self._emitter.emit_log(f'    [Sufficiency] Nó já é suficiente. Bloqueando expansão.')
            return leaf

        experience_context = self._get_lessons_context(leaf.feedback)
        critica = leaf.feedback
        failed_strategies: set[str] = set(leaf.tried_strategies)  # persiste entre chamadas

        # ── Abordagem gradativa: controla progressão de complexidade ──
        prev_was_isolated_rejected = False
        prev_was_2comp_rejected = False

        for tentativa in range(3):
            if self._emitter.is_cancelled():
                break

            nota = str(leaf.q_value / max(1, leaf.visits))

            # ── Abordagem gradativa: força composição progressiva ──
            if tentativa == 1 and prev_was_isolated_rejected:
                # Tentativa 0 isolada falhou → força composição de 2
                self._emitter.emit_log(f'[*] Expandindo nó (Tentativa {tentativa + 1}/3) | Abordagem gradativa: composição (2 eixos) | Nota: {nota}')
                comp_keys = self.mutation_bandit.force_composition(2)
                strategy = comp_keys
                strategy_key = self._strategy_registry.get_composite_key(strategy)
                _, strategy_desc, _ = self._strategy_registry.build_composite_prompt(strategy)
                is_composite = True
                # Salta seleção normal e vai direto para o fluxo de composição
            elif tentativa == 2 and prev_was_2comp_rejected:
                # Tentativa 1 (composição de 2) falhou → força composição de 3
                self._emitter.emit_log(f'[*] Expandindo nó (Tentativa {tentativa + 1}/3) | Abordagem gradativa: composição (3 eixos) | Nota: {nota}')
                comp_keys = self.mutation_bandit.force_composition(3)
                strategy = comp_keys
                strategy_key = self._strategy_registry.get_composite_key(strategy)
                _, strategy_desc, _ = self._strategy_registry.build_composite_prompt(strategy)
                is_composite = True
                # Salta seleção normal e vai direto para o fluxo de composição
            else:
                # ── Seleciona e resolve estratégia (composição ou isolada) ──
                is_first_try = (len(failed_strategies) == 0 and tentativa == 0)
                strategy = self._pick_strategy(leaf, force_known=is_first_try)

                if isinstance(strategy, list):
                    # Composição: obtém composite_key e descrição
                    strategy_key = self._strategy_registry.get_composite_key(strategy)
                    _, strategy_desc, _ = self._strategy_registry.build_composite_prompt(strategy)
                    is_composite = True
                else:
                    strategy_key = strategy
                    strategy_desc = ''
                    is_composite = False

                # ── Verifica se a estratégia (ou composite) já falhou para este nó ──
                if strategy_key in failed_strategies:
                    fallback = self._try_fallback_strategy(leaf, failed_strategies)
                    if fallback is None:
                        self._emitter.emit_log('    [!] Todas as estratégias conhecidas já falharam para este nó. Retornando sem expansão.')
                        return leaf
                    strategy_key, strategy_prompt, strategy_desc = fallback
                    is_composite = strategy_key.startswith('composite:')

                strategy_prompt = ''  # será definido no fluxo

            if tentativa > 0:
                time.sleep(2 * tentativa)

            feedback_completo = critica + (experience_context if experience_context else '')

            # ── FLUXO DE COMPOSIÇÃO ──
            if is_composite:
                parts = strategy_key[len('composite:'):].split('+')
                if not strategy_desc:
                    strategy_desc = self._strategy_registry.get_name(strategy_key)
                if not self._try_reserve_strategy(leaf, strategy_key):
                    self._emitter.emit_log(
                        f'    [Reserva] Estratégia {strategy_desc} já reservada por outra thread. Tentando outra estratégia...'
                    )
                    continue
                self._emitter.emit_log(f'[*] Expandindo nó (Tentativa {tentativa + 1}/3) | Estratégia: {strategy_desc} | Nota: {nota}')
                try:
                    current_instruction = leaf.instruction
                    accumulated_critica = critica
                    composicao_sucesso = True

                    for s in parts:
                        prompt_s = self._strategy_registry.get_prompt(s)
                        prompt_s = self._inject_dynamic_data(s, prompt_s)

                        candidata, nova_critica, sucesso = self._try_generate_mutation(
                            leaf, s, prompt_s, feedback_completo, nota, accumulated_critica,
                            current_instruction=current_instruction,
                            timeout_override=self.config.composite_timeout_s
                        )
                        if self._iteration_circuit_broken or self._check_iteration_abort():
                            return leaf
                        accumulated_critica = nova_critica

                        if not sucesso:
                            composicao_sucesso = False
                            break

                        current_instruction = candidata
                        feedback_completo = accumulated_critica + (experience_context if experience_context else '')

                    if not composicao_sucesso:
                        with self.lock:
                            leaf.tried_strategies.add(strategy_key)
                            failed_strategies.add(strategy_key)
                            self._expansion_failure[strategy_key] = self._expansion_failure.get(strategy_key, 0) + 1
                        self._emitter.emit_log(f'    [!] Composição {strategy_desc} falhou em etapa intermediária. Selecionando nova estratégia...')
                        continue

                    candidata_final = current_instruction
                    critica = accumulated_critica

                    if self._is_candidate_valid(candidata_final, leaf, strategy_desc):
                        ab_cases = self.experience_store.get_ab_test_cases(hash_instruction(self.skill_original), top_k=5)
                        ab_approved, score_orig, score_mut = self._run_ab_gate(leaf.instruction, candidata_final, ab_cases)
                        if ab_approved:
                            # Checkpoint incremental: preserva candidato aprovado pelo Gate A/B
                            self._save_incremental_checkpoint(
                                stage='gate_ab',
                                instruction=candidata_final,
                                strategy_key=strategy_key,
                                strategy_desc=strategy_desc,
                                gate_ab_score=score_mut,
                            )
                            post_cases = self.experience_store.get_ab_test_cases(
                                hash_instruction(self.skill_original), top_k=self.config.post_eval_sample_size
                            )
                            post_approved, post_score_orig, post_score_mut, post_def_orig, post_def_mut = self._run_post_eval(
                                leaf.instruction, candidata_final, post_cases
                            )
                            if post_approved:
                                child = self._create_child_node(leaf, candidata_final, critica, strategy_key, strategy_desc)
                                child.gate_ab_score = score_mut
                                child.gate_post_eval_score = post_score_mut
                                # Atualiza checkpoint incremental com Post-Eval
                                self._save_incremental_checkpoint(
                                    stage='post_eval',
                                    instruction=candidata_final,
                                    strategy_key=strategy_key,
                                    strategy_desc=strategy_desc,
                                    gate_ab_score=score_mut,
                                    gate_post_eval_score=post_score_mut,
                                )
                                with self.lock:
                                    self._expansion_success[strategy_key] = self._expansion_success.get(strategy_key, 0) + 1
                                    leaf.tried_strategies.discard(strategy_key)
                                return child
                            else:
                                # Post-Eval reprovou: descarta checkpoint incremental
                                self._discard_incremental_checkpoint()
                                with self.lock:
                                    leaf.tried_strategies.add(strategy_key)
                                    failed_strategies.add(strategy_key)
                                    self._expansion_failure[strategy_key] = self._expansion_failure.get(strategy_key, 0) + 1
                                self._emitter.emit_log(f'    [!] Post-Eval comportamental rejeitou composição {strategy_desc}. Tentando outra estratégia...')
                        else:
                            with self.lock:
                                leaf.tried_strategies.add(strategy_key)
                                failed_strategies.add(strategy_key)
                                self._expansion_failure[strategy_key] = self._expansion_failure.get(strategy_key, 0) + 1
                            self._emitter.emit_log(f'    [!] Gate A/B rejeitou composição {strategy_desc}. Tentando outra estratégia...')
                    else:
                        with self.lock:
                            leaf.tried_strategies.add(strategy_key)
                            failed_strategies.add(strategy_key)
                            self._expansion_failure[strategy_key] = self._expansion_failure.get(strategy_key, 0) + 1
                finally:
                    self._release_reserved_strategy(leaf, strategy_key)
                # Track for gradative escalation
                if tentativa == 1 and len(parts) == 2:
                    prev_was_2comp_rejected = True
                continue

            # ── FLUXO DE ESTRATÉGIA ISOLADA ──
            if not strategy_desc:
                strategy_desc = self._strategy_registry.get_name(strategy_key) or strategy_key
            strategy_prompt = self._strategy_registry.get_prompt(strategy_key)
            strategy_prompt = self._inject_dynamic_data(strategy_key, strategy_prompt)
            if not self._try_reserve_strategy(leaf, strategy_key):
                self._emitter.emit_log(
                    f'    [Reserva] Estratégia {strategy_desc} já reservada por outra thread. Tentando outra estratégia...'
                )
                continue

            try:
                self._emitter.emit_log(f'[*] Expandindo nó (Tentativa {tentativa + 1}/3) | Estratégia: {strategy_desc} | Nota: {nota}')

                candidata, nova_critica, sucesso = self._try_generate_mutation(
                    leaf, strategy_key, strategy_prompt, feedback_completo, nota, critica
                )
                if self._iteration_circuit_broken or self._check_iteration_abort():
                    return leaf
                critica = nova_critica

                if sucesso and self._is_candidate_valid(candidata, leaf, strategy_desc):
                    # Gate A/B: aprova apenas mutações com melhoria mensurável
                    ab_cases = self.experience_store.get_ab_test_cases(hash_instruction(self.skill_original), top_k=5)
                    ab_approved, score_orig, score_mut = self._run_ab_gate(leaf.instruction, candidata, ab_cases)
                    if ab_approved:
                        # Checkpoint incremental: preserva candidato aprovado pelo Gate A/B
                        self._save_incremental_checkpoint(
                            stage='gate_ab',
                            instruction=candidata,
                            strategy_key=strategy_key,
                            strategy_desc=strategy_desc,
                            gate_ab_score=score_mut,
                        )
                        # Post-Eval Comportamental: valida comportamento real do agente
                        post_cases = self.experience_store.get_ab_test_cases(
                            hash_instruction(self.skill_original), top_k=self.config.post_eval_sample_size
                        )
                        post_approved, post_score_orig, post_score_mut, post_def_orig, post_def_mut = self._run_post_eval(
                            leaf.instruction, candidata, post_cases
                        )
                        if post_approved:
                            child = self._create_child_node(leaf, candidata, critica, strategy_key, strategy_desc)
                            child.gate_ab_score = score_mut
                            child.gate_post_eval_score = post_score_mut
                            # Atualiza checkpoint incremental com Post-Eval
                            self._save_incremental_checkpoint(
                                stage='post_eval',
                                instruction=candidata,
                                strategy_key=strategy_key,
                                strategy_desc=strategy_desc,
                                gate_ab_score=score_mut,
                                gate_post_eval_score=post_score_mut,
                            )
                            with self.lock:
                                self._expansion_success[strategy_key] = self._expansion_success.get(strategy_key, 0) + 1
                                leaf.tried_strategies.discard(strategy_key)  # sucesso: remove da lista de falhas
                            return child
                        else:
                            # Post-Eval comportamental reprovou
                            self._discard_incremental_checkpoint()
                            with self.lock:
                                leaf.tried_strategies.add(strategy_key)
                                failed_strategies.add(strategy_key)
                                self._expansion_failure[strategy_key] = self._expansion_failure.get(strategy_key, 0) + 1
                            self._emitter.emit_log(f'    [!] Post-Eval comportamental rejeitou mutação de {strategy_desc}. Tentando outra estratégia...')
                            # Track for gradative approach
                            if tentativa == 0 and not is_composite:
                                prev_was_isolated_rejected = True
                            continue
                    else:
                        # Gate A/B reprovou: estratégia falhou para este nó
                        with self.lock:
                            leaf.tried_strategies.add(strategy_key)
                            failed_strategies.add(strategy_key)
                            self._expansion_failure[strategy_key] = self._expansion_failure.get(strategy_key, 0) + 1
                        self._emitter.emit_log(f'    [!] Gate A/B rejeitou mutação de {strategy_desc}. Tentando outra estratégia...')
                        # Track for gradative approach
                        if tentativa == 0 and not is_composite:
                            prev_was_isolated_rejected = True
                        continue

                # Estratégia falhou — registra e tenta próxima
                with self.lock:
                    leaf.tried_strategies.add(strategy_key)
                    failed_strategies.add(strategy_key)
                    self._expansion_failure[strategy_key] = self._expansion_failure.get(strategy_key, 0) + 1
                    if strategy_key in self._discovered_strategies:
                        total_attempts = self._expansion_success.get(strategy_key, 0) + self._expansion_failure.get(strategy_key, 0)
                        if total_attempts >= 3 and self._expansion_success.get(strategy_key, 0) == 0:
                            self._emitter.emit_log(f'    [Discover Deprioritize] Estratégia "{strategy_desc}" com 0% de sucesso após {total_attempts} tentativas. Reduzindo prior.')
                            self.mutation_bandit.update(strategy_key, -0.5)  # penalidade forte no bandit
                self._emitter.emit_log(f'    [!] Estratégia {strategy_desc} falhou. Selecionando nova estratégia...')
            finally:
                self._release_reserved_strategy(leaf, strategy_key)

            # Track for gradative approach
            if tentativa == 0 and not is_composite:
                prev_was_isolated_rejected = True

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
        child_len = len(child.instruction)
        parent_len = len(parent_instruction)
        if child_len == parent_len:
            return reward
        
        # Calculate raw multiplier before clamp
        raw_mult = cfg.density_threshold / max(0.01, child_len / max(1, parent_len))
        
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
            is_at_floor = abs(density_mult - cfg.density_multiplier_min) < 0.001
            self._emitter.emit_log(
                f"    [{direction}] child_len={child_len}/{parent_len} parent | "
                f"raw_mult={raw_mult:.3f} -> clamped={density_mult:.3f} | "
                f"Fator: {density_mult:.2f}{' [PISO]' if is_at_floor else ''}"
            )
            
            # Track floor occurrences and warn if >80% of recent penalties are at floor
            with self.lock:
                if not hasattr(self, '_density_floor_history'):
                    self._density_floor_history = []
                self._density_floor_history.append(is_at_floor)
                if len(self._density_floor_history) > 10:
                    self._density_floor_history.pop(0)
                if len(self._density_floor_history) >= 10:
                    pct_at_floor = sum(self._density_floor_history) / len(self._density_floor_history)
                    if pct_at_floor > 0.8:
                        self._emitter.emit_log(
                            f'    [Density Audit] {pct_at_floor:.0%} das últimas penalidades de densidade '
                            f'estão no piso ({cfg.density_multiplier_min}). '
                            f'Considere ajustar density_threshold ({cfg.density_threshold}) ou o piso.'
                        )
        
        return reward * density_mult

    def _is_cancelled(self) -> bool:
        return self._emitter.is_cancelled() or getattr(self, '_abort_flag', False)

    def _remaining_time(self, timeout_cap: float | None = None) -> float:
        if self._iteration_deadline > 0:
            remaining = self._iteration_deadline - time.perf_counter()
        elif self._iteration_start_time > 0:
            remaining = self.config.iteration_timeout_s - (time.perf_counter() - self._iteration_start_time)
        else:
            remaining = self.config.iteration_timeout_s
        remaining = max(0.0, remaining)
        if timeout_cap is None:
            return remaining
        return max(0.0, min(timeout_cap, remaining))

    def _try_reserve_strategy(self, leaf: MCTSNode, strategy_key: str) -> bool:
        with leaf.lock:
            if strategy_key in leaf.reserved_strategies:
                return False
            leaf.reserved_strategies.add(strategy_key)
            return True

    def _release_reserved_strategy(self, leaf: MCTSNode, strategy_key: str) -> None:
        with leaf.lock:
            leaf.reserved_strategies.discard(strategy_key)

    def _check_iteration_abort(self) -> bool:
        """Verifica se a iteração deve ser abortada: cancelamento pelo usuário, abort flag, ou circuit breaker."""
        if self._is_cancelled():
            return True

        if self._iteration_deadline > 0 and time.perf_counter() > self._iteration_deadline:
            self._iteration_circuit_broken = True
            self._emitter.emit_log('    [Circuit Breaker] Deadline já passado, abortando.')
            return True

        # Circuit breaker: verifica teto de tempo
        if self._iteration_start_time > 0:
            elapsed = time.perf_counter() - self._iteration_start_time
            if elapsed > self.config.iteration_timeout_s:
                self._iteration_circuit_broken = True
                self._emitter.emit_log(
                    f'    [Circuit Breaker] Iteração excedeu teto de '
                    f'{self.config.iteration_timeout_s}s ({elapsed:.1f}s). Abortando.'
                )
                return True

        # Circuit breaker: verifica teto de chamadas LLM
        with self.lock:
            calls = self._llm_call_count
        if calls >= self.config.iteration_llm_call_limit:
            self._iteration_circuit_broken = True
            self._emitter.emit_log(
                f'    [Circuit Breaker] Iteração excedeu teto de '
                f'{self.config.iteration_llm_call_limit} chamadas LLM ({calls}). Abortando.'
            )
            return True

        return False

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
        parent_reward = child.parent.raw_reward if child.parent else 0.0
        self._last_iter_parent_raw = parent_reward  # exposto para log [Score Chain]
        shaped_reward = calcular_delta_reward(reward, parent_reward)
        child.shaped_reward = shaped_reward
        self.backpropagation(child, shaped_reward)
        with self.lock:
            if child.mutation_strategy:
                self.mutation_bandit.update(child.mutation_strategy, shaped_reward)
                # Rastreamento de custo por estratégia
                strategy = child.mutation_strategy
                llm_calls = self._llm_call_count  # custo LLM acumulado nesta iteração/expansão
                estimated_tokens = llm_calls * 2000
                success = reward > 0.0
                self.mutation_bandit.record_cost(strategy, llm_calls, estimated_tokens, success)
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

    def _save_checkpoint(self, child: MCTSNode, reward: float) -> None:
        """Persiste o melhor nó em arquivo de checkpoint."""
        import json
        import os
        from datetime import datetime, timezone

        checkpoint_dir = os.path.join('outputs', 'strategies')
        os.makedirs(checkpoint_dir, exist_ok=True)

        checkpoint_path = os.path.join(checkpoint_dir, f'checkpoint_{self.job_id}.json')

        data = {
            'instruction': child.instruction,
            'score': reward,
            'strategy': child.mutation_strategy or 'unknown',
            'depth': child.depth,
            'gate_ab_score': child.gate_ab_score,
            'gate_post_eval_score': child.gate_post_eval_score,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
            'iteration': self._expand_count,  # approximate iteration counter
        }

        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self._emitter.emit_log(
            f'    [Checkpoint] Melhor nó salvo: score={reward:.3f}, '
            f'strategy={child.mutation_strategy or "unknown"}, depth={child.depth}'
        )

    def _save_incremental_checkpoint(
        self, stage: str, instruction: str = "",
        strategy_key: str = "", strategy_desc: str = "",
        gate_ab_score: float = 0.0, gate_post_eval_score: float = 0.0,
    ) -> None:
        """Salva/atualiza checkpoint incremental entre estágios de gate ou descoberta."""
        from datetime import datetime, timezone

        is_update = self._incremental_checkpoint is not None

        self._incremental_checkpoint = {
            'instruction': instruction,
            'strategy_key': strategy_key,
            'strategy_desc': strategy_desc,
            'gate_ab_score': gate_ab_score,
            'gate_post_eval_score': gate_post_eval_score,
            'stage': stage,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        }

        if stage == 'gate_ab':
            self._emitter.emit_log(
                f'    [Checkpoint Incremental] Gate A/B aprovado: score={gate_ab_score:.3f}, '
                f'strat={strategy_desc}'
            )
        elif stage == 'post_eval':
            self._emitter.emit_log(
                f'    [Checkpoint Incremental] Post-Eval aprovado: score={gate_post_eval_score:.3f} '
                f'(completo: A/B={gate_ab_score:.3f}, Post-Eval={gate_post_eval_score:.3f})'
            )
        elif stage == 'discovery':
            self._emitter.emit_log(
                f'    [Checkpoint Incremental] Descoberta salva: strat={strategy_desc}, '
                f'eixo={strategy_key}'
            )

    def _discard_incremental_checkpoint(self) -> None:
        """Descarta o checkpoint incremental (ex.: Post-Eval reprovou)."""
        if self._incremental_checkpoint:
            self._emitter.emit_log(
                '    [Checkpoint Incremental] Descartado (Post-Eval reprovou)'
            )
            self._incremental_checkpoint = None

    def _apply_gate_fallback(self, child, reason: str, heuristic_result: dict):
        """Gate Fallback: preserva candidato aprovado pelos gates quando simulação não é possível."""
        fallback_raw = child.gate_ab_score
        child.raw_reward = fallback_raw
        child.last_reward = fallback_raw
        child.feedback = f"fallback: {reason}, gate-approved"

        if reason == "simulação timeout":
            self._emitter.emit_log(
                f'    [Gate Fallback] Simulação timeout. '
                f'Usando fallback_raw={fallback_raw:.3f} do Gate A/B '
                f'(score_mut={child.gate_ab_score:.3f}). '
                f'Post-Eval={child.gate_post_eval_score:.3f}'
            )
        else:
            self._emitter.emit_log(
                f'    [Gate Fallback] Circuit breaker pré-simulação. '
                f'Usando fallback_raw={fallback_raw:.3f} do Gate A/B '
                f'(A/B={child.gate_ab_score:.3f}). '
                f'Post-Eval={child.gate_post_eval_score:.3f}'
            )

        reward = self._apply_reward_multipliers(fallback_raw, heuristic_result, child)
        child.multiplied_reward = reward
        self._commit_iteration(child, reward, child.feedback)
        with self.lock:
            if fallback_raw > self.best_reward_so_far:
                self._save_checkpoint(child, fallback_raw)
                self.best_reward_so_far = fallback_raw
        self._last_iter_mult = child.multiplied_reward
        self._last_iter_shaped = child.shaped_reward
        parent_raw = getattr(self, '_last_iter_parent_raw', 0.0)
        score = child.q_value / max(1, child.visits)
        self._emitter.emit_log(
            f'    [Score Chain] CANONICAL raw-scale parent_raw={parent_raw:.3f} | '
            f'child_raw={child.raw_reward:.3f} → mult={child.multiplied_reward:.3f} → '
            f'shaped={child.shaped_reward:.3f} (0.6*mult + 0.4*(mult - parent_raw)) → '
            f'γ-discount → Q/visits={score:.3f}'
        )
        return False, fallback_raw

    def _run_mcts_iteration(self, root: MCTSNode) -> Tuple[bool, float]:
        """RN-06: Verifica cancelamento em 3 checkpoints obrigatórios."""
        self._last_iter_strategy = 'N/A'
        self._last_iter_depth = 0

        if self._check_iteration_abort():
            return True, 0.0

        leaf = self.selection(root)

        # Time-gate preventivo: verificar se há tempo para gates + simulação
        if self._remaining_time() < self.config.min_time_for_gates_s + 60:
            self._emitter.emit_log(
                '    [Circuit Breaker] Tempo restante insuficiente para '
                'gates + simulação. Abortando.'
            )
            return True, 0.0

        child = leaf  # fallback caso _expand_child lance exceção
        try:
            child = self._expand_child(leaf)
            # Atribuir IMEDIATAMENTE após _expand_child, antes de qualquer checkpoint,
            # para que o log sempre reflita a estratégia real usada na expansão
            if child != leaf:
                self._last_iter_strategy = child.mutation_strategy or 'unknown'
                self._last_iter_depth = child.depth
        finally:
            if leaf != child:
                leaf.remove_virtual_loss()

        if self._check_iteration_abort():
            if child != leaf:
                child.remove_virtual_loss()
            return True, 0.0

        # BUG-2 fix: se a expansão falhou e retornou o próprio leaf,
        # não há filho novo para simular. Evita iteração desperdiçada.
        if child == leaf:
            self._last_iter_strategy = 'none'
            self._last_iter_depth = leaf.depth
            self._emitter.emit_log('    [Iteração Descartada] Nó pai retornado sem filho. Nenhuma estratégia gerou candidato novo.')
            return False, 0.0

        is_pruned, heuristic_result = self._evaluate_and_prune(child)
        if is_pruned:
            return False, 0.0

        # Checkpoint provisório para candidatos aprovados pelos gates
        if child.gate_ab_score > 0 and child.gate_post_eval_score > 0:
            self._save_checkpoint(child, child.gate_ab_score)
            self._emitter.emit_log(
                f'    [Checkpoint Provisório] Candidato gate-approved salvo: '
                f'A/B={child.gate_ab_score:.3f}, Post-Eval={child.gate_post_eval_score:.3f}'
            )

        if self._check_iteration_abort():
            if child.gate_post_eval_score > 0:
                return self._apply_gate_fallback(child, "circuit breaker pré-simulação", heuristic_result)
            return True, 0.0

        remaining = self._remaining_time()
        if remaining <= 0:
            if child.gate_post_eval_score > 0:
                return self._apply_gate_fallback(child, "circuit breaker pré-simulação", heuristic_result)
            self._iteration_circuit_broken = True
            self._emitter.emit_log('    [Circuit Breaker] Sem tempo restante para iniciar simulation(). Abortando.')
            return True, 0.0

        simulation_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = simulation_executor.submit(self.simulation, child.instruction)
        try:
            raw_reward, feedback = future.result(timeout=remaining)
        except concurrent.futures.TimeoutError:
            # Gate Fallback: preservar candidato aprovado pelos gates
            if child.gate_ab_score > 0:
                return self._apply_gate_fallback(child, "simulação timeout", heuristic_result)

            self._iteration_circuit_broken = True
            self._emitter.emit_log(
                f'    [Circuit Breaker] simulation() excedeu a janela restante ({remaining:.2f}s). '
                f'Thread em background continuará mas resultado será descartado.'
            )
            return True, 0.0
        finally:
            simulation_executor.shutdown(wait=False, cancel_futures=True)

        child.raw_reward = raw_reward
        reward = self._apply_reward_multipliers(raw_reward, heuristic_result, child)
        child.multiplied_reward = reward

        if raw_reward == 0.0 and feedback.startswith("Erro interno na avaliação"):
            child.had_technical_error = True

        if reward >= self.config.sufficiency_threshold:
            self._emitter.emit_log(f'    [Sufficiency] Nó atingiu limiar de suficiência ({reward:.3f} >= {self.config.sufficiency_threshold}). Marcando como terminal.')
            child.is_sufficient = True

        child.feedback = feedback
        child.last_reward = raw_reward  # escala raw (canônica) ao longo do DAG

        # best_reward_so_far agora rastreia raw_reward (escala canônica de qualidade),
        # não multiplied_reward. Isso unifica a régua usada pela poda relativa,
        # checkpoint e seleção final.
        with self.lock:
            if raw_reward > self.best_reward_so_far:
                old_best = self.best_reward_so_far
                # Save checkpoint BEFORE updating best_reward_so_far
                self._save_checkpoint(child, raw_reward)
                self.best_reward_so_far = raw_reward

        self._commit_iteration(child, reward, feedback)

        # Armazena métricas para o log [ITER X/Y]
        self._last_iter_mult = child.multiplied_reward
        self._last_iter_shaped = child.shaped_reward
        parent_raw = getattr(self, '_last_iter_parent_raw', 0.0)

        score = child.q_value / max(1, child.visits)
        self._emitter.emit_log(
            f'    [Score Chain] CANONICAL raw-scale parent_raw={parent_raw:.3f} | '
            f'child_raw={child.raw_reward:.3f} → mult={child.multiplied_reward:.3f} → '
            f'shaped={child.shaped_reward:.3f} (0.6*mult + 0.4*(mult - parent_raw)) → '
            f'γ-discount → Q/visits={score:.3f}'
        )

        return False, raw_reward

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
        if self._abort_flag:
            return True, consecutive_zeros, consecutive_api_errors
        if self._remaining_time(1.0) <= 0:
            self._iteration_circuit_broken = True
            remaining_iters = self.config.max_iterations - i
            if remaining_iters > 0:
                self._emitter.emit_log(
                    f'[Batch Abort] Deadline esgotado, pulando iterações {i+1}-{self.config.max_iterations}'
                )
            return True, consecutive_zeros, consecutive_api_errors
        from datetime import datetime, timezone
        t_start = time.perf_counter()
        self._iteration_start_time = t_start
        self._iteration_deadline = t_start + self.config.iteration_timeout_s
        self._iteration_circuit_broken = False
        self._emitter.emit_log(f'\n--- Iteração MCTS {i + 1}/{self.config.max_iterations} ---')
        strategy_used = 'N/A'
        depth_reached = 0
        try:
            should_break, iter_reward = self._run_mcts_iteration(root)
            strategy_used = getattr(self, '_last_iter_strategy', 'N/A')
            depth_reached = getattr(self, '_last_iter_depth', 0)
            self._emit_cost_event(i)  # emite metricas de custo apos a iteracao

            # Log de progressão com timestamp e latência
            # raw_reward é a escala canônica de qualidade; mult e shaped são
            # exibidos apenas quando divergem significativamente (|diff| > 0.05)
            elapsed = time.perf_counter() - t_start
            ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
            mult_reward = getattr(self, '_last_iter_mult', None)
            shaped_reward = getattr(self, '_last_iter_shaped', None)
            extra_parts = []
            if mult_reward is not None and abs(mult_reward - iter_reward) > 0.05:
                extra_parts.append(f'mult={mult_reward:.3f}')
            if shaped_reward is not None and abs(shaped_reward - iter_reward) > 0.05:
                extra_parts.append(f'shaped={shaped_reward:.3f}')
            extra = (' | ' + ' | '.join(extra_parts)) if extra_parts else ''
            self._emitter.emit_log(
                f'[ITER {i + 1:>3}/{self.config.max_iterations}] {ts} | {elapsed:.2f}s | '
                f'strat={strategy_used} | raw={iter_reward:.3f}{extra} | depth={depth_reached}'
            )

            # Circuit breaker abort: não conta como plateau nem como zero
            if self._iteration_circuit_broken:
                return False, consecutive_zeros, consecutive_api_errors

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
            elapsed = time.perf_counter() - t_start
            ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
            self._emitter.emit_log(
                f'[ITER {i + 1:>3}/{self.config.max_iterations}] {ts} | {elapsed:.2f}s | '
                f'strat={strategy_used} | reward=ERROR | depth={depth_reached}'
            )
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

    def _select_and_log_best_node(self, root: MCTSNode) -> tuple:
        """Retorna o melhor nó (por score) e o score da raiz.

        BUG-3 fix: raiz (depth=0) é excluída da competição. A raiz representa
        a skill original — se ela fosse selecionada significaria que nenhum filho
        superou o ponto de partida. Esse caso já é tratado separadamente em
        _format_best_node via `if best_node == root`. Excluir aqui evita
        que o gamma-discount diluído da raiz (que acumula muitas visitas)
        vença por volume em runs curtos (≤ 5 iterações).
        """
        root_score = root.q_value / max(1, root.visits)
        all_nodes = self._get_all_nodes(root)
        # BUG-3 fix: filtra a raiz; se só existir a raiz, retorna ela como fallback
        candidate_nodes = [n for n in all_nodes if n.depth > 0]
        if not candidate_nodes:
            return root, root_score  # fallback: nenhum filho gerado ainda
        best_node = max(candidate_nodes, key=lambda n: (
            n.q_value / max(1, n.visits),
            n.visits,
            n.depth,
        ))
        return best_node, root_score

    def _format_best_node(self, root: MCTSNode) -> str:
        best_node, root_score = self._select_and_log_best_node(root)

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

        best_score = best_node.q_value / max(1, best_node.visits)

        # Expor para _report_technical_errors
        self._best_node = best_node

        # Guarda anti-regressão: compara raw_reward (escala canônica), não Q/visits.
        # Raw_reward é a saída direta de funcao_de_recompensa, comparável entre
        # raiz e filhos (raiz não passa por multipliers nem delta-shaping).
        # Se raw_reward == 0 (checkpoint incompleto), usa gate_ab_score como proxy.
        if best_node != root:
            comparison_value = best_node.raw_reward
            if comparison_value == 0.0 and best_node.gate_ab_score > 0:
                comparison_value = best_node.gate_ab_score
                self._emitter.emit_log(
                    f'[Guarda Anti-Regressão] Usando gate_ab_score={comparison_value:.3f} '
                    f'como proxy (checkpoint incompleto, sem simulação)'
                )
            if comparison_value < root.raw_reward:
                self._emitter.emit_error(
                    f'[!] GUARDA ANTI-REGRESSÃO: Melhor nó (raw={comparison_value:.3f}) '
                    f'é pior que a raiz (raw={root.raw_reward:.3f}). '
                    f'Retornando skill original.'
                )
                self._emitter.emit_log(
                    f'[Veredito Final] GUARDA ANTI-REGRESSÃO: melhor nó rejeitado '
                    f'(raw={comparison_value:.3f} < raiz raw={root.raw_reward:.3f}). '
                    f'Retornando skill original.'
                )
                return root.instruction
        elif best_node == root:
            self._emitter.emit_log(
                f'[!] ATENCAO: Nenhuma otimizacao superou a skill original. '
                f'O otimizador nao encontrou melhoria significativa. '
                f'raw={best_node.raw_reward:.3f}, visits={best_node.visits}'
            )
            self._emitter.emit_log(
                f'[Veredito Final] Nenhum filho superou a raiz. '
                f'Retornando skill original. raw={root.raw_reward:.3f}, visits={root.visits}'
            )
        else:
            self._emitter.emit_log(
                f'[Veredito Final] Nó aceito: score={best_score:.3f}, raw={best_node.raw_reward:.3f}, '
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
        root.raw_reward = reward  # escala canônica de qualidade para comparação com filhos
        root.last_reward = root.raw_reward  # raiz propaga a mesma escala raw para o primeiro nível
        self.backpropagation(root, reward)

    def _run_threaded_search(self, root: MCTSNode) -> None:
        cfg = self.config
        consecutive_zeros = 0
        consecutive_api_errors = 0
        self._abort_flag = False

        iteration = 0
        while iteration < cfg.max_iterations:
            if self._emitter.is_cancelled() or self._abort_flag:
                if self._abort_flag:
                    self._emitter.emit_log(f'    [Abort] Flag de abort detectada. Não iniciando novo batch (iterações restantes: {cfg.max_iterations - iteration}).')
                break

            batch_size = min(cfg.num_threads, cfg.max_iterations - iteration)
            batch_iterations = list(range(iteration, iteration + batch_size))
            self._emitter.emit_log(f'    [Batch] Iniciando iterações {batch_iterations[0] + 1}-{batch_iterations[-1] + 1} de {cfg.max_iterations} ({batch_size} threads)')

            with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
                futures = {
                    executor.submit(self._run_single_iteration, root, i, consecutive_zeros, consecutive_api_errors): i
                    for i in batch_iterations
                }

                for future in concurrent.futures.as_completed(futures):
                    i = futures[future]
                    if self._emitter.is_cancelled():
                        self._emitter.emit_log('\n[!] OTIMIZAÇÃO INTERROMPIDA PELO USUÁRIO.')
                        executor.shutdown(wait=False, cancel_futures=True)
                        return
                    try:
                        should_break, z, e = future.result()
                        with self.lock:
                            # Propaga o pior caso de zeros/errors consecutivos entre threads do batch
                            consecutive_zeros = max(consecutive_zeros, z)
                            consecutive_api_errors = max(consecutive_api_errors, e)
                        if should_break:
                            self._abort_flag = True
                            # Conta quantas futures ainda estão pendentes
                            remaining = sum(1 for f in futures if not f.done())
                            if remaining > 0:
                                self._emitter.emit_log(f'    [Plateau Abort] Cancelando {remaining} iterações restantes do batch corrente.')
                            executor.shutdown(wait=False, cancel_futures=True)
                            return
                    except Exception as ex:
                        self._emitter.emit_error(f'[!] Erro fatal em thread (iter {i + 1}): {ex}')
                        consecutive_api_errors += 1
                        if consecutive_api_errors >= 3:
                            self._emitter.emit_error('[!] Falhas técnicas persistentes. Abortando.')
                            self._abort_flag = True
                            executor.shutdown(wait=False, cancel_futures=True)
                            return

            iteration += batch_size

    def _log_final_stats(self) -> None:
        self.experience_store.save()
        self._emitter.emit_log(f'[*] {len(self.experience_store.experiences)} experiências salvas na memória de longo prazo.')
        tt = self.transposition_table
        self._emitter.emit_log(
            f'[*] Tabela de Transposição: {tt.size} nós únicos, '
            f'{tt.hits} hits de {tt.lookups} buscas ({tt.hit_rate:.1%} taxa de reaproveitamento).'
        )
        self._log_bandit_stats()

        # Estatísticas de convergência
        root = self._root
        root_q_var = root.variance() if root.visits > 0 else 0.0
        self._emitter.emit_log(f'[*] Convergência MCTS: variância Q-value na raiz = {root_q_var:.4f}, visitas = {root.visits}')

        # Eficiência de expansão acumulada
        total_success = sum(self._expansion_success.values())
        total_failure = sum(self._expansion_failure.values())
        total_attempts = total_success + total_failure
        if total_attempts > 0:
            self._emitter.emit_log(f'[*] Eficiência de Expansão Acumulada: {total_success}/{total_attempts} ({total_success/total_attempts:.1%})')
            # Detalhamento por estratégia
            for strategy in sorted(set(list(self._expansion_success.keys()) + list(self._expansion_failure.keys()))):
                s = self._expansion_success.get(strategy, 0)
                f = self._expansion_failure.get(strategy, 0)
                if s + f > 0:
                    desc = get_strategy_description(strategy)
                    self._emitter.emit_log(f'    {desc}: {s}/{s+f} ({s/(s+f):.1%})')

        # Custo por aprovação por estratégia
        bandit_stats = self.mutation_bandit.get_stats()
        strategies_with_cost = [
            (k, v) for k, v in bandit_stats.items()
            if v.successful_expansions > 0
        ]
        if strategies_with_cost:
            self._emitter.emit_log('[*] Custo por aprovação (chamadas LLM):')
            for key, stats in sorted(strategies_with_cost, key=lambda x: (
                x[1].total_llm_calls / max(1, x[1].successful_expansions)
            )):
                custo = stats.total_llm_calls / max(1, stats.successful_expansions)
                desc = get_strategy_description(key)
                llm_info = f'{stats.total_llm_calls} chamadas LLM, ' if stats.total_llm_calls > 0 else 'sem custo LLM registrado, '
                self._emitter.emit_log(
                    f'    {desc}: {stats.successful_expansions} aprovações, '
                    f'{llm_info}'
                    f'custo/aprov={custo:.1f}'
                )

        if self._gates_without_test_cases > 0 or self._post_evals_without_test_cases > 0:
            self._emitter.emit_log(
                f'[*] Avaliações sem dados reais: Gate A/B={self._gates_without_test_cases}, '
                f'Post-Eval={self._post_evals_without_test_cases} — '
                f'considere adicionar casos de teste ao experience store para reduzir incerteza.'
            )

    def _report_technical_errors(self) -> None:
        """Reporta erros técnicos de infraestrutura que invalidaram avaliações.
        Distingue 'score zero real' de 'avaliação falhou por erro de contrato/configuração'."""
        total_evaluations = self._total_llm_calls
        tech_errors = self._technical_error_count

        if tech_errors > 0:
            pct = (tech_errors / max(1, total_evaluations)) * 100
            best_node = getattr(self, '_best_node', None)
            if best_node is not None and best_node.had_technical_error:
                desc = get_strategy_description(best_node.mutation_strategy) if best_node.mutation_strategy else 'unknown'
                self._emitter.emit_error(
                    f'\n[!] ATENÇÃO CRÍTICA: O próprio nó vencedor (strategy={desc}) '
                    f'teve sua avaliação comprometida por erro técnico. '
                    f'O resultado desta execução NÃO é confiável. '
                    f'{tech_errors}/{total_evaluations} avaliações ({pct:.1f}%) falharam no total.\n'
                    f'    Causas comuns: LM mal configurado, contrato de tipo violado, '
                    f'schema mismatch não tratado.\n'
                    f'    Verifique os logs de [Simulação] Recompensa 0.00! para diagnóstico.'
                )
            else:
                desc_part = ''
                if best_node is not None and best_node.mutation_strategy:
                    desc = get_strategy_description(best_node.mutation_strategy)
                    desc_part = f' O nó vencedor (strategy={desc}, raw={best_node.raw_reward:.3f}) foi avaliado com sucesso — o resultado final não está contaminado.'
                self._emitter.emit_error(
                    f'\n[!] ATENÇÃO: {tech_errors}/{total_evaluations} avaliações '
                    f'({pct:.1f}%) falharam por erro técnico de infraestrutura '
                    f'(não por score baixo).{desc_part}\n'
                    f'    Causas comuns: LM mal configurado, contrato de tipo violado, '
                    f'schema mismatch não tratado.\n'
                    f'    Verifique os logs de [Simulação] Recompensa 0.00! para diagnóstico.'
                )
        else:
            self._emitter.emit_log(
                f'[*] Nenhum erro técnico de avaliação detectado '
                f'({total_evaluations} avaliações realizadas).'
            )

    def optimize(self) -> str:
        cfg = self.config
        self._emitter.emit_log('\n[+] Inicializando o pipeline MCTS RL customizado com refinamentos...')
        self._emitter.emit_log(f'    Config: γ={cfg.gamma}, C_ucb={cfg.c_param}, α_pw={cfg.progressive_alpha}, threshold={cfg.value_threshold}')

        try:
            root = MCTSNode(self.skill_original, critica='Rascunho Inicial')
            self.notify_node(root)
            self._evaluate_root(root, cfg.root_median_samples)

            self._root = root
            self._run_threaded_search(root)
            self._log_final_stats()

            self._emitter.emit_log('\n=======================================================\n                OTIMIZAÇÃO CONCLUÍDA                   \n=======================================================\n')
            final_instruction = self._format_best_node(root)
            self._report_technical_errors()
            return final_instruction
        finally:
            self._llm_executor.shutdown(wait=False)
