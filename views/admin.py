from __future__ import annotations

import os
from datetime import date
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from View.PY.FrmAdmin import Ui_FrmAdmin
from database import Database, UsuarioAutenticado
from utils.exportacao import exportar_excel, importar_csv, importar_excel
from utils.relatorios import formatar_moeda, resumo_vendas
from utils.validacao import (
    formatar_cpf,
    formatar_telefone,
    validar_campos,
    validar_cpf,
    validar_email,
    validar_senha,
)
from utils.widgets import TabelaFiltrada, item_readonly


class AdminWindow(QMainWindow):
    def __init__(self, db: Database, usuario: UsuarioAutenticado) -> None:
        super().__init__()
        self._db = db
        self._usuario = usuario
        self._ui = Ui_FrmAdmin()
        self._ui.setupUi(self)

        self._ui.lbl_seja_bem_vindo.setText(f"Seja Bem-Vindo(a) — {usuario.nome}")
        self._ui.lbl_seja_bem_vindo.setFixedWidth(500)

        self._tabela_colab = TabelaFiltrada(self._ui.pg_colaboradores)
        self._tabela_fornec = TabelaFiltrada(self._ui.pg_fornecedores)
        self._tabela_prod = TabelaFiltrada(self._ui.pg_produtos)

        self._tabela_colab.linha_excluida.connect(self._excluir_colaborador)
        self._tabela_fornec.linha_excluida.connect(self._excluir_fornecedor)
        self._tabela_prod.linha_excluida.connect(self._excluir_produto)
        self._tabela_prod.linha_editada.connect(self._editar_produto)

        self._injetar_tabela(self._ui.pg_colaboradores, self._tabela_colab)
        self._injetar_tabela(self._ui.pg_fornecedores, self._tabela_fornec)
        self._injetar_tabela(self._ui.pg_produtos, self._tabela_prod)

        self._conectar_navegacao()
        self._conectar_acoes()
        self._adicionar_menu_dados()
        self._atualizar_tudo()

    def _injetar_tabela(self, pagina: QWidget, tabela: TabelaFiltrada) -> None:
        layout = pagina.layout()
        if layout is None:
            layout = QVBoxLayout(pagina)
            pagina.setLayout(layout)
        layout.addWidget(tabela)

    def _conectar_navegacao(self) -> None:
        ui = self._ui
        nav = ui.Telas_do_menu

        ui.btn_home.clicked.connect(lambda: [nav.setCurrentWidget(ui.pg_home), self._carregar_dashboard()])
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

    def _adicionar_menu_dados(self) -> None:
        menu = self.menuBar().addMenu("Dados")

        acoes = [
            ("Exportar Produtos (Excel)", self._exportar_produtos_excel),
            ("Exportar Vendas (Excel)", self._exportar_vendas_excel),
            ("Importar Produtos (Excel/CSV)", self._importar_produtos),
            None,
            ("Relatório de Vendas por Período", self._abrir_relatorio_periodo),
            ("Produtos com Estoque Crítico", self._abrir_estoque_critico),
            ("Ranking de Vendedores", self._abrir_ranking_vendedores),
            ("Histórico de Movimentações", self._abrir_movimentacoes),
            ("Ajuste Manual de Estoque", self._abrir_ajuste_estoque),
        ]

        for item in acoes:
            if item is None:
                menu.addSeparator()
            else:
                titulo, slot = item
                act = QAction(titulo, self)
                act.triggered.connect(slot)
                menu.addAction(act)

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

        titulo = QLabel("Visão Geral do Estoque")
        titulo.setStyleSheet("font-size: 18px; font-weight: bold; font-family: Montserrat; margin-bottom: 12px;")
        layout.addWidget(titulo)

        grid = QHBoxLayout()
        cards = [
            ("Produtos Cadastrados", str(kpis["total_skus"]), False),
            ("Valor em Estoque", formatar_moeda(kpis["valor_estoque"]), False),
            ("Vendas Hoje", formatar_moeda(kpis["vendas_hoje"]), False),
            ("Vendas no Mês", formatar_moeda(kpis["vendas_mes"]), False),
            ("Total de Clientes", str(kpis["total_clientes"]), False),
            ("Alertas de Estoque", str(kpis["alertas_estoque"]), kpis["alertas_estoque"] > 0),
        ]
        for titulo_card, valor, alerta in cards:
            grid.addWidget(self._criar_card(titulo_card, valor, alerta))

        layout.addLayout(grid)
        layout.addStretch()

    def _criar_card(self, titulo: str, valor: str, alerta: bool = False) -> QWidget:
        cor_valor = "#e55" if alerta else "#9F3FFA"
        card = QWidget()
        card.setStyleSheet("background:#1e1e2e; border-radius:10px; padding:14px;")
        vl = QVBoxLayout(card)
        lbl_t = QLabel(titulo)
        lbl_t.setStyleSheet("color:#aaa; font-size:11px; font-family:Montserrat;")
        lbl_v = QLabel(valor)
        lbl_v.setStyleSheet(f"color:{cor_valor}; font-size:22px; font-weight:bold; font-family:Montserrat;")
        vl.addWidget(lbl_t)
        vl.addWidget(lbl_v)
        return card

    def _carregar_colaboradores(self) -> None:
        try:
            rows = self._db.listar_colaboradores()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        self._tabela_colab.preencher(
            ["Usuário", "Nível", "Nome", "CPF", "E-mail", "Telefone", "Cargo"],
            rows,
        )

    def _carregar_fornecedores(self) -> None:
        try:
            rows = self._db.listar_fornecedores()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        self._tabela_fornec.preencher(["ID", "Nome", "Endereço", "Contato"], rows)

    def _carregar_produtos(self) -> None:
        try:
            rows = self._db.listar_produtos()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        self._tabela_prod.preencher(
            ["ID", "Código", "Descrição", "Valor Unit.", "Estoque", "Mín.", "Fornecedor"],
            rows,
            colunas_alerta=(4, 5),
        )

    def _cadastrar_colaborador(self) -> None:
        ui = self._ui
        login = ui.line_login.text().strip()
        senha = ui.line_senha.text()
        nome = ui.line_nome.text().strip()
        cpf = ui.line_cpf.text().strip()
        email = ui.line_email.text().strip()
        telefone = ui.line_telefone.text().strip()
        cargo = ui.line_cargo.text().strip()
        nivel = "colaborador" if ui.radio_colaborador.isChecked() else "admin"

        faltando = validar_campos({"Login": login, "Senha": senha, "Nome": nome})
        if faltando:
            QMessageBox.warning(self, "Campos obrigatórios", f"Preencha: {', '.join(faltando)}")
            return

        erro_senha = validar_senha(senha)
        if erro_senha:
            QMessageBox.warning(self, "Senha inválida", erro_senha)
            return

        if email and not validar_email(email):
            QMessageBox.warning(self, "E-mail inválido", "Informe um e-mail válido.")
            return

        if cpf and not validar_cpf(cpf):
            QMessageBox.warning(self, "CPF inválido", "O CPF informado não é válido.")
            return

        try:
            self._db.cadastrar_colaborador(
                login, senha, nivel, nome,
                formatar_cpf(cpf) if cpf else "",
                email, formatar_telefone(telefone) if telefone else "", cargo,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao cadastrar", str(exc))
            return

        QMessageBox.information(self, "Sucesso", "Colaborador cadastrado com sucesso.")
        self._carregar_colaboradores()

    def _excluir_colaborador(self, row: int) -> None:
        usuario = self._tabela_colab.dado_linha(row, 0)
        nome = self._tabela_colab.dado_linha(row, 2)

        if usuario == self._usuario.login:
            QMessageBox.warning(self, "Ação negada", "Você não pode excluir sua própria conta.")
            return

        resposta = QMessageBox.question(
            self, "Confirmar exclusão",
            f"Excluir o colaborador '{nome}'?\n\nEssa ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        try:
            self._db.remover_colaborador(usuario)
            self._carregar_colaboradores()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))

    def _cadastrar_fornecedor(self) -> None:
        nome = self._ui.line_cadastrar_nome_fornecedores.text().strip()
        endereco = self._ui.line_cadastrar_endereco_fornecedores.text().strip()
        contato = self._ui.line_cadastrar_contato_fornecedores.text().strip()

        if not nome:
            QMessageBox.warning(self, "Campo obrigatório", "O nome do fornecedor é obrigatório.")
            return

        try:
            self._db.cadastrar_fornecedor(nome, endereco, contato)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao cadastrar", str(exc))
            return

        QMessageBox.information(self, "Sucesso", "Fornecedor cadastrado com sucesso.")
        self._carregar_fornecedores()

    def _excluir_fornecedor(self, row: int) -> None:
        fornecedor_id = int(self._tabela_fornec.dado_linha(row, 0))
        nome = self._tabela_fornec.dado_linha(row, 1)

        resposta = QMessageBox.question(
            self, "Confirmar exclusão",
            f"Excluir o fornecedor '{nome}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        try:
            self._db.remover_fornecedor(fornecedor_id)
            self._carregar_fornecedores()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))

    def _excluir_produto(self, row: int) -> None:
        produto_id = int(self._tabela_prod.dado_linha(row, 0))
        descricao = self._tabela_prod.dado_linha(row, 2)

        resposta = QMessageBox.question(
            self, "Confirmar exclusão",
            f"Excluir o produto '{descricao}'?\n\nIsso também apagará o histórico de movimentações.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        try:
            self._db.remover_produto(produto_id)
            self._carregar_produtos()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))

    def _editar_produto(self, row: int) -> None:
        produto_id = int(self._tabela_prod.dado_linha(row, 0))
        try:
            produtos = self._db.listar_produtos()
            produto = next((p for p in produtos if p[0] == produto_id), None)
            fornecedores = self._db.listar_fornecedores()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return

        if produto is None:
            return

        dialog = _DialogEditarProduto(produto, [f[1] for f in fornecedores], self)
        if dialog.exec_() != QDialog.Accepted:
            return

        cod, descricao, valor, qtde, minimo, fornecedor = dialog.dados()
        try:
            self._db.atualizar_produto(produto_id, cod, descricao, valor, qtde, minimo, fornecedor)
            self._carregar_produtos()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar", str(exc))

    def _exportar_produtos_excel(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar como", "produtos.xlsx", "Excel (*.xlsx)")
        if not caminho:
            return
        try:
            rows = self._db.listar_produtos()
            exportar_excel(
                caminho, "Produtos",
                ["ID", "Código", "Descrição", "Valor Unit.", "Estoque", "Mín.", "Fornecedor"],
                rows,
                colunas_alerta={4: (4, 5)},
            )
            QMessageBox.information(self, "Exportado", f"Salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _exportar_vendas_excel(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar como", "vendas.xlsx", "Excel (*.xlsx)")
        if not caminho:
            return
        try:
            rows = self._db.listar_vendas()
            exportar_excel(
                caminho, "Vendas",
                ["ID", "Vendedor", "Cliente CPF", "Produto", "Qtde", "Total", "Data"],
                rows,
            )
            QMessageBox.information(self, "Exportado", f"Salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _importar_produtos(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir arquivo", "", "Excel/CSV (*.xlsx *.csv)")
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
                    int(linha[3]),
                    int(linha[4]) if len(linha) > 4 else 5,
                    str(linha[5]) if len(linha) > 5 else "",
                )
            except Exception:
                erros += 1

        msg = f"{len(dados) - erros} produto(s) importado(s)."
        if erros:
            msg += f"\n{erros} linha(s) com erro ignoradas."
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
            f"Vendas {inicio} a {fim}  |  "
            f"Receita: {formatar_moeda(resumo['receita_total'])}  |  "
            f"Itens: {resumo['itens_vendidos']}",
            ["ID", "Vendedor", "Cliente CPF", "Produto", "Qtde", "Total", "Data"],
            rows, self,
        ).exec_()

    def _abrir_estoque_critico(self) -> None:
        try:
            rows = self._db.produtos_com_estoque_baixo()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        _DialogTabela(
            f"Estoque Crítico — {len(rows)} produto(s)",
            ["ID", "Código", "Descrição", "Estoque", "Mín.", "Fornecedor"],
            rows, self,
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
            formatado, self,
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
            rows, self,
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
            self._carregar_dashboard()
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
        self.resize(960, 520)

        layout = QVBoxLayout(self)
        lbl = QLabel(titulo)
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; font-family: Montserrat;")
        layout.addWidget(lbl)

        self._tabela = TabelaFiltrada()
        self._tabela.preencher(cabecalhos, linhas)
        layout.addWidget(self._tabela)

        botoes = QHBoxLayout()
        btn_exportar = QPushButton("Exportar Excel")
        btn_exportar.clicked.connect(lambda: self._exportar(cabecalhos, linhas))
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
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
        return (
            self._inicio.date().toString("yyyy-MM-dd"),
            self._fim.date().toString("yyyy-MM-dd"),
        )


class _DialogEditarProduto(QDialog):
    def __init__(
        self,
        produto: tuple[Any, ...],
        fornecedores: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Produto")
        self.setFixedSize(440, 320)

        layout = QFormLayout(self)

        self._cod = QLineEdit(str(produto[1]))
        self._descricao = QLineEdit(str(produto[2]))

        self._valor = QLineEdit(str(produto[3]).replace(".", ","))
        self._valor.setPlaceholderText("0,00")

        self._qtde = QSpinBox()
        self._qtde.setRange(0, 999999)
        self._qtde.setValue(int(produto[4]))

        self._minimo = QSpinBox()
        self._minimo.setRange(0, 999999)
        self._minimo.setValue(int(produto[5]))

        self._fornecedor = QComboBox()
        self._fornecedor.addItems(fornecedores)
        atual = str(produto[6]) if produto[6] else ""
        idx = self._fornecedor.findText(atual)
        if idx >= 0:
            self._fornecedor.setCurrentIndex(idx)

        layout.addRow("Código:", self._cod)
        layout.addRow("Descrição:", self._descricao)
        layout.addRow("Valor unit. (R$):", self._valor)
        layout.addRow("Estoque atual:", self._qtde)
        layout.addRow("Estoque mínimo:", self._minimo)
        layout.addRow("Fornecedor:", self._fornecedor)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addRow(botoes)

    def _validar(self) -> None:
        if not self._cod.text().strip() or not self._descricao.text().strip():
            QMessageBox.warning(self, "Campos obrigatórios", "Código e descrição são obrigatórios.")
            return
        try:
            float(self._valor.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Valor inválido", "Informe um valor numérico válido.")
            return
        self.accept()

    def dados(self) -> tuple[str, str, float, int, int, str]:
        return (
            self._cod.text().strip(),
            self._descricao.text().strip(),
            float(self._valor.text().replace(",", ".")),
            self._qtde.value(),
            self._minimo.value(),
            self._fornecedor.currentText(),
        )


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
        layout.addWidget(QLabel(
            f"<b>{len(dados)}</b> linha(s) encontradas. "
            "Colunas esperadas: Código, Descrição, Valor, Estoque, Estoque Mín., Fornecedor"
        ))

        tabela = TabelaFiltrada()
        tabela.preencher(cabecalhos, [tuple(r) for r in dados[:100]])
        layout.addWidget(tabela)

        if len(dados) > 100:
            layout.addWidget(QLabel(f"(exibindo primeiras 100 de {len(dados)} linhas)"))

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
        self.setFixedSize(420, 300)
        self._produtos = produtos

        layout = QFormLayout(self)

        self._combo = QComboBox()
        for p in produtos:
            self._combo.addItem(f"[{p[1]}] {p[2]}  (atual: {p[4]})", userData=p[0])
        layout.addRow("Produto:", self._combo)

        self._spin = QSpinBox()
        self._spin.setRange(1, 99999)
        layout.addRow("Quantidade:", self._spin)

        tipo_widget = QWidget()
        tipo_layout = QHBoxLayout(tipo_widget)
        tipo_layout.setContentsMargins(0, 0, 0, 0)
        self._radio_entrada = QRadioButton("Entrada (adicionar)")
        self._radio_saida = QRadioButton("Saída (remover)")
        self._radio_entrada.setChecked(True)
        tipo_layout.addWidget(self._radio_entrada)
        tipo_layout.addWidget(self._radio_saida)
        layout.addRow("Tipo:", tipo_widget)

        self._motivo = QLineEdit()
        self._motivo.setPlaceholderText("Ex: Recebimento NF 1234, Perda, Inventário...")
        layout.addRow("Motivo:", self._motivo)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addRow(botoes)

    def _validar(self) -> None:
        if not self._motivo.text().strip():
            QMessageBox.warning(self, "Campo obrigatório", "Informe o motivo do ajuste.")
            return
        self.accept()

    def dados(self) -> tuple[int, int, str, str]:
        tipo = "entrada" if self._radio_entrada.isChecked() else "saida"
        return (
            self._combo.currentData(),
            self._spin.value(),
            tipo,
            self._motivo.text().strip(),
        )
