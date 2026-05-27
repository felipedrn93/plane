# Coluna "Caminho do pai" (parent breadcrumb)

**Data:** 2026-05-27
**Autor:** felipedrn93

## Contexto

Nas listas e views do Plane, quando uma sub-tarefa aparece, nada na linha/card indicava de qual tarefa-pai ela descende. Em hierarquias com 2+ níveis o usuário perdia a referência. Esta modificação adiciona uma propriedade **`parent_breadcrumb`** que mostra a cadeia de ancestrais como `A > Y` (cada nó clicável abre o peek-overview do ancestral) em todos os layouts: Spreadsheet (coluna dedicada) e List/Kanban/Calendar/Gantt (badge compacto via `all-properties.tsx`).

Default ligado, com toggle em "Display properties".

## Decisões de design

1. **CTE recursivo no backend** (não no frontend): a cadeia é calculada com `WITH RECURSIVE` em PostgreSQL, **uma query por listagem** (não N por linha). Filtra ancestrais com `deleted_at IS NULL`. Robusta contra paginação/filtros — não depende de "todos os ancestrais já estarem na cache do MobX". Wrap em `try/except` defensivo: se algo falha, a listagem segue funcionando com `parent_chain: []`.
2. **Campo virtual** (`parent_chain`): NÃO é coluna no DB, NÃO entra em migration. É derivado em runtime. Mas precisa ser declarado em todas as "shadow allowlists" (serializers + `.values()` projections) — segue o checklist documentado em [tarefas-recorrentes.md](tarefas-recorrentes.md#pitfalls--todos-os-lugares-onde-um-campo-novo-de-issue-precisa-aparecer).
3. **Clicável**: cada nó vira link via `ControlLink` + `useIssuePeekOverviewRedirection`. Mesmo padrão usado em `issue-detail/parent/root.tsx`.
4. **Truncamento agressivo**: chains com 4+ ancestrais colapsam intermediários para `…` (configurável via `collapseAfter`). Tooltip mostra a chain completa em texto.
5. **Sort/filter por parent_chain**: fora de escopo (v2). Header da coluna na Spreadsheet usa `sort_order` como fallback no menu — clica em qualquer opção e cai no sort manual.

## Esquema do `parent_chain`

Read-only no payload de Issue (não persistido). Ordem: raiz primeiro, pai imediato por último.

```json
[
  { "id": "uuid", "name": "A", "project_id": "uuid", "identifier": "PROJ", "sequence_id": 1 },
  { "id": "uuid", "name": "Y", "project_id": "uuid", "identifier": "PROJ", "sequence_id": 3 }
]
```

Para uma issue raiz: `[]`.

## Arquivos criados

**Backend**

- (nenhum — implementação reusa `plane.utils.grouper`)

**Frontend**

- `apps/web/core/components/issues/issue-layouts/properties/parent-breadcrumb.tsx` — componente `ParentBreadcrumb` (puro; recebe `chain` e `workspaceSlug`, renderiza links com `ControlLink` + `Tooltip` com chain completa).
- `apps/web/core/components/issues/issue-layouts/spreadsheet/columns/parent-breadcrumb-column.tsx` — wrapper que projeta a coluna na Spreadsheet.

**Docs**

- `mods/parent-breadcrumb.md` (este arquivo).

## Arquivos modificados

**Backend**

- `apps/api/plane/utils/grouper.py`
  - Helpers novos: `fetch_parent_chains(issue_ids)` (executa o `WITH RECURSIVE` em SQL cru), `attach_parent_chain(rows)` (mutate de lista de dicts), `attach_parent_chain_to_instances(instances)` (mutate de instâncias do model).
  - `issue_on_results()` materializa a queryset e chama `attach_parent_chain()` antes de retornar.
- `apps/api/plane/app/views/issue/base.py`
  - `IssueListEndpoint.get`: branch `.values()` materializa em `list(...)` e chama `attach_parent_chain`; branch serializer chama `attach_parent_chain_to_instances` antes de passar pro `IssueSerializer`.
  - `IssueViewSet.create`: response pós-create injeta `parent_chain` via `attach_parent_chain([issue])`.
  - `IssuePaginatedViewSet.process_paginated_result`: materializa e chama `attach_parent_chain`.
  - `IssueDetailEndpoint.get`: `on_results` envolve com `attach_parent_chain_to_instances` antes do `IssueListDetailSerializer`.
- `apps/api/plane/app/views/issue/sub_issue.py`
  - `SubIssuesEndpoint.get`: chama `attach_parent_chain` na lista de dicts.
- `apps/api/plane/app/serializers/issue.py`
  - `IssueSerializer`: novo campo `parent_chain = SerializerMethodField()` + `get_parent_chain` lendo `getattr(obj, "parent_chain", [])`.
  - `IssueListDetailSerializer.to_representation`: adiciona `parent_chain: getattr(instance, "parent_chain", []) or []`.
- `apps/api/plane/db/models/issue.py`
  - `get_default_display_properties()`: adiciona `"parent_breadcrumb": True`.

**Frontend / Tipos**

- `packages/types/src/issues/issue.ts`
  - Novo tipo `TIssueParentChainNode`.
  - `TBaseIssue.parent_chain?: TIssueParentChainNode[]`.
- `packages/types/src/view-props.ts`
  - `IIssueDisplayProperties.parent_breadcrumb?: boolean`.

**Frontend / Constantes**

- `packages/constants/src/issue/common.ts`
  - `ISSUE_DISPLAY_PROPERTIES_KEYS` inclui `"parent_breadcrumb"`.
  - `ISSUE_DISPLAY_PROPERTIES` inclui entry com `titleTranslationKey: "issue.parent_breadcrumb.column"`.
  - `SPREADSHEET_PROPERTY_LIST` inclui `"parent_breadcrumb"` (na ordem, depois de `sub_issue_count`).
  - `SPREADSHEET_PROPERTY_DETAILS.parent_breadcrumb`: usa `sort_order` para asc/desc (no-op no menu — sort real fica pra v2).

**Frontend / Store**

- `apps/web/core/store/issue/issue-details/issue.store.ts`
  - `addIssueToStore` inclui `parent_chain: issue?.parent_chain` na allowlist (mesmo pitfall do `recurrence_pattern`).

**Frontend / Componentes**

- `apps/web/core/components/issues/issue-layouts/properties/all-properties.tsx`
  - Renderiza `<WithDisplayPropertiesHOC displayPropertyKey="parent_breadcrumb">…<ParentBreadcrumb …/></WithDisplayPropertiesHOC>` no início da lista de propriedades (cobre List/Kanban — esses layouts montam o card via `IssueProperties`). `shouldRenderProperty` esconde se `issue.parent_id` é null ou a chain está vazia.
- `apps/web/core/components/issues/preview-card/root.tsx`
  - Calendar/Gantt usam blocos compactos sem `IssueProperties` mas têm um hover preview (`WorkItemPreviewCard`). Adicionado bloco de breadcrumb logo abaixo do identifier+state, só quando há cadeia. Cobre Calendar e Gantt indiretamente. Props do componente estendidas para incluir `parent_chain` e `parent_id`.
- `apps/web/core/components/issues/issue-layouts/properties/index.ts` — re-exporta `parent-breadcrumb`.
- `apps/web/core/components/issues/issue-layouts/spreadsheet/columns/index.ts` — re-exporta `parent-breadcrumb-column`.
- `apps/web/ce/components/issues/issue-layouts/utils.tsx`
  - `SPREADSHEET_COLUMNS.parent_breadcrumb = SpreadsheetParentBreadcrumbColumn`.
  - `SpreadSheetPropertyIconMap.ParentBreadcrumbIcon = ListTree` (ícone do `lucide-react`).

**i18n**

- `packages/i18n/src/locales/en/work-item.json` e `pt-BR/work-item.json`
  - Nova seção `issue.parent_breadcrumb.*` com `column` (header da coluna) e `tooltip_full` (heading do tooltip).
  - Demais locales caem no fallback i18next para `en`.

## Fluxo end-to-end

1. Frontend abre uma view (kanban/list/spreadsheet/calendar/gantt) → faz GET na rota de listagem (`IssueViewSet.list` ou `IssuePaginatedViewSet.list`).
2. Backend monta a queryset, projeta com `.values(*required_fields)` em `issue_on_results`, e em seguida chama `attach_parent_chain(rows)`.
3. `attach_parent_chain` coleta os ids com `parent_id != null` e dispara **uma** query `WITH RECURSIVE` que devolve, para cada id, a lista de ancestrais (raiz → pai imediato).
4. Cada dict de issue ganha o campo `parent_chain`. Resposta sai com o campo.
5. Frontend recebe, MobX guarda no `issueMap` (root store usa spread; o sub-store `issue.store.ts` inclui `parent_chain` na allowlist explícita).
6. Spreadsheet: a coluna "Parent path" (gateada por `displayProperties.parent_breadcrumb`) renderiza `<ParentBreadcrumb chain={issue.parent_chain} />`. Outros layouts: `all-properties.tsx` renderiza o badge gateado pela mesma display property.
7. Clicar em qualquer nó do breadcrumb chama `handleRedirection` (peek overview do ancestral).

## Como testar

```bash
# Backend (smoke direto na queryset)
cd apps/api
python manage.py shell
# >>> from plane.utils.grouper import fetch_parent_chains, attach_parent_chain
# >>> from plane.db.models import Issue
# >>> ids = list(Issue.issue_objects.filter(parent__isnull=False).values_list("id", flat=True)[:5])
# >>> fetch_parent_chains(ids)
```

```bash
# Frontend
pnpm install
pnpm --filter web dev
```

**Smoke manual:**

1. Criar 3 issues encadeadas: `A` (raiz) → `Y` (parent=A) → `X` (parent=Y).
2. Abrir a view Spreadsheet do projeto → confirmar coluna "Parent path" na linha de `X` mostra `A > Y`.
3. Toggle em "Display properties" → coluna some/aparece.
4. Clicar em `A` no breadcrumb → peek-overview de `A` abre.
5. Repetir em Kanban / List / Calendar / Gantt → badge "A > Y" aparece no card de `X`.
6. Criar um 4º nível (`Z` com parent=X) e verificar o ellipsis `A > … > X` quando a chain tem 4+ nós.

## Pitfalls específicos

- **`getComputedDisplayProperties` é uma whitelist hardcoded — sem isso, o toggle "esquece" a cada navegação** (descoberto após o deploy). `packages/utils/src/work-item/base.ts:getComputedDisplayProperties` re-constrói o objeto `displayProperties` listando cada chave conhecida (`assignee`, `start_date`, …). Qualquer chave fora da lista é dropada toda vez que o filtro store recarrega do backend (`fetchFilters`). Sintoma: usuário liga "Caminho do pai", a coluna aparece, navega, volta, ela some — o PATCH gravou OK no `display_properties` JSONB mas o load passa pelo helper que filtra fora. **Fix:** adicionar `parent_breadcrumb: displayProperties?.parent_breadcrumb ?? true` ao helper. Lição reutilizável: ao adicionar qualquer display property nova, atualizar TANTO `IIssueDisplayProperties` (type) QUANTO `getComputedDisplayProperties` (whitelist) — não basta o type.
- **5 `get_default_display_properties()` espalhados, não 1**: além de `db/models/issue.py` (project user property), existem versões idênticas em `cycle.py`, `module.py`, `view.py` (saved views) e `workspace.py` (workspace user property + `view_props` nested). Cada uma define o default para registros novos do seu próprio JSONB. Pular qualquer uma faz a coluna nascer desligada em views daquele tipo.
- **`get_default_display_properties()` é lazy — só vale para registros novos** (descoberto no deploy do CT 105 em 2026-05-27). Após subir a feature, o usuário não viu nada na tela: a coluna estava implementada, o backend devolvia `parent_chain` corretamente, mas o `WithDisplayPropertiesHOC` esconde tudo se `displayProperties.parent_breadcrumb` for falsy. Causa: o default novo só entra em `ProjectUserProperty` recém-criados; as 13 linhas que já existiam tinham `display_properties` sem o flag. **Duas saídas:**
  1. Cada usuário liga manualmente: filtros → "Display properties" → clica "Caminho do pai" (a UI já lista o toggle porque eu adicionei o item em `ISSUE_DISPLAY_PROPERTIES` e `ISSUE_DISPLAY_PROPERTIES_KEYS`).
  2. Backfill em massa no banco:
     ```sql
     UPDATE project_user_properties
     SET display_properties = jsonb_set(display_properties, '{parent_breadcrumb}', 'true'::jsonb, true)
     WHERE NOT (display_properties ? 'parent_breadcrumb');
     ```
     Aplicar **uma vez** após o deploy. Generaliza para qualquer display property nova: o default no model só protege registros novos; legados precisam ser tocados explicitamente.
- **CTE em queries pesadas**: o `WITH RECURSIVE` é eficiente, mas em projetos com hierarquias muito profundas (10+ níveis) pode adicionar latência. Mitigação: o CTE filtra por `id = ANY(%s)` (só os ids da página atual), então o custo é proporcional ao tamanho da página × profundidade média.
- **Issues raiz não geram query**: `attach_parent_chain` só dispara a CTE se ao menos uma issue da página tem `parent_id != null`. Listas onde todas as issues são raiz custam 0 queries adicionais.
- **Public API (`apps/api/plane/api/serializers/issue.py`) não expõe `parent_chain`** — usa `exclude` em vez de `fields`, então só campos do model entram. Decisão consciente: consumidores do REST público não têm UI para isso. Se precisar no futuro, declarar `parent_chain` explicitamente lá.
- **Sort header da coluna spreadsheet é no-op** (cai em `sort_order` em ambas as opções). Sort real por profundidade/nome-da-raiz exige CTE no `ORDER BY` do queryset principal — v2.

## Fora do escopo (v2)

- Sort por `parent_chain` no servidor.
- Filtro "mostrar só itens com pai" / "mostrar só itens raiz".
- Edição inline do parent direto pelo breadcrumb (já existe em peek-overview).
- Breadcrumb nas notificações / dashboards.
- Cache do CTE em Redis quando a hierarquia muda raramente.
