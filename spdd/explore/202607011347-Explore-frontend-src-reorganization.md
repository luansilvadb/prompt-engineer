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
