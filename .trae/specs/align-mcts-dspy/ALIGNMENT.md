# Documentação de Alinhamento MCTS + DSPY

## 1. Visão Geral

Este documento registra as alterações implementadas no alinhamento das implementações de MCTS (Monte Carlo Tree Search) e DSPY (Declarative Self-improving Python) do projeto, seguindo as melhores práticas consolidadas de ambas as tecnologias conforme a literatura especializada.

### Objetivo do Alinhamento
- Integrar de forma coesa a lógica de busca em árvore do MCTS com a camada declarativa de otimização do DSPY
- Garantir separação de responsabilidades e modularidade
- Atender às melhores práticas do survey de Swiechowski et al. (MCTS) e da documentação DSPY 2026

## 2. Justificativas MCTS (Swiechowski et al.)

### 2.1 Políticas de Seleção Plugáveis (Strategy Pattern)
**Base:** Seção 3 do survey — UCT, UCB1-Tuned e alternativas de seleção.

**Decisão:** Extraímos os métodos `best_child_*` de `MCTSNode` para classes de política independentes (`PUCTPolicy`, `UCB1Policy`, `UCB1TunedPolicy`) implementando a interface `ISelectionPolicy`.

**Justificativa:** O survey documenta que diferentes políticas de seleção (UCT, UCB1-Tuned, PUCT/AlphaZero) têm desempenho distinto dependendo do domínio. Encapsulá-las como Strategy Pattern permite:
- Troca de política em runtime sem modificar a árvore
- Adição de novas políticas (ex: EXP3, UCB-V) sem alterar código existente
- Testabilidade isolada de cada estratégia de seleção

### 2.2 Knowledge-Bias UCT
**Base:** Seção 4.4 e 4.6 — Policy Update, Knowledge-Bias UCT.

**Decisão:** Integramos priors do `ValueEstimator` na seleção via `knowledge_bias_lambda`.

**Justificativa:** O survey descreve Knowledge-Bias UCT como forma de incorporar conhecimento de domínio (redes neurais, heurísticas, dados de especialistas) no processo de seleção. Nosso `ValueEstimator` aprende com experiências passadas (Dyna-2) e agora influencia a seleção proporcionalmente à confiança acumulada.

### 2.3 Max Depth e Sufficiency Threshold
**Base:** Seção 3.4 (DAGs/Transposition Tables) e Seção 7.1.1 (Action Reduction).

**Decisão:** Adicionamos `max_depth` e `sufficiency_threshold` ao `MCTSConfig`.

**Justificativa:** 
- `max_depth`: Previne crescimento descontrolado em espaços de busca profundos, seguindo o princípio de Action Reduction (Sec. 3.1).
- `sufficiency_threshold`: Implementa Early Termination (Sec. 3.3) baseado em qualidade, não apenas contagem de iterações. Nós que atingem qualidade "suficiente" não precisam de mais exploração.

### 2.4 Validação de Retropropagação
**Base:** Seção 3.4 — Backpropagation em DAGs.

**Decisão:** Adicionamos validação de intervalo [0,1] no reward antes da retropropagação e detecção de Q-values negativos.

**Justificativa:** O survey enfatiza que a retropropagação em DAGs (Transposition Tables) requer cuidado extra com a consistência das estatísticas. Validar rewards no intervalo esperado previne corrupção silenciosa das estimativas de valor.

## 3. Justificativas DSPY (Documentação 2026)

### 3.1 Signatures com Type Hints
**Base:** Documentação DSPY — Signatures and Modules (formato 2026).

**Decisão:** Modernizamos todas as Signatures do formato `field: str = dspy.InputField()` para `field: dspy.InputField[str] = dspy.InputField()`.

**Justificativa:** O formato moderno oferece:
- Type hints que o DSPY interpreta para validação e parsing
- Suporte a tipos enriquecidos (`bool`, `float`, `list[str]`)
- Melhor integração com ferramentas de tipo (mypy, pyright)
- Base para funcionalidades futuras como validação automática de outputs

### 3.2 JudgeModule como dspy.Module
**Base:** Documentação DSPY — Modules, Composing custom modules.

**Decisão:** Encapsulamos o AvaliadorModoB como `JudgeModule(dspy.Module)` com método `forward()`.

**Justificativa:** Módulos DSPY são a unidade fundamental de composição e otimização. Como `dspy.Module`:
- O juiz pode ser composto em pipelines maiores
- Pode ser compilado por qualquer otimizador DSPY (GEPA, MIPROv2)
- Suporta `save()`/`load()` padronizados
- É marcado como `_compiled=True` após otimização, impedindo re-otimização acidental

### 3.3 Métrica DSPY Compilável
**Base:** Documentação DSPY — Optimizers, GEPA (feedback-rich metric).

**Decisão:** Criamos `create_dspy_metric()` que retorna uma métrica compatível com `dspy.Metric`.

**Justificativa:** Otimizadores como GEPA exigem métricas que retornam feedback rico (não apenas score). Nossa métrica:
- Retorna `float` para MIPROv2
- Popula `pred.feedback` para GEPA
- Retorna `bool` para BootstrapFewShot
- Reutiliza a função de recompensa composicional existente

### 3.4 Rastreamento de Métricas (Latência, Taxa de Compilação)
**Base:** Documentação DSPY — "Compiling is expensive".

**Decisão:** Adicionamos rastreamento de latência por chamada LLM e taxa de sucesso de compilação.

**Justificativa:** A documentação DSPY alerta que compilação é cara. Métricas de latência e taxa de sucesso permitem:
- Auditar o custo-benefício da recompilação
- Identificar regressões de desempenho
- Tomar decisões informadas sobre frequência de recompilação

## 4. Guia de Manutenção para Sessões de Pairing Futuras

### 4.1 Checklist Pré-Sessão
1. Verificar versão do DSPY instalada (`pip show dspy`)
2. Confirmar que `golden_set.json` está atualizado
3. Revisar métricas de drift do último juiz compilado
4. Verificar se há novas estratégias de mutação não cobertas pelo bandit

### 4.2 Durante a Sessão
1. **MCTS:** Sempre validar que novas políticas de seleção implementam `ISelectionPolicy`
2. **MCTS:** Testar `max_depth` e `sufficiency_threshold` com valores extremos antes de calibrar
3. **DSPY:** Novas Signatures DEVEM usar type hints modernos (`InputField[str]`)
4. **DSPY:** Novos módulos DEVEM herdar de `dspy.Module`
5. **Integração:** Qualquer alteração na função de recompensa deve manter compatibilidade com `dspy.Metric`

### 4.3 Pós-Sessão
1. Executar `test_mcts.py`, `test_dspy_signatures.py`, `test_optimizer_integration.py`
2. Verificar taxa de sucesso de compilação do teleprompter
3. Atualizar este documento com novas decisões de design
4. Revisar métricas de convergência MCTS (variância Q-value na raiz)

### 4.4 Pontos de Atenção
- **Não modificar** `MCTSNode.best_child_*` — estão deprecated; usar políticas em `selection_policies.py`
- **Não instanciar** `AvaliadorModoBSignature` diretamente — usar `JudgeModule`
- **Sempre** usar `_sanitize_unicode_for_api` em chamadas ao avaliador
- **Sempre** validar rewards no intervalo [0,1] antes de backprop
- **Sempre** verificar `is_sufficient` antes de expandir um nó

## 5. Registro de Alterações

| Data | Alteração | Arquivos |
|------|-----------|----------|
| 2026-07-23 | Signatures modernizadas com type hints | `src/infrastructure/dspy_impl.py` |
| 2026-07-23 | JudgeModule como dspy.Module | `src/infrastructure/judge_module.py` (novo) |
| 2026-07-23 | Métrica DSPY compilável | `src/infrastructure/dspy_metric.py` (novo) |
| 2026-07-23 | Políticas de seleção MCTS plugáveis | `src/domain/selection_policies.py` (novo), `src/optimizer.py` |
| 2026-07-23 | Knowledge-Bias UCT integrado | `src/domain/selection_policies.py` |
| 2026-07-23 | max_depth e sufficiency_threshold | `src/domain/config.py`, `src/domain/mcts.py`, `src/optimizer.py` |
| 2026-07-23 | Validações de recompensa/expansão/backprop | `src/signatures.py`, `src/optimizer.py` |
| 2026-07-23 | Rastreamento de métricas DSPY | `src/domain/events.py`, `src/optimizer.py`, `src/teleprompter.py` |
| 2026-07-23 | AlignConfig unificado | `src/domain/align_config.py` (novo) |
