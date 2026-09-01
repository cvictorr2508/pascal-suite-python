# Refatoração 27 — resultado da matriz de loader

## Job NPAD 2069965

A matriz `baseline` / `LD_PRELOAD` / `RTLD_GLOBAL` foi executada no mesmo nó (`r1i3n3`) sob `pascalanalyzer -t man`.

Resultado:

- job: `COMPLETED / 0:0`;
- 8 testes unitários: `OK`;
- `baseline`: `runs_with_region_1 = 0`;
- `preload`: `runs_with_region_1 = 0`;
- `rtld_global`: `runs_with_region_1 = 0`;
- nenhum modo sofreu `SIGSEGV/-11`.

## Conclusão

O momento/escopo do `dlopen` não explica a diferença entre o executável C nativo e o processo Python. Não há evidência para alterar `pascalops.py` para `RTLD_GLOBAL` nem para adicionar `LD_PRELOAD` ao wrapper de produção.

A diferença estrutural restante é que o controle C é um ELF linkado com `-lmpascalops`, enquanto o caminho Python apresentado ao Analyzer não possui `libmpascalops.so` em `DT_NEEDED`.

## Próximo teste

Usar um launcher C linkado com `-lmpascalops` como alvo direto do Analyzer e comparar:

1. `linked_selftest`: região nativa no próprio launcher (controle positivo);
2. `linked_exec`: launcher executa `exec()` do mesmo workload Python;
3. `linked_spawn`: launcher permanece vivo e executa o Python em processo filho.

Esse teste determina se o Analyzer depende de reconhecer um alvo ELF instrumentado antes da execução e se o contexto manual sobrevive a `exec()` ou pode ser herdado por um filho.

Nenhuma mudança de produção deve ser feita antes desse resultado.
