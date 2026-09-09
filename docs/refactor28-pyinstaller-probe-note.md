# Refactoring 28 — PyInstaller probe note

The first archive-inspection probe failed before opening `pascalanalyzer`. The
default NPAD package index exposed PyInstaller only through version 4.10, while
the active interpreter was Python 3.13.

Official Python 3.13 support was introduced in PyInstaller 6.10. The probe
therefore requires `pyinstaller>=6.10,<7` and, when the default index does not
provide that range, retries explicitly against `https://pypi.org/simple` inside
the isolated `.refactor28-pyi-tools/venv` environment.

The probe only lists the CArchive/PYZ embedded in the ELF recursively with
`pyi-archive_viewer`. It installs nothing in the working research environment
and modifies no institutional PaScal file.

