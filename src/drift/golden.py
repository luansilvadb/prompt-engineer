import json
import os
import sys
from pathlib import Path
from typing import List, Optional

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
                    print(f"[+] Golden set padrão restaurado localmente com sucesso em {path}")
                except Exception as e:
                    path = frozen_path
                    print(f"[!] Falha ao criar golden set localmente: {e}. Usando do executável diretamente.")
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
            ))
        return probes

    def _load(self):
        path = self._store_path()
        if not path.exists():
            path = self._restore_frozen_golden(path)
        if not path.exists():
            print(f"[!] Golden set ausente em {path}. Portão operará em fail-open.")
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.version = data.get('version', '')
            self.curated_at = data.get('curated_at', '')
            self.probes = self._parse_golden_json(data)
            print(f"[*] Golden set v{self.version} carregado: {len(self.probes)} probes.")
        except Exception as e:
            print(f"[!] Erro ao carregar golden set ({e}). Operando sem âncora.")
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
                }
                for p in self.probes
            ],
        }
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
