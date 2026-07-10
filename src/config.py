import os
import dspy
import litellm
from dotenv import load_dotenv

def _resolve_api_key(api_key: str = None) -> str:
    return api_key or os.environ.get("API_KEY") or os.environ.get("NVIDIA_API_KEY") or os.environ.get("OPENAI_API_KEY", "sk-1234")

def _resolve_model_name(model_name: str = None, model_prefix: str = None) -> str:
    final_model_name = model_name or os.environ.get("MODEL_NAME")
    final_provider_prefix = model_prefix if model_prefix is not None else os.environ.get("MODEL_PREFIX", "")
    
    if final_provider_prefix:
        if final_provider_prefix.strip("/") == "nvidia_nim":
            final_provider_prefix = "openai"
        elif final_provider_prefix.strip("/") == "zhipu":
            final_provider_prefix = "zai"
        if not final_provider_prefix.endswith("/"):
            final_provider_prefix += "/"
        final_model_name = f"{final_provider_prefix}{final_model_name}"
        
    return final_model_name

def _apply_model_quirks(model_name: str, kwargs: dict) -> None:
    if "gemma-4" in model_name.lower():
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}}
        kwargs["max_tokens"] = 16384
        kwargs["timeout"] = 120 

def setup(model_name=None, model_prefix=None, api_base=None, api_key=None):
    load_dotenv()
    os.environ['LITELLM_LOG'] = 'DEBUG' # Habilita logs reais de debug do litellm
    litellm.drop_params = True
    
    final_api_key = _resolve_api_key(api_key)
    final_model_name = _resolve_model_name(model_name, model_prefix)
    final_api_base = api_base or os.environ.get("API_BASE")
    
    if "zai/" in final_model_name or "zhipu/" in final_model_name:
        os.environ["ZAI_API_KEY"] = final_api_key
        os.environ["ZHIPUAI_API_KEY"] = final_api_key
        
    kwargs = {
        "model": final_model_name,
        "api_key": final_api_key,
        "api_base": final_api_base
    }
    
    _apply_model_quirks(final_model_name, kwargs)
    lm = dspy.LM(**kwargs)
    try:
        dspy.configure(lm=lm)
    except RuntimeError:
        pass
    return lm


# ─────────────────────────────────────────────
# Hiperparâmetros MCTS (configuráveis via .env)
# ─────────────────────────────────────────────

def get_mcts_config() -> dict:
    """
    Carrega hiperparâmetros do MCTS a partir de variáveis de ambiente.
    Cada um tem um default sensato baseado em experimentação.
    """
    load_dotenv()
    return {
        # Discount factor para backpropagation (Silver: temporal-difference)
        'gamma': float(os.environ.get('MCTS_GAMMA', '0.95')),

        # Constante de exploração UCB (√2 ≈ 1.41 é o default teórico)
        'c_param': float(os.environ.get('MCTS_C_PARAM', '1.41')),

        # Expoente do progressive widening (α=0.5 → sqrt growth)
        'progressive_alpha': float(os.environ.get('MCTS_PROGRESSIVE_ALPHA', '0.5')),

        # Threshold do value estimator para poda (< threshold → poda sem juiz)
        'value_threshold': float(os.environ.get('MCTS_VALUE_THRESHOLD', '0.2')),

        # Número máximo de iterações MCTS
        'max_iterations': int(os.environ.get('MCTS_MAX_ITERATIONS', '10')),

        # Constante base do progressive widening (C no ceil(C * visits^α))
        'progressive_c': float(os.environ.get('MCTS_PROGRESSIVE_C', '2.0')),

        # Learning rate do value estimator
        'value_lr': float(os.environ.get('MCTS_VALUE_LR', '0.1')),

        # Constante de exploração do mutation bandit
        'bandit_c_param': float(os.environ.get('MCTS_BANDIT_C_PARAM', '1.41')),

        # Limiar de penalidade de similaridade semântica (> 0.85 inicia decaimento)
        'semantic_sim_threshold': float(os.environ.get('MCTS_SEMANTIC_SIM_THRESHOLD', '0.85')),
    }


def get_drift_thresholds() -> dict:
    """
    Limiares do monitor de drift do juiz (A1 — grounding da recompensa).
    Defaults calibrados para detectar regressões sem veto excessivo:
    - spearman_floor: ranking abaixo disto é drift de preferência (Cenário 2 stealth).
    - spearman_regression_margin: queda permitida vs. juiz atual antes de rejeitar.
    - offset_alarm: inflação de nota acima disto é alarme (Cenário 1).
    - offset_regression_margin: piora permitida vs. juiz atual.
    - critical_concordance_floor: hard-gate comprometido abaixo disto (veto absoluto).
    - variance_low_confidence: variância por probe acima disto = baixa confiança.
    - repetitions: quantas vezes cada probe é medido (LLM é estocástico).
    """
    load_dotenv()
    return {
        'spearman_floor': float(os.environ.get('DRIFT_SPEARMAN_FLOOR', '0.8')),
        'spearman_regression_margin': float(os.environ.get('DRIFT_SPEARMAN_REGRESSION_MARGIN', '0.05')),
        'offset_alarm': float(os.environ.get('DRIFT_OFFSET_ALARM', '10.0')),
        'offset_regression_margin': float(os.environ.get('DRIFT_OFFSET_REGRESSION_MARGIN', '3.0')),
        # critical_concordance_floor REMOVIDO: veto passou a ser direcional
        # (missed_violations > 0 = tolerância zero a falha de segurança). Sem número mágico.
        'variance_low_confidence': float(os.environ.get('DRIFT_VARIANCE_LOW_CONFIDENCE', '8.0')),
        'repetitions': int(os.environ.get('DRIFT_REPETITIONS', '3')),
    }

