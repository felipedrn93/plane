# Spreadsheet Column Reordering — Design Spec

**Data:** 2026-05-27
**Autor:** Felipe (fork felipedrn93/plane @ branch preview)
**Status:** Aprovado para implementação

## Resumo

Permitir que cada usuário reordene as colunas da Spreadsheet view (work items) via drag-and-drop no cabeçalho, com persistência por contexto (project, cycle, module, workspace, project view) no backend, igual ao padrão atual de `display_properties`.

## Motivação

Hoje a ordem das colunas da Spreadsheet vem de uma constante hardcoded (`SPREADSHEET_PROPERTY_LIST`). Usuários querem organizar suas listas do jeito que preferem e não ter que reconfigurar a cada navegação. A persistência precisa ser por usuário e sobreviver entre sessões e dispositivos.

## Escopo

**Dentro:**
- Spreadsheet view em todos os contextos: project, cycle, module, workspace, project view custom.
- Drag-and-drop no cabeçalho de coluna.
- Persistência backend por usuário e por contexto.
- Coluna sticky de título (Title) permanece como primeira, não-reordenável.

**Fora (explícito):**
- List view, Kanban, Gantt, Calendar.
- Spreadsheets de profile, archived, workspace-draft.
- Reordenar a coluna sticky de Title.
- Compartilhar ordem entre usuários (continua per-user).
- Persistir largura de coluna.

## Decisões-chave

1. **Persistência:** novo campo `display_properties_order` (JSON array) nos models de user properties — não substitui `display_properties` (que continua sendo objeto de booleanos para visibilidade).
2. **Granularidade:** por contexto (mesmo padrão do `display_properties` atual).
3. **UX:** drag direto no cabeçalho da coluna.
4. **Default:** `[]` no banco significa "usar ordem default" (`SPREADSHEET_PROPERTY_LIST`).
5. **Colunas novas:** propriedades adicionadas ao Plane depois do save do usuário entram automaticamente no fim, na posição definida em `SPREADSHEET_PROPERTY_LIST`.
6. **Validação:** backend é permissivo; frontend sanitiza (filtra inválidas, dedupa).

## Modelo de dados (backend)

Novo campo em cada model de user properties:

```python
display_properties_order = models.JSONField(default=list)
# Exemplo: ["state", "priority", "assignee", "labels", "due_date", ...]
```

Models afetados:

| Model | Arquivo | Cobre |
|---|---|---|
| `ProjectUserProperty` | `apps/api/plane/db/models/project.py` | spreadsheet de projeto |
| `CycleUserProperties` | `apps/api/plane/db/models/cycle.py` | spreadsheet de cycle |
| `ModuleUserProperties` | `apps/api/plane/db/models/module.py` | spreadsheet de module |
| `WorkspaceUserProperties` | `apps/api/plane/db/models/workspace.py` | spreadsheet workspace-level |
| **`IssueViewUserProperty` (NOVA tabela)** | `apps/api/plane/db/models/view.py` | spreadsheets de Views custom — per-user (o `IssueView.display_properties` atual é compartilhado entre usuários; criamos tabela separada para a ordem per-user) |

**Nova model `IssueViewUserProperty`** (em `apps/api/plane/db/models/view.py`):

```python
class IssueViewUserProperty(WorkspaceBaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="view_property_user")
    view = models.ForeignKey("db.IssueView", on_delete=models.CASCADE,
                             related_name="view_user_properties")
    display_properties_order = models.JSONField(default=list)

    class Meta:
        db_table = "issue_view_user_properties"
        unique_together = ["user", "view", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "view"],
                condition=Q(deleted_at__isnull=True),
                name="view_user_property_unique_user_view_when_deleted_at_null",
            )
        ]
```

**Migrations:** uma migration única `0XXX_add_display_properties_order.py` que:
- Adiciona campo `display_properties_order` em `ProjectUserProperty`, `CycleUserProperties`, `ModuleUserProperties`, `WorkspaceUserProperties` (default `[]`, `null=False`).
- Cria nova tabela `IssueViewUserProperty` com schema acima.
- Sem data migration (registros antigos ficam com `[]` → comportamento idêntico ao atual).

**Serializers:** adicionar `display_properties_order` no `Meta.fields` (ou explicitamente nos `read_only_fields`/payload dos endpoints `*UserProperty`).

**Semântica do campo:**
- `[]` → frontend usa `SPREADSHEET_PROPERTY_LIST` na ordem default.
- `["priority","assignee","state"]` → renderiza nessa ordem; chaves do default ausentes são anexadas no fim na ordem default.
- Backend não valida conteúdo. Frontend filtra chaves inválidas e remove duplicatas.

## Frontend — tipos e constantes

**`packages/types/src/view-props.ts`:**

```ts
export type TIssueDisplayPropertiesOrder = (keyof IIssueDisplayProperties)[];

export interface IIssueFilters {
  // ... existentes
  displayProperties: IIssueDisplayProperties;
  displayPropertiesOrder: TIssueDisplayPropertiesOrder;  // novo
}
```

**`packages/constants/src/issue/filter.ts`:**

```ts
export enum EIssueFilterType {
  FILTERS = "filters",
  DISPLAY_FILTERS = "display_filters",
  DISPLAY_PROPERTIES = "display_properties",
  DISPLAY_PROPERTIES_ORDER = "display_properties_order",  // novo
  KANBAN_FILTERS = "kanban_filters",
}
```

Atualizar `TSupportedFilterTypeForUpdate` e `TSupportedFilterForUpdate` para incluir o novo tipo e payload `TIssueDisplayPropertiesOrder`.

## Frontend — helper de sanitização

**`apps/web/core/store/issue/helpers/issue-filter-helper.store.ts`:**

```ts
computedDisplayPropertiesOrder(savedOrder?: unknown): TIssueDisplayPropertiesOrder {
  const defaultOrder = SPREADSHEET_PROPERTY_LIST;
  if (!Array.isArray(savedOrder) || savedOrder.length === 0) return defaultOrder;

  const validKeys = new Set(defaultOrder);
  const seen = new Set<string>();
  const sanitized: TIssueDisplayPropertiesOrder = [];

  for (const key of savedOrder) {
    if (typeof key !== "string") continue;
    if (!validKeys.has(key as keyof IIssueDisplayProperties)) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    sanitized.push(key as keyof IIssueDisplayProperties);
  }

  // Acrescenta no fim qualquer chave do default que não esteja presente
  for (const key of defaultOrder) {
    if (!seen.has(key)) sanitized.push(key);
  }

  return sanitized;
}
```

Garante:
- `[]` → default puro
- chaves inválidas filtradas
- duplicatas removidas
- propriedades novas (não conhecidas pelo save antigo) anexadas no fim na ordem default

## Frontend — filter stores

Stores afetados:

- `apps/web/core/store/issue/project/filter.store.ts`
- `apps/web/core/store/issue/cycle/filter.store.ts`
- `apps/web/core/store/issue/module/filter.store.ts`
- `apps/web/core/store/issue/workspace/filter.store.ts`
- `apps/web/core/store/issue/project-views/filter.store.ts`

**Em cada um:**

1. **`fetchFilters`** — ler `_filters?.display_properties_order` da resposta, passar por `computedDisplayPropertiesOrder`, e popular `this.filters[contextId].displayPropertiesOrder`.

2. **`updateFilters`** — novo case:

```ts
case EIssueFilterType.DISPLAY_PROPERTIES_ORDER: {
  const newOrder = this.computedDisplayPropertiesOrder(filters as TIssueDisplayPropertiesOrder);

  runInAction(() => {
    set(this.filters, [contextId, "displayPropertiesOrder"], newOrder);
  });

  await this.projectService.updateProjectUserProperties(workspaceSlug, contextId, {
    display_properties_order: newOrder,
  });
  break;
}
```

(adaptar nome do service por contexto: `cycleService`, `moduleService`, etc.)

3. **Tratamento de erro:** segue o padrão existente — `catch` chama `fetchFilters(workspaceSlug, contextId)` para revert, e re-throw.

**Profiles/archived/workspace-draft:** ficam de fora desse corte. Podem ser adicionados depois reusando os mesmos primitivos sem mudança arquitetural.

## Frontend — UI e drag-and-drop

**Biblioteca:** reaproveitar `@dnd-kit/core` + `@dnd-kit/sortable` (já em uso no Plane).

**Arquivos afetados:**

- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-view.tsx`
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-table.tsx`
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header.tsx`
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header-column.tsx`

**`spreadsheet-view.tsx`:**

Aplicar a ordem do user ANTES do filtro de cycle/module:

```ts
const orderedAll = applyUserOrder(SPREADSHEET_PROPERTY_LIST, displayPropertiesOrder);
const spreadsheetColumnsList = isWorkspaceLevel
  ? orderedAll
  : orderedAll.filter((property) => {
      if (property === "cycle" && !currentProjectDetails?.cycle_view) return false;
      if (property === "modules" && !currentProjectDetails?.module_view) return false;
      return true;
    });
```

`applyUserOrder` pode ser inline ou um util; a saída do `computedDisplayPropertiesOrder` já cumpre esse papel — então basta passar a ordem saneada do store.

**`spreadsheet-header.tsx`:**

```tsx
<DndContext
  onDragEnd={handleColumnReorder}
  sensors={sensors}
  collisionDetection={closestCenter}
>
  <SortableContext
    items={spreadsheetColumnsList}
    strategy={horizontalListSortingStrategy}
  >
    {/* Sticky: ficam FORA do SortableContext */}
    <SelectionColumn />
    <TitleColumn />

    {/* Reordenáveis */}
    {spreadsheetColumnsList.map((propertyKey) => (
      <SortableHeaderColumn
        key={propertyKey}
        propertyKey={propertyKey}
        displayProperties={displayProperties}
        displayFilters={displayFilters}
        handleDisplayFilterUpdate={handleDisplayFilterUpdate}
      />
    ))}
  </SortableContext>
</DndContext>
```

**`SortableHeaderColumn`** (novo wrapper sobre `SpreadsheetHeaderColumn`):

- `useSortable({ id: propertyKey })`
- Aplica `transform` + `transition` via `style`.
- Drag handle cobre o título e o ícone da propriedade, **mas não** o `ChevronDown` do menu de sort (que tem onClick próprio). Implementação: aplicar `{...attributes} {...listeners}` num `<div>` interno que NÃO cobre o trigger do menu.
- Feedback visual: `opacity-50` enquanto arrasta, `cursor: grab/grabbing`.

**Handler:**

```ts
function handleColumnReorder(event: DragEndEvent) {
  const { active, over } = event;
  if (!over || active.id === over.id) return;
  const oldIndex = spreadsheetColumnsList.indexOf(active.id as string);
  const newIndex = spreadsheetColumnsList.indexOf(over.id as string);
  if (oldIndex < 0 || newIndex < 0) return;

  const newOrder = arrayMove(spreadsheetColumnsList, oldIndex, newIndex);
  // O store sanitiza e dispara o PATCH (optimistic + rollback no catch)
  issuesFilter.updateFilters(
    workspaceSlug,
    contextId,
    EIssueFilterType.DISPLAY_PROPERTIES_ORDER,
    newOrder
  );
}
```

**Sticky horizontal scroll:** preservado — colunas sticky ficam fora do `SortableContext`, CSS sticky atual intacto.

**Acessibilidade:** suporte a teclado vem de fábrica do `@dnd-kit` (Tab + Space + setas). Anúncios screen-reader opcionais nessa primeira versão.

**`spreadsheet-table.tsx`:** continua iterando `spreadsheetColumnsList` para body (cada `IssueColumn` da row). Mesma fonte de verdade do header garante consistência.

## Fluxo de dados completo

```
Usuário arrasta header "Priority" antes de "State"
  ↓
SpreadsheetHeader.onDragEnd
  ↓ arrayMove
issuesFilter.updateFilters(
  workspaceSlug, projectId,
  EIssueFilterType.DISPLAY_PROPERTIES_ORDER,
  ["priority","state","assignee", ...]
)
  ↓
ProjectIssuesFilter.updateFilters (case novo)
  1. sanitize via computedDisplayPropertiesOrder
  2. optimistic: set(this.filters, [projectId, "displayPropertiesOrder"], novaOrdem)
  3. await projectService.updateProjectUserProperties(...)
  4. catch → fetchFilters() revert + throw
  ↓
PATCH /api/v1/workspaces/<slug>/projects/<id>/user-properties/
  ↓
ProjectUserProperty.display_properties_order = [...]
  ↓
MobX reativo → SpreadsheetView re-renderiza
```

## Casos de borda

| Caso | Comportamento |
|---|---|
| Usuário nunca reordenou (`[]` no banco) | `computedDisplayPropertiesOrder([])` retorna `SPREADSHEET_PROPERTY_LIST` puro |
| Nova propriedade adicionada ao Plane após o save | Aparece no fim, na posição definida em `SPREADSHEET_PROPERTY_LIST` |
| Propriedade removida do Plane | Filtrada fora pelo helper; nunca renderiza chave inexistente |
| Optimistic update falha (rede/permissão) | `catch` chama `fetchFilters` que repuxa do servidor → UI volta ao estado real |
| Cycle/module sem `cycle_view`/`module_view` no projeto | Filtro de hoje (`spreadsheet-view.tsx` linhas 72–78) aplicado APÓS a ordem |
| Duas abas reordenando simultaneamente | Last-write-wins (igual `display_properties` atual). Sem locking. |
| View custom criada nova (sem registro de user properties ainda) | Backend retorna `[]` → cai no caso default |
| Resposta da API vem com `display_properties_order` corrompido (tipo errado) | `computedDisplayPropertiesOrder` retorna default sem quebrar |

## Endpoints

Reutilizados — cada um passa a aceitar `display_properties_order` no payload (via serializer atualizado):

- `PATCH /workspaces/<slug>/projects/<id>/user-properties/`
- `PATCH /workspaces/<slug>/projects/<pid>/cycles/<cid>/user-properties/`
- `PATCH /workspaces/<slug>/projects/<pid>/modules/<mid>/user-properties/`
- `PATCH /workspaces/<slug>/user-properties/`
- **NOVO endpoint:** `GET/PATCH /workspaces/<slug>/views/<vid>/user-properties/` (project view) e `GET/PATCH /workspaces/<slug>/workspace-views/<vid>/user-properties/` (workspace view) — viewset novo que opera sobre `IssueViewUserProperty`.

## Testes

**Backend:**

- Migration aplica limpa em DB existente; default `[]` em todos os registros antigos.
- `PATCH .../user-properties/` aceita `display_properties_order: ["state","priority"]` e persiste.
- `GET .../user-properties/` retorna o array salvo.
- Aceita `[]` (reset implícito ao default do frontend).
- Aceita chaves desconhecidas sem 500 (frontend sanitiza; backend é permissivo).

**Frontend (helper + store):**

- `computedDisplayPropertiesOrder([])` → retorna `SPREADSHEET_PROPERTY_LIST` puro.
- `computedDisplayPropertiesOrder(["priority","state"])` → priority, state, depois resto do default na ordem original.
- `computedDisplayPropertiesOrder(["priority","invalida","state"])` → invalida filtrada fora.
- `computedDisplayPropertiesOrder(["state","state","priority"])` → dedup, "state" só aparece uma vez.
- `computedDisplayPropertiesOrder(undefined)` / `null` / `{}` → retorna default sem quebrar.
- Store: `updateFilters(DISPLAY_PROPERTIES_ORDER, ...)` chama o service correto e aplica optimistic update.
- Store: rollback ao falhar a chamada de API.

**Smoke test manual antes de marcar pronto:**

1. Subir app local, abrir spreadsheet de um projeto.
2. Arrastar "Priority" pra antes de "State" → mudança instantânea.
3. F5 → ordem persiste.
4. Abrir outro projeto → ordem do primeiro NÃO vaza (persistência por contexto).
5. Abrir cycle do mesmo projeto → ordem independente.
6. Repetir num view custom workspace-level.
7. Logout → login em outra máquina (ou janela anônima) → ordem persiste no usuário.
8. Toggle display properties (mostrar/esconder coluna) continua funcionando e respeita a ordem.

## Migração e rollout

- **Sem feature flag** — mudança é backward-compatible (campo novo com default `[]`, semântica de "sem ordem custom" = ordem default atual).
- **Migration única**, sem data migration.
- **Rollback seguro:** reverter a migration apenas remove a coluna; nada quebra (frontend trata ausência via `?.`).
- **Deploy:** backend primeiro (migration), depois frontend. Frontend antigo ignora o campo novo no payload; backend novo aceita payload sem `display_properties_order`.
