# Filtro/ordenação por Data de finalização + filtro de Bloqueio

**Data:** 2026-06-02
**Autor:** felipedrn93
**Branch:** main

## Contexto

Faltavam dois recursos nos filtros de issues:

1. **Data de finalização** (`Issue.completed_at`, preenchido quando a issue entra num estado do
   grupo `completed`): poder **filtrar** por essa data, **ordenar** por ela e exibi-la como
   **coluna/campo** na planilha (menu Exibir), no mesmo padrão de "Criada em"/"Atualizada em".
2. **Bloqueio**: poder ver **apenas tarefas bloqueadas** ou **apenas não bloqueadas**.

O Plane tem dois mecanismos de filtro rodando juntos: o legado `issue_filters()` (dict, param por
campo) e o moderno **rich filters** (`IssueFilterSet` + `ComplexFilterBackend`, expressão JSON no
param `filters`). A UI de filtros do usuário usa o **rich filters**; é nele que as novas
propriedades foram registradas. A ordenação usa o param `order_by` → `order_issue_queryset`.

## Decisões de design

1. **Tudo no FilterSet compartilhado.** `IssueFilterSet` (em `plane/utils/filters/filterset.py`) é
   usado por projeto, arquivados, ciclo, módulo, view e "minhas issues". Adicionar as propriedades
   ali cobre **todas as telas de issues** de uma vez. `completed_at` entra em `Meta.fields` como
   `["exact", "range"]` (igual a `created_at`/`updated_at`); o `BaseFilterSet.get_filters()` já gera
   o `completed_at__exact` automaticamente.

2. **Bloqueio = bloqueador ainda em aberto (bloqueio "ativo").** Uma issue é considerada bloqueada
   quando possui relação `blocked_by` (reverse FK `issue_relation`, ver `relation.py`) **cujo
   bloqueador** (`related_issue`) está em estado dos grupos `backlog/unstarted/started` — ou seja,
   ignora bloqueios já resolvidos (bloqueador `completed`/`cancelled`). Implementado como
   `is_blocked = BooleanFilter(method="filter_is_blocked")`, cujo método usa **`Exists`/`~Exists`**
   (subconsulta correlacionada em `issue_relations.issue_id`) — `Q(Exists(...))` para "bloqueada" e
   `~Q(Exists(...))` para "não bloqueada". Optou-se por `Exists` em vez de join + `~Q`: **não
   multiplica linhas** (independe de `.distinct()` no queryset externo) e o caso negado vira um
   `NOT EXISTS` barato. Isso é essencial na visão global "Seu trabalho"
   (`WorkspaceUserProfileIssuesEndpoint`), cujo queryset **não** tem `.distinct()` e onde o
   `~Q` por join travava ("Not blocked" rodando pra sempre), enquanto no projeto (conjunto pequeno)
   era rápido.

3. **Ordenação por `completed_at` não exigiu mudança no backend.** `order_issue_queryset` já trata
   campos arbitrários no branch `else` (`order_by("completed_at"/"-completed_at", "-created_at")`).
   No front, basta `completed_at` estar em `TIssueOrderByOptions` e `ISSUE_ORDER_BY_OPTIONS` e nos
   arrays `order_by` das páginas.

4. **UI do filtro de bloqueio = single-select** "Blocked"/"Not blocked" (operador `exact`,
   valores `"true"`/`"false"`), renderizado pelo `SingleSelectFilterValueInput` já existente. O
   adapter monta a condição `is_blocked__exact = "true"|"false"`, validada contra
   `IssueFilterSet.base_filters`. O filtro de data de `completed_at` é cópia de `created_at`/
   `updated_at` (operadores `exact`/`range`), com a mesma semântica/UX (paridade intencional).

5. **"Data de finalização" como display property global** (`completed_on`), no padrão de
   `created_on`/`updated_on`: aparece no seletor de colunas da planilha, renderiza
   `issue.completed_at` e ordena pelo cabeçalho (`-completed_at`/`completed_at`). Default ligado
   (`?? true`), igual aos irmãos de data.

## Arquivos modificados

### Backend (`apps/api`)

- `plane/utils/filters/filterset.py` — `IssueFilterSet`: `completed_at` em `Meta.fields`;
  `is_blocked` (`BooleanFilter`, `distinct=True`) + método `filter_is_blocked`.

### Tipos (`packages/types`)

- `src/view-props.ts` — `WORK_ITEM_FILTER_PROPERTY_KEYS` += `completed_at`, `is_blocked`;
  `TIssueOrderByOptions` += `completed_at`/`-completed_at`; `IIssueDisplayProperties` += `completed_on`.

### Constantes (`packages/constants`)

- `src/issue/common.ts` — `ISSUE_ORDER_BY_OPTIONS` (+`-completed_at`); `ISSUE_DISPLAY_PROPERTIES_KEYS`,
  `SPREADSHEET_PROPERTY_LIST`, `SPREADSHEET_PROPERTY_DETAILS` (+`completed_on`); `ISSUE_DISPLAY_PROPERTIES`
  (+`completed_on` → botão de toggle no menu **Exibir → Propriedades**, ao lado de start/due date).
- `src/issue/filter.ts` — `ISSUE_DISPLAY_FILTERS_BY_PAGE`: `completed_at`+`is_blocked` nos `filters`
  e `-completed_at` nos `order_by` das páginas `issues`/`archived_issues`/`my_issues`/`profile_issues`.

### Utils (`packages/utils`)

- `src/work-item-filters/configs/filters/date.ts` — `getCompletedAtFilterConfig`.
- `src/work-item-filters/configs/filters/blocked.ts` — **novo**, `getBlockedFilterConfig` (single-select).
- `src/work-item-filters/configs/filters/index.ts` — export do `blocked`.
- `src/work-item/base.ts` — `getComputedDisplayProperties`: default `completed_on ?? true`.

### Web (`apps/web`)

- `ce/hooks/work-item-filters/use-work-item-filters-config.tsx` — memos `completedAtFilterConfig`
  (sempre habilitado, como as datas) e `blockedFilterConfig` (gated por `isFilterEnabled`); inclusão
  em `configs[]` e `configMap`.
- `core/components/issues/issue-layouts/spreadsheet/columns/completed-on-column.tsx` — **novo**
  `SpreadsheetCompletedOnColumn`; export em `.../columns/index.ts`.
- `ce/components/issues/issue-layouts/utils.tsx` — `completed_on: SpreadsheetCompletedOnColumn` em
  `SPREADSHEET_COLUMNS`.

### i18n (`packages/i18n`)

- `src/locales/<lang>/common.json` (19 idiomas) — `common.order_by.completed_date` e
  `common.sort.completed_on` (inglês como placeholder; `pt-BR` traduzido).

## Como testar

1. **Checagem**: `pnpm turbo run check --filter=web --filter=@plane/types --filter=@plane/constants --filter=@plane/utils`.
2. **Backend (shell Django, sem credenciais)**: `IssueFilterSet.base_filters` contém `is_blocked`,
   `is_blocked__exact`, `completed_at`, `completed_at__range`, `completed_at__exact`. Conferir que o
   filtro de bloqueio devolve só issues com `blocked_by` cujo bloqueador está aberto, e a negação o
   complemento (as contagens somam o total).
3. **UI**: no painel de filtros (projeto/ciclo/módulo/view/minhas issues/perfil/arquivados) aparecem
   "Completed at" (data) e "Blocked" (Blocked/Not blocked); o dropdown "Ordenar por" mostra
   "Data de finalização"; a planilha tem a coluna "Finalizada em" no seletor de colunas, renderiza a
   data e ordena pelo cabeçalho. Verificar os params enviados (`completed_at__range`,
   `is_blocked__exact`, `order_by=-completed_at`).
4. **Deploy CT 105**: rebuild `web` + `api` (FilterSet). `worker`/`beat-worker` não mudam (sem código
   Celery). Sem migração nova (`completed_at` já é campo do `Issue`).

## Pitfalls / fora de escopo

- Não se mexeu no `issue_filters()` legado nem no `order_issue_queryset` (ordenação já funcionava).
- O filtro de data de `completed_at` herda a mesma semântica de `created_at`/`updated_at` do
  rich-filter (paridade intencional, não uma melhoria de UX de data).
- `sub_work_items` não recebe os novos filtros (só herdou, inofensivamente, a opção de ordenação
  `-completed_at`).
- O ícone `"CalendarDays"` de `SPREADSHEET_PROPERTY_DETAILS.completed_on` espelha `created_on`/
  `updated_on` (que usam a mesma string, ainda que o map de ícones tenha a chave `CalenderDays`).

---

## Atualização (2026-06-02): data de finalização nos demais layouts + tag [BLOQUEADO]

### Data de finalização fora da planilha

Antes `completed_on` só tinha renderizador na planilha. Agora também é exibida como _pill_ somente
leitura (`completed_at` é automático) na linha de propriedades dos cards (list/kanban/calendar/gantt),
respeitando o toggle do menu **Exibir → Propriedades**.

- `apps/web/core/components/issues/issue-layouts/properties/all-properties.tsx` — _pill_ `completed_on`
  (ícone `CalendarCheck`, `renderFormattedDate(issue.completed_at)`), via `WithDisplayPropertiesHOC`.

### Tag [BLOQUEADO] (badge vermelho ao lado do ID)

Mostra um badge vermelho **BLOQUEADO** ao lado do identificador da tarefa sempre que há bloqueio ativo.
Fica ao lado do **ID** (não do nome) porque no kanban o nome trunca e esconderia a marca.

**Design:** o backend anota `is_blocked` (`Exists`) **uma única vez** em `issue_queryset_grouper`
(`plane/utils/grouper.py`), que é o ponto comum dos 5 endpoints que usam `issue_on_results`
(projeto/ciclo/módulo/"Seu trabalho"/arquivados); as views globais (`view/base.py` →
`ViewIssueListSerializer`) recebem a anotação no próprio `apply_annotations`. A subconsulta é
compartilhada com o filtro via `plane.utils.blocked.active_blocked_exists()`.

**Performance:** a anotação é um `Exists` correlacionado calculado **só nas linhas da página**
(paginação ~100), no índice `issue_relations.issue_id` — mesma classe de `sub_issues_count`/
`link_count`/`attachment_count` já existentes. Impacto pequeno, proporcional à página, **não** ao
workspace.

**Arquivos:**

- `apps/api/plane/utils/blocked.py` — **novo**, `active_blocked_exists()` + `ACTIVE_BLOCKER_STATE_GROUPS`.
- `apps/api/plane/utils/filters/filterset.py` — `filter_is_blocked` refatorado para usar o helper (DRY).
- `apps/api/plane/utils/grouper.py` — anota `is_blocked` em `issue_queryset_grouper` e adiciona
  `"is_blocked"` em `issue_on_results.required_fields` (a _shadow allowlist_ do `.values()`).
- `apps/api/plane/app/views/view/base.py` — `apply_annotations` anota `is_blocked` (views globais).
- `apps/api/plane/app/serializers/view.py` (`ViewIssueListSerializer`) e
  `apps/api/plane/app/serializers/issue.py` (`IssueListDetailSerializer`) — expõem `is_blocked`
  (`getattr` seguro).
- `packages/types/src/issues/issue.ts` — `is_blocked?: boolean` em `TBaseIssue`.
- `apps/web/ce/components/issues/issue-details/issue-identifier.tsx` — badge **BLOQUEADO**
  (`bg-danger-primary`) após o `IdentifierText`, quando `issue.is_blocked` (modo store-data).

**Pitfalls:** o badge só aparece quando o ID está visível (`displayProperties.key`), pois vive dentro
do `IssueIdentifier`. O texto "BLOQUEADO" é fixo (não i18n), coerente com os demais rótulos do fork.
`IssueSerializer` (CRUD/detalhe) **não** recebeu `is_blocked` (conflito `read_only_fields = fields`
em ModelSerializer); o store preserva o valor vindo da listagem ao mesclar respostas de update.
