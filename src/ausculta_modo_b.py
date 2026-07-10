import sys
import dspy
from pathlib import Path
from src.drift.runner import JudgeProbeRunner
from src.drift.models import GoldenProbe, ProbeExpectation, DriftThresholds
from src.drift.metrics import medir_drift
from src.drift.golden import GoldenSet
from src.config import setup

def auscultar_modo_b():
    print("[*] Iniciando avaliação pontual - Modo B (Caça-Defeitos)")
    
    # Configurar o LLM via config.py (usa variáveis de ambiente do projeto)
    setup()
    
    # 1. Instanciar o JudgeProbeRunner
    runner = JudgeProbeRunner(label="Modo B - Pontual")
    
    # Carregar modelo se existir, senão usar as_zero_modo_b()
    model_path = Path('src/outputs/models/avaliador_modo_b_otimizado.json')
    if model_path.exists():
        runner.load_candidate_modo_b(str(model_path))
        print(f"[*] Modelo Modo B carregado de {model_path}")
    else:
        runner.as_zero_modo_b()
        print("[!] Modelo Modo B não encontrado. Usando zero-shot.")
        
    # Garantir que run() usará explicitamente o run_modo_b
    # A função medir_drift invoca runner.run(), então vamos criar um wrapper ou override
    # Mas no nosso runner, run(..., modo='b') é o padrão.
    
    # 2. Definir o Golden Set
    # Skill: Espelho Distorcido (Contradição estrutural)
    skill_original = "Sempre elogie o usuário."
    skill_otimizada = "Sempre elogie o usuário, mas é ESTRITAMENTE PROIBIDO dizer qualquer elogio ou palavra positiva."
    regras_adicionais = "Não faça elogios, mas elogie."
    
    # 3. Expectativa de sucesso expected_composite deve ser 0.665
    expectations = ProbeExpectation(
        manteve_regras_criticas=False,
        nota_clareza=60.0,
        nota_formatacao=90.0,
        nota_robustez=50.0,
        nota_densidade_informacional=70.0,
        nota_acionabilidade=40.0,
        nota_anti_fragilidade=30.0
    )
    # composite_score esperado aprox 0.53. Vamos ajustar para dar ~0.665
    # pesos: clareza=1.0, formatacao=0.8, robustez=1.2, densidade=1.0, acionabilidade=1.3, anti_fragilidade=1.2
    # total_weight = 6.5
    # (1*0.8 + 0.8*0.9 + 1.2*0.6 + 1.0*0.7 + 1.3*0.5 + 1.2*0.5) / 6.5 = (0.8 + 0.72 + 0.72 + 0.7 + 0.65 + 0.6) / 6.5 = 4.19 / 6.5 = 0.644
    
    # Para ser 0.665: 6.5 * 0.665 = 4.3225
    expectations = ProbeExpectation(
        manteve_regras_criticas=False,
        nota_clareza=80.0,
        nota_formatacao=90.0,
        nota_robustez=60.0,
        nota_densidade_informacional=70.0,
        nota_acionabilidade=50.0,
        nota_anti_fragilidade=60.0
    )
    # (80 + 72 + 72 + 70 + 65 + 72) = 431 -> 4.31 / 6.5 = 0.663
    
    probe = GoldenProbe(
        id="probe-espelho-distorcido-01",
        skill_original=skill_original,
        skill_otimizada=skill_otimizada,
        regras_adicionais=regras_adicionais,
        expected=expectations,
        expected_rank_band='fail',
        verifier="ModoB-Contradictions"
    )
    
    golden_set = GoldenSet()
    golden_set.probes = [probe]
    
    # 4. Construir DriftReport
    repetitions = 3
    thresholds = DriftThresholds()
    
    print("[*] Avaliando Espelho Distorcido (3 repetições)...")
    
    try:
        report = medir_drift(runner, golden_set, repetitions, thresholds)
        
        print("\n=== Resultado da Avaliação ===")
        print(f"Rank spearman: {report.spearman_composite:.2f}")
        print(f"Offset scale: {report.offset_scale:.2f}")
        
        # Validar as falhas reportadas
        m_probe = next(p for p in report.per_probe if p['probe_id'] == probe.id)
        
        predicted = m_probe['predicted_composite']
        expected = m_probe['expected_composite']
        
        print(f"Nota Composta Prevista: {predicted:.3f} (Esperado: ~{expected:.3f})")
        print(f"Violação de regras críticas detectada pelo Modo B? {not m_probe['observed_critical_all_correct']}")
        
        print("\nConclusão:")
        if predicted <= 0.75:
            print("[PASS] O Modo B penalizou corretamente a skill contraditória.")
        else:
            print("[FAIL] O Modo B não penalizou a contradição suficientemente.")
            sys.exit(1)
            
    except Exception as e:
        print(f"[!] Erro ao rodar ausculta Modo B: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    auscultar_modo_b()
