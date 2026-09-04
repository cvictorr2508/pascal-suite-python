# Refatoração 28 — nota do probe PyInstaller

O primeiro probe de inspeção do archive falhou antes de abrir o `pascalanalyzer`: o índice `pip` padrão do ambiente NPAD expôs PyInstaller somente até 4.10, enquanto o Python ativo é 3.13.

O suporte oficial a Python 3.13 foi introduzido no PyInstaller 6.10. Por isso o probe agora exige `pyinstaller>=6.10,<7` e, caso o índice padrão não disponibilize essa faixa, faz uma segunda tentativa explicitamente em `https://pypi.org/simple`, sempre dentro de `.refactor28-pyi-tools/venv`.

O objetivo permanece apenas listar recursivamente o CArchive/PYZ embutido no ELF usando `pyi-archive_viewer`; nenhum pacote é instalado no venv de trabalho e nenhum arquivo do PaScal institucional é modificado.
