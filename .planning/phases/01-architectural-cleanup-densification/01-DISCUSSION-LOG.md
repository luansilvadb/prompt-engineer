# Phase 1 Discussion Log

## Reorganização de Módulos (Densification)
- **Options presented:** Criar subpastas lógicas vs Manter na raiz com prefixos/sufixos vs Apenas um utils.py
- **Selected:** Criar subpastas lógicas (ex: `src/drift/`) contendo vários arquivos pequenos, separando bem as responsabilidades
- **Notes:** O usuário optou por estruturar com subpastas, isolando domínios.

## Estratégia de Complexidade Ciclomática
- **Options presented:** Padrões OO vs Funções auxiliares vs Agente decide
- **Selected:** Funções auxiliares simples e funcionais, focando apenas na redução da complexidade de leitura do código
- **Notes:** Foi preferida uma abordagem mais simples (funcional) para evitar overengineering.

## Tratamento de Código Morto
- **Options presented:** Apagar imediatamente vs Mover para archive vs Usar @deprecated
- **Selected:** Apagar tudo imediatamente. O controle de versão (Git) já garante que podemos recuperar se precisarmos. Queremos o código limpo.
- **Notes:** Foco em eliminar dívida técnica limpando código morto de vez sem deixar lixo no repositório.
