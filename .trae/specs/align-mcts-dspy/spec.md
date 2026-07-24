# Alinhamento MCTS + DSPY Spec

## Why
O projeto combina MCTS (Monte Carlo Tree Search) para busca de otimização com DSPY para avaliação declarativa, mas a integração atual trata o DSPY como mero invocador de LLM em vez de aproveitar seu ecossistema completo de módulos, otimizadores e métricas. As implementações de MCTS e DSPY precisam ser alinhadas às melhores práticas consolidadas de cada tecnologia, garantindo coesão arquitetural, separação de responsabilidades e métricas rastreáveis.

## What Changes
- Modernização das Signatures DSPY com type hints Python e field types enriquecidos (**BREAKING** em `dspy_impl.py` — adaptadores permanecem compatíveis)
- Extração de métrica DSPY compilável (função de recompensa como `dspy.Metric`) para uso com otimizadores nativos
- Camada formal de Módulos DSPY compondo o pipeline de avaliação (juiz como `dspy.Module`)
- Refatoração da seleção MCTS para interface plugável de políticas (Strategy Pattern para PUCT/UCB1/UCB1-Tuned)
- Validação formal da função de recompensa, eficiência de expansão de nós e consistência da retropropagação
- Adição de depth limit configurável e sufficiency threshold na árvore MCTS
- Integração de Knowledge-Bias UCT com priors do ValueEstimator
- Rastreamento de métricas de desempenho DSPY (custo/token, latência, taxa de sucesso de compilação)
- Unificação de configuração MCTS+DSPY em config central
- Documentação técnica do alinhamento com justificativas baseadas nas melhores práticas

## Impact
- Affected specs: N/A (primeiro spec de alinhamento)
- Affected code: `src/domain/mcts.py`, `src/infrastructure/dspy_impl.py`, `src/signatures.py`, `src/optimizer.py`, `src/teleprompter.py`, `src/evaluators/value.py`, `src/domain/config.py`, `src/config.py`

## ADDED Requirements

### Requirement: Signatures DSPY Modernizadas
O sistema SHALL utilizar o formato moderno (2026) de Signatures DSPY com type hints Python nativos (`str`, `float`, `bool`, `Literal`, `list[str]`) em todos os campos de InputField e OutputField.

#### Scenario: Signature com type hints
- **WHEN** uma Signature DSPY é definida no sistema
- **THEN** cada campo usa type hint Python como primeiro argumento de `dspy.InputField()` ou `dspy.OutputField()`

#### Scenario: Retrocompatibilidade de adaptadores
- **WHEN** uma Signature é modernizada com type hints
- **THEN** os adaptadores existentes (DSPyStrategyDiscoverer, DSPySelfReflectiveAgent, DSPyMutadorCognitivoAgent, DSPyAvaliadorModoB) continuam funcionando sem alteração de interface pública

### Requirement: Métrica DSPY Compilável
O sistema SHALL expor uma função de métrica compatível com `dspy.Metric` (assinatura `(example, pred, trace=None) -> float | bool`) que encapsula a função de recompensa composicional, permitindo que otimizadores nativos DSPY (GEPA, MIPROv2) a utilizem diretamente.

#### Scenario: Métrica usada por GEPA
- **WHEN** o teleprompter GEPA compila o juiz
- **THEN** a métrica recebe `(example, pred)` e retorna um score float no intervalo [0, 1]

#### Scenario: Feedback rico para GEPA
- **WHEN** a métrica é chamada com `trace` não-nulo
- **THEN** o atributo `feedback` do `Prediction` é populado com o feedback detalhado do avaliador

### Requirement: Juiz como Módulo DSPY
O sistema SHALL encapsular o AvaliadorModoB como uma subclasse de `dspy.Module` com método `forward()`, permitindo composição, compilação por otimizadores DSPY e persistência via `save()`/`load()` padronizados.

#### Scenario: Juiz como dspy.Module
- **WHEN** o juiz é instanciado
- **THEN** a classe herda de `dspy.Module` e expõe `forward(skill_original, skill_otimizada, regras_adicionais)` retornando um `dspy.Prediction`

#### Scenario: Persistência padronizada
- **WHEN** o juiz compilado é salvo
- **THEN** utiliza `module.save(path)` do DSPY em vez de `dspy.ChainOfThought(...).save(path)`

### Requirement: Políticas de Seleção MCTS Plugáveis
O sistema SHALL implementar um Strategy Pattern para políticas de seleção MCTS, onde cada política (PUCT, UCB1, UCB1-Tuned) é uma classe que implementa a interface `ISelectionPolicy` com método `select(node, config) -> MCTSNode`.

#### Scenario: Troca de política em runtime
- **WHEN** a configuração `selection_policy` é alterada
- **THEN** o Optimizer instancia a política correspondente sem modificar o código de seleção

#### Scenario: Nova política adicionada
- **WHEN** uma nova política de seleção é registrada
- **THEN** basta implementar `ISelectionPolicy` e registrá-la no dicionário de políticas, sem alterar `MCTSNode` ou `Optimizer`

### Requirement: Limites de Profundidade e Sufficiency Threshold
O sistema SHALL configurar `max_depth` e `sufficiency_threshold` no `MCTSConfig`, aplicando-os durante a expansão e seleção para evitar crescimento descontrolado da árvore e detectar convergência precoce tática.

#### Scenario: Nó atinge profundidade máxima
- **WHEN** um nó atinge `max_depth` durante a seleção
- **THEN** a expansão é bloqueada e o nó é tratado como folha terminal

#### Scenario: Sufficiency threshold atingido
- **WHEN** o score de um nó excede `sufficiency_threshold`
- **THEN** o nó é marcado como suficiente e não recebe mais expansões

### Requirement: Knowledge-Bias UCT
O sistema SHALL integrar priors do `ValueEstimator` como knowledge-bias na seleção UCT, combinando o prior aprendido com o valor observado via média ponderada controlada por `lambda` de blend.

#### Scenario: Prior do ValueEstimator influencia seleção
- **WHEN** a política de seleção calcula o score de um nó filho
- **THEN** o prior do `ValueEstimator` é combinado com Q-value via `score = lambda * prior + (1-lambda) * q_value`

### Requirement: Rastreamento de Métricas DSPY
O sistema SHALL emitir eventos de métricas DSPY (latência de chamada ao LM, tokens estimados, taxa de sucesso de compilação) durante a otimização, acessíveis via SSE para o frontend.

#### Scenario: Métricas DSPY emitidas
- **WHEN** uma chamada LLM é feita via módulo DSPY
- **THEN** latência e tokens estimados são registrados e emitidos como evento de custo

#### Scenario: Taxa de sucesso de compilação rastreada
- **WHEN** um teleprompter completa a compilação
- **THEN** a taxa de exemplos do trainset que passam na métrica é registrada

### Requirement: Configuração Unificada
O sistema SHALL consolidar parâmetros de configuração MCTS e DSPY em um único dataclass `AlignConfig` que agrupa `MCTSConfig` e parâmetros DSPY (tipo de otimizador, budget de compilação, métrica de qualidade, thresholds de drift).

#### Scenario: Config unificada carregada do ambiente
- **WHEN** o sistema inicia
- **THEN** `AlignConfig` é populado de variáveis de ambiente com defaults documentados

## MODIFIED Requirements

### Requirement: Função de Recompensa Validada
A função `funcao_de_recompensa` em `src/signatures.py` SHALL ser estendida para:
1. Validar que o score retornado está estritamente em [0, 1]
2. Registrar warning quando `manteve_regras_criticas=False` mas score > 0
3. Emitir métrica de latência da chamada ao avaliador
4. Expor-se como `dspy.Metric` compatível com otimizadores nativos

#### Scenario: Score fora do intervalo
- **WHEN** o cálculo de score produz valor fora de [0, 1]
- **THEN** o valor é clampado e um warning é emitido no log

### Requirement: Eficiência de Expansão de Nós
O método `_expand_node` do `Optimizer` SHALL ser modificado para:
1. Registrar contadores de tentativas de expansão bem-sucedidas vs. falhas por estratégia
2. Emitir métrica de eficiência (expansões bem-sucedidas / total de tentativas)
3. Respeitar `max_depth` da configuração

#### Scenario: Métrica de eficiência emitida
- **WHEN** uma iteração MCTS completa
- **THEN** a taxa de sucesso de expansão é emitida via evento de custo

### Requirement: Consistência da Retropropagação
O método `backpropagation` do `Optimizer` SHALL ser modificado para:
1. Validar que `reward` está em [0, 1] antes de propagar
2. Registrar inconsistências (ex: Q-value negativo após backprop)
3. Emitir estatísticas de convergência (variância do Q-value na raiz)

#### Scenario: Reward inválido detectado
- **WHEN** `reward` passado para `backpropagation` é negativo ou > 1
- **THEN** um erro é emitido e o reward é clampado

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
