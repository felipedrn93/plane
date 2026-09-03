# Reordenar colunas da Spreadsheet por usuário

**Data:** 2026-05-27
**Autor:** felipedrn93
**Branch:** main (commits `17d7628ef`..`b0a4a3bd4`)
**Spec / plano:** [docs/superpowers/specs/2026-05-27-spreadsheet-column-reordering-design.md](../docs/superpowers/specs/2026-05-27-spreadsheet-column-reordering-design.md) · [docs/superpowers/plans/2026-05-27-spreadsheet-column-reordering.md](../docs/superpowers/plans/2026-05-27-spreadsheet-column-reordering.md)

## Contexto

Na Spreadsheet view (a única visualização realmente tabular do Plane) a ordem das colunas vinha de uma constante hardcoded `SPREADSHEET_PROPERTY_LIST` em `packages/constants/src/issue/common.ts`. Cada usuário queria organizar suas listas do jeito que prefere e que isso sobrevivesse a reload e troca de dispositivo.

Esta modificação adiciona drag-and-drop horizontal nos cabeçalhos das colunas, com persistência **por usuário e por contexto** (project, cycle, module, workspace, project view custom), no mesmo padrão do `display_properties` já existente.

## Decisões de design

1. **Novo campo `display_properties_order` (array de chaves)**, não substituir o `display_properties` (que continua sendo objeto de booleanos para visibilidade). Separa "o que mostrar" de "em que ordem".
2. **Persistência por contexto** seguindo o padrão atual: adicionado um JSONField em cada model `*UserProperty` já existente (Project, Cycle, Module, Workspace). Para views custom (`IssueView`), o `display_properties` original é shared entre usuários, então foi necessário criar uma **tabela nova `IssueViewUserProperty`** dedicada a settings per-user de view.
3. **Default `[]` = "usar ordem default"**. Sem data migration; registros antigos ficam vazios e comportamento idêntico ao anterior.
4. **Colunas novas entram no fim automaticamente** — o helper `computedDisplayPropertiesOrder` anexa qualquer chave de `SPREADSHEET_PROPERTY_LIST` que não esteja no array salvo. Adicionar uma display property nova no futuro não obriga o usuário a resetar a ordem.
5. **Backend permissivo, frontend sanitiza** — backend aceita qualquer array, frontend filtra chaves desconhecidas, remove duplicatas e ajusta para o set válido (mesma postura do `display_properties` JSONB).
6. **Coluna sticky de título permanece fixa como primeira** (não reorderável). Só as colunas de propriedades (state, priority, assignee, etc.) são móveis. Preserva o sticky-scroll horizontal existente.
7. **Drag handle dedicado (não o `<th>` inteiro)** — um pequeno ícone `GripVertical` (lucide-react) aparece à esquerda do header no hover. Evita conflito com o `onClick` do menu de sort/clear que vive no chevron do mesmo header. Decisão tomada explicitamente após review apontar a colisão.
8. **`@atlaskit/pragmatic-drag-and-drop`** (já no projeto, padrão usado em `LabelDndHOC`) — não foi adicionada nova dependência.
9. **Endpoints REST novos para views custom** — `GET/PATCH /api/workspaces/<slug>/projects/<pid>/views/<vid>/user-properties/` e `GET/PATCH /api/workspaces/<slug>/views/<vid>/user-properties/` (workspace-level). Reusa o pattern do `ProjectUserDisplayPropertyEndpoint`.
10. **Optimistic update + revert** — frontend aplica a ordem nova em MobX imediatamente; em erro de rede, `fetchFilters` repuxa do servidor e a UI volta ao estado real (padrão existente nos filter stores).

## Esquema do campo

`display_properties_order`: JSONB, array de strings, default `[]`. Cada string é uma chave de `IIssueDisplayProperties` (subset reordenável):

```json
[
  "state",
  "priority",
  "parent_breadcrumb",
  "assignee",
  "labels",
  "start_date",
  "due_date",
  "estimate",
  "created_on",
  "updated_on",
  "link",
  "attachment_count",
  "sub_issue_count",
  "modules",
  "cycle"
]
```

- `[]` (default) → frontend usa ordem de `SPREADSHEET_PROPERTY_LIST` puro.
- Array parcial (ex: `["priority", "state"]`) → renderiza nessa ordem; demais chaves do default anexadas no fim.
- Backend NÃO valida conteúdo. Frontend descarta chaves inválidas e duplicatas.

## Arquivos criados

**Backend**

- `apps/api/plane/db/migrations/0123_display_properties_order.py` — migration hand-written (4 `AddField` + `CreateModel` `IssueViewUserProperty` + `AddConstraint`).

**Endpoints**

- `apps/api/plane/app/views/view/base.py` — novas classes `IssueViewUserPropertyEndpoint` e `WorkspaceIssueViewUserPropertyEndpoint` (appended ao final do arquivo).

**Frontend**

- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-column-dnd.helpers.ts` — função pura `moveColumn(list, from, to)`.

**Docs**

- `docs/superpowers/specs/2026-05-27-spreadsheet-column-reordering-design.md`
- `docs/superpowers/plans/2026-05-27-spreadsheet-column-reordering.md`
- `mods/reordenar-colunas-spreadsheet.md` (este arquivo)

## Arquivos modificados

**Backend / Models**

- `apps/api/plane/db/models/project.py` — campo `display_properties_order = models.JSONField(default=list)` em `ProjectUserProperty`.
- `apps/api/plane/db/models/cycle.py` — idem em `CycleUserProperties`.
- `apps/api/plane/db/models/module.py` — idem em `ModuleUserProperties`.
- `apps/api/plane/db/models/workspace.py` — idem em `WorkspaceUserProperties`.
- `apps/api/plane/db/models/view.py` — nova classe `IssueViewUserProperty` (extends `WorkspaceBaseModel`; FK user + FK view; unique constraint partial em `(user, view)` ignorando soft-deletes); import `Q`.
- `apps/api/plane/db/models/__init__.py` — export `IssueViewUserProperty`.

**Backend / Serializers & URLs**

- `apps/api/plane/app/serializers/view.py` — `IssueViewUserPropertySerializer` (`fields = "__all__"`, `read_only_fields = ["user", "workspace", "view"]`).
- `apps/api/plane/app/serializers/__init__.py` — export do serializer.
- `apps/api/plane/app/views/__init__.py` — export dos dois endpoints.
- `apps/api/plane/app/urls/views.py` — registro de 2 rotas (project-scoped + workspace-scoped).

**Frontend / Tipos**

- `packages/types/src/view-props.ts`
  - Novo tipo `TIssueDisplayPropertiesOrder = (keyof IIssueDisplayProperties)[]`.
  - `IIssueFilters.displayPropertiesOrder?: TIssueDisplayPropertiesOrder`.
  - `IIssueFiltersResponse.display_properties_order?: string[]` (propaga para `IProjectUserPropertiesResponse` e `IWorkspaceUserPropertiesResponse` via extends).
  - `TSupportedFilterForUpdate` union estendida com `TIssueDisplayPropertiesOrder`.
  - Novo interface `IIssueViewUserPropertiesResponse` (id, user, view, workspace, project, display_properties_order).

**Frontend / Constantes**

- `packages/constants/src/issue/filter.ts`
  - Enum `EIssueFilterType` ganha `DISPLAY_PROPERTIES_ORDER = "display_properties_order"`.
  - `TSupportedFilterTypeForUpdate` union estendida.

**Frontend / Service**

- `apps/web/core/services/view.service.ts` — 4 métodos novos: `getViewUserProperties` / `updateViewUserProperties` (project-scoped) e `getWorkspaceViewUserProperties` / `updateWorkspaceViewUserProperties` (workspace-scoped).

**Frontend / Store**

- `apps/web/core/store/issue/helpers/issue-filter-helper.store.ts`
  - Helper `computedDisplayPropertiesOrder(savedOrder?: unknown): TIssueDisplayPropertiesOrder` — sanitiza input (drop não-string, drop chaves inválidas, dedup, append default-keys faltantes).
  - `computedIssueFilters` estendido para incluir `displayPropertiesOrder`.
- `apps/web/core/store/issue/project/filter.store.ts` — `fetchFilters` lê `display_properties_order` e popula store; novo case `DISPLAY_PROPERTIES_ORDER` no switch chama `updateProjectUserProperties({display_properties_order: newOrder})`.
- `apps/web/core/store/issue/cycle/filter.store.ts` — mesma estrutura, service `patchCycleIssueFilters`.
- `apps/web/core/store/issue/module/filter.store.ts` — mesma estrutura, service `patchModuleIssueFilters`.
- `apps/web/core/store/issue/workspace/filter.store.ts` — mesma estrutura; persistência em **localStorage** (não backend) — mesma limitação herdada do case `DISPLAY_PROPERTIES` neste store, que só roda em static views (all-issues/assigned/created/subscribed).
- `apps/web/core/store/issue/project-views/filter.store.ts` — fetch passa a fazer GET extra em `getViewUserProperties` (com fallback gracioso ao default se endpoint falhar); novo case chama `updateViewUserProperties`.

**Frontend / Componentes Spreadsheet**

- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header-column.tsx` — reescrito: `useEffect` registra `combine(draggable({element: handle, ...}), dropTargetForElements({element: th, ...}))`. Drop indicator inline (`w-[2px] h-full bg-accent-primary`, posicionado à left/right do `<th>` conforme direção do drag). Drag handle separado (`<button ref={dragHandleRef}>` com `GripVertical`, `opacity-0` default → `opacity-100` no hover do `<th>` via `group/spreadsheet-header`).
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header.tsx` — props `onReorder?` e `isReorderEnabled?`; map agora passa `index` e ambos para cada `SpreadsheetHeaderColumn`.
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-table.tsx` — props `onReorderColumn?` e `isReorderEnabled?`; propaga para `SpreadsheetHeader` (renomeando `onReorderColumn` → `onReorder`).
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-view.tsx` — props `displayPropertiesOrder?` e `onReorderColumns?`; aplica a ordem ANTES do filtro cycle/module (`orderedAll = displayPropertiesOrder?.length ? displayPropertiesOrder : SPREADSHEET_PROPERTY_LIST`); `handleReorderColumn(from, to)` aplica `moveColumn` localmente e chama `onReorderColumns(newOrder)`.
- `apps/web/core/components/issues/issue-layouts/spreadsheet/base-spreadsheet-root.tsx` — lê `issuesFilter.issueFilters?.displayPropertiesOrder`; cria `handleReorderColumns` que chama `updateFilters(projectId, EIssueFilterType.DISPLAY_PROPERTIES_ORDER, newOrder)`; passa ambos para `SpreadsheetView`. Cobre 4 contextos (project, cycle, module, project-view) via reuse do hook `useIssuesActions`.
- `apps/web/core/components/issues/issue-layouts/spreadsheet/roots/workspace-root.tsx` — wiring análogo, manualmente (este root não usa `BaseSpreadsheetRoot`); passa `globalViewId` para o store de workspace.

## Fluxo end-to-end

```
Usuário pega o handle GripVertical de "Priority" e arrasta antes de "State"
  ↓
SpreadsheetHeaderColumn.useEffect → draggable.onDrop / dropTarget.onDrop
  ↓ calcula (from, to)
SpreadsheetHeader.onReorder(from, to)
  ↓
SpreadsheetTable.onReorderColumn(from, to)
  ↓
SpreadsheetView.handleReorderColumn(from, to)
  ↓ moveColumn(spreadsheetColumnsList, from, to)
onReorderColumns(newOrder)
  ↓ (definido em BaseSpreadsheetRoot)
useIssuesActions.updateFilters(projectId, EIssueFilterType.DISPLAY_PROPERTIES_ORDER, newOrder)
  ↓
ProjectIssuesFilter.updateFilters case DISPLAY_PROPERTIES_ORDER
  1. sanitize via computedDisplayPropertiesOrder
  2. optimistic: set(this.filters, [projectId, "displayPropertiesOrder"], newOrder)
  3. await projectService.updateProjectUserProperties(slug, projectId, {display_properties_order: newOrder})
  4. catch → fetchFilters() para reverter + throw
  ↓
PATCH /api/workspaces/<slug>/projects/<id>/user-properties/
  ↓
ProjectUserProperty.display_properties_order = [...]
  ↓
MobX → SpreadsheetView re-renderiza com nova ordem (header + cada row)
```

## Endpoints

| Verbo     | URL                                                                    | Endpoint class                                      | Body PATCH                          |
| --------- | ---------------------------------------------------------------------- | --------------------------------------------------- | ----------------------------------- |
| GET/PATCH | `/api/workspaces/<slug>/projects/<pid>/user-properties/`               | `ProjectUserDisplayPropertyEndpoint` (já existia)   | `{display_properties_order: [...]}` |
| GET/PATCH | `/api/workspaces/<slug>/projects/<pid>/cycles/<cid>/user-properties/`  | `CycleUserPropertiesEndpoint` (já existia)          | idem                                |
| GET/PATCH | `/api/workspaces/<slug>/projects/<pid>/modules/<mid>/user-properties/` | `ModuleUserPropertiesEndpoint` (já existia)         | idem                                |
| GET/PATCH | `/api/workspaces/<slug>/user-properties/`                              | `WorkspaceUserPropertiesEndpoint` (já existia)      | idem                                |
| GET/PATCH | `/api/workspaces/<slug>/projects/<pid>/views/<vid>/user-properties/`   | **`IssueViewUserPropertyEndpoint` (novo)**          | idem                                |
| GET/PATCH | `/api/workspaces/<slug>/views/<vid>/user-properties/`                  | **`WorkspaceIssueViewUserPropertyEndpoint` (novo)** | idem                                |

Os 4 endpoints pré-existentes expõem o campo novo automaticamente porque seus serializers usam `fields = "__all__"`.

## Como testar

**Backend (psql, verificar persistência)**

```sql
-- Verificar coluna na tabela
\d project_user_properties

-- Ver dado salvo após reordenar via UI
SELECT user_id, project_id, display_properties_order
FROM project_user_properties
WHERE display_properties_order != '[]'::jsonb;

-- Verificar tabela nova de views custom
\dt issue_view_user_properties
```

**Frontend (smoke manual)**

1. Abrir um projeto → layout Spreadsheet.
2. Passar mouse no cabeçalho de uma coluna → ícone `⋮⋮` (GripVertical) aparece à esquerda.
3. Arrastar pelo ícone para outra posição → coluna move; linhas de body acompanham.
4. F5 → ordem persiste.
5. Abrir outro projeto → ordem default (não vaza do primeiro).
6. Abrir cycle do mesmo projeto → ordem independente.
7. View custom workspace-level → reordenar e confirmar persistência via novo endpoint.
8. Click no chevron do menu de sort → menu abre normalmente (não dispara drag, pois o handle é dedicado).
9. Toggle on/off de coluna em "Display properties" → coluna some/aparece sem perder a ordem das demais.

## Pitfalls específicos

- **`computedIssueFilters` em `IssueFilterHelperStore` precisa propagar o novo campo.** Adicionei `displayPropertiesOrder: filters?.displayPropertiesOrder` na cópia que essa função retorna. Sem isso, o getter `issueFilters` no store nunca exporia a ordem ao componente. Mesmo pitfall da `parent_breadcrumb` quando ela foi adicionada (ver [parent-breadcrumb.md](parent-breadcrumb.md#pitfalls-específicos)).
- **`get_or_create` com `workspace__slug=slug` falha no create.** Django filtra lookups com `__` no path de criação. Como `WorkspaceBaseModel.workspace` é NOT NULL e `WorkspaceBaseModel.save()` só auto-deriva via `project`, o `IssueViewUserPropertyEndpoint` resolve a workspace antes via `Workspace.objects.get(slug=slug)` e passa via `defaults={"workspace_id": ..., "project_id": ...}`. Sintoma sem o fix: primeiro PATCH/GET por usuário em uma view crasha com `IntegrityError`. (Endpoints existentes como `CycleUserPropertiesEndpoint` têm o mesmo trap latente; só não dispara em produção porque o registro normalmente já é criado por outro caminho antes.)
- **`@allow_permission` no workspace endpoint usa `level="WORKSPACE"`** (assinatura keyword), enquanto no project endpoint a forma posicional `@allow_permission([ROLE.ADMIN, ...])` basta (defaulta para project-level). Misturar as duas formas confunde — copiar exatamente do endpoint análogo (`WorkspaceViewViewSet.list` em `view/base.py:71` foi o modelo).
- **5 models, 1 migration** — adicionar campo nos 4 `*UserProperty` existentes + criar `IssueViewUserProperty` em uma migration única. Cada `*UserProperty` em arquivo separado é fácil de esquecer; verificar via grep `class .*UserPropert` em `apps/api/plane/db/models/`.
- **`unique_together` + `UniqueConstraint` partial** — `IssueViewUserProperty.Meta` carrega os dois (igual sibling models). O `unique_together` cobre soft-deletes (`(user, view, deleted_at)`), o `UniqueConstraint` partial garante unicidade entre live rows (`(user, view) WHERE deleted_at IS NULL`). Pattern copiado de `CycleUserProperties`.
- **Migration hand-written**: como o ambiente de desenvolvimento usado para gerar a migration não tinha Postgres rodando, `manage.py makemigrations` não foi executado. O arquivo `0123_display_properties_order.py` foi escrito à mão seguindo a estrutura emitida por uma migration recente análoga (`0101_description_descriptionversion.py`). Quando o ambiente local tiver DB, rodar `makemigrations --dry-run` para validar que não há drift; se Django sugerir uma `0124_alter_*`, alinhar.
- **`WorkspaceSpreadsheetRoot` não usa `BaseSpreadsheetRoot`** — descoberto via code review. As Spreadsheets de project/cycle/module/project-view delegam ao base; o root de workspace tem fetch/render próprio. O wiring de reorder precisa ser duplicado lá (importar `IIssueDisplayProperties`, criar `handleReorderColumns`, passar `displayPropertiesOrder` + `onReorderColumns` para o `SpreadsheetView`).
- **Drag handle vs. menu de sort** — primeira versão deixou o `<th>` inteiro como drag target. Resultou em clicks "quase-drag" disparando reorder em vez de abrir o menu de sort. Refatorado para usar `dragHandle: handleRef.current` no `draggable()` do pragmatic-drag-and-drop, com um botão dedicado (`GripVertical`) visível só no hover do header.
- **Workspace static views (all-issues, assigned, ...) persistem em localStorage**, não no backend. É a limitação herdada do case `DISPLAY_PROPERTIES` no `workspace/filter.store.ts`. Se um dia se quiser persistir no backend para esses views, o WorkspaceUserProperties já tem o campo — basta wirar o PATCH no store (atualmente só faz `handleIssuesLocalFilters.set(...)`).
- **Para o conjunto reorderável bater com o renderizado**, `SPREADSHEET_PROPERTY_LIST` (a fonte de verdade da ordem) precisa ficar sincronizada com `IIssueDisplayProperties` (o tipo de visibility). Adicionar uma chave nova em `IIssueDisplayProperties` sem incluir em `SPREADSHEET_PROPERTY_LIST` significa que essa chave nunca será reorderável (mas ainda aparece via `WithDisplayPropertiesHOC`). E vice-versa: incluir em `SPREADSHEET_PROPERTY_LIST` sem o tipo quebra typecheck.

## Fora do escopo (v2)

- **List view, Kanban, Calendar, Gantt** — feature só cobre Spreadsheet. List/Kanban renderizam props como chips/badges via `IssueProperties` em ordem hardcoded no JSX.
- **Sort/filter por ordem custom** — a ordem é puramente visual; queries continuam usando `display_filters.order_by`.
- **Largura de coluna persistida** — escopo separado.
- **Compartilhar ordem entre usuários** — continua per-user em todos os contextos.
- **Acessibilidade por teclado** — `@atlaskit/pragmatic-drag-and-drop` não traz suporte a teclado out of the box. Drag só por mouse/touch.
- **Backend persistence para workspace static views** — hoje vai pra localStorage; mover para o `WorkspaceUserProperties.display_properties_order` exige adaptar o switch no `workspace/filter.store.ts`.
- **Spreadsheet de profile / archived / workspace-draft** — usam stores próprios não incluídos neste corte.
