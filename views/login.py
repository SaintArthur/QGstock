from __future__ import annotations

from PyQt5.QtWidgets import QMainWindow, QMessageBox

from View.PY.FrmLogin import Ui_login
from database import Database, UsuarioAutenticado


class LoginWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self._ui = Ui_login()
        self._ui.setupUi(self)
        self._ui.pushButton.clicked.connect(self._autenticar)
        self._ui.lineEdit_2.returnPressed.connect(self._autenticar)

    def _autenticar(self) -> None:
        usuario = self._ui.lineEdit.text().strip()
        senha = self._ui.lineEdit_2.text()

        if not usuario or not senha:
            QMessageBox.warning(self, "Atenção", "Preencha usuário e senha.")
            return

        try:
            autenticado = self._db.autenticar(usuario, senha)
        except Exception as exc:
            QMessageBox.critical(self, "Erro de conexão", f"Não foi possível acessar o banco de dados.\n\n{exc}")
            return

        if autenticado is None:
            QMessageBox.warning(self, "Acesso negado", "Usuário ou senha incorretos.")
            self._ui.lineEdit_2.clear()
            self._ui.lineEdit_2.setFocus()
            return

        self._abrir_painel(autenticado)

    def _abrir_painel(self, usuario: UsuarioAutenticado) -> None:
        from views.admin import AdminWindow
        from views.colaborador import ColaboradorWindow

        if usuario.nivel == "admin":
            self._proximo = AdminWindow(self._db, usuario)
        else:
            self._proximo = ColaboradorWindow(self._db, usuario)

        self.close()
        self._proximo.show()
