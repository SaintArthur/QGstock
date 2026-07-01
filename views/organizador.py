from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.exportacao import exportar_csv, exportar_excel, importar_csv, importar_excel
from utils.organizador import (
    TEMPLATES_BUILTIN,
    Coluna,
    ResultadoOrganizacao,
    Template,
    TRANSFORMACOES_DISPONIVEIS,
    TIPOS_CAMPO,
    detectar_mapeamento_automatico,
    listar_templates_salvos,
    organizar,
)

_PASTA_TEMPLATES = Path(__file__).parent.parent / "templates"

_COR_ERRO = QColor(255, 180, 180)
_COR_AVISO = QColor(255, 230, 150)
_COR_DUP = QColor(200, 200, 200)
_COR_OK = QColor(180, 240, 180)

_ESTILO_BTN_PRIMARIO = (
    "background:#9F3FFA; color:white; font-weight:bold; "
    "padding:9px 20px; border-radius:7px; font-family:Montserrat; font-size:13px;"
)
_ESTILO_BTN_SECUNDARIO = (
    "padding:8px 16px; border-radius:7px; border:1px solid #555; font-family:Montserrat;"
)


def _item_ro(valor: Any, cor: QColor | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(str(valor) if valor is not None else "")
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    if cor:
        item.setBackground(cor)
    return item


def _preencher_tabela_preview(
    tabela: QTableWidget,
    cabecalhos: list[str],
    linhas: list[list[Any]],
    max_linhas: int = 500,
    linhas_erro: set[int] | None = None,
    linhas_aviso: set[int] | None = None,
    linhas_dup: set[int] | None = None,
) -> None:
    exibir = linhas[:max_linhas]
    tabela.setColumnCount(len(cabecalhos))
    tabela.setHorizontalHeaderLabels(cabecalhos)
    tabela.setRowCount(len(exibir))
    tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    tabela.horizontalHeader().setStretchLastSection(True)
    tabela.verticalHeader().setVisible(True)
    tabela.setAlternatingRowColors(False)

    erros = linhas_erro or set()
    avisos = linhas_aviso or set()
    dups = linhas_dup or set()

    for row_idx, linha in enumerate(exibir):
        linha_real = row_idx + 2
        if linha_real in dups:
            cor = _COR_DUP
        elif linha_real in erros:
            cor = _COR_ERRO
        elif linha_real in avisos:
            cor = _COR_AVISO
        else:
            cor = None

        for col_idx, valor in enumerate(linha):
            tabela.setItem(row_idx, col_idx, _item_ro(valor, cor))


class OrganizadorDialog(QDialog):
    def __init__(self, db: Any = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("Organizador de Planilhas")
        self.resize(1100, 700)
        self.setMinimumSize(900, 600)

        self._cabecalhos_fonte: list[str] = []
        self._dados_fonte: list[list[Any]] = []
        self._arquivo_atual: str = ""
        self._template_atual: Template | None = None
        self._resultado: ResultadoOrganizacao | None = None

        self._construir_ui()
        self._ir_para(0)

    def _construir_ui(self) -> None:
        layout_raiz = QVBoxLayout(self)
        layout_raiz.setSpacing(0)
        layout_raiz.setContentsMargins(0, 0, 0, 0)

        layout_raiz.addWidget(self._construir_cabecalho())

        self._stack = QStackedWidget()
        self._stack.addWidget(self._pagina_arquivo())
        self._stack.addWidget(self._pagina_template())
        self._stack.addWidget(self._pagina_resultado())
        layout_raiz.addWidget(self._stack)

        layout_raiz.addWidget(self._construir_rodape())

    def _construir_cabecalho(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background:#1a1a2e; border-bottom: 2px solid #9F3FFA;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 14, 20, 14)

        lbl_titulo = QLabel("Organizador de Planilhas")
        lbl_titulo.setStyleSheet("color:white; font-size:17px; font-weight:bold; font-family:Montserrat;")
        layout.addWidget(lbl_titulo)

        layout.addStretch()

        self._passos: list[QLabel] = []
        nomes = ["1. Arquivo", "2. Template", "3. Resultado"]
        for i, nome in enumerate(nomes):
            lbl = QLabel(nome)
            lbl.setStyleSheet("color:#888; font-family:Montserrat; font-size:12px; padding:4px 12px;")
            layout.addWidget(lbl)
            self._passos.append(lbl)

        return widget

    def _construir_rodape(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background:#111; border-top:1px solid #333;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 10, 20, 10)

        self._btn_voltar = QPushButton("← Voltar")
        self._btn_voltar.setStyleSheet(_ESTILO_BTN_SECUNDARIO)
        self._btn_voltar.clicked.connect(self._passo_anterior)
        layout.addWidget(self._btn_voltar)

        layout.addStretch()

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color:#aaa; font-family:Montserrat; font-size:12px;")
        layout.addWidget(self._lbl_status)

        layout.addStretch()

        self._btn_proximo = QPushButton("Próximo →")
        self._btn_proximo.setStyleSheet(_ESTILO_BTN_PRIMARIO)
        self._btn_proximo.clicked.connect(self._passo_proximo)
        layout.addWidget(self._btn_proximo)

        return widget

    def _pagina_arquivo(self) -> QWidget:
        pg = QWidget()
        pg.setStyleSheet("background:#12121f;")
        layout = QVBoxLayout(pg)
        layout.setContentsMargins(30, 30, 30, 20)
        layout.setSpacing(16)

        lbl = QLabel("Selecione o arquivo para organizar")
        lbl.setStyleSheet("color:white; font-size:15px; font-weight:bold; font-family:Montserrat;")
        layout.addWidget(lbl)

        zona_upload = QWidget()
        zona_upload.setStyleSheet(
            "border: 2px dashed #9F3FFA; border-radius: 12px; "
            "background:#1a1a2e; padding: 20px;"
        )
        zona_layout = QVBoxLayout(zona_upload)
        zona_layout.setAlignment(Qt.AlignCenter)

        self._lbl_arquivo = QLabel("Nenhum arquivo selecionado")
        self._lbl_arquivo.setStyleSheet("color:#aaa; font-family:Montserrat; font-size:13px;")
        self._lbl_arquivo.setAlignment(Qt.AlignCenter)
        zona_layout.addWidget(self._lbl_arquivo)

        btn_selecionar = QPushButton("Escolher arquivo (Excel ou CSV)")
        btn_selecionar.setStyleSheet(_ESTILO_BTN_PRIMARIO)
        btn_selecionar.setFixedWidth(280)
        btn_selecionar.clicked.connect(self._selecionar_arquivo)
        zona_layout.addWidget(btn_selecionar, alignment=Qt.AlignCenter)

        lbl_formatos = QLabel("Formatos aceitos: .xlsx, .xls, .csv")
        lbl_formatos.setStyleSheet("color:#666; font-size:11px; font-family:Montserrat;")
        lbl_formatos.setAlignment(Qt.AlignCenter)
        zona_layout.addWidget(lbl_formatos)

        layout.addWidget(zona_upload)

        self._lbl_info_arquivo = QLabel("")
        self._lbl_info_arquivo.setStyleSheet("color:#9F3FFA; font-family:Montserrat; font-size:12px;")
        layout.addWidget(self._lbl_info_arquivo)

        grp_preview = QGroupBox("Prévia dos dados (primeiras 20 linhas)")
        grp_preview.setStyleSheet(
            "QGroupBox { color:white; font-family:Montserrat; border:1px solid #333; "
            "border-radius:8px; margin-top:8px; padding-top:10px; } "
            "QGroupBox::title { subcontrol-origin:margin; padding:0 6px; }"
        )
        grp_layout = QVBoxLayout(grp_preview)
        self._tabela_preview = QTableWidget()
        self._tabela_preview.setStyleSheet("background:#1a1a2e; color:white; gridline-color:#333;")
        self._tabela_preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabela_preview.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabela_preview.verticalHeader().setDefaultSectionSize(22)
        grp_layout.addWidget(self._tabela_preview)
        layout.addWidget(grp_preview)

        return pg

    def _pagina_template(self) -> QWidget:
        pg = QWidget()
        pg.setStyleSheet("background:#12121f;")
        layout = QHBoxLayout(pg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Painel esquerdo — seleção e edição de template
        painel_esq = QWidget()
        painel_esq.setMaximumWidth(340)
        esq_layout = QVBoxLayout(painel_esq)
        esq_layout.setSpacing(10)

        lbl_t = QLabel("Template")
        lbl_t.setStyleSheet("color:white; font-size:14px; font-weight:bold; font-family:Montserrat;")
        esq_layout.addWidget(lbl_t)

        self._combo_template = QComboBox()
        self._combo_template.setStyleSheet("padding:6px; font-family:Montserrat; color:white; background:#1a1a2e;")
        self._combo_template.currentIndexChanged.connect(self._ao_mudar_template)
        esq_layout.addWidget(self._combo_template)
        self._recarregar_templates()

        self._lbl_desc_template = QLabel("")
        self._lbl_desc_template.setStyleSheet("color:#aaa; font-size:11px; font-family:Montserrat;")
        self._lbl_desc_template.setWordWrap(True)
        esq_layout.addWidget(self._lbl_desc_template)

        btn_novo = QPushButton("+ Criar template do zero")
        btn_novo.setStyleSheet(_ESTILO_BTN_SECUNDARIO + "color:white;")
        btn_novo.clicked.connect(self._criar_template)
        esq_layout.addWidget(btn_novo)

        btn_salvar = QPushButton("Salvar template atual")
        btn_salvar.setStyleSheet(_ESTILO_BTN_SECUNDARIO + "color:white;")
        btn_salvar.clicked.connect(self._salvar_template)
        esq_layout.addWidget(btn_salvar)

        self._chk_remover_dup = QCheckBox("Remover linhas duplicadas")
        self._chk_remover_dup.setChecked(True)
        self._chk_remover_dup.setStyleSheet("color:white; font-family:Montserrat;")
        esq_layout.addWidget(self._chk_remover_dup)

        esq_layout.addStretch()

        btn_organizar = QPushButton("Organizar planilha →")
        btn_organizar.setStyleSheet(_ESTILO_BTN_PRIMARIO)
        btn_organizar.clicked.connect(self._executar_organizacao)
        esq_layout.addWidget(btn_organizar)

        layout.addWidget(painel_esq)

        # Painel direito — mapeamento de colunas
        painel_dir = QWidget()
        dir_layout = QVBoxLayout(painel_dir)
        dir_layout.setSpacing(8)

        lbl_m = QLabel("Mapeamento de Colunas")
        lbl_m.setStyleSheet("color:white; font-size:14px; font-weight:bold; font-family:Montserrat;")
        dir_layout.addWidget(lbl_m)

        lbl_hint = QLabel(
            "Para cada coluna do template, selecione qual coluna do seu arquivo corresponde. "
            "O sistema tenta detectar automaticamente."
        )
        lbl_hint.setStyleSheet("color:#888; font-size:11px; font-family:Montserrat;")
        lbl_hint.setWordWrap(True)
        dir_layout.addWidget(lbl_hint)

        self._tabela_mapeamento = QTableWidget()
        self._tabela_mapeamento.setStyleSheet(
            "QTableWidget { background:#1a1a2e; color:white; gridline-color:#333; } "
            "QHeaderView::section { background:#2a1a4e; color:white; padding:6px; }"
        )
        self._tabela_mapeamento.setColumnCount(4)
        self._tabela_mapeamento.setHorizontalHeaderLabels(
            ["Coluna do Template", "Tipo", "Obrig.", "Coluna do Arquivo"]
        )
        self._tabela_mapeamento.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabela_mapeamento.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabela_mapeamento.verticalHeader().setVisible(False)
        dir_layout.addWidget(self._tabela_mapeamento)

        layout.addWidget(painel_dir)

        return pg

    def _pagina_resultado(self) -> QWidget:
        pg = QWidget()
        pg.setStyleSheet("background:#12121f;")
        layout = QVBoxLayout(pg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Cards de stats
        self._cards_layout = QHBoxLayout()
        layout.addLayout(self._cards_layout)

        # Tabela resultado
        grp = QGroupBox("Dados Organizados")
        grp.setStyleSheet(
            "QGroupBox { color:white; font-family:Montserrat; border:1px solid #333; "
            "border-radius:8px; margin-top:8px; padding-top:10px; } "
            "QGroupBox::title { subcontrol-origin:margin; padding:0 6px; }"
        )
        grp_layout = QVBoxLayout(grp)

        lbl_legenda = QLabel(
            "  ■ Verde = OK    ■ Amarelo = aviso (valor suspeito)    "
            "■ Vermelho = erro (campo inválido)    ■ Cinza = duplicata removida"
        )
        lbl_legenda.setStyleSheet("color:#aaa; font-size:10px; font-family:Montserrat;")
        grp_layout.addWidget(lbl_legenda)

        self._tabela_resultado = QTableWidget()
        self._tabela_resultado.setStyleSheet(
            "QTableWidget { background:#1a1a2e; color:white; gridline-color:#333; } "
            "QHeaderView::section { background:#2a1a4e; color:white; padding:6px; }"
        )
        self._tabela_resultado.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabela_resultado.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabela_resultado.verticalHeader().setDefaultSectionSize(22)
        grp_layout.addWidget(self._tabela_resultado)

        layout.addWidget(grp)

        # Painel de problemas
        grp_prob = QGroupBox("Problemas Encontrados")
        grp_prob.setStyleSheet(
            "QGroupBox { color:white; font-family:Montserrat; border:1px solid #333; "
            "border-radius:8px; margin-top:4px; padding-top:10px; } "
            "QGroupBox::title { subcontrol-origin:margin; padding:0 6px; }"
        )
        grp_prob.setMaximumHeight(160)
        prob_layout = QVBoxLayout(grp_prob)
        self._txt_problemas = QTextEdit()
        self._txt_problemas.setReadOnly(True)
        self._txt_problemas.setStyleSheet(
            "background:#1a1a2e; color:#ddd; font-family:Consolas,monospace; font-size:11px;"
        )
        prob_layout.addWidget(self._txt_problemas)
        layout.addWidget(grp_prob)

        # Botões de ação
        acoes = QHBoxLayout()

        self._btn_importar_bd = QPushButton("Importar para Banco de Dados")
        self._btn_importar_bd.setStyleSheet(_ESTILO_BTN_PRIMARIO)
        self._btn_importar_bd.setVisible(False)
        self._btn_importar_bd.clicked.connect(self._importar_para_bd)
        acoes.addWidget(self._btn_importar_bd)

        acoes.addStretch()

        btn_exp_excel = QPushButton("Exportar Excel")
        btn_exp_excel.setStyleSheet(_ESTILO_BTN_SECUNDARIO + "color:white;")
        btn_exp_excel.clicked.connect(self._exportar_excel)
        acoes.addWidget(btn_exp_excel)

        btn_exp_csv = QPushButton("Exportar CSV")
        btn_exp_csv.setStyleSheet(_ESTILO_BTN_SECUNDARIO + "color:white;")
        btn_exp_csv.clicked.connect(self._exportar_csv)
        acoes.addWidget(btn_exp_csv)

        layout.addLayout(acoes)

        return pg

    def _ir_para(self, indice: int) -> None:
        self._stack.setCurrentIndex(indice)
        for i, lbl in enumerate(self._passos):
            if i == indice:
                lbl.setStyleSheet(
                    "color:#9F3FFA; font-family:Montserrat; font-size:12px; "
                    "padding:4px 12px; font-weight:bold; "
                    "border-bottom:2px solid #9F3FFA;"
                )
            elif i < indice:
                lbl.setStyleSheet("color:#4CAF50; font-family:Montserrat; font-size:12px; padding:4px 12px;")
            else:
                lbl.setStyleSheet("color:#888; font-family:Montserrat; font-size:12px; padding:4px 12px;")

        self._btn_voltar.setVisible(indice > 0)
        self._btn_proximo.setVisible(indice < 2)

    def _passo_proximo(self) -> None:
        atual = self._stack.currentIndex()
        if atual == 0 and not self._dados_fonte:
            QMessageBox.warning(self, "Arquivo necessário", "Selecione um arquivo antes de continuar.")
            return
        self._ir_para(atual + 1)

    def _passo_anterior(self) -> None:
        self._ir_para(self._stack.currentIndex() - 1)

    def _selecionar_arquivo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar planilha", "",
            "Planilhas (*.xlsx *.xls *.csv);;Excel (*.xlsx *.xls);;CSV (*.csv)"
        )
        if not caminho:
            return

        try:
            ext = os.path.splitext(caminho)[1].lower()
            if ext in (".xlsx", ".xls"):
                cab, dados = importar_excel(caminho)
            else:
                cab, dados = importar_csv(caminho)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao abrir arquivo", str(exc))
            return

        if not dados:
            QMessageBox.warning(self, "Arquivo vazio", "O arquivo não contém dados.")
            return

        self._arquivo_atual = caminho
        self._cabecalhos_fonte = cab
        self._dados_fonte = dados

        nome = os.path.basename(caminho)
        self._lbl_arquivo.setText(f"✓  {nome}")
        self._lbl_arquivo.setStyleSheet("color:#9F3FFA; font-family:Montserrat; font-size:13px; font-weight:bold;")
        self._lbl_info_arquivo.setText(
            f"{len(dados)} linhas  •  {len(cab)} colunas  •  {os.path.getsize(caminho) // 1024} KB"
        )

        _preencher_tabela_preview(self._tabela_preview, cab, dados, max_linhas=20)
        self._atualizar_mapeamento()

    def _recarregar_templates(self) -> None:
        self._combo_template.blockSignals(True)
        self._combo_template.clear()

        self._todos_templates: list[Template] = list(TEMPLATES_BUILTIN)
        self._todos_templates += listar_templates_salvos(_PASTA_TEMPLATES)

        for t in self._todos_templates:
            prefixo = "★ " if t.builtin else "◎ "
            self._combo_template.addItem(prefixo + t.nome)

        self._combo_template.blockSignals(False)
        self._combo_template.setCurrentIndex(0)
        self._ao_mudar_template(0)

    def _ao_mudar_template(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._todos_templates):
            return
        self._template_atual = self._todos_templates[idx]
        self._lbl_desc_template.setText(self._template_atual.descricao)
        self._atualizar_mapeamento()

    def _atualizar_mapeamento(self) -> None:
        if not self._template_atual or not self._cabecalhos_fonte:
            return

        template = self._template_atual
        colunas = template.colunas

        if not colunas:
            self._tabela_mapeamento.setRowCount(1)
            self._tabela_mapeamento.setItem(
                0, 0, _item_ro("(Todas as colunas serão mantidas com limpeza básica)")
            )
            for c in range(1, 4):
                self._tabela_mapeamento.setItem(0, c, _item_ro(""))
            return

        mapa_auto = detectar_mapeamento_automatico(self._cabecalhos_fonte, colunas)
        self._tabela_mapeamento.setRowCount(len(colunas))
        self._combos_mapeamento: list[QComboBox] = []

        opcoes = ["— não mapear —"] + self._cabecalhos_fonte

        for row, col in enumerate(colunas):
            self._tabela_mapeamento.setItem(row, 0, _item_ro(col.nome_exibido))
            self._tabela_mapeamento.setItem(row, 1, _item_ro(TIPOS_CAMPO.get(col.tipo, col.tipo)))
            obrig = "✓" if col.obrigatorio else ""
            item_obrig = _item_ro(obrig)
            if col.obrigatorio:
                item_obrig.setForeground(QColor("#e55"))
            self._tabela_mapeamento.setItem(row, 2, item_obrig)

            combo = QComboBox()
            combo.setStyleSheet("background:#2a1a4e; color:white; padding:3px;")
            combo.addItems(opcoes)

            fonte_mapeada = mapa_auto.get(col.nome_alvo, "")
            if fonte_mapeada and fonte_mapeada in self._cabecalhos_fonte:
                combo.setCurrentText(fonte_mapeada)

            self._tabela_mapeamento.setCellWidget(row, 3, combo)
            self._combos_mapeamento.append(combo)

    def _obter_mapeamento_atual(self) -> dict[str, str]:
        if not self._template_atual or not self._template_atual.colunas:
            return {}
        mapa: dict[str, str] = {}
        for i, col in enumerate(self._template_atual.colunas):
            if i >= len(self._combos_mapeamento):
                break
            selecionado = self._combos_mapeamento[i].currentText()
            if selecionado != "— não mapear —":
                mapa[col.nome_alvo] = selecionado
        return mapa

    def _executar_organizacao(self) -> None:
        if not self._dados_fonte:
            QMessageBox.warning(self, "Sem dados", "Carregue um arquivo primeiro.")
            return
        if not self._template_atual:
            return

        mapeamento = self._obter_mapeamento_atual()

        try:
            self._resultado = organizar(
                self._cabecalhos_fonte,
                self._dados_fonte,
                self._template_atual,
                mapeamento,
                remover_duplicatas=self._chk_remover_dup.isChecked(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao organizar", str(exc))
            return

        self._exibir_resultado()
        self._ir_para(2)

    def _exibir_resultado(self) -> None:
        res = self._resultado
        if res is None:
            return

        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cards = [
            ("Total original", str(res.total_original), "#aaa"),
            ("Linhas limpas", str(len(res.dados)), "#4CAF50"),
            ("Erros", str(res.total_erros), "#e55" if res.total_erros else "#4CAF50"),
            ("Avisos", str(res.total_avisos), "#FFA726" if res.total_avisos else "#4CAF50"),
            ("Duplicatas", str(len(res.indices_duplicatas)), "#888"),
        ]
        for titulo, valor, cor in cards:
            card = QWidget()
            card.setStyleSheet("background:#1a1a2e; border-radius:8px; padding:10px; border:1px solid #333;")
            cl = QVBoxLayout(card)
            lt = QLabel(titulo)
            lt.setStyleSheet("color:#aaa; font-size:10px; font-family:Montserrat;")
            lv = QLabel(valor)
            lv.setStyleSheet(f"color:{cor}; font-size:22px; font-weight:bold; font-family:Montserrat;")
            cl.addWidget(lt)
            cl.addWidget(lv)
            self._cards_layout.addWidget(card)

        dups_reais = set()
        for idx in res.indices_duplicatas:
            dups_reais.add(idx + 2)

        _preencher_tabela_preview(
            self._tabela_resultado,
            res.cabecalhos,
            res.dados,
            max_linhas=500,
            linhas_erro=res.linhas_com_erro,
            linhas_aviso=res.linhas_com_aviso,
        )

        if res.problemas:
            linhas_prob = []
            for p in res.problemas[:200]:
                icone = "❌" if p.nivel == "erro" else "⚠️"
                linhas_prob.append(f"{icone}  Linha {p.linha}  |  {p.coluna}  →  {p.mensagem}")
            self._txt_problemas.setPlainText("\n".join(linhas_prob))
        else:
            self._txt_problemas.setPlainText("✓  Nenhum problema encontrado. Dados prontos para exportação.")

        pode_importar = (
            self._db is not None
            and self._template_atual is not None
            and self._template_atual.nome in ("Produtos", "Clientes")
            and res.total_erros == 0
        )
        self._btn_importar_bd.setVisible(pode_importar)
        if pode_importar:
            self._btn_importar_bd.setText(
                f"Importar {len(res.dados)} registro(s) → {self._template_atual.nome}"
            )

    def _importar_para_bd(self) -> None:
        res = self._resultado
        if res is None or self._db is None or self._template_atual is None:
            return

        nome_template = self._template_atual.nome
        resposta = QMessageBox.question(
            self, "Confirmar importação",
            f"Importar {len(res.dados)} linha(s) para a tabela de {nome_template.lower()}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        erros = 0
        for linha in res.dados:
            try:
                if nome_template == "Produtos" and len(linha) >= 4:
                    self._db.cadastrar_produto(
                        str(linha[0] or ""),
                        str(linha[1] or ""),
                        float(linha[2] or 0),
                        int(linha[3] or 0),
                        int(linha[4]) if len(linha) > 4 and linha[4] else 5,
                        str(linha[5]) if len(linha) > 5 and linha[5] else "",
                    )
                elif nome_template == "Clientes" and len(linha) >= 2:
                    self._db.cadastrar_cliente(
                        str(linha[0] or ""),
                        str(linha[1] or ""),
                        str(linha[2]) if len(linha) > 2 and linha[2] else "",
                        str(linha[3]) if len(linha) > 3 and linha[3] else "",
                    )
            except Exception:
                erros += 1

        ok = len(res.dados) - erros
        msg = f"{ok} registro(s) importado(s) com sucesso."
        if erros:
            msg += f"\n{erros} linha(s) com erro foram ignoradas."
        QMessageBox.information(self, "Importação concluída", msg)

    def _exportar_excel(self) -> None:
        if not self._resultado:
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar Excel", "planilha_organizada.xlsx", "Excel (*.xlsx)")
        if not caminho:
            return
        try:
            exportar_excel(caminho, "Dados", self._resultado.cabecalhos, [tuple(r) for r in self._resultado.dados])
            QMessageBox.information(self, "Exportado", f"Salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _exportar_csv(self) -> None:
        if not self._resultado:
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", "planilha_organizada.csv", "CSV (*.csv)")
        if not caminho:
            return
        try:
            exportar_csv(caminho, self._resultado.cabecalhos, [tuple(r) for r in self._resultado.dados])
            QMessageBox.information(self, "Exportado", f"Salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _criar_template(self) -> None:
        dialog = _DialogCriarTemplate(self._cabecalhos_fonte, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        novo = dialog.template()
        self._todos_templates.append(novo)
        self._combo_template.addItem("◎ " + novo.nome)
        self._combo_template.setCurrentIndex(self._combo_template.count() - 1)

    def _salvar_template(self) -> None:
        if self._template_atual is None:
            return
        if self._template_atual.builtin:
            QMessageBox.information(
                self, "Template embutido",
                "Templates embutidos não podem ser sobrescritos.\n"
                "Use 'Criar template do zero' para fazer uma cópia personalizada."
            )
            return
        try:
            caminho = self._template_atual.salvar(_PASTA_TEMPLATES)
            QMessageBox.information(self, "Salvo", f"Template salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar", str(exc))


class _DialogCriarTemplate(QDialog):
    def __init__(self, colunas_sugeridas: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Criar Novo Template")
        self.resize(680, 500)
        self._colunas_sugeridas = colunas_sugeridas

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        self._nome = QLineEdit()
        self._nome.setPlaceholderText("Ex: Fornecedores Regional")
        self._descricao = QLineEdit()
        self._descricao.setPlaceholderText("Descrição breve do uso deste template")
        form.addRow("Nome:", self._nome)
        form.addRow("Descrição:", self._descricao)
        layout.addLayout(form)

        lbl = QLabel("Colunas do template (uma por linha, formato: nome_interno | Nome Exibido | tipo | obrigatorio)")
        lbl.setStyleSheet("color:#aaa; font-size:11px; font-family:Montserrat;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        lbl_tipos = QLabel(f"Tipos disponíveis: {', '.join(TIPOS_CAMPO.keys())}")
        lbl_tipos.setStyleSheet("color:#777; font-size:10px; font-family:Montserrat;")
        layout.addWidget(lbl_tipos)

        self._tabela_colunas = QTableWidget()
        self._tabela_colunas.setColumnCount(4)
        self._tabela_colunas.setHorizontalHeaderLabels(
            ["Nome interno", "Nome exibido", "Tipo", "Obrigatório"]
        )
        self._tabela_colunas.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabela_colunas.setRowCount(len(colunas_sugeridas) or 1)

        for i, col in enumerate(colunas_sugeridas):
            self._tabela_colunas.setItem(i, 0, QTableWidgetItem(col.lower().replace(" ", "_")))
            self._tabela_colunas.setItem(i, 1, QTableWidgetItem(col))

            combo_tipo = QComboBox()
            combo_tipo.addItems(list(TIPOS_CAMPO.keys()))
            self._tabela_colunas.setCellWidget(i, 2, combo_tipo)

            chk = QCheckBox()
            chk.setChecked(True)
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self._tabela_colunas.setCellWidget(i, 3, chk_widget)

        layout.addWidget(self._tabela_colunas)

        btn_add = QPushButton("+ Adicionar coluna")
        btn_add.clicked.connect(self._adicionar_linha)
        layout.addWidget(btn_add)

        botoes = QHBoxLayout()
        btn_ok = QPushButton("Criar Template")
        btn_ok.setStyleSheet(_ESTILO_BTN_PRIMARIO)
        btn_ok.clicked.connect(self._validar)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        botoes.addStretch()
        botoes.addWidget(btn_cancel)
        botoes.addWidget(btn_ok)
        layout.addLayout(botoes)

    def _adicionar_linha(self) -> None:
        row = self._tabela_colunas.rowCount()
        self._tabela_colunas.setRowCount(row + 1)
        combo = QComboBox()
        combo.addItems(list(TIPOS_CAMPO.keys()))
        self._tabela_colunas.setCellWidget(row, 2, combo)
        chk = QCheckBox()
        chk.setChecked(False)
        chk_w = QWidget()
        chk_l = QHBoxLayout(chk_w)
        chk_l.addWidget(chk)
        chk_l.setAlignment(Qt.AlignCenter)
        chk_l.setContentsMargins(0, 0, 0, 0)
        self._tabela_colunas.setCellWidget(row, 3, chk_w)

    def _validar(self) -> None:
        if not self._nome.text().strip():
            QMessageBox.warning(self, "Nome obrigatório", "Informe um nome para o template.")
            return
        self.accept()

    def template(self) -> Template:
        colunas: list[Coluna] = []
        for row in range(self._tabela_colunas.rowCount()):
            nome_int_item = self._tabela_colunas.item(row, 0)
            nome_ext_item = self._tabela_colunas.item(row, 1)
            combo_tipo = self._tabela_colunas.cellWidget(row, 2)
            chk_w = self._tabela_colunas.cellWidget(row, 3)

            if not nome_int_item or not nome_int_item.text().strip():
                continue

            tipo: TipoCampo = combo_tipo.currentText() if combo_tipo else "texto"
            obrig = False
            if chk_w:
                chk = chk_w.findChild(QCheckBox)
                if chk:
                    obrig = chk.isChecked()

            colunas.append(Coluna(
                nome_alvo=nome_int_item.text().strip(),
                nome_exibido=(nome_ext_item.text().strip() if nome_ext_item else nome_int_item.text().strip()),
                tipo=tipo,
                obrigatorio=obrig,
                transformacoes=["trim"],
            ))

        return Template(
            nome=self._nome.text().strip(),
            descricao=self._descricao.text().strip(),
            colunas=colunas,
            builtin=False,
        )
