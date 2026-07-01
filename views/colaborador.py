from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from View.PY.FrmColaborador import Ui_FrmColaborador
from database import Database, UsuarioAutenticado
from utils.exportacao import exportar_excel
from utils.relatorios import formatar_moeda
from utils.widgets import TabelaFiltrada


class ColaboradorWindow(QMainWindow):
    def __init__(self, db: Database, usuario: UsuarioAutenticado) -> None:
        super().__init__()
        self._db = db
        self._usuario = usuario
        self._ui = Ui_FrmColaborador()
        self._ui.setupUi(self)
        self.setWindowTitle(f"QGstock — {usuario.nome}")

        self._construir_interface()
        self._carregar_dados()

    def _construir_interface(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        cabecalho = QHBoxLayout()
        lbl_bem_vindo = QLabel(f"Bem-vindo(a), <b>{self._usuario.nome}</b>")
        lbl_bem_vindo.setStyleSheet("font-size: 16px; font-family: Montserrat;")
        cabecalho.addWidget(lbl_bem_vindo)
        cabecalho.addStretch()

        btn_venda = QPushButton("+ Nova Venda")
        btn_venda.setStyleSheet(
            "background:#9F3FFA; color:white; font-weight:bold; "
            "padding:8px 16px; border-radius:6px; font-family:Montserrat;"
        )
        btn_venda.clicked.connect(self._registrar_venda)
        cabecalho.addWidget(btn_venda)

        btn_exportar = QPushButton("Exportar Minhas Vendas")
        btn_exportar.setStyleSheet("padding:8px 16px; border-radius:6px;")
        btn_exportar.clicked.connect(self._exportar_vendas)
        cabecalho.addWidget(btn_exportar)

        layout.addLayout(cabecalho)

        kpi_layout = QHBoxLayout()
        self._lbl_hoje = QLabel("—")
        self._lbl_mes = QLabel("—")
        self._lbl_num = QLabel("—")

        for rotulo, lbl in [
            ("Vendas Hoje", self._lbl_hoje),
            ("Vendas no Mês", self._lbl_mes),
            ("Total de Vendas", self._lbl_num),
        ]:
            card = QWidget()
            card.setStyleSheet("background:#1e1e2e; border-radius:10px; padding:14px;")
            cl = QVBoxLayout(card)
            lt = QLabel(rotulo)
            lt.setStyleSheet("color:#aaa; font-size:11px; font-family:Montserrat;")
            lbl.setStyleSheet("color:#9F3FFA; font-size:20px; font-weight:bold; font-family:Montserrat;")
            cl.addWidget(lt)
            cl.addWidget(lbl)
            kpi_layout.addWidget(card)

        layout.addLayout(kpi_layout)

        lbl_tabela = QLabel("Minhas Vendas")
        lbl_tabela.setStyleSheet("font-size:14px; font-weight:bold; font-family:Montserrat;")
        layout.addWidget(lbl_tabela)

        self._tabela = TabelaFiltrada()
        layout.addWidget(self._tabela)

    def _carregar_dados(self) -> None:
        self._carregar_kpis()
        self._carregar_vendas()

    def _carregar_kpis(self) -> None:
        try:
            kpis = self._db.kpis_dashboard()
        except Exception:
            return
        self._lbl_hoje.setText(formatar_moeda(kpis["vendas_hoje"]))
        self._lbl_mes.setText(formatar_moeda(kpis["vendas_mes"]))

    def _carregar_vendas(self) -> None:
        try:
            todas = self._db.listar_vendas()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        minhas = [v for v in todas if v[1] == self._usuario.nome]
        self._lbl_num.setText(str(len(minhas)))
        self._tabela.preencher(
            ["ID", "Vendedor", "Cliente CPF", "Produto", "Qtde", "Total", "Data"],
            minhas,
        )

    def _registrar_venda(self) -> None:
        try:
            produtos = self._db.listar_produtos()
            clientes = self._db.listar_clientes()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return

        disponiveis = [p for p in produtos if int(p[4]) > 0]
        if not disponiveis:
            QMessageBox.warning(self, "Sem estoque", "Nenhum produto disponível em estoque.")
            return

        dialog = _DialogNovaVenda(disponiveis, clientes, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        produto_id, cliente_cpf, quantidade, total = dialog.dados()
        try:
            self._db.registrar_venda(self._usuario.nome, cliente_cpf, produto_id, quantidade, total)
            QMessageBox.information(self, "Venda registrada", f"Total: {formatar_moeda(total)}")
            self._carregar_dados()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao registrar venda", str(exc))

    def _exportar_vendas(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar como", f"vendas_{self._usuario.login}.xlsx", "Excel (*.xlsx)"
        )
        if not caminho:
            return
        try:
            todas = self._db.listar_vendas()
            minhas = [v for v in todas if v[1] == self._usuario.nome]
            exportar_excel(
                caminho, "Minhas Vendas",
                ["ID", "Vendedor", "Cliente CPF", "Produto", "Qtde", "Total", "Data"],
                minhas,
            )
            QMessageBox.information(self, "Exportado", f"Salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))


class _DialogNovaVenda(QDialog):
    def __init__(
        self,
        produtos: list[tuple[Any, ...]],
        clientes: list[tuple[Any, ...]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Registrar Nova Venda")
        self.setFixedSize(440, 290)
        self._produtos = produtos

        layout = QFormLayout(self)

        self._combo_prod = QComboBox()
        for p in produtos:
            self._combo_prod.addItem(
                f"[{p[1]}] {p[2]}  —  {formatar_moeda(float(p[3]))}  (estoque: {p[4]})",
                userData=(p[0], float(p[3]), int(p[4])),
            )
        self._combo_prod.currentIndexChanged.connect(self._atualizar_total)
        layout.addRow("Produto:", self._combo_prod)

        self._combo_cliente = QComboBox()
        self._combo_cliente.addItem("— Venda avulsa (sem cadastro) —", userData="")
        for c in clientes:
            self._combo_cliente.addItem(f"{c[2]} — CPF: {c[1]}", userData=c[1])
        layout.addRow("Cliente:", self._combo_cliente)

        self._spin = QSpinBox()
        self._spin.setRange(1, 9999)
        self._spin.valueChanged.connect(self._atualizar_total)
        layout.addRow("Quantidade:", self._spin)

        self._lbl_total = QLabel("R$ 0,00")
        self._lbl_total.setStyleSheet(
            "font-size:18px; font-weight:bold; color:#9F3FFA; font-family:Montserrat;"
        )
        layout.addRow("Total:", self._lbl_total)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("Confirmar Venda")
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addRow(botoes)

        self._atualizar_total()

    def _atualizar_total(self) -> None:
        dado = self._combo_prod.currentData()
        if dado:
            _, valor_unit, _ = dado
            self._lbl_total.setText(formatar_moeda(valor_unit * self._spin.value()))

    def _validar(self) -> None:
        dado = self._combo_prod.currentData()
        if not dado:
            return
        _, _, estoque = dado
        if self._spin.value() > estoque:
            QMessageBox.warning(
                self, "Estoque insuficiente",
                f"Estoque disponível: {estoque} unidade(s).",
            )
            return
        self.accept()

    def dados(self) -> tuple[int, str, int, float]:
        produto_id, valor_unit, _ = self._combo_prod.currentData()
        return (
            produto_id,
            self._combo_cliente.currentData() or "",
            self._spin.value(),
            valor_unit * self._spin.value(),
        )
