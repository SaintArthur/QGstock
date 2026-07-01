from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMessageBox


def _carregar_env() -> None:
    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass


def main() -> None:
    _carregar_env()

    from config import load_config
    from database import Database
    from views.login import LoginWindow

    app = QApplication(sys.argv)
    app.setApplicationName("QGstock")
    app.setOrganizationName("QG")

    cfg = load_config()

    try:
        db = Database(cfg)
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Falha na conexão com o banco de dados",
            f"Não foi possível conectar ao banco de dados.\n\n"
            f"Host: {cfg.host}:{cfg.port}\n"
            f"Banco: {cfg.database}\n\n"
            f"Verifique as configurações no arquivo .env ou nas variáveis de ambiente.\n\n"
            f"Detalhe técnico: {exc}",
        )
        sys.exit(1)

    janela = LoginWindow(db)
    janela.show()

    exit_code = app.exec_()
    db.fechar()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
