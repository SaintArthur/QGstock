from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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
    TIPOS_CAMPO,
    detectar_mapeamento_automatico,
    listar_templates_salvos,
    organizar,
)

_PASTA_TEMPLATES = Path(__file__).parent.parent / "templates"

_COR_ERRO = QColor(255, 180, 180)
_COR_AVISO = QColor(255, 230, 150)
_COR_OK = QColor(180, 240, 180)

_BTN_PRIMARIO = (
    "background:#9F3FFA;color:white;font-weight:bold;"
    "padding:9px 20px;border-radius:7px;font-family:Montserrat;font-size:13px;"
)
_BTN_SECUNDARIO = (
    "padding:8px 16px;border-radius:7px;border:1px solid #444;"
    "font-family:Montserrat;color:white;background:transparent;"
)


def _item_ro(valor: Any, cor: QColor | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(str(valor) if valor is not None else "")
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    if cor:
        item.setBackground(cor)
    return item


def _preencher_preview(
    tabela: QTableWidget,
    cabecalhos: list[str],
    linhas: list[list[Any]],
    max_linhas: int = 500,
    linhas_erro: set[int] | None = None,
    linhas_aviso: set[int] | None = None,
) -> None:
    exibir = linhas[:max_linhas]
    tabela.setColumnCount(len(cabecalhos))
    tabela.setHorizontalHeaderLabels(cabecalhos)
    tabela.setRowCount(len(exibir))
    tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    tabela.horizontalHeader().setStretchLastSection(True)
    tabela.verticalHeader().setVisible(True)

    erros = linhas_erro or set()
    avisos = linhas_aviso or set()

    for row_idx, linha in enumerate(exibir):
        linha_real = row_idx + 2
        if linha_real in erros:
            cor = _COR_ERRO
        elif linha_real in avisos:
            cor = _COR_AVISO
        else:
            cor = _COR_OK if linhas_erro is not None else None

        for col_idx, valor in enumerate(linha):
            tabela.setItem(row_idx, col_idx, _item_ro(valor, cor))


class OrganizadorWidget(QWidget):
    def __init__(self, db: Any = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self._cabecalhos_fonte: list[str] = []
        self._dados_fonte: list[list[Any]] = []
        self._arquivo_atual: str = ""
        self._template_atual: Template | None = None
        self._resultado: ResultadoOrganizacao | None = None
        self._combos_mapeamento: list[QComboBox] = []
        self._todos_templates: list[Template] = []

        self._construir_ui()
        self._ir_para(0)

    def _construir_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._construir_cabecalho())

        self._stack = QStackedWidget()
        self._stack.addWidget(self._pagina_arquivo())
        self._stack.addWidget(self._pagina_template())
        self._stack.addWidget(self._pagina_resultado())
        layout.addWidget(self._stack)

        layout.addWidget(self._construir_rodape())

    def _construir_cabecalho(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:#0d0d1a;border-bottom:2px solid #9F3FFA;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(20, 12, 20, 12)

        lbl = QLabel("Organizador de Planilhas")
        lbl.setStyleSheet("color:white;font-size:16px;font-weight:bold;font-family:Montserrat;")
        layout.addWidget(lbl)

        layout.addStretch()

        self._passos: list[QLabel] = []
        for nome in ["1. Arquivo", "2. Template", "3. Resultado"]:
            lbl_p = QLabel(nome)
            lbl_p.setStyleSheet("color:#888;font-family:Montserrat;font-size:12px;padding:4px 14px;")
            layout.addWidget(lbl_p)
            self._passos.append(lbl_p)

        return w

    def _construir_rodape(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:#0d0d1a;border-top:1px solid #1e1e3a;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(20, 10, 20, 10)

        self._btn_voltar = QPushButton("← Voltar")
        self._btn_voltar.setStyleSheet(_BTN_SECUNDARIO)
        self._btn_voltar.clicked.connect(self._passo_anterior)
        layout.addWidget(self._btn_voltar)

        layout.addStretch()

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color:#888;font-family:Montserrat;font-size:12px;")
        layout.addWidget(self._lbl_status)

        layout.addStretch()

        self._btn_proximo = QPushButton("Próximo →")
        self._btn_proximo.setStyleSheet(_BTN_PRIMARIO)
        self._btn_proximo.clicked.connect(self._passo_proximo)
        layout.addWidget(self._btn_proximo)

        return w

    def _pagina_arquivo(self) -> QWidget:
        pg = QWidget()
        pg.setStyleSheet("background:#12121f;")
        layout = QVBoxLayout(pg)
        layout.setContentsMargins(30, 24, 30, 16)
        layout.setSpacing(14)

        lbl = QLabel("Selecione o arquivo para organizar")
        lbl.setStyleSheet("color:white;font-size:14px;font-weight:bold;font-family:Montserrat;")
        layout.addWidget(lbl)

        zona = QWidget()
        zona.setStyleSheet(
            "border:2px dashed #9F3FFA;border-radius:12px;background:#1a1a2e;padding:20px;"
        )
        zona_layout = QVBoxLayout(zona)
        zona_layout.setAlignment(Qt.AlignCenter)

        self._lbl_arquivo = QLabel("Nenhum arquivo selecionado")
        self._lbl_arquivo.setStyleSheet("color:#888;font-family:Montserrat;font-size:12px;")
        self._lbl_arquivo.setAlignment(Qt.AlignCenter)
        zona_layout.addWidget(self._lbl_arquivo)

        btn = QPushButton("Escolher arquivo (Excel ou CSV)")
        btn.setStyleSheet(_BTN_PRIMARIO)
        btn.setFixedWidth(280)
        btn.clicked.connect(self._selecionar_arquivo)
        zona_layout.addWidget(btn, alignment=Qt.AlignCenter)

        lbl_fmt = QLabel("Formatos aceitos: .xlsx  .xls  .csv")
        lbl_fmt.setStyleSheet("color:#555;font-size:11px;font-family:Montserrat;")
        lbl_fmt.setAlignment(Qt.AlignCenter)
        zona_layout.addWidget(lbl_fmt)

        layout.addWidget(zona)

        self._lbl_info = QLabel("")
        self._lbl_info.setStyleSheet("color:#9F3FFA;font-family:Montserrat;font-size:11px;")
        layout.addWidget(self._lbl_info)

        grp = QGroupBox("Prévia dos dados (primeiras 20 linhas)")
        grp.setStyleSheet(
            "QGroupBox{color:white;font-family:Montserrat;border:1px solid #2a2a3e;"
            "border-radius:8px;margin-top:8px;padding-top:10px;}"
            "QGroupBox::title{subcontrol-origin:margin;padding:0 6px;}"
        )
        g_layout = QVBoxLayout(grp)
        self._tabela_preview = QTableWidget()
        self._tabela_preview.setStyleSheet(
            "QTableWidget{background:#1a1a2e;color:white;gridline-color:#2a2a3e;}"
            "QHeaderView::section{background:#0d0d1a;color:#aaa;padding:5px;}"
        )
        self._tabela_preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabela_preview.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabela_preview.verticalHeader().setDefaultSectionSize(22)
        g_layout.addWidget(self._tabela_preview)
        layout.addWidget(grp)

        return pg

    def _pagina_template(self) -> QWidget:
        pg = QWidget()
        pg.setStyleSheet("background:#12121f;")
        layout = QHBoxLayout(pg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        painel_esq = QWidget()
        painel_esq.setMaximumWidth(280)
        esq = QVBoxLayout(painel_esq)
        esq.setSpacing(10)

        lbl_t = QLabel("Template")
        lbl_t.setStyleSheet("color:white;font-size:13px;font-weight:bold;font-family:Montserrat;")
        esq.addWidget(lbl_t)

        self._combo_template = QComboBox()
        self._combo_template.setStyleSheet(
            "QComboBox{background:#1a1a2e;color:white;padding:6px;border:1px solid #333;border-radius:6px;}"
            "QComboBox QAbstractItemView{background:#1a1a2e;color:white;}"
        )
        self._combo_template.currentIndexChanged.connect(self._ao_mudar_template)
        esq.addWidget(self._combo_template)
        self._recarregar_templates()

        self._lbl_desc = QLabel("")
        self._lbl_desc.setStyleSheet("color:#888;font-size:11px;font-family:Montserrat;")
        self._lbl_desc.setWordWrap(True)
        esq.addWidget(self._lbl_desc)

        btn_novo = QPushButton("+ Criar template do zero")
        btn_novo.setStyleSheet(_BTN_SECUNDARIO)
        btn_novo.clicked.connect(self._criar_template)
        esq.addWidget(btn_novo)

        btn_salvar = QPushButton("Salvar template atual")
        btn_salvar.setStyleSheet(_BTN_SECUNDARIO)
        btn_salvar.clicked.connect(self._salvar_template)
        esq.addWidget(btn_salvar)

        self._chk_dup = QCheckBox("Remover linhas duplicadas")
        self._chk_dup.setChecked(True)
        self._chk_dup.setStyleSheet("color:white;font-family:Montserrat;font-size:12px;")
        esq.addWidget(self._chk_dup)

        esq.addStretch()

        btn_org = QPushButton("Organizar planilha →")
        btn_org.setStyleSheet(_BTN_PRIMARIO)
        btn_org.clicked.connect(self._executar)
        esq.addWidget(btn_org)

        layout.addWidget(painel_esq)

        painel_dir = QWidget()
        dir_layout = QVBoxLayout(painel_dir)
        dir_layout.setSpacing(8)

        lbl_m = QLabel("Mapeamento de Colunas")
        lbl_m.setStyleSheet("color:white;font-size:13px;font-weight:bold;font-family:Montserrat;")
        dir_layout.addWidget(lbl_m)

        lbl_h = QLabel(
            "Para cada coluna do template selecione a coluna correspondente do seu arquivo. "
            "O sistema detecta automaticamente quando os nomes são parecidos."
        )
        lbl_h.setStyleSheet("color:#666;font-size:11px;font-family:Montserrat;")
        lbl_h.setWordWrap(True)
        dir_layout.addWidget(lbl_h)

        self._tabela_mapeamento = QTableWidget()
        self._tabela_mapeamento.setStyleSheet(
            "QTableWidget{background:#1a1a2e;color:white;gridline-color:#2a2a3e;}"
            "QHeaderView::section{background:#0d0d1a;color:#aaa;padding:6px;}"
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
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._cards_layout = QHBoxLayout()
        layout.addLayout(self._cards_layout)

        grp = QGroupBox("Dados Organizados")
        grp.setStyleSheet(
            "QGroupBox{color:white;font-family:Montserrat;border:1px solid #2a2a3e;"
            "border-radius:8px;margin-top:6px;padding-top:10px;}"
            "QGroupBox::title{subcontrol-origin:margin;padding:0 6px;}"
        )
        g = QVBoxLayout(grp)

        lbl_leg = QLabel(
            "  ■ Verde = OK     ■ Amarelo = aviso     ■ Vermelho = erro (campo inválido)"
        )
        lbl_leg.setStyleSheet("color:#888;font-size:10px;font-family:Montserrat;")
        g.addWidget(lbl_leg)

        self._tabela_resultado = QTableWidget()
        self._tabela_resultado.setStyleSheet(
            "QTableWidget{background:#1a1a2e;color:white;gridline-color:#2a2a3e;}"
            "QHeaderView::section{background:#0d0d1a;color:#aaa;padding:6px;}"
        )
        self._tabela_resultado.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabela_resultado.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabela_resultado.verticalHeader().setDefaultSectionSize(22)
        g.addWidget(self._tabela_resultado)
        layout.addWidget(grp)

        grp_prob = QGroupBox("Problemas Encontrados")
        grp_prob.setStyleSheet(
            "QGroupBox{color:white;font-family:Montserrat;border:1px solid #2a2a3e;"
            "border-radius:8px;margin-top:4px;padding-top:10px;}"
            "QGroupBox::title{subcontrol-origin:margin;padding:0 6px;}"
        )
        grp_prob.setMaximumHeight(130)
        gp = QVBoxLayout(grp_prob)
        self._txt_prob = QTextEdit()
        self._txt_prob.setReadOnly(True)
        self._txt_prob.setStyleSheet(
            "background:#0d0d1a;color:#ddd;font-family:Consolas,monospace;font-size:11px;"
            "border:none;"
        )
        gp.addWidget(self._txt_prob)
        layout.addWidget(grp_prob)

        acoes = QHBoxLayout()
        self._btn_importar_bd = QPushButton("Importar para Banco de Dados")
        self._btn_importar_bd.setStyleSheet(_BTN_PRIMARIO)
        self._btn_importar_bd.setVisible(False)
        self._btn_importar_bd.clicked.connect(self._importar_bd)
        acoes.addWidget(self._btn_importar_bd)

        acoes.addStretch()

        btn_xlsx = QPushButton("Exportar Excel")
        btn_xlsx.setStyleSheet(_BTN_SECUNDARIO)
        btn_xlsx.clicked.connect(self._exportar_excel)
        acoes.addWidget(btn_xlsx)

        btn_csv = QPushButton("Exportar CSV")
        btn_csv.setStyleSheet(_BTN_SECUNDARIO)
        btn_csv.clicked.connect(self._exportar_csv)
        acoes.addWidget(btn_csv)

        btn_novo = QPushButton("Nova planilha")
        btn_novo.setStyleSheet(_BTN_SECUNDARIO)
        btn_novo.clicked.connect(self._reiniciar)
        acoes.addWidget(btn_novo)

        layout.addLayout(acoes)
        return pg

    def _ir_para(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        for i, lbl in enumerate(self._passos):
            if i == idx:
                lbl.setStyleSheet(
                    "color:#9F3FFA;font-family:Montserrat;font-size:12px;"
                    "padding:4px 14px;font-weight:bold;border-bottom:2px solid #9F3FFA;"
                )
            elif i < idx:
                lbl.setStyleSheet(
                    "color:#4CAF50;font-family:Montserrat;font-size:12px;padding:4px 14px;"
                )
            else:
                lbl.setStyleSheet(
                    "color:#888;font-family:Montserrat;font-size:12px;padding:4px 14px;"
                )
        self._btn_voltar.setVisible(idx > 0)
        self._btn_proximo.setVisible(idx < 2)

    def _passo_proximo(self) -> None:
        atual = self._stack.currentIndex()
        if atual == 0 and not self._dados_fonte:
            QMessageBox.warning(self, "Arquivo necessário", "Selecione um arquivo antes de continuar.")
            return
        self._ir_para(atual + 1)

    def _passo_anterior(self) -> None:
        self._ir_para(self._stack.currentIndex() - 1)

    def _reiniciar(self) -> None:
        self._cabecalhos_fonte = []
        self._dados_fonte = []
        self._arquivo_atual = ""
        self._resultado = None
        self._lbl_arquivo.setText("Nenhum arquivo selecionado")
        self._lbl_arquivo.setStyleSheet("color:#888;font-family:Montserrat;font-size:12px;")
        self._lbl_info.setText("")
        self._tabela_preview.setRowCount(0)
        self._ir_para(0)

    def _selecionar_arquivo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar planilha", "",
            "Planilhas (*.xlsx *.xls *.csv);;Excel (*.xlsx *.xls);;CSV (*.csv)",
        )
        if not caminho:
            return
        try:
            ext = os.path.splitext(caminho)[1].lower()
            cab, dados = (
                importar_excel(caminho) if ext in (".xlsx", ".xls") else importar_csv(caminho)
            )
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
        self._lbl_arquivo.setStyleSheet(
            "color:#9F3FFA;font-family:Montserrat;font-size:12px;font-weight:bold;"
        )
        tamanho = os.path.getsize(caminho)
        self._lbl_info.setText(
            f"{len(dados)} linhas  •  {len(cab)} colunas  •  {tamanho // 1024} KB"
        )

        _preencher_preview(self._tabela_preview, cab, dados, max_linhas=20)
        self._atualizar_mapeamento()

    def _recarregar_templates(self) -> None:
        self._combo_template.blockSignals(True)
        self._combo_template.clear()
        self._todos_templates = list(TEMPLATES_BUILTIN)
        self._todos_templates += listar_templates_salvos(_PASTA_TEMPLATES)
        for t in self._todos_templates:
            prefixo = "★ " if t.builtin else "◎ "
            self._combo_template.addItem(prefixo + t.nome)
        self._combo_template.blockSignals(False)
        self._combo_template.setCurrentIndex(0)
        self._ao_mudar_template(0)

    def _ao_mudar_template(self, idx: int) -> None:
        if 0 <= idx < len(self._todos_templates):
            self._template_atual = self._todos_templates[idx]
            self._lbl_desc.setText(self._template_atual.descricao)
            self._atualizar_mapeamento()

    def _atualizar_mapeamento(self) -> None:
        if not self._template_atual or not self._cabecalhos_fonte:
            return

        colunas = self._template_atual.colunas
        if not colunas:
            self._tabela_mapeamento.setRowCount(1)
            self._tabela_mapeamento.setItem(
                0, 0, _item_ro("Todas as colunas serão mantidas com limpeza básica")
            )
            for c in range(1, 4):
                self._tabela_mapeamento.setItem(0, c, _item_ro(""))
            self._combos_mapeamento = []
            return

        mapa_auto = detectar_mapeamento_automatico(self._cabecalhos_fonte, colunas)
        self._tabela_mapeamento.setRowCount(len(colunas))
        self._combos_mapeamento = []
        opcoes = ["— não mapear —"] + self._cabecalhos_fonte

        for row, col in enumerate(colunas):
            self._tabela_mapeamento.setItem(row, 0, _item_ro(col.nome_exibido))
            self._tabela_mapeamento.setItem(row, 1, _item_ro(TIPOS_CAMPO.get(col.tipo, col.tipo)))
            item_obrig = _item_ro("✓" if col.obrigatorio else "")
            if col.obrigatorio:
                item_obrig.setForeground(QColor("#e55"))
            self._tabela_mapeamento.setItem(row, 2, item_obrig)

            combo = QComboBox()
            combo.setStyleSheet(
                "QComboBox{background:#2a1a4e;color:white;padding:3px;border:none;}"
                "QComboBox QAbstractItemView{background:#1a1a2e;color:white;}"
            )
            combo.addItems(opcoes)
            mapeado = mapa_auto.get(col.nome_alvo, "")
            if mapeado and mapeado in self._cabecalhos_fonte:
                combo.setCurrentText(mapeado)
            self._tabela_mapeamento.setCellWidget(row, 3, combo)
            self._combos_mapeamento.append(combo)

    def _obter_mapeamento(self) -> dict[str, str]:
        if not self._template_atual or not self._template_atual.colunas:
            return {}
        mapa: dict[str, str] = {}
        for i, col in enumerate(self._template_atual.colunas):
            if i < len(self._combos_mapeamento):
                sel = self._combos_mapeamento[i].currentText()
                if sel != "— não mapear —":
                    mapa[col.nome_alvo] = sel
        return mapa

    def _executar(self) -> None:
        if not self._dados_fonte or not self._template_atual:
            QMessageBox.warning(self, "Sem dados", "Carregue um arquivo primeiro.")
            return

        try:
            self._resultado = organizar(
                self._cabecalhos_fonte,
                self._dados_fonte,
                self._template_atual,
                self._obter_mapeamento(),
                remover_duplicatas=self._chk_dup.isChecked(),
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

        for titulo, valor, cor in [
            ("Total original", str(res.total_original), "#aaa"),
            ("Linhas limpas", str(len(res.dados)), "#4CAF50"),
            ("Erros", str(res.total_erros), "#e55" if res.total_erros else "#4CAF50"),
            ("Avisos", str(res.total_avisos), "#FFA726" if res.total_avisos else "#4CAF50"),
            ("Duplicatas removidas", str(len(res.indices_duplicatas)), "#888"),
        ]:
            card = QWidget()
            card.setStyleSheet(
                "background:#1a1a2e;border-radius:8px;padding:10px;border:1px solid #2a2a3e;"
            )
            cl = QVBoxLayout(card)
            lt = QLabel(titulo)
            lt.setStyleSheet("color:#888;font-size:10px;font-family:Montserrat;")
            lv = QLabel(valor)
            lv.setStyleSheet(
                f"color:{cor};font-size:20px;font-weight:bold;font-family:Montserrat;"
            )
            cl.addWidget(lt)
            cl.addWidget(lv)
            self._cards_layout.addWidget(card)

        _preencher_preview(
            self._tabela_resultado,
            res.cabecalhos,
            res.dados,
            max_linhas=500,
            linhas_erro=res.linhas_com_erro,
            linhas_aviso=res.linhas_com_aviso,
        )

        if res.problemas:
            linhas_txt = [
                f"{'❌' if p.nivel == 'erro' else '⚠️'}  Linha {p.linha}  |  {p.coluna}  →  {p.mensagem}"
                for p in res.problemas[:300]
            ]
            self._txt_prob.setPlainText("\n".join(linhas_txt))
        else:
            self._txt_prob.setPlainText(
                "✓  Nenhum problema encontrado. Dados prontos para exportação."
            )

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

    def _importar_bd(self) -> None:
        res = self._resultado
        if res is None or self._db is None or self._template_atual is None:
            return

        nome = self._template_atual.nome
        resp = QMessageBox.question(
            self, "Confirmar importação",
            f"Importar {len(res.dados)} linha(s) para {nome.lower()}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        erros = 0
        for linha in res.dados:
            try:
                if nome == "Produtos" and len(linha) >= 4:
                    self._db.cadastrar_produto(
                        str(linha[0] or ""), str(linha[1] or ""),
                        float(linha[2] or 0), int(linha[3] or 0),
                        int(linha[4]) if len(linha) > 4 and linha[4] else 5,
                        str(linha[5]) if len(linha) > 5 and linha[5] else "",
                    )
                elif nome == "Clientes" and len(linha) >= 2:
                    self._db.cadastrar_cliente(
                        str(linha[0] or ""), str(linha[1] or ""),
                        str(linha[2]) if len(linha) > 2 and linha[2] else "",
                        str(linha[3]) if len(linha) > 3 and linha[3] else "",
                    )
            except Exception:
                erros += 1

        ok = len(res.dados) - erros
        msg = f"{ok} registro(s) importado(s)."
        if erros:
            msg += f"\n{erros} linha(s) ignoradas."
        QMessageBox.information(self, "Importação concluída", msg)

    def _exportar_excel(self) -> None:
        if not self._resultado:
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar Excel", "planilha_organizada.xlsx", "Excel (*.xlsx)"
        )
        if not caminho:
            return
        try:
            exportar_excel(
                caminho, "Dados",
                self._resultado.cabecalhos,
                [tuple(r) for r in self._resultado.dados],
            )
            QMessageBox.information(self, "Exportado", f"Salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))

    def _exportar_csv(self) -> None:
        if not self._resultado:
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar CSV", "planilha_organizada.csv", "CSV (*.csv)"
        )
        if not caminho:
            return
        try:
            exportar_csv(
                caminho,
                self._resultado.cabecalhos,
                [tuple(r) for r in self._resultado.dados],
            )
            QMessageBox.information(self, "Exportado", f"Salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))

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
                "Templates embutidos não podem ser alterados.\n"
                "Use 'Criar template do zero' para personalizar.",
            )
            return
        try:
            caminho = self._template_atual.salvar(_PASTA_TEMPLATES)
            QMessageBox.information(self, "Salvo", f"Template salvo em:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar", str(exc))


class OrganizadorDialog(QDialog):
    def __init__(self, db: Any = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Organizador de Planilhas")
        self.resize(1100, 700)
        self.setMinimumSize(880, 580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._widget = OrganizadorWidget(db=db, parent=self)
        layout.addWidget(self._widget)


class _DialogCriarTemplate(QDialog):
    def __init__(
        self, colunas_sugeridas: list[str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Criar Novo Template")
        self.resize(660, 480)
        self._colunas = colunas_sugeridas

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        self._nome = QLineEdit()
        self._nome.setPlaceholderText("Ex: Fornecedores Regional Sul")
        self._descricao = QLineEdit()
        self._descricao.setPlaceholderText("Descrição breve")
        form.addRow("Nome:", self._nome)
        form.addRow("Descrição:", self._descricao)
        layout.addLayout(form)

        lbl = QLabel(f"Tipos: {', '.join(TIPOS_CAMPO.keys())}")
        lbl.setStyleSheet("color:#888;font-size:11px;")
        layout.addWidget(lbl)

        self._tbl = QTableWidget()
        self._tbl.setColumnCount(4)
        self._tbl.setHorizontalHeaderLabels(["Nome interno", "Nome exibido", "Tipo", "Obrigatório"])
        self._tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tbl.setRowCount(max(len(colunas_sugeridas), 1))

        for i, col in enumerate(colunas_sugeridas):
            self._tbl.setItem(i, 0, QTableWidgetItem(col.lower().replace(" ", "_")))
            self._tbl.setItem(i, 1, QTableWidgetItem(col))
            combo = QComboBox()
            combo.addItems(list(TIPOS_CAMPO.keys()))
            self._tbl.setCellWidget(i, 2, combo)
            self._adicionar_checkbox(i, checked=True)

        layout.addWidget(self._tbl)

        btn_add = QPushButton("+ Adicionar coluna")
        btn_add.clicked.connect(self._add_linha)
        layout.addWidget(btn_add)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _adicionar_checkbox(self, row: int, checked: bool = False) -> None:
        chk = QCheckBox()
        chk.setChecked(checked)
        w = QWidget()
        l = QHBoxLayout(w)
        l.addWidget(chk)
        l.setAlignment(Qt.AlignCenter)
        l.setContentsMargins(0, 0, 0, 0)
        self._tbl.setCellWidget(row, 3, w)

    def _add_linha(self) -> None:
        row = self._tbl.rowCount()
        self._tbl.setRowCount(row + 1)
        combo = QComboBox()
        combo.addItems(list(TIPOS_CAMPO.keys()))
        self._tbl.setCellWidget(row, 2, combo)
        self._adicionar_checkbox(row, checked=False)

    def _validar(self) -> None:
        if not self._nome.text().strip():
            QMessageBox.warning(self, "Campo obrigatório", "Informe o nome do template.")
            return
        self.accept()

    def template(self) -> Template:
        colunas: list[Coluna] = []
        for row in range(self._tbl.rowCount()):
            ni = self._tbl.item(row, 0)
            ne = self._tbl.item(row, 1)
            ct = self._tbl.cellWidget(row, 2)
            cw = self._tbl.cellWidget(row, 3)
            if not ni or not ni.text().strip():
                continue
            obrig = False
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk:
                    obrig = chk.isChecked()
            colunas.append(Coluna(
                nome_alvo=ni.text().strip(),
                nome_exibido=(ne.text().strip() if ne else ni.text().strip()),
                tipo=ct.currentText() if ct else "texto",
                obrigatorio=obrig,
                transformacoes=["trim"],
            ))
        return Template(
            nome=self._nome.text().strip(),
            descricao=self._descricao.text().strip(),
            colunas=colunas,
            builtin=False,
        )
