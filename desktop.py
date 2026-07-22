"""Skill Optimizer — Desktop Application (PyWebView + FastAPI).

Inicia um servidor FastAPI em thread separada e o exibe em uma janela nativa.
Inclui tratamento de erros robusto, retry de porta e graceful shutdown.
"""

import socket
import sys
import threading
import time
import traceback

import uvicorn

from src.api import app

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_PORT_RETRIES = 5
PORT_RETRY_DELAY = 0.5  # segundos entre tentativas
SERVER_STARTUP_TIMEOUT = 15.0  # timeout para o servidor ficar pronto
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
APP_TITLE = "Skill Optimizer"


def get_free_port(preferred: int | None = None) -> int:
    """Encontra uma porta TCP livre, com tentativa opcional de porta preferida."""
    if preferred is not None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", preferred))
            s.close()
            return preferred
        except OSError:
            pass  # porta preferida ocupada, tenta automática

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = SERVER_STARTUP_TIMEOUT) -> bool:
    """Aguarda ativamente até que o servidor esteja aceitando conexões na porta."""
    start_time = time.time()
    while True:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            if time.time() - start_time > timeout:
                return False
            time.sleep(0.1)


class APIServer(threading.Thread):
    """Servidor FastAPI executando em thread separada."""

    def __init__(self, port: int, log_level: str = "warning"):
        super().__init__(daemon=True)
        self.port = port
        self._startup_error: Exception | None = None
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level=log_level,
            # Não usar reload em produção/desktop
            reload=False,
        )
        self.server = uvicorn.Server(config=config)

    def run(self) -> None:
        try:
            self.server.run()
        except Exception as e:
            self._startup_error = e
            # Log para debug — pode ser recuperado pelo processo pai
            traceback.print_exc()

    def stop(self) -> None:
        """Solicita shutdown graceful do servidor."""
        self.server.should_exit = True

    @property
    def startup_error(self) -> Exception | None:
        return self._startup_error


def _show_error_dialog(title: str, message: str) -> None:
    """Exibe diálogo de erro nativo (se PyWebView disponível) ou fallback para console."""
    try:
        import importlib.util

        if importlib.util.find_spec("webview") is None:
            raise ImportError("webview not available")
    except ImportError:
        pass

    # Fallback: imprime no console
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"  ERRO: {title}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)
    print(message, file=sys.stderr)
    print(f"{'=' * 60}\n", file=sys.stderr)

    # Tenta diálogo nativo do Windows como último recurso
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        pass


def main() -> None:
    """Entry point principal do aplicativo desktop."""
    # ── Resolver porta com retry ──────────────────────────────────────────
    port: int | None = None
    last_error: Exception | None = None

    for attempt in range(1, MAX_PORT_RETRIES + 1):
        try:
            port = get_free_port(preferred=8765 if attempt == 1 else None)
            break
        except OSError as e:
            last_error = e
            if attempt < MAX_PORT_RETRIES:
                time.sleep(PORT_RETRY_DELAY * attempt)

    if port is None:
        _show_error_dialog(
            "Erro de Rede",
            f"Não foi possível encontrar uma porta livre após {MAX_PORT_RETRIES} tentativas.\n\n"
            f"Erro: {last_error}\n\n"
            "Verifique se outro processo está bloqueando as portas ou reinicie o computador.",
        )
        sys.exit(1)

    # ── Iniciar servidor ──────────────────────────────────────────────────
    api_thread = APIServer(port)
    api_thread.start()

    if not wait_for_port(port, timeout=SERVER_STARTUP_TIMEOUT):
        # Verifica se o servidor reportou erro
        if api_thread.startup_error:
            _show_error_dialog(
                "Falha no Servidor",
                f"O servidor FastAPI não iniciou corretamente.\n\n"
                f"Erro: {api_thread.startup_error}\n\n"
                "Verifique as configurações do modelo no arquivo .env e tente novamente.",
            )
        else:
            _show_error_dialog(
                "Timeout de Inicialização",
                f"O servidor não respondeu em {SERVER_STARTUP_TIMEOUT:.0f} segundos na porta {port}.\n\n"
                "Possíveis causas:\n"
                "  - Firewall bloqueando a porta\n"
                "  - Antivírus interferindo\n"
                "  - Outro processo usando a mesma porta",
            )
        api_thread.stop()
        sys.exit(1)

    if api_thread.startup_error:
        _show_error_dialog(
            "Erro no Servidor",
            f"O servidor encontrou um erro durante a execução:\n\n{api_thread.startup_error}",
        )
        api_thread.stop()
        sys.exit(1)

    # ── Criar janela ──────────────────────────────────────────────────────
    try:
        import webview
    except ImportError as e:
        _show_error_dialog(
            "Dependência Ausente",
            f"PyWebView não está instalado.\n\n"
            f"Execute: pip install pywebview>=4.4.0\n\n"
            f"Erro: {e}",
        )
        api_thread.stop()
        sys.exit(1)

    url = f"http://127.0.0.1:{port}"

    try:
        window = webview.create_window(
            APP_TITLE,
            url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            maximized=True,
            # Permite copiar texto da janela (útil para debug)
            text_select=True,
        )
    except Exception as e:
        _show_error_dialog(
            "Erro ao Criar Janela",
            f"Não foi possível criar a janela do aplicativo.\n\nErro: {e}",
        )
        api_thread.stop()
        sys.exit(1)

    # ── Graceful shutdown ─────────────────────────────────────────────────
    window.events.closed += lambda: api_thread.stop()

    # ── Iniciar loop de eventos ───────────────────────────────────────────
    try:
        webview.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        _show_error_dialog(
            "Erro em Tempo de Execução",
            f"O aplicativo encontrou um erro inesperado:\n\n{e}",
        )
    finally:
        api_thread.stop()
        # Pequena pausa para o servidor encerrar gracefulmente
        time.sleep(0.5)


if __name__ == "__main__":
    main()
