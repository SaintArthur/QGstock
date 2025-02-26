import os
import sys
import time
import mysql.connector
import datetime
import openpyxl.drawing.image

from tkinter.filedialog import askdirectory
from tkinter import Tk

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QMessageBox
from View.PY.FrmLogin import Ui_login
from View.PY.FrmAdmin import Ui_FrmAdmin
from View.PY.FrmColaborador import Ui_FrmColaborador
from openpyxl import *

banco = mysql.connector.connect(
    host='localhost',
    port='3306',
    user='root',
    passwd='',
    database='banco_pystock'
)

cursor = banco.cursor()

class FrmLogin(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_login()
        self.ui.setupUi(self)
        self.ui.pushButton.clicked.connect(lambda: self.logar())

    def logar(self):
        global window, UserLogado
        cursor.execute("SELECT * FROM login")
        logins = cursor.fetchall()
        usuario = self.ui.lineEdit.text()
        senha = self.ui.lineEdit_2.text()
        for login in logins:
            if usuario == login[0] and senha == login[1]:
                UserLogado = login[3]
                if login[2] == 'admin':
                    window.close()
                    window = FrmAdmin()
                    window.show()
                if login[2] == 'colaborador':
                    window.close()
                    window = FrmColaborador()
                    window.show()
                break

class FrmAdmin(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_FrmAdmin()
        self.ui.setupUi(self)
        self.ui.lbl_seja_bem_vindo.setText(f'Seja Bem-Vindo(a) - {UserLogado}')
        self.ui.lbl_seja_bem_vindo.setFixedWidth(500)

        self.ui.btn_home.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.pg_home))
        self.ui.btn_colaboradores.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.pg_colaboradores))
        self.ui.btn_cadastrar_colaboradores.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.pg_cadastro_colaboradores))
        self.ui.btn_alterar_colaboradores.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.alterar_colaboradores))
        self.ui.btn_cadastro.clicked.connect(self.CadastroColaboradores)

        self.ui.btn_fornecedores.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.pg_fornecedores))
        self.ui.btn_adicionar_forncedores.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.pg_cadastrar_fornecedores))
        self.ui.btn_editar_fornecedores.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.pg_alterar_fornecedores))
        self.ui.btn_cadastrar_forncedores.clicked.connect(self.CadastrarFornecedores)

        self.ui.btn_produtos.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.pg_produtos))
        self.ui.btn_cadastrar_produto.clicked.connect(lambda: self.ui.Telas_do_menu.setCurrentWidget(self.ui.pg_cadastar_produtos))

        self.AtualizaTabelasLogin()
        self.AtualizaTabelasFornecedores()
        self.AtualizaTabelasProdutos()

    def CadastroColaboradores(self):
        login = self.ui.line_login.text()
        senha = self.ui.line_senha.text()
        nome = self.ui.line_nome.text()
        cpf = self.ui.line_cpf.text()
        email = self.ui.line_email.text()
        telefone = self.ui.line_telefone.text()
        cargo = self.ui.line_cargo.text()
        nivel = 'colaborador' if self.ui.radio_colaborador.isChecked() else 'admin'

        comando_SQL = 'INSERT INTO login (login, senha, nivel, nome, cpf, email, telefone, cargo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)'
        dados = (login, senha, nivel, nome, cpf, email, telefone, cargo)
        cursor.execute(comando_SQL, dados)
        banco.commit()
        self.AtualizaTabelasLogin()

    def CadastrarFornecedores(self):
        nome = self.ui.line_cadastrar_nome_fornecedores.text()
        endereco = self.ui.line_cadastrar_endereco_fornecedores.text()
        contato = self.ui.line_cadastrar_contato_fornecedores.text()
        comando_SQL = 'INSERT INTO fornecedores VALUES (%s,%s,%s)'
        dados = (nome, endereco, contato)
        cursor.execute(comando_SQL, dados)
        banco.commit()
        self.AtualizaTabelasFornecedores()

    def AtualizaTabelasLogin(self):
        cursor.execute('SELECT * FROM login')
        self.ui.tabela_colaboradores.clearContents()

    def AtualizaTabelasFornecedores(self):
        cursor.execute('SELECT * FROM fornecedores')
        self.ui.tabela_fornecedores.clearContents()

    def AtualizaTabelasProdutos(self):
        cursor.execute('SELECT * FROM produtos')
        self.ui.tabela_produto.clearContents()

class FrmColaborador(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_FrmColaborador()
        self.ui.setupUi(self)

window = FrmLogin()
window.show()