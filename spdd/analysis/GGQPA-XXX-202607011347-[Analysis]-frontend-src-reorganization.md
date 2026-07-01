# SPDD Analysis: Reorganização do Frontend para pasta src/

## Original Business Requirement
```markdown
# Registro de Exploração: Reorganização do Frontend para pasta src/

**Data**: 2026-07-01
**Objetivo**: Reestruturar a organização de arquivos no frontend para mover toda a lógica de código JavaScript de dentro de `assets/js` para uma pasta de código-fonte dedicada `src/` na raiz do frontend, mantendo a pasta `assets/` dedicada exclusivamente a arquivos de estilização (CSS).

---

## 1. Nova Estrutura Arquitetural

A nova distribuição do frontend sob a **Opção A** será:

```
frontend/
├── index.html                  # Atualizado para ler /src/index.js
├── assets/
│   └── index.css               # Apenas estilos (estáticos)
└── src/                        # Pasta de lógica exclusiva (Vanilla JS)
    ├── index.js
    ├── dom.js
    ├── sse.js
    ├── utils.js
    ├── viewmodels/
    │   ├── ViewModelBase.js
    │   ├── ConfigViewModel.js
    │   ├── TreeViewModel.js
    │   ├── ConsoleViewModel.js
    │   ├── HistoryViewModel.js
    │   └── JudgeViewModel.js
    └── views/
        ├── ConfigView.js
        ├── TreeView.js
        ├── ConsoleView.js
        ├── HistoryView.js
        └── JudgeView.js
```

---

## 2. Ajustes Necessários

### A. Frontend (HTML e Importações)
*   **Ponto de Entrada**: No arquivo [index.html](file:///d:/good/frontend/index.html), atualizar a linha de carregamento do script principal de:
    ```html
    <script type="module" src="/assets/js/index.js"></script>
    ```
    para:
    ```html
    <script type="module" src="/src/index.js"></script>
    ```
*   **Imports Relativos**: Atualizar os caminhos de importação nos arquivos JavaScript se necessário (como o arquivo [sse.js](file:///d:/good/frontend/assets/js/sse.js) que importava de `./dom.js` e passará a importar no mesmo nível). Como estamos movendo todos os arquivos de `assets/js/*` para `src/*` mantendo a mesma relação interna de pastas, as importações internas relativas (ex: `import { ConfigViewModel } from './viewmodels/ConfigViewModel.js'`) continuarão funcionando sem modificações!

### B. Backend (Serviço de Arquivos Estáticos)
*   **Rotas no FastAPI**: Em [src/api.py](file:///d:/good/src/api.py), a rota de arquivos estáticos atual monta apenas a pasta `/assets`. Precisamos adicionar o mount para a nova pasta `/src` para permitir que o navegador requisite os arquivos do frontend:
    ```python
    app.mount('/src', StaticFiles(directory=str(frontend_dir / 'src')), name='src')
    ```
```

## Domain Concept Identification

### Existing Concepts (from codebase)
*   **StaticMount**: Configuração de roteador FastAPI que expõe diretórios físicos para consumo HTTP de arquivos estáticos (CSS, imagens). Definido no inicializador do app em [src/api.py](file:///d:/good/src/api.py).
*   **ScriptLoader**: Tag `<script type="module">` dentro de [index.html](file:///d:/good/frontend/index.html) encarregada de iniciar a execução da lógica JS no navegador.

### New Concepts Required
*   **SourceMount**: Rota do FastAPI `/src` adicionada especificamente para servir os arquivos fonte JS reestruturados na raiz do frontend, mantendo-os independentes dos arquivos de visual/estilo.

### Key Business Rules
*   **Separação Conceitual de Assets**: A pasta `/assets` deve expor estritamente recursos de design (atualmente, o arquivo `/assets/index.css`), enquanto a lógica funcional é encapsulada na pasta `/src`.
*   **Preservação das Relações Relativas**: A hierarquia de pastas internas (`viewmodels/`, `views/`) deve ser copiada de forma idêntica para que nenhuma diretiva de importação interna precise ser reescrita.

---

## Strategic Approach

### Solution Direction
*   Montagem de um novo mount point no FastAPI que aponta para a pasta física `frontend/src`.
*   Migração de todos os scripts e subpastas de `frontend/assets/js/` para `frontend/src/` usando comandos shell.
*   Atualização da referência de ponto de entrada no HTML principal.
*   Remoção do diretório legado `js/` de dentro de `assets/` para evitar redundâncias e erros de cache.

### Key Design Decisions
*   **Método de Migração**: Execução via Powershell de movimentação recursiva.
    *   *Trade-off*: É rápido e garante a cópia imediata, mas o reloader do Uvicorn reiniciará durante a movimentação. O reloader lidará bem com isso uma vez finalizada a operação.
*   **Exposição Seletiva de Diretórios**: Manter os mounts de `/assets` e `/src` separados no FastAPI.
    *   *Trade-off*: Adiciona duas linhas de código no backend, mas preserva a separação de conceitos limpa que o usuário solicitou.

### Alternatives Considered
*   **Montar a raiz `frontend/` inteira como estático**: Rejeitado, pois exporia o código do backend se o diretório estivesse aninhado, além de ir contra as diretivas de isolamento de rotas do FastAPI que mantêm a rota raiz `/` servindo o `index.html` de forma controlada através de rotas dedicadas.

---

## Risk & Gap Analysis

### Requirement Ambiguities
*   Nenhuma ambiguidade crítica de negócio. O escopo e a estrutura de pastas da Opção A foram definidos de forma inequívoca pelo usuário.

### Edge Cases
*   **Imports em arquivos dinâmicos (sse.js)**: Como todos os arquivos mantêm suas posições relativas exatas, os imports de caminhos como `import { el } from '../dom.js'` em `views/TreeView.js` continuarão funcionando perfeitamente, já que `TreeView.js` continua um nível abaixo de `dom.js` na nova pasta `src`.
*   **Cache do Navegador**: O navegador pode manter o arquivo `/assets/js/index.js` antigo em cache se o diretório antigo não for deletado e a rota antiga `/assets` continuar montada.
    *   *Mitigação*: A exclusão total do diretório antigo `assets/js` garante que requisições legadas de cache falhem e forcem a atualização.

### Technical Risks
*   **Interrupção temporária do Servidor de Desenvolvimento**: A remoção e adição de arquivos no diretório sob monitoramento do Uvicorn disparará múltiplos recarregamentos.
    *   *Mitigação*: A movimentação deve ser feita de forma atômica/em lote e rápida para que o reloader do FastAPI se restabeleça logo em seguida.

### Acceptance Criteria Coverage
| AC# | Description | Addressable? | Gaps/Notes |
|-----|-------------|--------------|------------|
| AC1 | Mover todos os arquivos JS de `assets/js` para `src/` | Sim | Mover via script de console. |
| AC2 | Atualizar import de script no HTML principal para `/src/index.js` | Sim | Alterar linha correspondente em [index.html](file:///d:/good/frontend/index.html). |
| AC3 | Adicionar mount estático para `/src` no FastAPI | Sim | Atualizar inicialização em [src/api.py](file:///d:/good/src/api.py). |
