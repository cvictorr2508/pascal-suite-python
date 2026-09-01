# Refatoração 27 — resultado da matriz de alvo linkado

## Job NPAD 2070698

O job `2070698` terminou `COMPLETED / 0:0` no nó `r1i3n7`.

O launcher C possui `DT_NEEDED` para `libmpascalops.so` e resolve a biblioteca da instalação `pascalsuite/2025-07-08`.

### linked_selftest

O mesmo processo ELF chamado diretamente pelo `pascalanalyzer -t man` executou `pascal_start(9)` / `pascal_stop(9)` e produziu região `9` com duração de aproximadamente `1.999993 s`.

Resultado: **passou**.

### linked_exec

O launcher linkado fez `exec()` para o Python, que executou a região via binding Python.

Resultado: o JSON não contém `regions`.

### linked_spawn

O launcher linkado permaneceu vivo e executou o Python em um filho via `fork()` + `exec()`.

Resultado: o JSON não contém `regions`.

## Conclusão

`successful_target_modes=linked_selftest`.

O Analyzer/runtime manual da instalação atual associa a instrumentação ao processo nativo reconhecido. O contexto funcional de `libmpascalops` não se torna utilizável pelo processo Python após `exec()` e não é transferido de forma suficiente a um filho Python.

As hipóteses `LD_PRELOAD`, `RTLD_GLOBAL`, launcher + `exec` e launcher + `spawn` estão descartadas como correções de produção.

## Próximo gate

Validar um **supervisor nativo de regiões**: o processo linkado permanece como alvo do Analyzer e recebe do Python comandos `START/STOP` por pipes. O supervisor executa `_pascal_start/_pascal_stop` no próprio processo e confirma cada operação ao Python antes de prosseguir.

Critério de aceite do protótipo:

- região `1` aparece no JSON nativo do Analyzer;
- duração fica entre `1.5 s` e `2.5 s` para um workload Python de aproximadamente `2 s`;
- processo termina sem `SIGSEGV/-11`;
- nenhum JSON é reestruturado ou fabricado.
