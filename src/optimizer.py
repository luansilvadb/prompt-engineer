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

import dspy
import time
import math
import random
import datetime
import uuid
from pathlib import Path
from typing import Callable, Tuple, Optional

from src.signatures import SelfReflectiveAgent, StrategyDiscoverer, funcao_de_recompensa, calcular_delta_reward, load_avaliador, MutadorCognitivoAgent, MutadorCognitivoOutput, _validate_raciocinio
from src.config import get_mcts_config
from src.experience_store import ExperienceStore, Experience, hash_instruction
from src.value_estimator import ValueEstimator
from src.mutations import (
    MutationBandit, get_mutation_prompt, get_strategy_description, registry
)
from src.semantic_evaluator import calculate_semantic_penalty
from src.heuristic_evaluator import evaluate_heuristics
from src.density_evaluator import calculate_density_multiplier


class MCTSNode:
    def __init__(
        self,
        instruction: str,
        parent: Optional['MCTSNode'] = None,
        feedback: str = '',
        node_id: Optional[str] = None,
        critica: str = '',
        mutation_strategy: str = '',
        depth: int = 0,
    ):
        self.instruction = instruction
        self.q_value = 0.0
        self.visits = 0
        self.feedback = feedback
        self.children = []
        self.parent = parent
        self.node_id = node_id if node_id else str(uuid.uuid4())
        self.critica = critica
        self.mutation_strategy = mutation_strategy
        self.depth = depth
        # Reward absoluto da última simulação (usado para delta shaping)
        self.last_reward = 0.0

    def max_children_allowed(self, progressive_c: float = 2.0, alpha: float = 0.5) -> int:
        """
        Progressive Widening: max_children = ceil(C * visits^α).
        Nós mais visitados (promissores) ganham mais filhos.
        Nós com poucas visitas ficam com poucos filhos (poda natural).
        """
        if self.visits == 0:
            return 1
        return max(1, math.ceil(progressive_c * (self.visits ** alpha)))

    def best_child_ucb(self, c_param: float = 1.41) -> Optional['MCTSNode']:
        """Seleção UCB1 padrão para a fase de seleção."""
        if not self.children:
            return None
            
        def ucb_score(child: 'MCTSNode') -> float:
            if child.visits == 0:
                return float('inf')
            return (child.q_value / child.visits) + c_param * math.sqrt(
                math.log(max(1, self.visits)) / child.visits
            )
            
        return max(self.children, key=ucb_score)

    def best_child_thompson(self) -> Optional['MCTSNode']:
        """
        Thompson Sampling para a seleção FINAL.
        
        Silver: "Think ahead, don't be greedy."
        
        Em vez do greedy best_child(c_param=0), sorteia da posterior
        Beta(α, β) de cada filho. Naturalmente seleciona o melhor
        mas com exploração residual proporcional à incerteza.
        """
        if not self.children:
            return None
        
        def thompson_score(child: 'MCTSNode') -> float:
            if child.visits == 0:
                return random.random()
            # Converter q_value médio [0,1] em parâmetros Beta
            mean = child.q_value / max(1, child.visits)
            # α e β proporcionais às visitas (mais visitas → distribuição mais concentrada)
            alpha = max(1.0, mean * child.visits + 1)
            beta = max(1.0, (1 - mean) * child.visits + 1)
            return random.betavariate(alpha, beta)
        
        return max(self.children, key=thompson_score)


class Optimizer:
    def __init__(
        self,
        skill_original: str,
        on_progress: Callable[[str], None] = lambda msg: None,
        on_error: Callable[[str], None] = lambda msg: None,
        is_cancelled: Callable[[], bool] = lambda: False,
        on_node: Callable[[dict], None] = lambda node: None,
        regras_adicionais: str = ''
    ):
        self.skill_original = skill_original
        self.on_progress = on_progress
        self.on_error = on_error
        self.is_cancelled = is_cancelled
        self.on_node = on_node
        self.regras_adicionais = regras_adicionais
        
        # Carregar hiperparâmetros configuráveis
        config = get_mcts_config()
        self.max_iterations = config['max_iterations']
        self.c_param = config['c_param']
        self.gamma = config['gamma']
        self.progressive_alpha = config['progressive_alpha']
        self.progressive_c = config['progressive_c']
        self.value_threshold = config['value_threshold']
        self.semantic_sim_threshold = config.get('semantic_sim_threshold', 0.85)
        self.lexical_density_min = config.get('lexical_density_min', 0.35)
        self.verbosity_penalty_factor = config.get('verbosity_penalty_factor', 0.85)
        self.density_threshold = config.get('density_threshold', 1.0)
        self.density_multiplier_min = config.get('density_multiplier_min', 0.5)
        self.density_multiplier_max = config.get('density_multiplier_max', 1.5)
        self.density_structured_bonus = config.get('density_structured_bonus', 0.2)
        
        # Componentes evoluídos
        self.agent = dspy.ChainOfThought(SelfReflectiveAgent)
        self.agent_cognitivo = dspy.ChainOfThought(MutadorCognitivoAgent)
        self.strategy_discoverer = dspy.Predict(StrategyDiscoverer)
        self.experience_store = ExperienceStore()
        self.value_estimator = ValueEstimator(learning_rate=config['value_lr'])
        self.mutation_bandit = MutationBandit(c_param=config['bandit_c_param'])
        
        # Carregar priors do experience store no bandit
        strategy_stats = self.experience_store.get_strategy_stats()
        if strategy_stats:
            self.mutation_bandit.load_priors(strategy_stats)
            self.on_progress(f'[*] Memória experiencial carregada: {len(self.experience_store.experiences)} experiências, {len(strategy_stats)} estratégias conhecidas.')

        # Prior boosting incondicional para MutadorCognitivo (COGN-01)
        cognitivo_prior = {
            'mutador_cognitivo': {
                'count': config.get('cognitivo_prior_count', 4),
                'mean_delta': config.get('cognitivo_prior_mean_delta', 0.05),
            }
        }
        self.mutation_bandit.load_priors(cognitivo_prior)
        self.on_progress(f'[*] Mutador Cognitivo prior boosting: {cognitivo_prior["mutador_cognitivo"]["count"]} virtual count, delta={cognitivo_prior["mutador_cognitivo"]["mean_delta"]}')

        # Tentar carregar modelo treinado do teleprompter
        load_avaliador()

    def selection(self, node: MCTSNode) -> MCTSNode:
        """Seleção UCB com progressive widening."""
        while node.children and len(node.children) >= node.max_children_allowed(self.progressive_c, self.progressive_alpha):
            best = node.best_child_ucb(self.c_param)
            if best is None:
                return node
            node = best
        return node

    def simulation(self, instruction: str) -> Tuple[float, str]:
        if self.is_cancelled():
            return 0.0, 'Cancelado pelo usuário.'
        try:
            example = dspy.Example(skill_original=self.skill_original, regras_adicionais=self.regras_adicionais)
            prediction = dspy.Prediction(skill_otimizada=instruction)
            reward, feedback = funcao_de_recompensa(example, prediction)
            if reward == 0.0:
                self.on_error(f"    [Simulação] Recompensa 0.00! Motivo: {feedback}")
            else:
                self.on_progress(f"    [Simulação] Recompensa obtida: {reward:.2f}")
            
            # Atualizar value estimator com observação real (online learning)
            self.value_estimator.update(instruction, reward)
            
            return float(reward), feedback
        except Exception as e:
            self.on_error(f"[!] Erro na simulação: {e}")
            return 0.0, f"Erro na simulação: {str(e)}"

    def _should_prune(self, instruction: str) -> bool:
        """
        Value Estimator: pré-filtra candidatos ruins sem gastar chamada LLM.
        Só poda se o estimador tem confiança suficiente (>0.3).
        """
        if self.value_estimator.confidence < 0.3:
            return False  # Estimador ainda não confiável
        
        estimated = self.value_estimator.estimate(instruction)
        if estimated < self.value_threshold:
            self.on_progress(f"    [Poda] Value estimator: {estimated:.2f} < threshold {self.value_threshold}. Podando.")
            return True
        return False

    def notify_node(self, node: MCTSNode):
        try:
            node_data = {
                'id': node.node_id,
                'parent_id': node.parent.node_id if node.parent else None,
                'instruction': node.instruction,
                'feedback': node.feedback,
                'critica': node.critica,
                'q_value': node.q_value,
                'visits': node.visits,
                'score': float(node.q_value / max(1, node.visits)),
                'mutation_strategy': node.mutation_strategy,
                'depth': node.depth,
            }
            self.on_node(node_data)
        except Exception as e:
            self.on_error(f"[!] Erro ao notificar nó do MCTS: {e}")

    def backpropagation(self, node: MCTSNode, reward: float):
        """
        Backpropagation com γ discount.
        
        Silver: temporal-difference — nós mais próximos da folha
        recebem mais crédito que nós distantes.
        """
        current = node
        depth_from_leaf = 0
        while current is not None:
            discounted_reward = reward * (self.gamma ** depth_from_leaf)
            current.q_value += discounted_reward
            current.visits += 1
            self.notify_node(current)
            current = current.parent
            depth_from_leaf += 1

    def _expand_node(self, leaf: MCTSNode) -> MCTSNode:
        # Selecionar estratégia de mutação via bandit
        strategy = self.mutation_bandit.select()
        
        if strategy == '__DISCOVER__':
            self.on_progress('[*] Bandit escolheu __DISCOVER__. Inventando nova heurística de mutação...')
            try:
                estrategias_conhecidas = ", ".join([registry.get_name(k) for k in registry.get_all_keys() if k != '__DISCOVER__'])
                if not estrategias_conhecidas:
                    estrategias_conhecidas = "Nenhuma. Você é livre para criar a primeira heurística (Tabula Rasa)."
                    
                nova_estrat = self.strategy_discoverer(
                    skill_atual=leaf.instruction,
                    feedbacks_recentes=leaf.feedback or "Nenhum feedback ainda. Invente algo inovador.",
                    estrategias_conhecidas=estrategias_conhecidas
                )
                
                # Gerar chave segura
                import re
                key_raw = nova_estrat.nome_estrategia.lower()
                key = re.sub(r'[^a-z0-9_]', '_', key_raw)[:30] + '_' + str(uuid.uuid4())[:4]
                
                registry.add_strategy(key, nova_estrat.nome_estrategia, nova_estrat.prompt_estrategia)
                self.on_progress(f'[+] Nova estratégia descoberta! {nova_estrat.nome_estrategia}')
                
                strategy = key
            except Exception as e:
                self.on_error(f'[!] Falha ao inventar estratégia: {e}. Usando fallback.')
                strategy = '__DISCOVER__'
                
        strategy_prompt = get_mutation_prompt(strategy)
        strategy_desc = get_strategy_description(strategy)
        
        # Buscar experiências similares para enriquecer o contexto
        similar_experiences = self.experience_store.query_similar(leaf.feedback, top_k=3)
        experience_context = ''
        if similar_experiences:
            lessons = [f"- Estratégia '{exp.mutation_strategy}': delta={exp.delta_reward:+.2f}" 
                       for exp in similar_experiences if exp.delta_reward != 0]
            if lessons:
                experience_context = '\nLições de otimizações passadas:\n' + '\n'.join(lessons[:3])
        
        critica = leaf.feedback
        nova_instrucao = leaf.instruction
        
        for tentativa in range(3):
            if self.is_cancelled():
                break
            if tentativa > 0:
                time.sleep(2 * tentativa)
            
            nota = str(leaf.q_value / max(1, leaf.visits))
            self.on_progress(f'[*] Expandindo nó (Tentativa {tentativa + 1}/3) | Estratégia: {strategy_desc} | Nota: {nota}')
            
            # Compor o contexto completo de feedback
            feedback_completo = critica
            if experience_context:
                feedback_completo += experience_context
            
            try:
                COGNITIVO_KEY = 'mutador_cognitivo'
                if strategy == COGNITIVO_KEY:
                    predicao = self.agent_cognitivo(
                        instrucao_anterior=leaf.instruction,
                        nota_anterior=nota,
                        feedback_juiz=feedback_completo,
                        estrategia_mutacao=strategy_prompt,
                    )
                    try:
                        _validate_raciocinio(predicao.raciocinio_estruturado)
                    except Exception as e:
                        self.on_error(f'[!] raciocinio_estruturado invalido: {e}')
                    try:
                        MutadorCognitivoOutput(nova_instrucao=predicao.nova_instrucao)
                    except Exception as e:
                        self.on_error(f'[!] nova_instrucao secoes cognitivas invalidas: {e}')
                else:
                    predicao = self.agent(
                        instrucao_anterior=leaf.instruction,
                        nota_anterior=nota,
                        feedback_juiz=feedback_completo,
                        estrategia_mutacao=strategy_prompt,
                    )
                candidata = predicao.nova_instrucao
                if candidata and candidata.strip() and candidata.strip() != leaf.instruction.strip():
                    # Checar via value estimator antes de aceitar
                    if self._should_prune(candidata):
                        self.on_progress(f'    [!] Candidata podada pelo value estimator. Tentando novamente...')
                        critica = f'{critica}\nA última tentativa gerou uma skill de baixa qualidade estimada. Mude radicalmente a abordagem.'
                        continue
                    
                    self.on_progress(f'    [Crítica]: {predicao.critica}')
                    critica = predicao.critica
                    nova_instrucao = candidata
                    break
                else:
                    self.on_error('    [!] Instrução gerada nula ou idêntica. Mudando abordagem...')
                    critica = f'{critica}\nInstrução idêntica ou nula. Teste uma mudança radical.'
            except Exception as e:
                self.on_error(f'    [!] Erro técnico na geração: {str(e)}')
                critica = f'{critica}\nErro técnico ({e}). Tente uma reescrita mais simples.'
        else:
            self.on_error('[!] Falha em gerar nova instrução após 3 tentativas. Usando variação mínima.')
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

    def _run_mcts_iteration(self, root: MCTSNode) -> Tuple[bool, bool, float]:
        """Returns (should_break, is_error, reward)"""
        if self.is_cancelled():
            return True, False, 0.0
        
        leaf = self.selection(root)
        if len(leaf.children) >= leaf.max_children_allowed(self.progressive_c, self.progressive_alpha):
            child = leaf
        else:
            child = self._expand_node(leaf)
        
        if self.is_cancelled():
            return True, False, 0.0
        
        # --- HEURISTIC PENALTY (Layer 1 & 2) ---
        heuristic_result = evaluate_heuristics(
            child.instruction,
            density_min=self.lexical_density_min,
            penalty_factor=self.verbosity_penalty_factor
        )

        if heuristic_result.get("prune"):
            self.on_progress(f"    [Poda Heurística] {heuristic_result.get('reason')}")
            child.feedback = heuristic_result.get("reason")
            child.last_reward = 0.0
            self.backpropagation(child, 0.0)
            return False, False, 0.0
        # ----------------------------------------
        
        reward, feedback = self.simulation(child.instruction)
        
        # --- HEURISTIC MULTIPLIER (Layer 2) ---
        multiplier = heuristic_result.get("penalty_multiplier", 1.0)
        if multiplier < 1.0:
            self.on_progress(f"    [Penalidade Heurística] Fator de decaimento: {multiplier:.2f}")
        reward = reward * multiplier
        # --------------------------------------
        
        # --- SEMANTIC PENALTY ---
        parent_instruction = child.parent.instruction if child.parent else self.skill_original
        penalty = calculate_semantic_penalty(
            child.instruction, 
            parent_instruction, 
            threshold=self.semantic_sim_threshold
        )
        if penalty < 1.0:
            self.on_progress(f"    [Penalidade Semântica] Fator de decaimento: {penalty:.2f}")
        reward = reward * penalty
        # ------------------------

        # --- DENSITY MULTIPLIER (COGN-04) ---
        parent_for_density = child.parent.instruction if child.parent else self.skill_original
        density_mult = calculate_density_multiplier(
            child_instruction=child.instruction,
            parent_instruction=parent_for_density,
            mutation_strategy=child.mutation_strategy,
            density_threshold=self.density_threshold,
            density_multiplier_min=self.density_multiplier_min,
            density_multiplier_max=self.density_multiplier_max,
            structured_bonus=self.density_structured_bonus,
        )
        if density_mult != 1.0:
            direction = "Bonus por Densidade" if density_mult > 1.0 else "Penalidade por Densidade"
            self.on_progress(f"    [{direction}] Fator: {density_mult:.2f}")
        reward = reward * density_mult
        # ------------------------------------

        child.feedback = feedback
        child.last_reward = reward
        
        # Delta reward shaping: comparar com o pai
        parent_reward = child.parent.last_reward if child.parent else 0.0
        shaped_reward = calcular_delta_reward(reward, parent_reward)
        
        self.backpropagation(child, shaped_reward)
        
        # Atualizar mutation bandit com a recompensa observada
        if child.mutation_strategy:
            self.mutation_bandit.update(child.mutation_strategy, shaped_reward)
        
        # Registrar experiência na store
        self.experience_store.add(Experience(
            skill_hash=hash_instruction(self.skill_original),
            mutation_strategy=child.mutation_strategy,
            delta_reward=reward - parent_reward,
            absolute_reward=reward,
            feedback=feedback[:500],  # Truncar feedback longo
            parent_instruction_hash=hash_instruction(child.parent.instruction) if child.parent else '',
            instruction=child.instruction,
            parent_instruction=child.parent.instruction if child.parent else self.skill_original
        ))
        
        return False, False, reward

    def optimize(self) -> str:
        self.on_progress('\n[+] Inicializando o pipeline MCTS RL customizado com refinamentos...')
        self.on_progress(f'    Config: γ={self.gamma}, C_ucb={self.c_param}, α_pw={self.progressive_alpha}, threshold={self.value_threshold}')
        
        root = MCTSNode(self.skill_original, critica='Rascunho Inicial')
        self.notify_node(root)
        
        self.on_progress('[*] Avaliando a instrução original (raiz)...')
        reward, feedback = self.simulation(root.instruction)
        root.feedback = feedback
        root.last_reward = reward
        self.backpropagation(root, reward)
        
        consecutive_zeros = 0
        consecutive_api_errors = 0
        
        for i in range(self.max_iterations):
            if self.is_cancelled():
                self.on_progress('\n[!] OTIMIZAÇÃO INTERROMPIDA PELO USUÁRIO.')
                break
                
            self.on_progress(f'\n--- Iteração MCTS {i + 1}/{self.max_iterations} ---')
            
            try:
                should_break, is_error, iter_reward = self._run_mcts_iteration(root)
                if should_break:
                    break
                
                if iter_reward == 0.0:
                    consecutive_zeros += 1
                else:
                    consecutive_zeros = 0
                    
                consecutive_api_errors = 0
                
                if consecutive_zeros >= 5:
                    self.on_error('\n[!] ALERTA: 5 iterações consecutivas com recompensa 0.0. Abortando por plateau.')
                    break
            except Exception as e:
                consecutive_api_errors += 1
                self.on_error(f'[!] Erro inesperado na iteração {i + 1}: {e}')
                if consecutive_api_errors >= 3:
                    self.on_error('[!] Falhas técnicas persistentes. Abortando.')
                    break
        
        # Salvar experiências acumuladas nesta sessão
        self.experience_store.save()
        self.on_progress(f'[*] {len(self.experience_store.experiences)} experiências salvas na memória de longo prazo.')
        
        # Log das estatísticas do bandit
        stats = self.experience_store.get_strategy_stats()
        if stats:
            self.on_progress('[*] Performance das estratégias de mutação:')
            for strategy, s in sorted(stats.items(), key=lambda x: x[1].get('mean_delta', 0), reverse=True):
                desc = get_strategy_description(strategy)
                self.on_progress(f'    {desc}: Δ médio={s["mean_delta"]:+.3f}, usos={int(s["count"])}')
                    
        self.on_progress('\n=======================================================\n                OTIMIZAÇÃO CONCLUÍDA                   \n=======================================================\n')
        
        # Seleção final via Thompson Sampling (exploração residual)
        best = root.best_child_thompson()
        if best:
            self.on_progress(f'[+] Melhor filho selecionado (Thompson): score={best.q_value / max(1, best.visits):.3f}, visits={best.visits}, strategy={get_strategy_description(best.mutation_strategy)}')
            return best.instruction
        return root.instruction

def save_optimized_skill(content: str) -> Path:
    """
    Salva o conteúdo da skill otimizada em um arquivo com timestamp.
    Retorna o caminho (Path) do arquivo salvo.
    """
    output_dir = Path('src/outputs/skills')
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'skill_otimizada_{timestamp}.md'
    output_file.write_text(content, encoding='utf-8')
    return output_file
