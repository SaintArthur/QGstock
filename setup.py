import cx_Freeze
import os
import sys

executables = [
    cx_Freeze.Executable(
        script='PyStock - App.py', 
        icon='View/Imagens/Logo Ico.ico', 
        base='Win32GUI'
    )
]

cx_Freeze.setup(
    name="PyStock",
    version="1.0",
    description="Aplicativo PyStock",
    options={
        'build_exe': {
            'packages': [
                'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 
                'mysql.connector', 'os', 'sys', 
                'openpyxl.drawing.image', 'datetime', 'time', 
                'tkinter.filedialog', 'openpyxl'
            ],
            'include_files': [
                'View/',  # Inclui a pasta com subpastas.
                'Base xls.xlsx'  # Inclui o arquivo Excel.
            ] 
        }
    },
    executables=executables
)