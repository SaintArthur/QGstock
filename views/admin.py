from __future__ import annotations

import os
from datetime import date
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAction,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from View.PY.FrmAdmin import Ui_FrmAdmin
from database import Database, UsuarioAutenticado
from utils.exportacao import exportar_csv, exportar_excel, importar_csv, importar_excel
from utils.relatorios import formatar_moeda, resumo_estoque, resumo_vendas


_COR_ALERTA = QColor(255, 200, 200)


def _item_readonly(valor: Any) -> QTableWidgetItem:
    item = QTableWidgetItem(str(valor) if valor is not None else "")
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    return item


def _preencher_tabela(
    tabela: QTableWidget,
    cabecalhos: list[str],
    linhas: list[tuple[Any, ...]],
    colunas_alerta: tuple[int, int] | None = None,
) -> None:
    tabela.setColumnCount(len(cabecalhos))
    tabela.setHorizontalHeaderLabels(cabecalhos)
    tabela.setRowCount(len(linhas))
    tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    tabela.setAlternatingRowColors(True)

    for row_idx, linha in enumerate(linhas):
        for col_idx, valor in enumerate(linha):
            tabela.setItem(row_idx, col_idx, _item_readonly(valor))

        if colunas_alerta is not None:
            col_qtde, col_minimo = colunas_alerta
            try:
                qtde = int(linha[col_qtde])
                minimo = int(linha[col_minimo])
                if qtde <= minimo:
                    for c in range(len(linha)):
                        item = tabela.item(row_idx, c)
                        if item:
                            item.setBackground(_COR_ALERTA)
            except (TypeError, ValueError):
                pass


class AdminWindow(QMainWindow):
    def __init__(self, db: Database, usuario: UsuarioAutenticado) -> None:
        super().__init__()
        self._db = db
        self._usuario = usuario
        self._ui = Ui_FrmAdmin()
        self._ui.setupUi(self)

        self._ui.lbl_seja_bem_vindo.setText(f"Seja Bem-Vindo(a) — {usuario.nome}")
        self._ui.lbl_seja_bem_vindo.setFixedWidth(500)

        self._conectar_navegacao()
        self._conectar_acoes()
        self._adicionar_menu_exportacao()
        self._atualizar_tudo()

    def _conectar_navegacao(self) -> None:
        ui = self._ui
        nav = ui.Telas_do_menu

        ui.btn_home.clicked.connect(lambda: nav.setCurrentWidget(ui.pg_home))
        ui.btn_colaboradores.clicked.connect(lambda: [nav.setCurrentWidget(ui.pg_colaboradores), self._carregar_colaboradores()])
        ui.btn_cadastrar_colaboradores.clicked.connect(lambda: nav.setCurrentWidget(ui.pg_cadastro_colaboradores))
        ui.btn_alterar_colaboradores.clicked.connect(lambda: nav.setCurrentWidget(ui.alterar_colaboradores))

        ui.btn_fornecedores.clicked.connect(lambda: [nav.setCurrentWidget(ui.pg_fornecedores), self._carregar_fornecedores()])
        ui.btn_adicionar_forncedores.clicked.connect(lambda: nav.setCurrentWidget(ui.pg_cadastrar_fornecedores))
        ui.btn_editar_fornecedores.clicked.connect(lambda: nav.setCurrentWidget(ui.pg_alterar_fornecedores))

        ui.btn_produtos.clicked.connect(lambda: [nav.setCurrentWidget(ui.pg_produtos), self._carregar_produtos()])
        ui.btn_cadastrar_produto.clicked.connect(lambda: nav.setCurrentWidget(ui.pg_cadastar_produtos))

    def _conectar_acoes(self) -> None:
        self._ui.btn_cadastro.clicked.connect(self._cadastrar_colaborador)
        self._ui.btn_cadastrar_forncedores.clicked.connect(self._cadastrar_fornecedor)

    def _adicionar_menu_exportacao(self) -> None:
        menu_dados = self.menuBar().addMenu("Dados")

        act_export_produtos = QAction("Exportar Produtos (Excel)", self)
        act_export_produtos.triggered.connect(self._exportar_produtos_excel)
        menu_dados.addAction(act_export_produtos)

        act_export_vendas = QAction("Exportar Vendas (Excel)", self)
        act_export_vendas.triggered.connect(self._exportar_vendas_excel)
        menu_dados.addAction(act_export_vendas)

        act_import_produtos = QAction("Importar Produtos (Excel/CSV)", self)
        act_import_produtos.triggered.connect(self._importar_produtos)
        menu_dados.addAction(act_import_produtos)

        menu_dados.addSeparator()

        act_relatorio = QAction("Relatório de Vendas por Período", self)
        act_relatorio.triggered.connect(self._abrir_relatorio_periodo)
        menu_dados.addAction(act_relatorio)

        act_estoque_baixo = QAction("Produtos com Estoque Crítico", self)
        act_estoque_baixo.triggered.connect(self._abrir_estoque_critico)
        menu_dados.addAction(act_estoque_baixo)

        act_ranking = QAction("Ranking de Vendedores", self)
        act_ranking.triggered.connect(self._abrir_ranking_vendedores)
        menu_dados.addAction(act_ranking)

        act_movimentacoes = QAction("Histórico de Movimentações", self)
        act_movimentacoes.triggered.connect(self._abrir_movimentacoes)
        menu_dados.addAction(act_movimentacoes)

        act_ajustar = QAction("Ajuste Manual de Estoque", self)
        act_ajustar.triggered.connect(self._abrir_ajuste_estoque)
        menu_dados.addAction(act_ajustar)

    def _atualizar_tudo(self) -> None:
        self._carregar_dashboard()
        self._carregar_colaboradores()
        self._carregar_fornecedores()
        self._carregar_produtos()

    def _carregar_dashboard(self) -> None:
        try:
            kpis = self._db.kpis_dashboard()
        except Exception:
            return

        pg = self._ui.pg_home
        layout = pg.layout()
        if layout is None:
            layout = QVBoxLayout(pg)
            pg.setLayout(layout)
        else:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        kpi_items = [
            ("Produtos Cadastrados", str(kpis["total_skus"])),
            ("Valor em Estoque", formatar_moeda(kpis["valor_estoque"])),
            ("Vendas Hoje", formatar_moeda(kpis["vendas_hoje"])),
            ("Vendas no Mês", formatar_moeda(kpis["vendas_mes"])),
            ("Clientes", str(kpis["total_clientes"])),
            ("Alertas de Estoque", str(kpis["alertas_estoque"])),
        ]

        grid = QHBoxLayout()
        for titulo, valor in kpi_items:
            card = self._criar_card_kpi(titulo, valor)
            grid.addWidget(card)

        layout.addLayout(grid)
        layout.addStretch()

    def _criar_card_kpi(self, titulo: str, valor: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(
            "background-color: #1e1e2e; border-radius: 10px; padding: 10px;"
        )
        vl = QVBoxLayout(card)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("color: #aaa; font-size: 11px; font-family: Montserrat;")
        lbl_valor = QLabel(valor)
        lbl_valor.setStyleSheet(
            "color: #9F3FFA; font-size: 20px; font-weight: bold; font-family: Montserrat;"
        )
        vl.addWidget(lbl_titulo)
        vl.addWidget(lbl_valor)
        return card

    def _carregar_colaboradores(self) -> None:
        try:
            rows = self._db.listar_colaboradores()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        _preencher_tabela(
            self._ui.tabela_colaboradores,
            ["Usuário", "Nível", "Nome", "CPF", "E-mail", "Telefone", "Cargo"],
            rows,
        )

    def _carregar_fornecedores(self) -> None:
        try:
            rows = self._db.listar_fornecedores()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        _preencher_tabela(
            self._ui.tabela_fornecedores,
            ["ID", "Nome", "Endereço", "Contato"],
            rows,
        )

    def _carregar_produtos(self) -> None:
        try:
            rows = self._db.listar_produtos()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        _preencher_tabela(
            self._ui.tabela_produto,
            ["ID", "Código", "Descrição", "Valor Unit.", "Estoque", "Mín.", "Fornecedor"],
            rows,
            colunas_alerta=(4, 5),
        )

    def _cadastrar_colaborador(self) -> None:
        ui = self._ui
        campos = {
            "login": ui.line_login.text().strip(),
            "senha": ui.line_senha.text(),
            "nome": ui.line_nome.text().strip(),
            "cpf": ui.line_cpf.text().strip(),
            "email": ui.line_email.text().strip(),
            "telefone": ui.line_telefone.text().strip(),
            "cargo": ui.line_cargo.text().strip(),
        }
        nivel = "colaborador" if ui.radio_colaborador.isChecked() else "admin"

        if not campos["login"] or not campos["senha"] or not campos["nome"]:
            QMessageBox.warning(self, "Atenção", "Login, senha e nome são obrigatórios.")
            return

        try:
            self._db.cadastrar_colaborador(
                campos["login"], campos["senha"], nivel,
                campos["nome"], campos["cpf"], campos["email"],
                campos["telefone"], campos["cargo"],
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao cadastrar", str(exc))
            return

        QMessageBox.information(self, "Sucesso", "Colaborador cadastrado com sucesso.")
        self._carregar_colaboradores()

    def _cadastrar_fornecedor(self) -> None:
        nome = self._ui.line_cadastrar_nome_fornecedores.text().strip()
        endereco = self._ui.line_cadastrar_endereco_fornecedores.text().strip()
        contato = self._ui.line_cadastrar_contato_fornecedores.text().strip()

        if not nome:
            QMessageBox.warning(self, "Atenção", "O nome do fornecedor é obrigatório.")
            return

        try:
            self._db.cadastrar_fornecedor(nome, endereco, contato)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao cadastrar", str(exc))
            return

        QMessageBox.information(self, "Sucesso", "Fornecedor cadastrado com sucesso.")
        self._carregar_fornecedores()

    def _exportar_produtos_excel(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar como", "produtos.xlsx", "Excel (*.xlsx)"
        )
        if not caminho:
            return
        try:
            rows = self._db.listar_produtos()
            exportar_excel(
                caminho,
                "Produtos",
                ["ID", "Código", "Descrição", "Valor Unit.", "Estoque", "Mín.", "Fornecedor"],
                rows,
                colunas_alerta={4: (4, 5)},
            )
            QMessageBox.information(self, "Exportado", f"Arquivo salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _exportar_vendas_excel(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar como", "vendas.xlsx", "Excel (*.xlsx)"
        )
        if not caminho:
            return
        try:
            rows = self._db.listar_vendas()
            exportar_excel(
                caminho,
                "Vendas",
                ["ID", "Vendedor", "Cliente CPF", "Produto", "Qtde", "Total", "Data"],
                rows,
            )
            QMessageBox.information(self, "Exportado", f"Arquivo salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _importar_produtos(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir arquivo", "", "Excel/CSV (*.xlsx *.csv)"
        )
        if not caminho:
            return

        try:
            ext = os.path.splitext(caminho)[1].lower()
            cabecalhos, dados = (
                importar_excel(caminho) if ext == ".xlsx" else importar_csv(caminho)
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao importar", str(exc))
            return

        if not dados:
            QMessageBox.warning(self, "Arquivo vazio", "Nenhum dado encontrado no arquivo.")
            return

        dialog = _DialogPreviewImportacao(cabecalhos, dados, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        erros = 0
        for linha in dados:
            try:
                self._db.cadastrar_produto(
                    str(linha[0]), str(linha[1]),
                    float(str(linha[2]).replace(",", ".")),
                    int(linha[3]), int(linha[4] if len(linha) > 4 else 5),
                    str(linha[5] if len(linha) > 5 else ""),
                )
            except Exception:
                erros += 1

        msg = f"{len(dados) - erros} produto(s) importado(s)."
        if erros:
            msg += f"\n{erros} linha(s) com erro foram ignoradas."
        QMessageBox.information(self, "Importação concluída", msg)
        self._carregar_produtos()

    def _abrir_relatorio_periodo(self) -> None:
        dialog = _DialogPeriodo(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        inicio, fim = dialog.periodo()
        try:
            rows = self._db.relatorio_vendas_periodo(inicio, fim)
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return

        resumo = resumo_vendas(rows)
        _DialogTabela(
            f"Vendas de {inicio} a {fim}  |  "
            f"Receita: {formatar_moeda(resumo['receita_total'])}  |  "
            f"Itens: {resumo['itens_vendidos']}",
            ["ID", "Vendedor", "Cliente CPF", "Produto", "Qtde", "Total", "Data"],
            rows,
            self,
        ).exec_()

    def _abrir_estoque_critico(self) -> None:
        try:
            rows = self._db.produtos_com_estoque_baixo()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return

        _DialogTabela(
            f"Produtos com Estoque Crítico — {len(rows)} item(s)",
            ["ID", "Código", "Descrição", "Estoque Atual", "Estoque Mín.", "Fornecedor"],
            rows,
            self,
        ).exec_()

    def _abrir_ranking_vendedores(self) -> None:
        try:
            rows = self._db.ranking_vendedores()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return

        formatado = [(r[0], r[1], formatar_moeda(float(r[2]))) for r in rows]
        _DialogTabela(
            "Ranking de Vendedores",
            ["Vendedor", "Nº Vendas", "Total Vendido"],
            formatado,
            self,
        ).exec_()

    def _abrir_movimentacoes(self) -> None:
        try:
            rows = self._db.listar_movimentacoes()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return

        _DialogTabela(
            f"Histórico de Movimentações — {len(rows)} registro(s)",
            ["ID", "Produto", "Tipo", "Quantidade", "Motivo", "Data/Hora"],
            rows,
            self,
        ).exec_()

    def _abrir_ajuste_estoque(self) -> None:
        try:
            produtos = self._db.listar_produtos()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return

        dialog = _DialogAjusteEstoque(produtos, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        produto_id, quantidade, tipo, motivo = dialog.dados()
        try:
            self._db.ajustar_estoque(produto_id, quantidade, tipo, motivo)
            QMessageBox.information(self, "Sucesso", "Estoque ajustado com sucesso.")
            self._carregar_produtos()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))


class _DialogTabela(QDialog):
    def __init__(
        self,
        titulo: str,
        cabecalhos: list[str],
        linhas: list[tuple[Any, ...]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(900, 500)

        layout = QVBoxLayout(self)
        lbl = QLabel(titulo)
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(lbl)

        tabela = QTableWidget()
        _preencher_tabela(tabela, cabecalhos, linhas)
        layout.addWidget(tabela)

        botoes = QHBoxLayout()
        btn_exportar = QPushButton("Exportar Excel")
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
        btn_exportar.clicked.connect(lambda: self._exportar(cabecalhos, linhas))
        botoes.addWidget(btn_exportar)
        botoes.addStretch()
        botoes.addWidget(btn_fechar)
        layout.addLayout(botoes)

    def _exportar(self, cabecalhos: list[str], linhas: list[tuple[Any, ...]]) -> None:
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar como", "relatorio.xlsx", "Excel (*.xlsx)")
        if caminho:
            try:
                exportar_excel(caminho, "Relatório", cabecalhos, linhas)
                QMessageBox.information(self, "Exportado", f"Salvo em:\n{caminho}")
            except Exception as exc:
                QMessageBox.critical(self, "Erro", str(exc))


class _DialogPeriodo(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Selecionar Período")
        self.setFixedSize(300, 160)

        layout = QFormLayout(self)
        self._inicio = QDateEdit(date.today().replace(day=1))
        self._inicio.setCalendarPopup(True)
        self._inicio.setDisplayFormat("yyyy-MM-dd")
        self._fim = QDateEdit(date.today())
        self._fim.setCalendarPopup(True)
        self._fim.setDisplayFormat("yyyy-MM-dd")

        layout.addRow("Data início:", self._inicio)
        layout.addRow("Data fim:", self._fim)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addRow(botoes)

    def periodo(self) -> tuple[str, str]:
        return self._inicio.date().toString("yyyy-MM-dd"), self._fim.date().toString("yyyy-MM-dd")


class _DialogPreviewImportacao(QDialog):
    def __init__(
        self,
        cabecalhos: list[str],
        dados: list[list[Any]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prévia da Importação")
        self.resize(800, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{len(dados)} linha(s) encontradas. Confirmar importação?"))

        tabela = QTableWidget()
        _preencher_tabela(tabela, cabecalhos, [tuple(r) for r in dados[:50]])
        layout.addWidget(tabela)

        if len(dados) > 50:
            layout.addWidget(QLabel(f"(mostrando primeiras 50 de {len(dados)} linhas)"))

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)


class _DialogAjusteEstoque(QDialog):
    def __init__(
        self, produtos: list[tuple[Any, ...]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajuste Manual de Estoque")
        self.setFixedSize(400, 300)
        self._produtos = produtos

        from PyQt5.QtWidgets import QComboBox, QRadioButton, QSpinBox

        layout = QFormLayout(self)

        self._combo = QComboBox()
        for p in produtos:
            self._combo.addItem(f"[{p[1]}] {p[2]}", userData=p[0])
        layout.addRow("Produto:", self._combo)

        self._spin_qtde = QSpinBox()
        self._spin_qtde.setMinimum(1)
        self._spin_qtde.setMaximum(99999)
        layout.addRow("Quantidade:", self._spin_qtde)

        tipo_widget = QWidget()
        tipo_layout = QHBoxLayout(tipo_widget)
        self._radio_entrada = QRadioButton("Entrada")
        self._radio_saida = QRadioButton("Saída")
        self._radio_entrada.setChecked(True)
        tipo_layout.addWidget(self._radio_entrada)
        tipo_layout.addWidget(self._radio_saida)
        layout.addRow("Tipo:", tipo_widget)

        self._motivo = QLineEdit()
        self._motivo.setPlaceholderText("Ex: Recebimento NF 1234")
        layout.addRow("Motivo:", self._motivo)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addRow(botoes)

    def _validar(self) -> None:
        if not self._motivo.text().strip():
            QMessageBox.warning(self, "Atenção", "Informe o motivo do ajuste.")
            return
        self.accept()

    def dados(self) -> tuple[int, int, str, str]:
        tipo = "entrada" if self._radio_entrada.isChecked() else "saida"
        return (
            self._combo.currentData(),
            self._spin_qtde.value(),
            tipo,
            self._motivo.text().strip(),
        )
