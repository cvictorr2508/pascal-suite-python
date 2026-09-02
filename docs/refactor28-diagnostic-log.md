# Refatoração 28 — log de diagnóstico

## Estado atual

### Job 2071093 — matriz de backends RAPL

- `--rple sysfs`: região manual e energia global presentes; sem `region_energy`.
- `--rpls sysfs`: região manual e amostras RAPL presentes; sem `region_energy`.
- qualquer caso contendo `perf`: Analyzer aborta antes de produzir JSON com `ModuleNotFoundError: No module named 'profiler'`.
- o Analyzer retorna código 0 mesmo nesses abortos, portanto sucesso exige também JSON válido.

### Job 2071932 — runtime perf

- `perf_event_paranoid=-1`;
- `power/energy-pkg/` e `power/energy-ram/` disponíveis;
- `perf stat` mede RAPL diretamente com sucesso;
- `python_profiler_available=false`;
- Analyzer contém assinaturas de bundle PyInstaller.

Conclusão: o bloqueio do backend `perf` está no runtime/empacotamento do Analyzer, não no hardware, kernel ou permissões do NPAD.

### Release oficial

O `pascalanalyzer` em `lappsufrn/pascal-releases/master` é byte a byte idêntico ao snapshot NPAD `2025-07-08` (mesmo SHA256 e BuildID). Reinstalar o release oficial atual não altera o comportamento.

### Inspeção PyInstaller

A primeira tentativa de instalar `pyinstaller>=6,<7` no ambiente de diagnóstico falhou porque o índice pip padrão expôs somente versões até 4.10. Como o Python usado é 3.13, o probe foi corrigido para exigir PyInstaller `>=6.10,<7`, versão que já suporta Python 3.13, e fazer fallback explícito para `https://pypi.org/simple` dentro do venv diagnóstico isolado.

O próximo gate é listar recursivamente o archive PyInstaller e determinar se `profiler`, `rapl`, `perf` e `sensor` estão presentes dentro do `PYZ-00.pyz`.
