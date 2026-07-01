from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

from config import load_config
from database import Database
from views.login import LoginWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("QGstock")
    app.setOrganizationName("QG")

    cfg = load_config()

    try:
        db = Database(cfg)
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Falha na conexão",
            f"Não foi possível conectar ao banco de dados.\n\n"
            f"Verifique as configurações em variáveis de ambiente ou no arquivo .env.\n\n"
            f"Detalhe: {exc}",
        )
        sys.exit(1)

    janela = LoginWindow(db)
    janela.show()

    exit_code = app.exec_()
    db.fechar()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
