# Módulo Clientes (cadastro com N empresas/CNPJ) + vínculo com tarefas

**Data:** 2026-09-05
**Autor:** felipedrn93
**Branch:** main
**Plano:** [docs/superpowers/plans/2026-09-03-clientes.md](../docs/superpowers/plans/2026-09-03-clientes.md)
**Spec:** [docs/superpowers/specs/2026-09-03-clientes-cadastro-design.md](../docs/superpowers/specs/2026-09-03-clientes-cadastro-design.md)

## Contexto

O fork é usado por uma consultoria que organiza o trabalho **por cliente**, e o Plane não tem esse conceito: o mais próximo seria abrir um projeto por cliente (inviável, porque o mesmo cliente aparece em vários projetos) ou usar rótulos (sem integridade, sem cadastro, sem CNPJ).

Esta mod acrescenta um cadastro de **Clientes** no menu do workspace — cada cliente com N **empresas**, cada empresa com CNPJ validado — e permite vincular cada tarefa a um cliente, com filtro, agrupamento e coluna na planilha, do mesmo jeito que já acontece com Ciclo ou Estado.

## Decisões de design

1. **Escopo workspace.** Clientes são do workspace, compartilhados por todos os projetos.
2. **O vínculo da tarefa é com o Cliente, não com a Empresa.** As empresas são dados cadastrais; a tarefa aponta para o cliente.
3. **Um cliente por tarefa** — FK única em `Issue`, comportando-se como Estado/Responsável (filtrável e agrupável), não como Rótulos.
4. **Entidades próprias com FK**, em vez de rótulos reaproveitados ou JSON genérico na `Issue`. O group-by do Plane assume colunas reais, e a FK dá integridade referencial.
5. **Status Ativo/Inativo no Cliente**, não em cada empresa. Cliente inativo some do dropdown de tarefas, mas continua aparecendo nas tarefas que já o referenciam.
6. **Exclusão bloqueada quando há tarefas vinculadas** — a API devolve `issue_count` e a UI oferece "Inativar" no lugar.
7. **CNPJ validado** pelos dígitos verificadores e único por workspace; guardado só com dígitos, exibido com máscara.
8. **Escrita para Admin e Membro**; Convidado apenas lê (`WorkspaceEntityPermission`).
9. **URL em inglês (`/clients`), rótulo em português ("Clientes")** — consistência com o resto do código, tradução via i18n.

Decisões tomadas durante a implementação, que divergem do plano original:

10. **A "aba Tarefas" do detalhe virou um botão "Ver N tarefas"** que leva a `/{slug}/workspace-views/all-issues/?client_id={clientId}`. O `AllIssueLayoutRoot` é acoplado ao `globalViewId` da rota e ao `useGlobalView`; embutir a lista na página de cliente exigiria refatorar um componente central de todas as views globais.

    **Correção posterior:** a primeira versão do botão usava `?client=` acreditando que a view global já lia filtros da query string pelo `routeFilters`. **Não lia.** O `routeFilters` era montado no `AllIssueLayoutRoot`, repassado por `views/helper.tsx` e chegava ao `WorkspaceSpreadsheetRoot` apenas como declaração de tipo — nunca era lido. Era código morto desde a migração para rich filters, e a requisição saía com `filters={}`. Foi preciso implementar a capacidade de verdade (ver `getRichFiltersFromSearchParams`, abaixo).

11. **O filtro foi implementado no caminho de _rich filters_**, não no `components/issues/filters/filters-selection/` que o plano citava — esse par (`filters/header/filters/cycle.tsx` + `applied-filters/cycle.tsx`) virou código órfão depois da migração e não tem nenhum importador. O chip do filtro aplicado é genérico (`components/rich-filters/filters-row`), então não precisou de componente próprio.
12. **A lista de clientes do filtro vem direto de `useClient().activeClients`**, e não plumbada pelos HOCs (`project-level.tsx` / `workspace-level.tsx`) como acontece com ciclos e módulos — clientes são de workspace, não de projeto.
13. **O dropdown seguiu o padrão do `dropdowns/cycle`** (`ComboDropDown` + `DropdownButton` + `Combobox.Options` com `position: fixed` e `usePopper`). O plano pedia `createPortal`, mas o `position: fixed` do combobox resolve o mesmo problema do peek overview (ver Pitfalls) e mantém o componente idêntico aos vizinhos.
14. **Ordenação por cliente na planilha ficou fora de escopo.** Não existe ordenação server-side por nome de cliente, então as duas chaves de ordem caem em `sort_order` e o menu do header fica inerte — mesmo tratamento dado à coluna de parent breadcrumb ([reordenar-colunas-spreadsheet.md](reordenar-colunas-spreadsheet.md)).

## Modelo de dados

```
Client (workspace)                ClientCompany (client)
  name          unique/workspace    name
  is_active     default True        cnpj    14 dígitos, unique/workspace
```

`Issue.client` é FK nullable com `on_delete=SET_NULL`.

## Arquivos criados

### Backend

- `apps/api/plane/utils/cnpj.py` — validação dos dígitos verificadores e normalização.
- `apps/api/plane/db/models/client.py` — `Client` e `ClientCompany`.
- `apps/api/plane/db/migrations/0127_client_clientcompany.py`, `0128_issue_client.py`.
- `apps/api/plane/app/serializers/client.py`, `apps/api/plane/app/urls/client.py`, `apps/api/plane/app/views/client/` — CRUD em `/api/workspaces/<slug>/clients/`.
- `apps/api/plane/tests/unit/` — `utils/test_cnpj.py`, `models/test_client.py`, `serializers/test_client.py`, `views/test_client.py`, `utils/test_issue_filters_client.py`, `utils/test_grouper_client.py`.

### Frontend

- `packages/types/src/client.ts` — `TClient`, `TClientCompany`.
- `packages/services/src/client/` — `ClientService`.
- `packages/utils/src/work-item-filters/configs/filters/client.ts` — config do filtro rich.
- `packages/utils/src/work-item-filters/route-filters.ts` — converte a query string em condições de rich filter.
- `apps/web/core/store/client.store.ts`, `apps/web/core/hooks/store/use-client.ts`.
- `apps/web/app/(all)/[workspaceSlug]/(projects)/clients/` — `layout.tsx`, `header.tsx`, `page.tsx`, `[clientId]/page.tsx`.
- `apps/web/core/components/clients/` — `clients-list-root.tsx`, `client-form-modal.tsx`, `client-detail-root.tsx`, `cnpj.ts`, `index.ts`.
- `apps/web/core/components/dropdowns/client.tsx` — dropdown de cliente.
- `apps/web/core/components/issues/issue-layouts/spreadsheet/columns/client-column.tsx`.
- `packages/i18n/src/locales/<19 locales>/clients.json`.

## Arquivos modificados

### Backend

- `plane/db/models/issue.py` — FK `Issue.client`; `plane/db/models/__init__.py`.
- `plane/app/serializers/issue.py` (+ `__init__.py`) — `client_id` no payload da issue.
- `plane/app/views/issue/base.py`, `issue/sub_issue.py` — `client_id` nas projeções `.values()`.
- `plane/app/urls/__init__.py`, `plane/app/views/__init__.py` — registro das rotas/views.
- `plane/utils/issue_filters.py` — `filter_client` (com `"None"` → `client_id__isnull`).
- `plane/utils/grouper.py` — `client_id` em `required_fields` e um branch em `issue_group_values`.
- `plane/utils/filters/filterset.py` — `client_id` / `client_id__in` no `IssueFilterSet`.
- `plane/utils/filters/converters.py` — `"client": "client_id"` e `client_id` em `DEFAULT_UUID_FIELDS`.

### Tipos e constantes

- `packages/types/src/issues/issue.ts` — `client_id` em `TIssue`; `packages/types/src/index.ts`.
- `packages/types/src/view-props.ts` — `client` em `IIssueFilterOptions`, `IIssueDisplayProperties`, `TIssueGroupByOptions`, `TIssueParams` e `client_id` em `WORK_ITEM_FILTER_PROPERTY_KEYS`.
- `packages/types/src/issues.ts` — `client` em `GroupByColumnTypes`.
- `packages/constants/src/workspace.ts` — item de sidebar.
- `packages/constants/src/issue/common.ts` — display property, `SPREADSHEET_PROPERTY_LIST` / `_DETAILS`, `FILTER_TO_ISSUE_MAP`, `ISSUE_GROUP_BY_OPTIONS` e as enums de group by servidor.
- `packages/constants/src/issue/filter.ts` — `client_id` nos `filters` por página, `client` nos `group_by`/`sub_group_by` e `EServerGroupByToFilterOptions`.
- `packages/i18n/src/constants/namespaces.ts` — namespace `clients`.

### Componentes e store do web

- `apps/web/core/store/root.store.ts` — registro do `ClientStore`.
- `apps/web/core/store/issue/issue-details/issue.store.ts` — `client_id` na allowlist do `addIssueToStore`.
- `apps/web/core/store/issue/helpers/base-issues.store.ts` — `client` em `ISSUE_GROUP_BY_KEY` e `ISSUE_FILTER_DEFAULT_DATA`.
- `apps/web/app/routes/core.ts` — rotas `/clients` e `/clients/:clientId`.
- `apps/web/ce/components/workspace/sidebar/helper.tsx`, `apps/web/core/components/workspace/sidebar/sidebar-item.tsx` — ícone e liberação do item estático.
- `apps/web/core/components/issues/issue-detail/sidebar.tsx` — linha "Cliente".
- `apps/web/core/components/issues/issue-layouts/utils.tsx` — `getClientColumns` no `groupByColumnMap`.
- `apps/web/ce/components/issues/issue-layouts/utils.tsx` — coluna e ícone da planilha.
- `apps/web/ce/hooks/work-item-filters/use-work-item-filters-config.tsx` — `clientFilterConfig`.
- `apps/web/core/components/issues/issue-layouts/roots/all-issue-layout-root.tsx` — filtros da query string entram no `initialWorkItemFilters`; `views/helper.tsx` e `spreadsheet/roots/workspace-root.tsx` perderam a prop `routeFilters`, que era código morto.

## Fluxo end-to-end

1. `/clients` lista os clientes do workspace (`ClientStore.fetchClients` → `GET /api/workspaces/<slug>/clients/`), com busca por nome ou CNPJ e alternância de inativos.
2. O modal cria/edita cliente e empresas; o CNPJ é mascarado no input e normalizado (só dígitos) no submit. Na edição, as empresas são diferenciadas contra o snapshot anterior: as sem `id` são criadas, as alteradas atualizadas e as que sumiram removidas.
3. No detalhe da tarefa, o `ClientDropdown` grava `client_id` via `issueOperations.update`. Clientes inativos ficam fora das opções, mas continuam aparecendo no botão quando já vinculados.
4. Filtro e agrupamento por cliente chegam ao backend como `client_id` (rich filters) ou `client` (converter legado) e são resolvidos direto na coluna da `Issue`.
5. Excluir um cliente com tarefas vinculadas é rejeitado pela API com `issue_count`; a lista mostra o toast de bloqueio com a ação "Inativar".

## Como testar

```bash
# backend — precisa do stack local no ar; o Python do host nao tem pytest-django
docker compose -f docker-compose-local.yml up -d plane-db plane-redis plane-mq plane-minio
docker exec plane-test sh -c 'cd /code && python -m pytest -m unit -q'
# baseline em 2026-09-05: 168 passaram, 5 falharam (pre-existentes, ver Pitfalls), 105 deselecionadas
python -m ruff check plane/ && python -m ruff format --check plane/

# frontend
pnpm turbo run check:types --filter=web
pnpm turbo run check:lint --filter=web     # 1001 warnings, 0 errors (mesmo baseline de antes da mod)
pnpm --filter @plane/i18n run check:sync
```

O util de filtro por URL tem 11 casos em `packages/utils/tests/route-filters.test.ts`:

```bash
pnpm --filter @plane/utils run test
```

Roteiro manual, com `pnpm dev`:

1. A sidebar mostra "Clientes" logo abaixo de "Página Inicial".
2. Criar "Acme" com duas empresas e "Globex" com uma.
3. Repetir em "Globex" um CNPJ já usado por "Acme" → erro de duplicidade.
4. Um CNPJ com dígito verificador errado (`11222333000182`) → erro inline, modal não fecha.
5. Vincular tarefas a "Acme" pelo dropdown do detalhe; recarregar e conferir que persistiu.
6. Planilha: a coluna "Clientes" mostra o vínculo e edita inline.
7. Filtros → Cliente → "Acme"; salvar como view, sair e reabrir → filtro preservado.
8. Kanban → Agrupar por → Cliente; arrastar um card entre colunas altera o vínculo.
9. `/clients/<id>` lista as empresas com CNPJ mascarado e o botão "Ver N tarefas" leva à view global filtrada.
10. Excluir "Acme" com tarefas vinculadas → bloqueio com a opção de inativar.

## Pitfalls

- **Shadow allowlists de campos de issue.** Um campo novo na `Issue` precisa aparecer em _todos_ os lugares que listam campos explicitamente: serializers, as projeções `.values()` de `views/issue/base.py` e `sub_issue.py`, e o `addIssueToStore` de `issue.store.ts` no front. Faltando o último, o dropdown mostra "Nenhum" mesmo com o valor salvo no banco — mesmo sintoma do `recurrence_pattern` em [tarefas-recorrentes.md](tarefas-recorrentes.md#pitfalls--todos-os-lugares-onde-um-campo-novo-de-issue-precisa-aparecer).
- **`client_id` é escalar e NÃO entra no `FIELD_MAPPER` do `plane/utils/grouper.py`.** Esse mapa existe só para campos de array (`label_ids`, `assignee_ids`, `module_ids`). Escalares como `state_id`, `cycle_id` e `client_id` só precisam entrar em `required_fields` e ganhar um branch em `issue_group_values`.
- **O item de sidebar precisa estar em dois lugares.** Além de `WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS(_LINKS)` nos constants, a chave tem que entrar no array `staticItems` de `core/components/workspace/sidebar/sidebar-item.tsx` — sem isso o item simplesmente não renderiza.
- **Painel do dropdown no peek overview.** O peek é uma sidebar de 400px com `overflow-hidden`: um `Popover` do Headless UI salta para a borda direita da página. É preciso `usePopper` com o painel fora do fluxo (`position: fixed`, como o `dropdowns/cycle`, ou `createPortal`).
- **Group by por cliente toca seis lugares tipados.** Além de `TIssueGroupByOptions`, o TypeScript exige `GroupByColumnTypes`, `TIssueParams`, `EIssueGroupByToServerOptions`, `EIssueGroupBYServerToProperty` e `EServerGroupByToFilterOptions` — sem os três últimos o `issue-filter-helper.store.ts` não compila.
- **O menu de agrupamento é gateado por página.** `ISSUE_GROUP_BY_OPTIONS` só define os rótulos; quem decide o que aparece em cada tela é `ISSUE_DISPLAY_FILTERS_BY_PAGE[*].layoutOptions[*].display_filters.group_by`. O mesmo vale para os filtros, no array `filters` de cada página.
- **O pre-commit é mais estrito que o CI.** O hook roda `oxlint --deny-warnings` nos arquivos staged, enquanto o `check:lint` do web aceita até 11957 warnings. Tocar em arquivos legados com warnings pré-existentes (`base-issues.store.ts` tem 15) trava o commit sem que a mudança tenha introduzido nada — ver [divida-ci-web.md](divida-ci-web.md).
- **A suíte unitária do backend já chega com 5 falhas.** `utils/test_url.py` (3 casos de limite de comprimento em `contains_url`), `bg_tasks/test_copy_s3_objects.py` e `bg_tasks/test_work_item_link_task.py` reprovam desde antes desta mod — os arquivos de teste e os módulos que eles exercitam estão idênticos ao commit anterior à feature. Não confundir com regressão.
- **O container de teste não é um serviço do compose.** É o `plane-test` (imagem `plane-api`, `sleep infinity`, `/code` montado do host), criado à mão e com `requirements/test.txt` instalado no runtime — a imagem `plane-api` e o `Dockerfile.dev` só instalam `requirements/local.txt`, sem `pytest`. Se o container for removido, é preciso recriar e reinstalar. No Git Bash, `docker exec -w /code` falha com `Cwd must be an absolute path` (conversão de path do MSYS); usar `docker exec plane-test sh -c 'cd /code && ...'`.
- **`routeFilters` era código morto — filtro por URL não existia.** Antes desta mod, `?qualquer_coisa=` na view global não tinha efeito: a prop trafegava por três componentes e nunca era lida. Quem filtra hoje é `getRichFiltersFromSearchParams`, que aceita só as propriedades de coleção (`client_id`, `state_id`, `cycle_id`, …), monta condições `<prop>__in` e as combina com os filtros salvos da view via `mergeRouteFiltersIntoExpression`. Um grupo de rich filters **não aninha** (`TWorkItemFilterAndGroup` guarda condições, não grupos), por isso o merge trata três casos: expressão vazia, grupo `and` existente e condição solta.
- **Os locales não são um `translations.json` único.** Cada idioma é uma pasta com um arquivo por namespace, e um namespace novo precisa ser registrado em `packages/i18n/src/constants/namespaces.ts`; `pnpm --filter @plane/i18n run check:types` regenera `types/keys.generated.ts`.

## Fora de escopo

- Ordenação da planilha por nome de cliente (precisa de suporte server-side).
- Aba de tarefas embutida no detalhe do cliente (ver decisão 10).
- Múltiplos clientes por tarefa e vínculo direto com a empresa.
