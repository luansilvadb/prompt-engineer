"""
Teste de sanidade do timeout do LiteLLM via dspy.LM.

Faz uma chamada real ao modelo configurado no .env e mede se
o timeout=90 configurado em src/config.py é respeitado.

Segurança: um watchdog externo (threading.Timer) mata o processo
após 150s se o LiteLLM ignorar o timeout (bug documentado em
versões < 1.44 do LiteLLM).

Uso:
    python scripts/test_timeout_sanity.py
"""

import os
import sys
import time
import threading

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WATCHDOG_SECONDS = 150  # teto máximo — se chegar aqui, o timeout foi ignorado


def watchdog():
    """Mata o processo se o LiteLLM ignorar o timeout e travar."""
    print(
        f"\n[WATCHDOG] {WATCHDOG_SECONDS}s atingidos — "
        f"o LiteLLM IGNOROU o timeout configurado."
    )
    print("[WATCHDOG] Encerrando processo forçadamente.")
    os._exit(1)


def main():
    from src.config import setup

    print("=" * 60)
    print("Teste de Sanidade — Timeout do LiteLLM via dspy.LM")
    print("=" * 60)

    # 1. Verificar versão do LiteLLM
    import litellm
    print(f"\n[1] Versão do LiteLLM: {litellm.__version__}")

    # 2. Configurar LM com timeout
    print("\n[2] Configurando dspy.LM com timeout=90 (via src/config.py)...")
    lm = setup()
    actual_timeout = lm.kwargs.get("timeout", "NÃO ENCONTRADO")
    print(f"    timeout em lm.kwargs: {actual_timeout}")

    if actual_timeout != 90:
        print(f"    [!] ALERTA: timeout esperado=90, encontrado={actual_timeout}")
        print("    A correção em src/config.py pode não ter sido aplicada.")
        return

    # 3. Iniciar watchdog
    print(f"\n[3] Iniciando watchdog ({WATCHDOG_SECONDS}s)...")
    timer = threading.Timer(WATCHDOG_SECONDS, watchdog)
    timer.daemon = True
    timer.start()

    # 4. Fazer chamada real e medir tempo
    print("\n[4] Fazendo chamada ao modelo (pode demorar até ~90s)...")
    print("    (se o timeout estiver funcionando, deve lançar exceção em ~90s)")
    start = time.monotonic()

    try:
        # Prompt que força o modelo a gerar muitos tokens,
        # garantindo que a chamada dure mais que o timeout de 90s
        result = lm(
            "Write a detailed 5000-word essay about the history of artificial "
            "intelligence from 1950 to 2024. Include specific dates, researchers, "
            "breakthroughs, and technical details. Structure it as a formal "
            "academic paper with abstract, introduction, 10 sections, and "
            "conclusion. Each section must be at least 400 words."
        )
        elapsed = time.monotonic() - start
        print(f"\n[!] Chamada completou em {elapsed:.1f}s — timeout NÃO foi acionado.")
        print(f"    (esperado: exceção de timeout em ~90s)")
        print(f"    O LiteLLM pode estar ignorando o timeout, ou o modelo ")
        print(f"    respondeu rápido demais para disparar o timeout de 90s.")
        print(f"    Tente novamente com um prompt mais pesado ou verifique ")
        print(f"    se o modelo está realmente demorando >90s por chamada.")

    except Exception as e:
        elapsed = time.monotonic() - start
        error_msg = str(e)

        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            print(f"\n[✓] SUCESSO: Timeout acionado em {elapsed:.1f}s")
            print(f"    Exceção: {type(e).__name__}: {error_msg[:200]}")
        elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
            print(f"\n[~] Rate limit atingido em {elapsed:.1f}s (esperado ~90s)")
            print(f"    O timeout não pôde ser testado porque a API rejeitou a")
            print(f"    chamada antes. Tente novamente mais tarde.")
        elif "connection" in error_msg.lower() or "refused" in error_msg.lower():
            print(f"\n[~] Erro de conexão em {elapsed:.1f}s")
            print(f"    Verifique se a API está acessível e as credenciais estão")
            print(f"    corretas no .env")
        else:
            print(f"\n[?] Exceção inesperada em {elapsed:.1f}s")
            print(f"    Tipo: {type(e).__name__}")
            print(f"    Mensagem: {error_msg[:300]}")

    finally:
        timer.cancel()
        print(f"\n[5] Watchdog cancelado. Tempo total: {elapsed:.1f}s")
        print("=" * 60)


if __name__ == "__main__":
    main()