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

O archive PyInstaller e os quatro binários históricos materializados via Git LFS
também foram eliminados: nenhum contém a implementação do contrato regional.

### Agregação regional `-a 1`

O gate com `--rpls sysfs`, `--rple sysfs`, ambos e `--ragt acc` produziu JSON
válido, mas nenhum caso declarou ou gravou mapas RAPL por região. `-a 1` adicionou
somente `imbalances` e `measurements`; portanto essa opção não controla a energia
regional e não deve entrar no caminho de produção.

### Evidência quantitativa do RAPL amostrado

No probe de aproximadamente 3 segundos, `--rple sysfs --rpls sysfs` produziu:

- energia global: `150.727032 J`;
- potência média amostrada: `50.377923 W`;
- energia da região 1 estimada por integração trapezoidal: `151.133062 J`;
- diferença relativa contra a energia global: `0.269%`.

As amostras nativas são, portanto, suficientes para derivar energia regional sem
reescrever o JSON. A estratégia escolhida é manter o Analyzer como fonte da
telemetria e realizar a integração no Viewer. O adaptador passa a solicitar
`--rple` como controle global e `--rpls` como série de potência.

O JSON histórico `testeIM.json` continua útil como referência de formato, mas não
como oráculo numérico: em regiões repetidas, o valor salvo é compatível com a
última ocorrência, não com a soma ou união temporal de todas as ocorrências.
