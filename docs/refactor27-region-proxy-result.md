# Refatoração 27 — resultado do native region proxy

## Job NPAD 2070730

O job `2070730` terminou `COMPLETED / 0:0` no nó `r1i3n7`.

O supervisor ELF foi linkado com `libmpascalops.so`, permaneceu como alvo direto do `pascalanalyzer -t man` e executou os marcadores PaScal em resposta a comandos enviados pelo processo Python por pipes.

## Resultado

O JSON nativo do Analyzer contém:

- região: `1`;
- `start_line`: `100`;
- `stop_line`: `110`;
- filename: `diagnose_pascal_region_proxy.py`;
- duração: aproximadamente `2.000082 s`.

A janela Python usada no gate foi de aproximadamente `2 s`, portanto o handshake `START/ACK` e `STOP/ACK` delimitou corretamente o intervalo executado pelo filho Python.

O job reportou:

```text
proxy_region_1=true
proxy_region_1_duration_s=2.000082016
proxy_duration_compatible=true
```

Os 14 testes existentes naquele ponto passaram.

## Conclusão arquitetural

O Issue #3 possui agora um caminho de produção validado:

1. `pascalanalyzer` inicia diretamente um supervisor nativo linkado com `libmpascalops`;
2. o supervisor inicia o runner Python e fornece dois descritores de pipe;
3. `pascal_region()` envia `START/STOP` ao supervisor e aguarda ACK;
4. `_pascal_start/_pascal_stop` são executados no processo nativo reconhecido pelo Analyzer;
5. o JSON permanece integralmente produzido pelo Analyzer.

A implementação de produção foi promovida no mesmo draft PR:

- backend `proxy` automático em `pascalops.py`;
- fonte C de produção em `src/pascalpy/instrumentation/native/`;
- compilação determinística do supervisor no diretório de saída do experimento;
- `GurobiFileAdapter` usando o supervisor ELF como alvo direto do Analyzer;
- `gurobi_runner.py` mantendo `model.optimize()` como única região `1`.

O gate seguinte é um smoke Gurobi de `1 core x 1 repetição` usando `instances/dummy.mps`, validando região `1`, backend `proxy` e invariante de threads.

`region_energy` continua fora de escopo e permanece no Issue #4.
