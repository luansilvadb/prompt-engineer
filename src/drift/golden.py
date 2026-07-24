import json
import os
import sys
from pathlib import Path
from typing import List

from loguru import logger
from src.drift.models import ProbeExpectation, GoldenProbe

GOLDEN_DIR = Path('src/outputs/golden')

class GoldenSet:
    """
    Coleção congelada de probes. BR2: nunca entra no trainset do teleprompter.
    BR3: read-only em runtime; save() só em curadoria offline.
    """

    def __init__(self):
        self.version: str = ''
        self.curated_at: str = ''
        self.probes: List[GoldenProbe] = []
        self._load()

    def _store_path(self) -> Path:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        return GOLDEN_DIR / 'golden_set.json'

    def _restore_frozen_golden(self, path: Path) -> Path:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            frozen_path = Path(sys._MEIPASS) / 'src' / 'outputs' / 'golden' / 'golden_set.json'
            if frozen_path.exists():
                try:
                    import shutil
                    shutil.copy2(frozen_path, path)
                    logger.info("[+] Golden set padão restaurado localmente com sucesso em {}", path)
                except Exception as e:
                    path = frozen_path
                    logger.warning("[!] Falha ao criar golden set localmente: {}. Usando do executável diretamente.", e)
        return path

    def _parse_golden_json(self, data: dict) -> List[GoldenProbe]:
        probes = []
        for pd in data.get('probes', []):
            exp = ProbeExpectation(**pd['expected'])
            probes.append(GoldenProbe(
                id=pd['id'],
                skill_original=pd['skill_original'],
                skill_otimizada=pd['skill_otimizada'],
                regras_adicionais=pd.get('regras_adicionais', ''),
                expected=exp,
                expected_rank_band=pd['expected_rank_band'],
                verifier=pd.get('verifier', ''),
                category=pd.get('category', 'general'),
                generator_model=pd.get('generator_model', ''),
                verification_hints=pd.get('verification_hints', []),
            ))
        return probes

    def _validate_circular_contamination(self):
        """
        A2 — Validação de contaminação circular: emite warning se probes
        gerados por LLM (NEIGHBOR, GPTOUT) não declaram modelo diferente
        do juiz atual. Probes gerados pelo mesmo modelo que avalia geram
        viés de autoavaliação (DESIGN.md §7.6).

        Consulta MODEL_NAME do ambiente (config.py usa os.environ, não um objeto settings).
        BUG-6 fix: usa loguru logger em vez de print() para que os logs
        cheguem ao sistema SSE e ao arquivo de log do job.
        """
        judge_model = os.environ.get('MODEL_NAME', 'unknown')

        for p in self.probes:
            gen = p.generator_model
            if not gen:
                continue
            # Human-curated probes são seguros — sem risco de contaminação
            if gen.startswith('human-curated'):
                continue
            # LLM-generated probe — verificar separação de modelos
            if judge_model and gen == judge_model:
                logger.warning(
                    "[!] A2 — CONTAMINAÇÃO CIRCULAR: probe {} foi gerado por {}, "
                    "mesmo modelo do juiz atual ({}). Métricas de drift podem ser "
                    "superestimadas (viés de autoavaliação). Considere regenerar com outro modelo.",
                    p.id, gen, judge_model,
                )
            else:
                logger.info("[*] A2 — OK: probe {} usa generator_model={}, juiz atual={}.", p.id, gen, judge_model)

    def _load(self):
        path = self._store_path()
        if not path.exists():
            path = self._restore_frozen_golden(path)
        if not path.exists():
            logger.warning("[!] Golden set ausente em {}. Portão operará em fail-open.", path)
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = f.read()
            data = json.loads(raw)
            self.version = data.get('version', '')
            self.curated_at = data.get('curated_at', '')
            self.probes = self._parse_golden_json(data)
            logger.info("[*] Golden set v{} carregado: {} probes.", self.version, len(self.probes))
            self._validate_circular_contamination()
        except json.JSONDecodeError as e:
            logger.warning(
                "[!] Golden set com JSON inválido em {}: {} (linha {}, coluna {}). "
                "Verifique se o arquivo usa aspas duplas e não contém caracteres inválidos. "
                "Operando sem âncora.",
                path, e.msg, e.lineno, e.colno,
            )
            self.probes = []
        except Exception as e:
            logger.error("[!] Erro ao carregar golden set em {}: {}. Operando sem âncora.", path, e)
            self.probes = []

    def is_empty(self) -> bool:
        return len(self.probes) == 0

    def save(self, version: str, curated_at: str):
        """Persistência atômica — USAR APENAS EM CURADORIA OFFLINE (BR3)."""
        path = self._store_path()
        temp_path = path.with_suffix('.tmp')
        data = {
            'version': version,
            'curated_at': curated_at,
            'probes': [
                {
                    'id': p.id,
                    'skill_original': p.skill_original,
                    'skill_otimizada': p.skill_otimizada,
                    'regras_adicionais': p.regras_adicionais,
                    'expected': {
                        'manteve_regras_criticas': p.expected.manteve_regras_criticas,
                        'nota_clareza': p.expected.nota_clareza,
                        'nota_formatacao': p.expected.nota_formatacao,
                        'nota_robustez': p.expected.nota_robustez,
                        'nota_densidade_informacional': p.expected.nota_densidade_informacional,
                        'nota_acionabilidade': p.expected.nota_acionabilidade,
                        'nota_anti_fragilidade': p.expected.nota_anti_fragilidade,
                    },
                    'expected_rank_band': p.expected_rank_band,
                    'verifier': p.verifier,
                    'category': p.category,
                    'generator_model': p.generator_model,
                    'verification_hints': p.verification_hints,
                }
                for p in self.probes
            ],
        }
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
