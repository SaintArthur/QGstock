from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLineEdit,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


_COR_ALERTA = QColor(255, 200, 200)
_COR_ALERTA_HOVER = QColor(255, 170, 170)


def item_readonly(valor: Any) -> QTableWidgetItem:
    cell = QTableWidgetItem(str(valor) if valor is not None else "")
    cell.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    return cell


class TabelaFiltrada(QWidget):
    linha_editada = pyqtSignal(int)
    linha_excluida = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._busca = QLineEdit()
        self._busca.setPlaceholderText("Pesquisar...")
        self._busca.setClearButtonEnabled(True)
        self._busca.setStyleSheet(
            "padding: 6px 10px; border-radius: 6px; "
            "border: 1px solid #444; font-family: Montserrat;"
        )
        self._busca.textChanged.connect(self._aplicar_filtro)
        layout.addWidget(self._busca)

        self._tabela = QTableWidget()
        self._tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabela.setAlternatingRowColors(True)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tabela.customContextMenuRequested.connect(self._exibir_menu)
        layout.addWidget(self._tabela)

        self._linhas_originais: list[tuple[Any, ...]] = []
        self._cabecalhos: list[str] = []
        self._colunas_alerta: tuple[int, int] | None = None

    @property
    def tabela(self) -> QTableWidget:
        return self._tabela

    def preencher(
        self,
        cabecalhos: list[str],
        linhas: list[tuple[Any, ...]],
        colunas_alerta: tuple[int, int] | None = None,
    ) -> None:
        self._cabecalhos = cabecalhos
        self._linhas_originais = linhas
        self._colunas_alerta = colunas_alerta
        self._busca.clear()
        self._renderizar(linhas)

    def linha_selecionada_index(self) -> int | None:
        indices = self._tabela.selectedItems()
        if not indices:
            return None
        return self._tabela.currentRow()

    def dado_linha(self, row: int, col: int) -> str:
        item = self._tabela.item(row, col)
        return item.text() if item else ""

    def _renderizar(self, linhas: list[tuple[Any, ...]]) -> None:
        self._tabela.setColumnCount(len(self._cabecalhos))
        self._tabela.setHorizontalHeaderLabels(self._cabecalhos)
        self._tabela.setRowCount(len(linhas))
        self._tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for row_idx, linha in enumerate(linhas):
            for col_idx, valor in enumerate(linha):
                self._tabela.setItem(row_idx, col_idx, item_readonly(valor))

            if self._colunas_alerta is not None:
                col_qtde, col_min = self._colunas_alerta
                try:
                    if int(linha[col_qtde]) <= int(linha[col_min]):
                        for c in range(len(linha)):
                            cell = self._tabela.item(row_idx, c)
                            if cell:
                                cell.setBackground(_COR_ALERTA)
                except (TypeError, ValueError):
                    pass

    def _aplicar_filtro(self, texto: str) -> None:
        texto = texto.strip().lower()
        if not texto:
            self._renderizar(self._linhas_originais)
            return

        filtradas = [
            linha
            for linha in self._linhas_originais
            if any(texto in str(v).lower() for v in linha if v is not None)
        ]
        self._renderizar(filtradas)

    def _exibir_menu(self, pos: Any) -> None:
        row = self._tabela.rowAt(pos.y())
        if row < 0:
            return

        menu = QMenu(self)
        act_editar = menu.addAction("Editar")
        act_excluir = menu.addAction("Excluir")
        act_excluir.setIcon(self.style().standardIcon(self.style().SP_TrashIcon))

        escolha = menu.exec_(self._tabela.viewport().mapToGlobal(pos))
        if escolha == act_editar:
            self.linha_editada.emit(row)
        elif escolha == act_excluir:
            self.linha_excluida.emit(row)
