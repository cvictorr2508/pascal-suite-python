# Refatoração 27 — registro de regiões PaScal para workloads Python

## Objetivo

Resolver o Issue #3: registrar corretamente regiões manuais do PaScal durante a execução de workloads Python/Gurobi, sem fabricar nem pós-processar a telemetria produzida pelo Analyzer.

`region_energy` não faz parte desta refatoração e permanece tratado separadamente no Issue #4.

## Diagnóstico

A Refatoração 26 corrigiu a ABI `ctypes` de `_pascal_start/_pascal_stop` e eliminou o `SIGSEGV`, porém o processo Python continuou sem produzir `data[*].regions["1"]`.

A Refatoração 27 isolou a diferença entre o executável C nativo e o processo Python:

1. **Matriz de loader — job NPAD 2069965**
   - `baseline`, `LD_PRELOAD` e `RTLD_GLOBAL` executaram sem crash;
   - nenhum modo registrou a região `1`;
   - conclusão: momento/escopo do carregamento da `.so` não é a causa.

2. **Matriz de alvo linkado — job NPAD 2070698**
   - `linked_selftest` registrou região nativa com duração aproximada de `1.999993 s`;
   - `exec()` para Python e `fork()+exec()` para Python não registraram regiões;
   - conclusão: `_pascal_start/_pascal_stop` precisam ser executados no processo nativo reconhecido pelo Analyzer.

3. **Native region proxy — job NPAD 2070730**
   - o Analyzer iniciou diretamente um supervisor ELF linkado com `libmpascalops.so`;
   - o Python enviou `START/STOP` por pipes e aguardou ACK;
   - a região `1` apareceu no JSON nativo do Analyzer;
   - duração PaScal: `2.000082016 s` para uma janela Python de aproximadamente `2 s`;
   - 14 testes passaram naquele estágio.

## Solução de produção

A arquitetura final mantém o Analyzer como soberano da medição:

```text
pascalanalyzer
    |
    v
supervisor ELF linkado com libmpascalops
    |
    +-- inicia gurobi_runner.py
    |
    +-- recebe START/STOP por pipes
    |
    +-- executa _pascal_start/_pascal_stop no próprio processo
```

No Python, a API permanece:

```python
with pascal_region(1):
    model.optimize()
```

Quando os descritores do proxy estão presentes, `pascal_region()` usa IPC. O processo Python não carrega `libmpascalops.so` nesse caminho. O fallback `ctypes` é carregado de forma lazy somente quando solicitado fora do proxy.

## Componentes permanentes

- `src/pascalpy/instrumentation/native/pascal_region_proxy.c` — supervisor nativo;
- `src/pascalpy/instrumentation/proxy_builder.py` — compilação/linkagem determinística do supervisor no diretório de saída;
- `src/pascalpy/instrumentation/pascalops.py` — seleção de backend proxy/ctypes e protocolo START/STOP;
- `src/pascalpy/adapters/gurobi_adapter.py` — faz o Analyzer executar diretamente o supervisor ELF;
- `src/pascalpy/runners/gurobi_runner.py` — mantém `model.optimize()` como única região `1` e registra o backend no metadata.

## Validação Gurobi

### Smoke 1 core — job NPAD 2070776

O caminho completo `rodar_yaml.py -> GurobiFileAdapter -> pascalanalyzer -> supervisor -> gurobi_runner.py` terminou `COMPLETED / 0:0`.

Resultados registrados pelo validador:

- `backend = proxy`;
- `threads_requested = 1`;
- `threads_effective = 1`;
- região `1` presente;
- duração da região PaScal: `0.060197830 s`;
- `Gurobi Runtime`: `0.059804916 s`;
- solve wall clock: `0.060487831 s`;
- `proxy_smoke_valid = true`.

A região PaScal acompanha a janela de `model.optimize()` com diferença submilissegundo.

### Carregamento lazy

Após o smoke, o fallback `ctypes` foi tornado lazy para evitar a mensagem espúria `Pascal not running` durante simples import/test discovery. A regressão correspondente verifica que importar `pascalops` em subprocesso limpo não toca no runtime nativo.

A suíte final foi executada novamente no NPAD e passou integralmente, sem `Pascal not running` nem `Bad file descriptor`.

### Strong scaling estrutural [1, 2, 4] x 1

O gate final foi executado no NPAD com `dummy.mps`, recursos `[1, 2, 4]` e uma repetição por configuração. O gate passou integralmente.

Foram validadas, para cada configuração:

- região `1` presente no JSON nativo;
- backend `proxy`;
- `Threads requested == Threads effective == cores`;
- afinidade contendo exatamente o número de CPUs da configuração;
- métricas Gurobi presentes;
- duração PaScal compatível com `Gurobi Runtime` e solve wall clock.

Não foi exigido speedup monotônico porque `dummy.mps` é um workload estrutural, não um benchmark de desempenho.

## Critérios de aceite do Issue #3

- [x] workload Python produz `data[*].regions["1"]`;
- [x] tempos da região são compatíveis com a janela medida;
- [x] nenhum `SIGSEGV/-11`;
- [x] nenhum pós-processamento do JSON PaScal;
- [x] `model.optimize()` permanece como única região `1` do runner;
- [x] strong scaling estrutural preserva `cores == Threads`;
- [x] import do pacote não provoca probe espúrio do runtime PaScal.

## Limite conhecido

A disponibilidade de `region_energy` na instalação `pascalsuite/2025-07-08` do NPAD não é resolvida aqui. Esse tema permanece no Issue #4 e não bloqueia o registro correto das regiões manuais implementado nesta refatoração.
