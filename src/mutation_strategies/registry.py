"""
Mutation Strategies — Registry (Dynamic Strategy Store)

Catálogo de estratégias de mutação que o MCTS pode aplicar, com suporte
a descoberta autônoma de novas estratégias (Tabula Rasa).

Responsabilidade única deste módulo: persistência e acesso ao catálogo de
estratégias. A seleção por bandit vive em `bandit.py`; a fachada pública
(`get_strategy_description`) vive em `api.py`.

Extraído de `src/mutations.py` (Phase 1 densification, ARC-03/D-01). O
caminho legado `src.mutations` continua resolvendo via re-export shim
(plano 01-05), então consumidores como `optimizer.py` e
`test_discoverer.py` não precisam mudar.
"""

import json
import os
from pathlib import Path
from typing import Dict, List

STRATEGIES_DIR = Path('src/outputs/strategies')


class StrategyRegistry:
    def __init__(self):
        self.job_id = None
        self.strategies: Dict[str, Dict[str, str]] = {}
        self._load()
        self._seed_hardcoded_strategies()

    def set_job_id(self, job_id: str):
        """Define o escopo da sessão (job) e recarrega as estratégias locais."""
        self.job_id = job_id
        self._load()
        self._seed_hardcoded_strategies()

    def _store_path(self) -> Path:
        STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
        if self.job_id:
            return STRATEGIES_DIR / f'discovered_strategies_{self.job_id}.json'
        return STRATEGIES_DIR / 'discovered_strategies.json'

    def _load(self):
        self.strategies = {}
        path = self._store_path()
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                seen_names: set[str] = set()
                deduplicated: dict[str, dict[str, str]] = {}
                for key, entry in raw.items():
                    name = entry.get('name', '')
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    deduplicated[key] = entry
                self.strategies = deduplicated
                if len(deduplicated) < len(raw):
                    self.save()
            except Exception:
                pass

    def save(self):
        path = self._store_path()
        temp_path = path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.strategies, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except Exception:
            pass

    def add_strategy(self, key: str, name: str, prompt: str) -> str | None:
        for existing_key, s in self.strategies.items():
            if s['name'] == name:
                return existing_key
        self.strategies[key] = {'name': name, 'prompt': prompt}
        self.save()
        return None

    def get_prompt(self, key: str) -> str:
        if key == '__DISCOVER__':
            return ''
        if key.startswith('composite:') and key not in self.strategies:
            parts_key = key[len('composite:'):]
            constituent_keys = parts_key.split('+')
            return self.build_composite_prompt(constituent_keys)[2]
        return self.strategies.get(key, {}).get('prompt', '')

    def get_name(self, key: str) -> str:
        if key == '__DISCOVER__':
            return 'Descoberta Autônoma de Reflexo (Tabula Rasa)'
        if key.startswith('composite:') and key not in self.strategies:
            parts = key[len('composite:'):].split('+')
            names = [self.get_name(p) for p in parts]
            return "Composição: " + " + ".join(names)
        return self.strategies.get(key, {}).get('name', key)

    def build_composite_prompt(self, strategy_keys: list[str]) -> tuple[str, str, str]:
        parts: list[str] = []
        for k in strategy_keys:
            p = self.strategies.get(k, {}).get('prompt', '')
            if p:
                parts.append(p)
        composite_key = self.get_composite_key(strategy_keys)
        composite_name = self.composite_name(strategy_keys)
        composite_prompt = "\n\n--- PRÓXIMA ESTRATÉGIA ---\n\n".join(parts)
        return (composite_key, composite_name, composite_prompt)

    def composite_name(self, strategy_keys: list[str]) -> str:
        names = [self.get_name(k) for k in strategy_keys]
        return "Composição: " + " + ".join(names)

    @staticmethod
    def get_composite_key(strategy_keys: list[str]) -> str:
        return "composite:" + "+".join(strategy_keys)

    def _seed_hardcoded_strategies(self):
        COGNITIVO_KEY = 'mutador_cognitivo'
        if COGNITIVO_KEY not in self.strategies:
            self.add_strategy(
                key=COGNITIVO_KEY,
                name='Mutador Cognitivo',
                prompt=(
                    "Aplique derivação lógica estruturada obrigatória. "
                    "Antes de reescrever, derive explicitamente: "
                    "(1) Premissas — o que o feedback revela sobre a instrução atual; "
                    "(2) Deduções — implicações lógicas sobre o que precisa mudar; "
                    "(3) Conclusão — a regra arquitetural que a nova instrução deve implementar. "
                    "A nova instrução DEVE conter as seções ## Raciocínio, ## Regras, ## Conclusão."
                )
            )

        COMPRESSAO_KEY = 'compressao_formalizacao'
        if COMPRESSAO_KEY not in self.strategies:
            self.add_strategy(
                key=COMPRESSAO_KEY,
                name='Compressão e Formalização',
                prompt=(
                    "Comprima o prompt removendo redundâncias, padronizando a estrutura "
                    "(títulos, listas, negrito) e mantendo toda a capacidade funcional sem perda semântica. "
                    "Reduza repetições verbosas, consolide regras duplicadas, normalize a formatação "
                    "para markdown e preserve cada regra comportamental e restrição."
                )
            )

        EXEMPLOS_KEY = 'enriquecimento_exemplos'
        if EXEMPLOS_KEY not in self.strategies:
            self.add_strategy(
                key=EXEMPLOS_KEY,
                name='Enriquecimento com Exemplos',
                prompt=(
                    "Enriqueça o prompt com exemplos práticos e contraexemplos que contextualizem "
                    "casos de uso e limitações do sistema. Adicione exemplos concretos para cada regra, "
                    "forneça contraexemplos (o que NÃO fazer) e NÃO remova nenhuma regra existente."
                )
            )

        FALHA_KEY = 'reorganizacao_falha'
        if FALHA_KEY not in self.strategies:
            self.add_strategy(
                key=FALHA_KEY,
                name='Reorganização por Prioridade de Falha',
                prompt=(
                    "Reorganize o conteúdo do prompt com base na prioridade de falha — coloque "
                    "regras e diretrizes que resolvem os erros mais frequentes no início do texto. "
                    "Dados de erro serão injetados junto com este prompt. Reordene as seções de modo "
                    "que as regras mais críticas e mais frequentemente falhantes venham primeiro."
                )
            )

        BLOCOS_KEY = 'preservacao_blocos'
        if BLOCOS_KEY not in self.strategies:
            self.add_strategy(
                key=BLOCOS_KEY,
                name='Preservação Seletiva de Blocos',
                prompt=(
                    "Preserve blocos de raciocínio que demonstraram eficácia na resolução de casos "
                    "ambíguos. Mantenha intactos certos blocos durante a reescrita. Blocos eficazes "
                    "serão fornecidos junto com este prompt."
                )
            )

        TOM_KEY = 'variacao_tom'
        if TOM_KEY not in self.strategies:
            self.add_strategy(
                key=TOM_KEY,
                name='Variação de Tom e Registro',
                prompt=(
                    "Ajuste o tom e o registro linguístico do prompt sem alterar seu conteúdo semântico. "
                    "Varie a formalidade (técnico vs. coloquial), a voz (ativa vs. passiva), e o nível "
                    "de detalhe narrativo. Reformule as regras preservando exatamente o mesmo conjunto "
                    "de instruções comportamentais, apenas mudando como são expressas. "
                    "NÃO remova nenhuma regra; apenas reescreva o estilo."
                )
            )

        FORMATO_KEY = 'reestruturacao_formato'
        if FORMATO_KEY not in self.strategies:
            self.add_strategy(
                key=FORMATO_KEY,
                name='Reestruturação de Formato',
                prompt=(
                    "Reestruture o formato do prompt sem alterar seu significado. Converta listas em "
                    "prosa ou vice-versa, modularize em subseções com cabeçalhos, reorganize os blocos "
                    "em unidades semanticamente coesas, e alterne entre estilos de apresentação "
                    "(tabelas, bullets, parágrafos). Preserve todas as regras e restrições, apenas "
                    "mude a estrutura de apresentação do texto."
                )
            )

        CONTEXTO_KEY = 'especificacao_contexto'
        if CONTEXTO_KEY not in self.strategies:
            self.add_strategy(
                key=CONTEXTO_KEY,
                name='Especificação de Contexto de Uso',
                prompt=(
                    "Enriqueça o prompt explicitando o contexto de uso: pré-condições que devem ser "
                    "verdadeiras antes de aplicar a skill, restrições de domínio (quando a skill NÃO "
                    "se aplica), exceções e casos de borda que requerem tratamento especial. Adicione "
                    "uma seção de contexto de uso sem remover regras existentes. Especifique quando e "
                    "onde a skill deve ser invocada e sob quais hipóteses."
                )
            )

    def get_all_keys(self) -> List[str]:
        return list(self.strategies.keys())


# Instância global do registry
registry = StrategyRegistry()
