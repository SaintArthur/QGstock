import cx_Freeze

executables = [
    cx_Freeze.Executable(
        script="app.py",
        icon="View/Imagens/Logo Ico.ico",
        base="Win32GUI",
        target_name="QGstock.exe",
    )
]

cx_Freeze.setup(
    name="QGstock",
    version="2.0",
    description="Sistema de Controle de Estoque QGstock",
    options={
        "build_exe": {
            "packages": [
                "PyQt5.QtCore",
                "PyQt5.QtGui",
                "PyQt5.QtWidgets",
                "mysql.connector",
                "openpyxl",
                "openpyxl.drawing.image",
                "csv",
                "hashlib",
                "datetime",
            ],
            "include_files": [
                "View/",
                "config.py",
                "database.py",
                "views/",
                "utils/",
            ],
            "excludes": ["tkinter"],
        }
    },
    executables=executables,
)
