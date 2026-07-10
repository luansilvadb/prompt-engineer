# Phase 05: Avaliador de Profundidade Heurística - Discussion Log

This log is for human reference, audits, and retrospectives. It is not read by downstream agents.

## Area 1: Ação no MCTS
- **Question:** Reduzir score progressivamente ou podar o nó imediatamente?
- **User's Choice:** Reduzir a nota progressivamente (multiplicador de penalidade), assim preservamos caminhos que podem evoluir.
- **Notes:** O usuário sugeriu redução progressiva, mas nas perguntas seguintes refinou a abordagem para podar em casos extremos usando um filtro rápido.

## Area 2: Métricas do Textstat
- **Question:** Qual heurística específica define 'verbosidade oca'? (Flesch-Kincaid, densidade lexical ou combinada?)
- **User's Choice:** Fórmula combinada, mas utilizando a Densidade Lexical como um filtro de poda rápida e prioritário.
- **Notes:** Abordagem em duas camadas. Poda rápida com Densidade Lexical; penalização progressiva com a fórmula combinada.

## Area 3: Ordem de Avaliação
- **Question:** Calcular antes ou depois da avaliação do LLM/Sentence-transformers?
- **User's Choice:** Calcular as heurísticas ANTES do LLM e do sentence-transformers como filtro primário.
- **Notes:** Abordagem sequencial para o filtro primário. Em seguida, processamento paralelo para a Camada 2 (LLM e sentence-transformers).
