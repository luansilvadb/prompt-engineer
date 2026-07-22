import os
import sys
import dspy
import litellm
from pathlib import Path
from dotenv import load_dotenv

def _get_env_path() -> Path:
    """Retorna o caminho para o arquivo .env, suportando execução local e PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Build PyInstaller: o .env deve ficar na mesma pasta do executável
        return Path(sys.executable).parent / '.env'
    else:
        # Dev local: .env fica na raiz do projeto (acima da pasta src)
        return Path(__file__).resolve().parent.parent / '.env'

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
    else:
        kwargs["timeout"] = 90

def setup(model_name=None, model_prefix=None, api_base=None, api_key=None):
    load_dotenv(_get_env_path())
    os.environ['LITELLM_LOG'] = 'DEBUG' # Habilita logs reais de debug do litellm
    litellm.drop_params = True

    # Patch litellm.completion para sanitizar mensagens Unicode/non-ASCII que quebram o SDK da Zai/Zhipu
    if not getattr(litellm, "_sanitization_patched", False):
        from src.utils.unicode_sanitizer import _sanitize_unicode_for_api
        _orig_completion = litellm.completion

        def _deep_sanitize(obj):
            if isinstance(obj, str):
                return _sanitize_unicode_for_api(obj)
            elif isinstance(obj, list):
                return [_deep_sanitize(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: _deep_sanitize(v) for k, v in obj.items()}
            return obj

        def _patched_completion(*args, **kwargs):
            _safe_keys = {"api_key", "api_base"}
            sanitized_kwargs = {}
            for k, v in kwargs.items():
                if k in _safe_keys:
                    sanitized_kwargs[k] = v
                else:
                    sanitized_kwargs[k] = _deep_sanitize(v)
            
            sanitized_args = tuple(_deep_sanitize(a) for a in args)
            return _orig_completion(*sanitized_args, **sanitized_kwargs)

        litellm.completion = _patched_completion
        litellm._sanitization_patched = True

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
    # Com retries, 1 chamada LLM travada custa mais caro, porém 1 retry (default) ajuda com
    # rate limits ou erros transientes sem estourar o budget do MCTS excessivamente.
    dspy_num_retries = int(os.environ.get("DSPY_NUM_RETRIES", "1"))
    lm = dspy.LM(**kwargs, num_retries=dspy_num_retries)
    try:
        dspy.configure(lm=lm)
    except RuntimeError:
        pass
    return lm


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
    load_dotenv(_get_env_path())
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

