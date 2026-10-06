# CNPJ opcional no cadastro de clientes

**Data:** 2026-10-06
**Autor:** felipedrn93
**Branch:** main
**Relacionada:** [mods/clientes-cadastro.md](clientes-cadastro.md)

## Contexto

No cadastro original ([mods/clientes-cadastro.md](clientes-cadastro.md)) toda empresa exigia um CNPJ válido, e o formulário validava até a linha vazia inicial — na prática, não dava para cadastrar um cliente sem informar um CNPJ. Muitas vezes não temos o CNPJ certo na hora, mas precisamos do cliente cadastrado para vincular às tarefas.

## Decisões de design

1. **CNPJ vazio é aceito**; se preenchido, continua validado (dígitos verificadores) e único por workspace.
2. **Vazio é guardado como `""`** (convenção do Django para `CharField`), não `NULL`.
3. **A unicidade ignora CNPJ vazio**: a constraint `unique_client_company_cnpj_per_workspace_when_not_deleted` ganhou `~Q(cnpj="")`, senão a segunda empresa sem CNPJ colidiria.
4. **Cliente sem empresa nenhuma é permitido**: uma linha de empresa totalmente vazia não é validada e é descartada no submit (o filtro de linhas vazias já existia). O nome da empresa só é exigido se a linha tiver CNPJ.
5. No detalhe do cliente, empresa sem CNPJ mostra "—".

## Arquivos criados

- `apps/api/plane/db/migrations/0130_clientcompany_cnpj_optional.py` — `cnpj` com `blank=True, default=""` e constraint recriada excluindo vazio.

## Arquivos modificados

- `apps/api/plane/db/models/client.py` — campo `cnpj` opcional, constraint, `__str__` sem `<>` vazio.
- `apps/api/plane/app/serializers/client.py` — `cnpj` com `required=False, allow_blank=True`; valida só quando informado.
- `apps/api/plane/app/views/client/base.py` — checagem de CNPJ duplicado só quando informado (no `create` usava `validated_data["cnpj"]`).
- `apps/web/core/components/clients/client-form-modal.tsx` — validações de nome/CNPJ da empresa toleram linha vazia e CNPJ vazio.
- `apps/web/core/components/clients/client-detail-root.tsx` — "—" quando sem CNPJ.
- Testes: `tests/unit/serializers/test_client.py` (`test_cnpj_is_optional`), `tests/unit/models/test_client.py` (`test_blank_cnpj_is_not_unique`).

## Como testar

1. Clientes → Novo cliente → só o nome, deixando a linha de empresa vazia → cria sem erro.
2. Novo cliente com empresa preenchida só com nome (sem CNPJ) → cria; detalhe mostra "—".
3. Duas empresas sem CNPJ (no mesmo ou em outro cliente) → ambas salvam.
4. CNPJ inválido ou duplicado continua sendo recusado.

## Pitfalls

- A mudança tem **migration**: no deploy é preciso `docker compose build api migrator` + `docker compose up migrator` antes de subir o `api` (ver CLAUDE.md).
