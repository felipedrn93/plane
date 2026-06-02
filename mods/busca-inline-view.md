# Campo de busca inline na view/projeto (nome + caminho do pai + ID)

**Data:** 2026-06-02
**Autor:** felipedrn93
**Branch:** preview

## Contexto

Para encontrar uma tarefa, o único recurso era a busca global (Power-K), que abre um
modal e exige clicar no resultado para navegar — tirando o usuário da view atual. Faltava
um **campo de busca dentro da própria view** que, ao digitar, **filtra a lista** mostrando
só as tarefas que correspondem, sem trocar de tela.

Esta modificação adiciona um input de busca no topo de cada layout de work items (view do
projeto, views customizadas, ciclos e módulos). A busca casa por três critérios, de uma vez:

1. **Nome da tarefa** (`name ILIKE %q%`);
2. **Caminho do pai** — qualquer ancestral na cadeia (reaproveita o conceito do
   [mods/parent-breadcrumb.md](parent-breadcrumb.md): se um ancestral casa, a tarefa aparece);
3. **Identificador** (ex.: `PROJ-123`).

## Decisões de design

1. **Busca no servidor via parâmetro efêmero `search_text`** (re-fetch), e **não** filtragem
   client-side. É como todos os filtros do Plane já funcionam: muda os params →
   `fetchIssuesWithExistingPagination` → backend devolve só o que casa → os layouts renderizam
   naturalmente. **Os 5 layouts (list/kanban/spreadsheet/calendar/gantt) ficam intocados** e a
   busca é correta com paginação/agrupamento (acha itens ainda não carregados na página).
2. **`search_text` é efêmero**: vive só em memória (estado observável por entidade no filter
   store), **nunca** é persistido em `rich_filters`. Não polui views salvas. Some quando o
   processo/SPA recarrega; persiste por entidade enquanto a aba está aberta (digita "x" no
   projeto A, navega, volta ao A → ainda filtrado; pode limpar com o "×" ou Esc).
3. **CTE recursiva para o "caminho do pai"**: `parent_chain` é calculado pós-query (não é coluna
   no DB), então não dá para filtrar por nome de ancestral direto no ORM. A solução parte das
   issues cujo **nome/ID casa** (seed, indexável) e **desce** para os descendentes. O conjunto
   `{matches} ∪ {descendentes de matches}` é exatamente
   `{casa por nome/ID} ∪ {tem ancestral que casa}`. É mais leve que subir a árvore a partir de
   cada issue (poucos ancestrais casam). Mesmo padrão de SQL cru de `fetch_parent_chains`.
4. **Defensivo**: `search_issue_ids_by_text` é envolvido em `try/except` e devolve `[]` em falha
   ou query vazia — a listagem nunca quebra por causa da busca.
5. **Busca ignorando espaço** (2026-06-02): além do substring normal, a CTE compara `name`/identifier
   e a query com os espaços removidos (`replace(x, ' ', '')`). Assim "clube unir" também casa
   "clubeunir" e vice-versa. Vale para todas as telas (está no helper compartilhado).
6. **Escopo flexível**: o helper aceita `project_id` (projeto/ciclo/módulo/view de projeto) **ou**
   `workspace_slug` com `project_id=None` (Visualizações **globais de workspace**, cross-project).
   O `id__in` sempre intersecta com o queryset já escopado/permissionado, então o resultado é correto.
5. **Componente agnóstico de store**: `WorkItemSearch` depende só de uma interface estrutural
   mínima (`getSearchQuery` + `updateSearchQuery`), satisfeita pelos quatro filter stores. Um
   único componente cobre as quatro telas.
6. **Debounce de 300ms** (hook `useDebounce` já existente) antes de disparar o re-fetch.

## Esquema do parâmetro

Query param read-only, efêmero, enviado junto dos demais params de listagem:

```
GET /api/workspaces/<slug>/projects/<id>/issues/?search_text=atuarial&...
```

Backend devolve a listagem normal, já reduzida ao conjunto que casa.

## Arquivos criados

**Frontend**

- `apps/web/core/components/work-item-filters/work-item-search.tsx` — componente `WorkItemSearch`
  (input com lupa + botão limpar + Esc, debounced) e a interface estrutural
  `IWorkItemSearchFilterStore`.

**Docs**

- `mods/busca-inline-view.md` (este arquivo).

## Arquivos modificados

**Backend**

- `apps/api/plane/utils/grouper.py`
  - Helper novo `search_issue_ids_by_text(project_id, query, workspace_slug=None)` — `WITH RECURSIVE`
    que casa por `name ILIKE`, `identifier-sequence ILIKE` **e** as variantes sem espaço
    (`replace(x, ' ', '') ILIKE`) no seed, e desce para descendentes. Escopo por `project_id` ou,
    se `None`, por `workspace_slug` (views globais). Filtra `deleted_at IS NULL` em cada hop.
    Retorna `[]` defensivamente.
- `apps/api/plane/app/views/issue/base.py`
  - `IssueViewSet.list`: lê `search_text`; se presente, `issue_queryset.filter(id__in=search_issue_ids_by_text(project_id, search_text))`
    **antes** do `deepcopy` (para que os counts de grupo também reflitam a busca). Cobre a view do
    projeto **e as views customizadas** (que listam via `/issues/`).
  - Import do helper adicionado ao bloco `from plane.utils.grouper import (...)`.
- `apps/api/plane/app/views/cycle/issue.py` → `CycleIssueViewSet.list`: mesmo trecho + import.
- `apps/api/plane/app/views/module/issue.py` → `ModuleIssueViewSet.list`: mesmo trecho + import.
- `apps/api/plane/app/views/view/base.py` → `WorkspaceViewIssuesViewSet.list` (views globais de
  workspace): chama `search_issue_ids_by_text(None, search_text, workspace_slug=slug)` (cross-project) + import.

**Frontend / Tipos**

- `packages/types/src/view-props.ts` — `TIssueParams` inclui `"search_text"`.

**Frontend / Store**

- `apps/web/core/store/issue/helpers/issue-filter-helper.store.ts`
  - Base `IssueFilterHelperStore`: observable `searchQuery: Record<string,string>` + `getSearchQuery`
    + `setSearchQuery` (compartilhados pelos quatro stores concretos).
  - `computedFilteredParams` ganha 4º arg opcional `searchQuery`; se presente, seta
    `issueFiltersParams.search_text` **incondicionalmente** (igual a `filters`/`layout` — bypassa a
    whitelist `acceptableParamsByLayout`, então nenhum `handleIssueQueryParamsByLayout` muda).
- `apps/web/core/store/issue/project/filter.store.ts`,
  `apps/web/core/store/issue/project-views/filter.store.ts`,
  `apps/web/core/store/issue/cycle/filter.store.ts`,
  `apps/web/core/store/issue/module/filter.store.ts`,
  `apps/web/core/store/issue/workspace/filter.store.ts` (views globais)
  - Cada um: registra `searchQuery: observable` e `updateSearchQuery: action` no `makeObservable`;
    passa `this.getSearchQuery(id)` em `getAppliedFilters`; implementa `updateSearchQuery` (seta a
    query e chama `fetchIssuesWithExistingPagination(..., "mutation")` com a assinatura própria de
    cada store); declara os dois métodos na interface.

**Frontend / Componentes**

- `apps/web/core/components/issues/issue-layouts/roots/project-layout-root.tsx`,
  `roots/project-view-layout-root.tsx`, `roots/cycle-layout-root.tsx`, `roots/module-layout-root.tsx`,
  `roots/all-issue-layout-root.tsx` (views globais de workspace)
  - Renderizam `<WorkItemSearch .../>` numa barra slim alinhada à direita, **acima** do
    `WorkItemFiltersRow` (fora do `RowTransition` colapsável dele, para ficar sempre visível),
    passando `filterStore`/`entityId` corretos (projectId/viewId/cycleId/moduleId/globalViewId).
    No root global o `issuesFilter` é destruturado, então passa um objeto inline
    `{ getSearchQuery, updateSearchQuery }` (ambos arrow bound) como `filterStore`.

**i18n**

- `packages/i18n/src/locales/en/work-item.json` e `pt-BR/work-item.json`
  - Nova seção `issue.search.*` com `placeholder` e `clear`. Demais locales caem no fallback en.

## Fluxo end-to-end

1. Usuário digita no campo → estado local `value` com debounce de 300ms.
2. Debounced muda → `WorkItemSearch` chama `filterStore.updateSearchQuery(slug, entityId, value)`.
3. O store seta `searchQuery[entityId]` (observable) e dispara `fetchIssuesWithExistingPagination`.
4. O fetch monta os params via `getAppliedFilters → computedFilteredParams`, que injeta `search_text`.
5. Backend (`IssueViewSet`/`CycleIssueViewSet`/`ModuleIssueViewSet`) lê `search_text`, roda a CTE
   recursiva e reduz o queryset com `id__in`.
6. Layout re-renderiza com o conjunto reduzido. Limpar o campo → param some → lista volta ao normal.

## Como testar

**Backend (smoke direto):**

```bash
cd apps/api
python manage.py shell --settings=plane.settings.local
# >>> from plane.utils.grouper import search_issue_ids_by_text
# >>> search_issue_ids_by_text("<project_uuid>", "atuarial")
```

Com a cadeia `A (raiz) → Y (parent=A) → X (parent=Y)`:
- `search_issue_ids_by_text(pid, "A")` deve incluir `A`, `Y`, `X` (descendentes de A).
- `search_issue_ids_by_text(pid, "X")` deve incluir só `X`.
- Buscar o identificador `PROJ-<seq de A>` deve incluir A e descendentes.

**Frontend (manual):**

```bash
pnpm install
pnpm --filter web dev
```

1. Abrir a view do projeto → digitar o nome de uma sub-tarefa → a lista reduz a ela.
2. Digitar o nome de uma tarefa-pai → aparecem o pai **e** todos os descendentes (match por caminho do pai).
3. Digitar `PROJ-<n>` → aparece a issue daquele identificador.
4. Limpar (× ou Esc) → lista volta ao normal.
5. Repetir em **List, Kanban, Spreadsheet, Calendar, Gantt** → mesmo comportamento (layouts intocados).
6. Repetir em **view customizada, ciclo e módulo**.
7. Trocar de layout dentro da mesma view → a busca persiste (a barra fica fora do filtro colapsável).

## Pitfalls específicos

- **`search_text` NÃO persiste**: é só um param efêmero + observable em memória. Não entra em
  `rich_filters`/`display_filters`, não tem migration, não muda a forma da resposta (sem mexer em
  serializers). Recarregar a página zera a busca.
- **CTE filtra `deleted_at IS NULL` em cada hop**: um ancestral soft-deleted não faz ponte entre
  sub-árvores não relacionadas (mesmo cuidado de `fetch_parent_chains`).
- **`ILIKE '%q%'` com wildcard à esquerda não usa índice btree**: ok na escala atual (projetos do
  fork). Se crescer muito, considerar índice `pg_trgm` em `issues.name`.
- **Aplicar a busca ANTES do `copy.deepcopy(issue_queryset)`** no `IssueViewSet.list` — senão os
  counts por grupo (kanban/list agrupado) não refletem a busca.
- **Views globais de workspace ("All issues") agora cobertas** (2026-06-02): usam `view/base.py`
  (`WorkspaceViewIssuesViewSet.list(self, request, slug)`, sem `project_id`), o store
  `workspace/filter.store.ts` (EIssuesStoreType.GLOBAL) e o `all-issue-layout-root.tsx`. O helper
  recebe `workspace_slug` (seed escopado por workspace); como `parent_id` nunca cruza projetos, o
  walk-down de descendentes permanece dentro do projeto de cada match.
- **Cycle/module: assinatura do refetch difere** — `fetchIssuesWithExistingPagination(slug,
  projectId, "mutation", cycleId/moduleId)` (loadType antes do id), enquanto project é
  `(slug, projectId, "mutation")` e project-view é `(slug, projectId, viewId, "mutation")`. Cada
  `updateSearchQuery` encapsula a sua.

## Fora do escopo (v2)

- Realce (highlight) do termo casado no nome/breadcrumb da tarefa.
- Reset automático da busca ao sair da view (hoje persiste por entidade na sessão).
- Operadores avançados (ex.: `is:open`, `assignee:`) — isto é só busca textual; filtros estruturados
  continuam no rich-filter existente.
