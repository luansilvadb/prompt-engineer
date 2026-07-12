# Design System: Ultra-Minimalist Precision

Este documento define as diretrizes estéticas e técnicas da interface do projeto (Skill Optimizer MCTS), baseadas na estética **Ultra-Minimalista de Alta Precisão (Dev-Tool Premium)**. 

A inspiração arquitetural deriva de ferramentas modernas focadas em desenvolvedores, como Vercel, Linear e OpenAI, onde o foco absoluto está na densidade de informação e na ausência total de distrações visuais genéricas.

---

## 1. Princípios Fundamentais

1. **Foco Cirúrgico nos Dados:** A ferramenta lida com simulações matemáticas e árvores MCTS. O visual deve parecer um "painel de instrumentos de laboratório de software". Sem "blobs" coloridos, sem gradientes roxos genéricos.
2. **Monocromático Premium:** A interface opera quase puramente em preto, cinza-escuro e branco. Cores (azul, verde, vermelho) são estritamente reservadas para status semânticos.
3. **Densidade Tática:** Os tamanhos de fonte são ligeiramente menores que o padrão web (base `13px`) para permitir que painéis de logs e códigos sejam lidos sem excesso de rolagem.
4. **Física e Fricção:** Toda animação e transição possui um "peso" através do uso de curvas `cubic-bezier`, dando uma sensação tátil às interações.

---

## 2. Tipografia

A tipografia reflete limpeza e precisão geométrica.

*   **Fonte Principal (UI, Cabeçalhos e Corpo):** `Manrope`
    *   *Por quê?* É uma Sans-Serif moderna, técnica, altamente legível e com forte atitude profissional em pesos menores.
*   **Fonte de Código e Dados:** `JetBrains Mono`
    *   *Onde usar?* Logs de console, previews JSON, botões/tags numéricas, visualização das regras e scores dos nós.

---

## 3. Paleta de Cores (Tokens)

Toda a arquitetura CSS usa tokens rígidos. O fundo é escuridão total. As elevações ocorrem através da variação milimétrica do brilho cinza.

```css
:root {
    /* Fundo Absoluto */
    --bg-base: #000000; 
    
    /* Janelas e Painéis */
    --bg-surface: #0a0a0a;
    --bg-panel: #111111;
    
    /* Ações de Alto Contraste */
    --color-primary: #FFFFFF;
    --color-primary-hover: #EBEBEB;
    
    /* Status e Feedback Semântico */
    --color-secondary: #0070F3; /* Azul Vercel / Running */
    --color-success: #17C964;   /* Verde Sucesso */
    --color-warning: #F5A623;   /* Laranja Alerta */
    --color-danger: #F31260;    /* Vermelho Erro */
    
    /* Texto */
    --text-main: #EDEDED;
    --text-muted: #888888;
    
    /* Estrutura "Glass" Fina */
    --border-glass: rgba(255, 255, 255, 0.08);
    --border-active: rgba(255, 255, 255, 0.20);
}
```

---

## 4. Sombras e Efeitos Visuais (Milled Aluminum)

Abandonamos o conceito de "glassmorphism" borrado. A tridimensionalidade aqui é dada pelo **Efeito de Alumínio Usinado**.

*   **`--shadow-inset`:** `inset 0 1px 0 0 rgba(255, 255, 255, 0.06)`
    *   *Uso:* Adicionado aos painéis. Cria um filete de luz dura na borda superior interna do painel, imitando luz rebatendo em uma carcaça de metal.
*   **`--shadow-glow`:** `0 0 0 1px rgba(255, 255, 255, 0.15), 0 12px 32px rgba(0, 0, 0, 0.9)`
    *   *Uso:* Foco e destaque (ex: caminho ótimo do MCTS). Gera uma aura sutil sem parecer mágica brilhante barata.

---

## 5. Micro-Interações e Detalhes

### Curva de Transição Mestra
O sistema não usa `ease` genérico. Toda movimentação na tela é baseada na seguinte curva:
```css
--transition-snappy: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
```
Isso garante o comportamento "buttery smooth" consagrado por ecossistemas modernos (fricção alta no final da animação).

### Grids Estruturais
Zonas de visualização matemática complexa (como o canvas onde a **Árvore MCTS** é desenhada) recebem um padrão sutil de grade técnica em vez de liso sólido:
```css
background-image: 
    linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), 
    linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
```

### Componentes Semânticos: "Pills" CLI
Tags de número, scores e visitas em nós da árvore abandonam os grandes blocos coloridos para adotar o formato **Pill (Pílula)**: `border-radius: 12px`, padding mínimo, fonte minúscula monospace (10px) e fundo translúcido `rgba(255,255,255,0.05)`. 

### Scrollbars Customizadas
A experiência nativa de rolagem do SO deve ser sobrescrita em todo o site. Barras ultra-finas (6px) em tons de cinza/vidro translúcido, mantendo a tela imersiva.

---

## 6. Contratos de Qualidade (Backend MCTS)

O backend do Skill Optimizer MCTS enforca contratos estritos de qualidade (Design by Contract) para garantir a integridade do processo de otimização de instruções:

### 6.1 `IQualityGuard`
Enforca validações pré-commit essenciais:
*   **RN-01 (Linter):** Verifica violações do Ruff.
*   **RN-02 (Tests):** Executa suíte do Pytest e reporta falhas.
*   **RN-03 (Complexity):** Bloqueia funções com complexidade ciclomática $> 15$.
*   **RN-04 (Coverage):** Monitora cobertura de teste em módulos críticos (deve ser $\ge 70\%$).

### 6.2 `IDensityMultiplier`
Garante que o multiplicador de densidade lexical opere estritamente dentro das regras de negócio (RN-05):
*   Deve retornar $1.0$ se o threshold de densidade estiver desabilitado ou se as instruções (original vs. otimizada) tiverem o mesmo tamanho.
*   Invariante: o multiplicador resultante é limitado entre o piso e o teto definidos na configuração.

### 6.3 `IMCTSCancellation`
Força o cancelamento imediato de uma iteração MCTS caso o sinalizador de interrupção seja ativado. RN-06 define três checkpoints obrigatórios para fail-fast:
1.  Antes da seleção do nó.
2.  Imediatamente após a expansão do nó.
3.  Antes do início da simulação.

### 6.4 `IDriftGate`
O portão de controle de drift previne desvios de comportamento nos candidatos avaliados:
*   **RN-07 (Fail-Closed):** Qualquer exceção ou erro ao medir o drift causa a rejeição automática do candidato (segurança absoluta).
*   **RN-08 (Fail-Open):** Se o Golden Set de calibração estiver vazio ou ausente, a compilação segue com advertência explícita no log.
