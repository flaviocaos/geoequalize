"""
Ponto de entrada da aplicação.

Responsabilidade:
- Inicializar a aplicação Qt
- Configurar logging global
- Carregar configurações
- Exibir a tela de boas-vindas (splash), se habilitada
- Instanciar e exibir a MainWindow
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.splash_screen import SplashScreen
from utils.logging import setup_logging
from utils.config import AppConfig

_SKIP_SPLASH_FLAG = Path.home() / ".satellite_image_corrector" / "skip_splash.flag"


def _should_show_splash() -> bool:
    return not _SKIP_SPLASH_FLAG.exists()


def _persist_skip_splash() -> None:
    _SKIP_SPLASH_FLAG.parent.mkdir(parents=True, exist_ok=True)
    _SKIP_SPLASH_FLAG.write_text("skip", encoding="utf-8")


def main() -> int:
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("GeoEqualize")
    app.setOrganizationName("GeoEqualize")

    config = AppConfig.load_default()

    if _should_show_splash():
        splash = SplashScreen()
        result = splash.exec()
        if splash.should_skip_next_time():
            _persist_skip_splash()
        if result != SplashScreen.Accepted:
            return 0

    window = MainWindow(config=config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())