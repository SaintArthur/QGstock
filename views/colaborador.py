from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from View.PY.FrmColaborador import Ui_FrmColaborador
from database import Database, UsuarioAutenticado
from utils.exportacao import exportar_excel
from utils.relatorios import formatar_moeda
from views.admin import _item_readonly, _preencher_tabela


class ColaboradorWindow(QMainWindow):
    def __init__(self, db: Database, usuario: UsuarioAutenticado) -> None:
        super().__init__()
        self._db = db
        self._usuario = usuario
        self._ui = Ui_FrmColaborador()
        self._ui.setupUi(self)

        self._construir_interface()
        self._carregar_dados()

    def _construir_interface(self) -> None:
        central = self.centralWidget()
        if central is None:
            central = QWidget()
            self.setCentralWidget(central)

        layout_principal = QVBoxLayout(central)

        cabecalho = QHBoxLayout()
        lbl_bem_vindo = QLabel(f"Bem-vindo(a), {self._usuario.nome}")
        lbl_bem_vindo.setStyleSheet("font-size: 16px; font-weight: bold; font-family: Montserrat;")
        cabecalho.addWidget(lbl_bem_vindo)
        cabecalho.addStretch()

        btn_nova_venda = QPushButton("Nova Venda")
        btn_nova_venda.setStyleSheet(
            "background-color: #9F3FFA; color: white; font-weight: bold; padding: 8px 16px;"
        )
        btn_nova_venda.clicked.connect(self._registrar_venda)
        cabecalho.addWidget(btn_nova_venda)

        btn_exportar = QPushButton("Exportar Minhas Vendas")
        btn_exportar.clicked.connect(self._exportar_minhas_vendas)
        cabecalho.addWidget(btn_exportar)

        layout_principal.addLayout(cabecalho)

        self._kpi_widget = QWidget()
        kpi_layout = QHBoxLayout(self._kpi_widget)
        self._lbl_vendas_hoje = QLabel("—")
        self._lbl_vendas_mes = QLabel("—")
        self._lbl_num_vendas = QLabel("—")

        for titulo, lbl in [
            ("Vendas Hoje", self._lbl_vendas_hoje),
            ("Vendas no Mês", self._lbl_vendas_mes),
            ("Nº de Vendas", self._lbl_num_vendas),
        ]:
            card = QWidget()
            card.setStyleSheet("background: #1e1e2e; border-radius: 8px; padding: 8px;")
            cl = QVBoxLayout(card)
            lt = QLabel(titulo)
            lt.setStyleSheet("color: #aaa; font-size: 11px;")
            lbl.setStyleSheet("color: #9F3FFA; font-size: 18px; font-weight: bold;")
            cl.addWidget(lt)
            cl.addWidget(lbl)
            kpi_layout.addWidget(card)

        layout_principal.addWidget(self._kpi_widget)

        lbl_tabela = QLabel("Minhas Vendas")
        lbl_tabela.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout_principal.addWidget(lbl_tabela)

        self._tabela_vendas = QTableWidget()
        layout_principal.addWidget(self._tabela_vendas)

    def _carregar_dados(self) -> None:
        self._carregar_kpis()
        self._carregar_vendas()

    def _carregar_kpis(self) -> None:
        try:
            kpis = self._db.kpis_dashboard()
        except Exception:
            return
        self._lbl_vendas_hoje.setText(formatar_moeda(kpis["vendas_hoje"]))
        self._lbl_vendas_mes.setText(formatar_moeda(kpis["vendas_mes"]))

    def _carregar_vendas(self) -> None:
        try:
            todas = self._db.listar_vendas()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return

        minhas = [v for v in todas if v[1] == self._usuario.nome]
        self._lbl_num_vendas.setText(str(len(minhas)))
        _preencher_tabela(
            self._tabela_vendas,
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

        if not produtos:
            QMessageBox.warning(self, "Atenção", "Nenhum produto cadastrado.")
            return

        dialog = _DialogNovaVenda(produtos, clientes, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        produto_id, cliente_cpf, quantidade, total = dialog.dados()
        try:
            self._db.registrar_venda(
                self._usuario.nome, cliente_cpf, produto_id, quantidade, total
            )
            QMessageBox.information(self, "Sucesso", f"Venda registrada. Total: {formatar_moeda(total)}")
            self._carregar_dados()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao registrar venda", str(exc))

    def _exportar_minhas_vendas(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar como", f"vendas_{self._usuario.login}.xlsx", "Excel (*.xlsx)"
        )
        if not caminho:
            return
        try:
            todas = self._db.listar_vendas()
            minhas = [v for v in todas if v[1] == self._usuario.nome]
            exportar_excel(
                caminho,
                "Minhas Vendas",
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
        self.setFixedSize(420, 280)
        self._produtos = produtos

        layout = QFormLayout(self)

        self._combo_produto = QComboBox()
        for p in produtos:
            self._combo_produto.addItem(
                f"[{p[1]}] {p[2]}  —  {formatar_moeda(float(p[3]))}  (estoque: {p[4]})",
                userData=(p[0], float(p[3])),
            )
        self._combo_produto.currentIndexChanged.connect(self._atualizar_total)
        layout.addRow("Produto:", self._combo_produto)

        self._combo_cliente = QComboBox()
        self._combo_cliente.addItem("— sem cliente —", userData="")
        for c in clientes:
            self._combo_cliente.addItem(f"{c[2]} ({c[1]})", userData=c[1])
        layout.addRow("Cliente:", self._combo_cliente)

        self._spin_qtde = QSpinBox()
        self._spin_qtde.setMinimum(1)
        self._spin_qtde.setMaximum(9999)
        self._spin_qtde.valueChanged.connect(self._atualizar_total)
        layout.addRow("Quantidade:", self._spin_qtde)

        self._lbl_total = QLabel("R$ 0,00")
        self._lbl_total.setStyleSheet("font-size: 16px; font-weight: bold; color: #9F3FFA;")
        layout.addRow("Total:", self._lbl_total)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addRow(botoes)

        self._atualizar_total()

    def _atualizar_total(self) -> None:
        dados = self._combo_produto.currentData()
        if dados:
            _, valor_unit = dados
            total = valor_unit * self._spin_qtde.value()
            self._lbl_total.setText(formatar_moeda(total))

    def _validar(self) -> None:
        dados = self._combo_produto.currentData()
        if not dados:
            return
        produto_id, valor_unit = dados
        estoque = next(
            (int(p[4]) for p in self._produtos if p[0] == produto_id), 0
        )
        if self._spin_qtde.value() > estoque:
            QMessageBox.warning(
                self, "Estoque insuficiente",
                f"Estoque disponível: {estoque} unidade(s)."
            )
            return
        self.accept()

    def dados(self) -> tuple[int, str, int, float]:
        produto_id, valor_unit = self._combo_produto.currentData()
        cliente_cpf = self._combo_cliente.currentData() or ""
        quantidade = self._spin_qtde.value()
        total = valor_unit * quantidade
        return produto_id, cliente_cpf, quantidade, total
