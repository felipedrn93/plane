# Spreadsheet Column Reordering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que cada usuário reordene as colunas da Spreadsheet view via drag no header, com persistência por contexto (project, cycle, module, workspace, project view) per-user.

**Architecture:** Adicionar campo `display_properties_order` (JSON array de chaves) em 4 models existentes de user properties + criar nova tabela `IssueViewUserProperty` para views custom (hoje o `IssueView.display_properties` é compartilhado, não per-user). Frontend lê/escreve esse campo via os mesmos endpoints REST de user properties, sanitiza no carregamento (chaves inválidas filtradas, dedup, novas propriedades acrescentadas no fim), e aplica drag-and-drop horizontal no `SpreadsheetHeader` usando `@atlaskit/pragmatic-drag-and-drop` (já no projeto).

**Tech Stack:** Django 5 + DRF (backend), Next.js + React + MobX + TypeScript + `@atlaskit/pragmatic-drag-and-drop` (frontend), Postgres.

**Spec de referência:** `docs/superpowers/specs/2026-05-27-spreadsheet-column-reordering-design.md`

---

## File Structure

### Backend (Python)

**Modificar:**
- `apps/api/plane/db/models/project.py` (linha ~342) — adicionar campo em `ProjectUserProperty`
- `apps/api/plane/db/models/cycle.py` (linha ~133) — adicionar campo em `CycleUserProperties`
- `apps/api/plane/db/models/module.py` (linha ~193) — adicionar campo em `ModuleUserProperties`
- `apps/api/plane/db/models/workspace.py` (linha ~316) — adicionar campo em `WorkspaceUserProperties`
- `apps/api/plane/db/models/view.py` — adicionar nova classe `IssueViewUserProperty`
- `apps/api/plane/db/models/__init__.py` — exportar `IssueViewUserProperty`
- `apps/api/plane/app/urls/views.py` — registrar duas novas rotas (project view e workspace view user properties)

**Criar:**
- `apps/api/plane/db/migrations/0123_display_properties_order.py` — adiciona campo nos 4 models + cria nova tabela
- `apps/api/plane/app/serializers/view.py` (modificar ou criar) — `IssueViewUserPropertySerializer`
- `apps/api/plane/app/views/view/user_properties.py` — novos endpoints

**Testes:**
- `apps/api/plane/tests/test_user_property_order.py` (ou local equivalente — investigar estrutura de testes Python primeiro)

### Frontend (TypeScript)

**Modificar:**
- `packages/constants/src/issue/filter.ts` — adicionar `DISPLAY_PROPERTIES_ORDER` ao enum `EIssueFilterType` + tipos derivados
- `packages/types/src/view-props.ts` — adicionar `TIssueDisplayPropertiesOrder` e estender `IIssueFilters`
- `packages/types/src/issues/issue.ts` (ou onde estiver `IProjectUserPropertiesResponse`) — adicionar campo no tipo
- `apps/web/core/store/issue/helpers/issue-filter-helper.store.ts` — método `computedDisplayPropertiesOrder`
- `apps/web/core/store/issue/project/filter.store.ts` — fetch + case novo no switch
- `apps/web/core/store/issue/cycle/filter.store.ts` — idem
- `apps/web/core/store/issue/module/filter.store.ts` — idem
- `apps/web/core/store/issue/workspace/filter.store.ts` — idem
- `apps/web/core/store/issue/project-views/filter.store.ts` — idem (precisa de service novo)
- `apps/web/core/services/view.service.ts` — métodos `getViewUserProperties`/`updateViewUserProperties`
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-view.tsx` — passar ordem do store
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-table.tsx` — propagar `onReorder`
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header.tsx` — wire onReorder
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header-column.tsx` — virar draggable

**Criar:**
- `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-column-dnd.helpers.ts` — funções puras de DnD (calcular from/to)

**Testes:**
- Investigar se existe setup Jest/Vitest. Se sim, testes unitários do helper. Se não, criar setup mínimo só pra esse helper (não é bloqueante; smoke test manual cobre o caminho feliz).

---

## Phase 1: Backend — modelos, migration, endpoints

### Task 1: Adicionar `display_properties_order` aos 4 models existentes

**Files:**
- Modify: `apps/api/plane/db/models/project.py` (após linha 353)
- Modify: `apps/api/plane/db/models/cycle.py` (após linha 143)
- Modify: `apps/api/plane/db/models/module.py` (após linha 203)
- Modify: `apps/api/plane/db/models/workspace.py` (após linha 334)

- [ ] **Step 1: Editar `project.py`**

Abrir `apps/api/plane/db/models/project.py`. Localizar `class ProjectUserProperty` (linha 342). Após a linha `rich_filters = models.JSONField(default=dict)` (linha 353), adicionar:

```python
    display_properties_order = models.JSONField(default=list)
```

- [ ] **Step 2: Editar `cycle.py`**

Abrir `apps/api/plane/db/models/cycle.py`. Localizar `class CycleUserProperties` (linha 133). Após `rich_filters = models.JSONField(default=dict)` (linha 143), adicionar:

```python
    display_properties_order = models.JSONField(default=list)
```

- [ ] **Step 3: Editar `module.py`**

Abrir `apps/api/plane/db/models/module.py`. Localizar `class ModuleUserProperties` (linha 193). Após `rich_filters = models.JSONField(default=dict)` (linha 203), adicionar:

```python
    display_properties_order = models.JSONField(default=list)
```

- [ ] **Step 4: Editar `workspace.py`**

Abrir `apps/api/plane/db/models/workspace.py`. Localizar `class WorkspaceUserProperties` (linha 316). Após `rich_filters = models.JSONField(default=dict)` (linha 334), adicionar:

```python
    display_properties_order = models.JSONField(default=list)
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/plane/db/models/project.py apps/api/plane/db/models/cycle.py apps/api/plane/db/models/module.py apps/api/plane/db/models/workspace.py
git commit -m "feat(api): add display_properties_order to user property models"
```

---

### Task 2: Criar model `IssueViewUserProperty`

**Files:**
- Modify: `apps/api/plane/db/models/view.py`
- Modify: `apps/api/plane/db/models/__init__.py`

- [ ] **Step 1: Adicionar a classe ao `view.py`**

Abrir `apps/api/plane/db/models/view.py`. No topo, garantir que `Q` está importado:

```python
from django.db import models
from django.db.models import Q  # <- garantir
```

No final do arquivo (após `class IssueView`), adicionar:

```python
class IssueViewUserProperty(WorkspaceBaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="view_user_properties",
    )
    view = models.ForeignKey(
        "db.IssueView",
        on_delete=models.CASCADE,
        related_name="view_user_properties",
    )
    display_properties_order = models.JSONField(default=list)

    class Meta:
        verbose_name = "Issue View User Property"
        verbose_name_plural = "Issue View User Properties"
        db_table = "issue_view_user_properties"
        ordering = ("-created_at",)
        unique_together = ["user", "view", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "view"],
                condition=Q(deleted_at__isnull=True),
                name="view_user_property_unique_user_view_when_deleted_at_null",
            )
        ]

    def __str__(self):
        return f"{self.view.name} {self.user.email}"
```

- [ ] **Step 2: Exportar do `__init__.py`**

Abrir `apps/api/plane/db/models/__init__.py`. Localizar o bloco de imports do `view`. Adicionar `IssueViewUserProperty` no `from .view import (...)`:

```python
from .view import (
    GlobalView,
    IssueView,
    IssueViewUserProperty,  # <- novo
)
```

(O nome exato dos imports existentes precisa ser preservado — copiar exatamente o que está no arquivo e só acrescentar `IssueViewUserProperty`.)

- [ ] **Step 3: Commit**

```bash
git add apps/api/plane/db/models/view.py apps/api/plane/db/models/__init__.py
git commit -m "feat(api): add IssueViewUserProperty model for per-user view settings"
```

---

### Task 3: Gerar migration

**Files:**
- Create: `apps/api/plane/db/migrations/0123_display_properties_order.py`

- [ ] **Step 1: Gerar migration via Django**

Rodar (de dentro de `apps/api/`):

```bash
cd apps/api
python manage.py makemigrations db --name display_properties_order
```

Esperado: cria `apps/api/plane/db/migrations/0123_display_properties_order.py` contendo `AddField` para os 4 models existentes + `CreateModel` para `IssueViewUserProperty`.

- [ ] **Step 2: Inspecionar a migration gerada**

Abrir `apps/api/plane/db/migrations/0123_display_properties_order.py`. Conferir que:
- `dependencies` aponta para `('db', '0122_issue_recurrence_pattern')`.
- Tem 4 `migrations.AddField` (um por model: ProjectUserProperty, CycleUserProperties, ModuleUserProperties, WorkspaceUserProperties), todos com `field=models.JSONField(default=list)`.
- Tem 1 `migrations.CreateModel` para `IssueViewUserProperty`.
- Tem `AddConstraint` para o `UniqueConstraint` do model novo.

Se algo estiver diferente, AJUSTAR manualmente a migration para refletir o spec — não regenerar.

- [ ] **Step 3: Aplicar migration localmente**

```bash
python manage.py migrate db
```

Esperado: "Applying db.0123_display_properties_order... OK".

- [ ] **Step 4: Verificar no banco**

Rodar `python manage.py dbshell` e executar:

```sql
\d project_user_properties
\d cycle_user_properties
\d module_user_properties
\d workspace_user_properties
\d issue_view_user_properties
```

Esperado: nos 4 primeiros aparece a coluna `display_properties_order jsonb`. Na última (`issue_view_user_properties`) o schema completo com `user_id`, `view_id`, `display_properties_order`, `workspace_id`, etc.

- [ ] **Step 5: Commit**

```bash
git add apps/api/plane/db/migrations/0123_display_properties_order.py
git commit -m "feat(api): migrate display_properties_order column and IssueViewUserProperty table"
```

---

### Task 4: Endpoints REST para `IssueViewUserProperty`

**Files:**
- Create: `apps/api/plane/app/views/view/user_properties.py`
- Modify: `apps/api/plane/app/views/view/__init__.py` (exportar novos endpoints)
- Modify: `apps/api/plane/app/serializers/view.py` (adicionar serializer)
- Modify: `apps/api/plane/app/serializers/__init__.py` (exportar serializer)
- Modify: `apps/api/plane/app/urls/views.py` (registrar 2 rotas)

- [ ] **Step 1: Criar serializer**

Abrir `apps/api/plane/app/serializers/view.py`. No final, adicionar:

```python
from plane.db.models import IssueViewUserProperty  # <- adicionar import junto aos outros


class IssueViewUserPropertySerializer(BaseSerializer):
    class Meta:
        model = IssueViewUserProperty
        fields = "__all__"
        read_only_fields = ["user", "workspace", "view"]
```

(`BaseSerializer` já é importado nesse arquivo — confirmar antes de duplicar import.)

- [ ] **Step 2: Exportar serializer**

Abrir `apps/api/plane/app/serializers/__init__.py`. Localizar o bloco de `from .view import (...)` e adicionar `IssueViewUserPropertySerializer` à lista.

- [ ] **Step 3: Criar endpoints**

Criar `apps/api/plane/app/views/view/user_properties.py` com o conteúdo:

```python
# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueViewUserPropertySerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import IssueViewUserProperty


class IssueViewUserPropertyEndpoint(BaseAPIView):
    """GET/PATCH per-user settings for a project-scoped IssueView."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, view_id):
        prop, _ = IssueViewUserProperty.objects.get_or_create(
            user=request.user,
            view_id=view_id,
            workspace__slug=slug,
        )
        return Response(IssueViewUserPropertySerializer(prop).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def patch(self, request, slug, project_id, view_id):
        prop, _ = IssueViewUserProperty.objects.get_or_create(
            user=request.user,
            view_id=view_id,
            workspace__slug=slug,
        )
        serializer = IssueViewUserPropertySerializer(prop, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class WorkspaceIssueViewUserPropertyEndpoint(BaseAPIView):
    """GET/PATCH per-user settings for a workspace-scoped IssueView."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, view_id):
        prop, _ = IssueViewUserProperty.objects.get_or_create(
            user=request.user,
            view_id=view_id,
            workspace__slug=slug,
        )
        return Response(IssueViewUserPropertySerializer(prop).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def patch(self, request, slug, view_id):
        prop, _ = IssueViewUserProperty.objects.get_or_create(
            user=request.user,
            view_id=view_id,
            workspace__slug=slug,
        )
        serializer = IssueViewUserPropertySerializer(prop, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
```

**Nota:** o argumento `level="WORKSPACE"` em `allow_permission` é hipotético — antes de implementar, conferir em `apps/api/plane/app/permissions/__init__.py` ou em endpoints workspace-level existentes (ex: `WorkspaceViewIssuesViewSet` em `apps/api/plane/app/views/workspace.py`) qual é a assinatura real. Copiar exatamente o padrão usado nas views de `globalview` ou `workspaceview`. Se o nível é inferido pela URL/router, não precisa do argumento.

- [ ] **Step 4: Exportar endpoints**

Abrir `apps/api/plane/app/views/view/__init__.py`. Adicionar:

```python
from .user_properties import (
    IssueViewUserPropertyEndpoint,
    WorkspaceIssueViewUserPropertyEndpoint,
)
```

- [ ] **Step 5: Registrar URLs**

Abrir `apps/api/plane/app/urls/views.py`. Localizar imports no topo e adicionar:

```python
from plane.app.views import (
    # ... existentes ...
    IssueViewUserPropertyEndpoint,
    WorkspaceIssueViewUserPropertyEndpoint,
)
```

Dentro de `urlpatterns`, após as rotas existentes de views, adicionar:

```python
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/views/<uuid:view_id>/user-properties/",
        IssueViewUserPropertyEndpoint.as_view(),
        name="project-view-user-properties",
    ),
    path(
        "workspaces/<str:slug>/views/<uuid:view_id>/user-properties/",
        WorkspaceIssueViewUserPropertyEndpoint.as_view(),
        name="workspace-view-user-properties",
    ),
```

- [ ] **Step 6: Smoke test do endpoint**

Subir a API local (`python manage.py runserver` ou docker-compose conforme o fork). Com sessão autenticada, testar com `curl` ou Postman:

```bash
# PATCH inicial (cria o registro)
curl -X PATCH http://localhost:8000/api/workspaces/<slug>/projects/<pid>/views/<vid>/user-properties/ \
  -H "Content-Type: application/json" \
  -H "Cookie: <session-cookie>" \
  -d '{"display_properties_order": ["state","priority","assignee"]}'

# GET verifica que persistiu
curl http://localhost:8000/api/workspaces/<slug>/projects/<pid>/views/<vid>/user-properties/ \
  -H "Cookie: <session-cookie>"
```

Esperado: PATCH retorna 200 com o JSON salvo; GET retorna o mesmo array.

- [ ] **Step 7: Commit**

```bash
git add apps/api/plane/app/serializers/view.py apps/api/plane/app/serializers/__init__.py apps/api/plane/app/views/view/user_properties.py apps/api/plane/app/views/view/__init__.py apps/api/plane/app/urls/views.py
git commit -m "feat(api): endpoints for IssueViewUserProperty (project + workspace scope)"
```

---

### Task 5: Confirmar que serializers dos 4 models existentes expõem o campo novo

**Files:**
- Read: `apps/api/plane/app/serializers/issue.py` (linha ~359: `ProjectUserPropertySerializer`)
- Read: serializers de `CycleUserProperties`, `ModuleUserProperties`, `WorkspaceUserProperties`

- [ ] **Step 1: Confirmar `ProjectUserPropertySerializer`**

Abrir `apps/api/plane/app/serializers/issue.py` linha 359. Conferir que tem `fields = "__all__"`. Se sim, **nada a fazer** — Django adiciona o campo automaticamente.

- [ ] **Step 2: Conferir os outros 3**

Procurar (Grep) por `CycleUserPropertySerializer`, `ModuleUserPropertySerializer`, `WorkspaceUserPropertiesSerializer` (nomes podem variar — verificar). Em todos: confirmar `fields = "__all__"`.

Se algum deles usar lista explícita de fields ao invés de `__all__`, **adicionar** `"display_properties_order"` à lista.

- [ ] **Step 3: Smoke test via API**

Com a API rodando, fazer GET em `/api/workspaces/<slug>/projects/<pid>/user-properties/` e verificar que a resposta contém `"display_properties_order": []`.

- [ ] **Step 4: Commit (se houve mudança)**

```bash
git add apps/api/plane/app/serializers/
git commit -m "feat(api): expose display_properties_order in user property serializers"
```

Se não houve mudança, pular esse step.

---

## Phase 2: Frontend — tipos, constantes, helper de sanitização

### Task 6: Adicionar tipos e enum no monorepo

**Files:**
- Modify: `packages/constants/src/issue/filter.ts`
- Modify: `packages/types/src/view-props.ts`
- Modify: `packages/types/src/issues/issue.ts` (ou onde estiver `IProjectUserPropertiesResponse` — confirmar via Grep)

- [ ] **Step 1: Adicionar `DISPLAY_PROPERTIES_ORDER` ao enum**

Abrir `packages/constants/src/issue/filter.ts`. Localizar `enum EIssueFilterType`. Adicionar:

```ts
export enum EIssueFilterType {
  FILTERS = "filters",
  DISPLAY_FILTERS = "display_filters",
  DISPLAY_PROPERTIES = "display_properties",
  DISPLAY_PROPERTIES_ORDER = "display_properties_order",  // novo
  KANBAN_FILTERS = "kanban_filters",
}
```

(Se já existir um `TSupportedFilterTypeForUpdate` derivado desse enum, conferir que o novo valor está incluído. Em geral é um union type — adicionar `EIssueFilterType.DISPLAY_PROPERTIES_ORDER`.)

- [ ] **Step 2: Adicionar `TIssueDisplayPropertiesOrder`**

Abrir `packages/types/src/view-props.ts`. Adicionar:

```ts
import type { IIssueDisplayProperties } from "./issues";  // confirmar caminho relativo correto

export type TIssueDisplayPropertiesOrder = (keyof IIssueDisplayProperties)[];
```

- [ ] **Step 3: Estender `IIssueFilters`**

No mesmo arquivo `view-props.ts`, localizar `interface IIssueFilters`. Adicionar o campo:

```ts
export interface IIssueFilters {
  // ... existentes (richFilters, displayFilters, displayProperties, kanbanFilters)
  displayPropertiesOrder?: TIssueDisplayPropertiesOrder;
}
```

`?` (opcional) para não quebrar código existente que constrói o objeto sem esse campo.

- [ ] **Step 4: Estender `IProjectUserPropertiesResponse`**

Grep por `IProjectUserPropertiesResponse` para achar o arquivo. Adicionar campo:

```ts
export interface IProjectUserPropertiesResponse {
  // ... existentes
  display_properties_order?: string[];
}
```

Repetir para tipos análogos: `ICycleUserPropertiesResponse`, `IModuleUserPropertiesResponse`, `IWorkspaceUserPropertiesResponse` (se existirem). Se compartilharem uma base, atualizar a base.

- [ ] **Step 5: Adicionar tipo para View user properties**

No mesmo arquivo (ou em `packages/types/src/views.ts`), adicionar:

```ts
export interface IIssueViewUserPropertiesResponse {
  id: string;
  user: string;
  view: string;
  workspace: string;
  display_properties_order: string[];
}
```

- [ ] **Step 6: Adicionar `TSupportedFilterForUpdate` (se aplicável)**

Procurar (Grep) por `TSupportedFilterForUpdate`. Se for um union type que enumera todos os payloads possíveis, adicionar `TIssueDisplayPropertiesOrder`.

- [ ] **Step 7: Compilar tipos**

```bash
pnpm --filter @plane/types build
pnpm --filter @plane/constants build
```

Esperado: sem erros.

- [ ] **Step 8: Commit**

```bash
git add packages/constants packages/types
git commit -m "feat(types): add DISPLAY_PROPERTIES_ORDER filter type and TIssueDisplayPropertiesOrder"
```

---

### Task 7: Helper `computedDisplayPropertiesOrder`

**Files:**
- Modify: `apps/web/core/store/issue/helpers/issue-filter-helper.store.ts`
- Test: opcional — ver Step 7

- [ ] **Step 1: Adicionar import no helper**

Abrir `apps/web/core/store/issue/helpers/issue-filter-helper.store.ts`. Garantir imports:

```ts
import { SPREADSHEET_PROPERTY_LIST } from "@plane/constants";
import type { TIssueDisplayPropertiesOrder } from "@plane/types";
```

- [ ] **Step 2: Adicionar método à interface**

Em `interface IIssueFilterHelperStore`, adicionar:

```ts
computedDisplayPropertiesOrder(savedOrder?: unknown): TIssueDisplayPropertiesOrder;
```

- [ ] **Step 3: Implementar o método na classe**

Em `class IssueFilterHelperStore`, adicionar (depois de `computedDisplayProperties`):

```ts
/**
 * Sanitiza a ordem salva: descarta chaves inválidas, dedupa, e anexa
 * no fim qualquer chave do default que não esteja presente (para
 * cobrir propriedades novas adicionadas depois do save).
 */
computedDisplayPropertiesOrder = (savedOrder?: unknown): TIssueDisplayPropertiesOrder => {
  const defaultOrder = SPREADSHEET_PROPERTY_LIST;
  if (!Array.isArray(savedOrder) || savedOrder.length === 0) {
    return [...defaultOrder];
  }

  const validKeys = new Set<string>(defaultOrder);
  const seen = new Set<string>();
  const sanitized: TIssueDisplayPropertiesOrder = [];

  for (const key of savedOrder) {
    if (typeof key !== "string") continue;
    if (!validKeys.has(key)) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    sanitized.push(key as TIssueDisplayPropertiesOrder[number]);
  }

  for (const key of defaultOrder) {
    if (!seen.has(key)) sanitized.push(key);
  }

  return sanitized;
};
```

- [ ] **Step 4: Estender `computedIssueFilters` para incluir o novo campo**

No método `computedIssueFilters`, adicionar:

```ts
computedIssueFilters = (filters: IIssueFilters): IIssueFilters => ({
  richFilters: isEmpty(filters?.richFilters) ? {} : filters?.richFilters,
  displayFilters: isEmpty(filters?.displayFilters) ? undefined : filters?.displayFilters,
  displayProperties: isEmpty(filters?.displayProperties) ? undefined : filters?.displayProperties,
  displayPropertiesOrder: filters?.displayPropertiesOrder,  // <- novo
  kanbanFilters: isEmpty(filters?.kanbanFilters) ? undefined : filters?.kanbanFilters,
});
```

- [ ] **Step 5: Verificar typecheck**

```bash
pnpm --filter web check:types
```

Esperado: sem erros.

- [ ] **Step 6: Commit**

```bash
git add apps/web/core/store/issue/helpers/issue-filter-helper.store.ts
git commit -m "feat(web): add computedDisplayPropertiesOrder helper"
```

- [ ] **Step 7 (opcional): Teste unitário do helper**

Se houver setup Jest/Vitest no repo (verificar `apps/web/vitest.config.ts` ou similar), criar `apps/web/core/store/issue/helpers/__tests__/computed-display-properties-order.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { IssueFilterHelperStore } from "../issue-filter-helper.store";
import { SPREADSHEET_PROPERTY_LIST } from "@plane/constants";

describe("computedDisplayPropertiesOrder", () => {
  const helper = new IssueFilterHelperStore();

  it("retorna default puro quando saved é undefined", () => {
    expect(helper.computedDisplayPropertiesOrder(undefined)).toEqual([...SPREADSHEET_PROPERTY_LIST]);
  });

  it("retorna default puro quando saved é []", () => {
    expect(helper.computedDisplayPropertiesOrder([])).toEqual([...SPREADSHEET_PROPERTY_LIST]);
  });

  it("respeita ordem salva e acrescenta faltantes no fim", () => {
    const result = helper.computedDisplayPropertiesOrder(["priority", "state"]);
    expect(result[0]).toBe("priority");
    expect(result[1]).toBe("state");
    expect(new Set(result)).toEqual(new Set(SPREADSHEET_PROPERTY_LIST));
  });

  it("descarta chaves inválidas", () => {
    const result = helper.computedDisplayPropertiesOrder(["priority", "lixo", "state"]);
    expect(result).not.toContain("lixo");
    expect(result.slice(0, 2)).toEqual(["priority", "state"]);
  });

  it("descarta duplicatas", () => {
    const result = helper.computedDisplayPropertiesOrder(["state", "state", "priority"]);
    const stateCount = result.filter((k) => k === "state").length;
    expect(stateCount).toBe(1);
  });

  it("é resiliente a tipo errado", () => {
    expect(helper.computedDisplayPropertiesOrder(null)).toEqual([...SPREADSHEET_PROPERTY_LIST]);
    expect(helper.computedDisplayPropertiesOrder({} as any)).toEqual([...SPREADSHEET_PROPERTY_LIST]);
    expect(helper.computedDisplayPropertiesOrder("nope" as any)).toEqual([...SPREADSHEET_PROPERTY_LIST]);
  });
});
```

Rodar: `pnpm --filter web test computed-display-properties-order`. Esperado: 6 passes.

```bash
git add apps/web/core/store/issue/helpers/__tests__/
git commit -m "test(web): cover computedDisplayPropertiesOrder edge cases"
```

Se não houver setup de testes, pular esse step. Smoke test manual cobre depois.

---

## Phase 3: Frontend — services e filter stores

### Task 8: Service novo para `IssueViewUserProperty`

**Files:**
- Modify: `apps/web/core/services/view.service.ts`

- [ ] **Step 1: Adicionar imports e métodos**

Abrir `apps/web/core/services/view.service.ts`. Adicionar imports no topo:

```ts
import type { IIssueViewUserPropertiesResponse } from "@plane/types";
```

No final da classe `ViewService` (antes do último `}`), adicionar:

```ts
// User Properties (per-user view settings)
async getViewUserProperties(
  workspaceSlug: string,
  projectId: string,
  viewId: string
): Promise<IIssueViewUserPropertiesResponse> {
  return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/views/${viewId}/user-properties/`)
    .then((response) => response?.data)
    .catch((error) => {
      throw error?.response?.data;
    });
}

async updateViewUserProperties(
  workspaceSlug: string,
  projectId: string,
  viewId: string,
  data: Partial<IIssueViewUserPropertiesResponse>
): Promise<IIssueViewUserPropertiesResponse> {
  return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/views/${viewId}/user-properties/`, data)
    .then((response) => response?.data)
    .catch((error) => {
      throw error?.response?.data;
    });
}

async getWorkspaceViewUserProperties(
  workspaceSlug: string,
  viewId: string
): Promise<IIssueViewUserPropertiesResponse> {
  return this.get(`/api/workspaces/${workspaceSlug}/views/${viewId}/user-properties/`)
    .then((response) => response?.data)
    .catch((error) => {
      throw error?.response?.data;
    });
}

async updateWorkspaceViewUserProperties(
  workspaceSlug: string,
  viewId: string,
  data: Partial<IIssueViewUserPropertiesResponse>
): Promise<IIssueViewUserPropertiesResponse> {
  return this.patch(`/api/workspaces/${workspaceSlug}/views/${viewId}/user-properties/`, data)
    .then((response) => response?.data)
    .catch((error) => {
      throw error?.response?.data;
    });
}
```

- [ ] **Step 2: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/core/services/view.service.ts
git commit -m "feat(web): add view user properties service methods"
```

---

### Task 9: Wire-up no `project/filter.store.ts`

**Files:**
- Modify: `apps/web/core/store/issue/project/filter.store.ts`

- [ ] **Step 1: Atualizar `fetchFilters`**

Abrir `apps/web/core/store/issue/project/filter.store.ts`. Localizar `fetchFilters` (linha ~137). Após `const displayProperties = this.computedDisplayProperties(_filters?.display_properties);`, adicionar:

```ts
const displayPropertiesOrder = this.computedDisplayPropertiesOrder(_filters?.display_properties_order);
```

No `runInAction` no final, adicionar:

```ts
set(this.filters, [projectId, "displayPropertiesOrder"], displayPropertiesOrder);
```

- [ ] **Step 2: Adicionar case no switch de `updateFilters`**

No método `updateFilters`, switch `case`, após o `case EIssueFilterType.DISPLAY_PROPERTIES` block (linha ~272), adicionar:

```ts
case EIssueFilterType.DISPLAY_PROPERTIES_ORDER: {
  const newOrder = this.computedDisplayPropertiesOrder(filters);
  _filters.displayPropertiesOrder = newOrder;

  runInAction(() => {
    set(this.filters, [projectId, "displayPropertiesOrder"], newOrder);
  });

  await this.projectService.updateProjectUserProperties(workspaceSlug, projectId, {
    display_properties_order: newOrder,
  });
  break;
}
```

- [ ] **Step 3: Atualizar tipo local `_filters` (se for tipado)**

No início de `updateFilters`, onde `_filters` é construído (linha ~198), adicionar campo se estiver tipando explicitamente:

```ts
const _filters = {
  richFilters: this.filters[projectId].richFilters,
  displayFilters: this.filters[projectId].displayFilters as IIssueDisplayFilterOptions,
  displayProperties: this.filters[projectId].displayProperties as IIssueDisplayProperties,
  displayPropertiesOrder: this.filters[projectId].displayPropertiesOrder as TIssueDisplayPropertiesOrder,
  kanbanFilters: this.filters[projectId].kanbanFilters as TIssueKanbanFilters,
};
```

Importar `TIssueDisplayPropertiesOrder` no topo.

- [ ] **Step 4: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/core/store/issue/project/filter.store.ts
git commit -m "feat(web): persist display_properties_order in project filter store"
```

---

### Task 10: Wire-up no `cycle/filter.store.ts`

**Files:**
- Modify: `apps/web/core/store/issue/cycle/filter.store.ts`
- Modify (talvez): `apps/web/core/services/cycle/cycle.service.ts` (ou onde estiver o service de cycle — Grep `patchCycleUserProperties` ou `updateCycleUserProperties`)

- [ ] **Step 1: Confirmar API do service de cycle user properties**

Grep no projeto:

```bash
# (via Grep tool)
pattern: "CycleUserPropert|cycle.*user.*propert|cycle.*properties"
glob: "apps/web/core/services/**/*.ts"
```

Identificar o método existente que faz PATCH em `/api/workspaces/<slug>/projects/<pid>/cycles/<cid>/user-properties/`. Tipicamente algo como `patchCycleProperties` ou `updateCycleUserProperties`. Se NÃO existir, **criar** seguindo o padrão de `updateProjectUserProperties` em `project.service.ts:109`.

- [ ] **Step 2: Atualizar `fetchFilters` do cycle store**

Abrir `apps/web/core/store/issue/cycle/filter.store.ts`. Localizar `fetchFilters`. Após `const displayProperties = this.computedDisplayProperties(...)`, adicionar:

```ts
const displayPropertiesOrder = this.computedDisplayPropertiesOrder(_filters?.display_properties_order);
```

No `runInAction` final, adicionar:

```ts
set(this.filters, [cycleId, "displayPropertiesOrder"], displayPropertiesOrder);
```

- [ ] **Step 3: Adicionar case no switch do `updateFilters`**

Após o `case EIssueFilterType.DISPLAY_PROPERTIES` existente:

```ts
case EIssueFilterType.DISPLAY_PROPERTIES_ORDER: {
  const newOrder = this.computedDisplayPropertiesOrder(filters);
  _filters.displayPropertiesOrder = newOrder;

  runInAction(() => {
    set(this.filters, [cycleId, "displayPropertiesOrder"], newOrder);
  });

  // Substituir pelo nome real do método identificado no Step 1
  await this.cycleService.patchCycleProperties(workspaceSlug, projectId, cycleId, {
    display_properties_order: newOrder,
  });
  break;
}
```

Atualizar também o objeto `_filters` no início do método para incluir `displayPropertiesOrder` (igual fizemos no project store).

- [ ] **Step 4: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/core/store/issue/cycle/filter.store.ts apps/web/core/services/cycle/
git commit -m "feat(web): persist display_properties_order in cycle filter store"
```

---

### Task 10b: Wire-up no `module/filter.store.ts`

**Files:**
- Modify: `apps/web/core/store/issue/module/filter.store.ts`
- Modify (talvez): `apps/web/core/services/module/module.service.ts`

- [ ] **Step 1: Confirmar API do service de module user properties** — Grep análogo ao Step 1 da Task 10.

- [ ] **Step 2: Atualizar `fetchFilters`** — mesma estrutura da Task 10 Step 2, mas com `moduleId` no lugar de `cycleId`.

- [ ] **Step 3: Adicionar case no switch** — mesmo template, trocando `cycleService.patchCycleProperties` por `moduleService.patchModuleProperties` (nome real conforme Step 1).

- [ ] **Step 4: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/core/store/issue/module/filter.store.ts apps/web/core/services/module/
git commit -m "feat(web): persist display_properties_order in module filter store"
```

---

### Task 10c: Wire-up no `workspace/filter.store.ts`

**Files:**
- Modify: `apps/web/core/store/issue/workspace/filter.store.ts`
- Modify (talvez): `apps/web/core/services/workspace.service.ts` (ou similar)

- [ ] **Step 1: Confirmar API do service de workspace user properties** — Grep por `WorkspaceUserPropert` ou `workspace.*user.*propert` em `apps/web/core/services/`.

- [ ] **Step 2: Atualizar `fetchFilters`** — no workspace store o "context id" tipicamente é o próprio `workspaceSlug` (não há um sub-id como cycleId/moduleId). Confirmar olhando o código existente.

- [ ] **Step 3: Adicionar case no switch** — mesma estrutura.

- [ ] **Step 4: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/core/store/issue/workspace/filter.store.ts apps/web/core/services/
git commit -m "feat(web): persist display_properties_order in workspace filter store"
```

---

### Task 11: Wire-up no `project-views/filter.store.ts`

**Files:**
- Modify: `apps/web/core/store/issue/project-views/filter.store.ts`

Esse é mais elaborado porque o store hoje **não persiste** display properties no backend (só em memória).

- [ ] **Step 1: Importar service de view user properties**

No topo, garantir import:

```ts
import { ViewService } from "@/services/view.service";
```

E confirmar que `this.issueFilterService` existe — em alguns stores é `this.viewService`. Verificar no construtor.

- [ ] **Step 2: Atualizar `fetchFilters`**

`fetchFilters` hoje recebe `viewDetails` direto (não faz GET). Modificar para:
1. Após pegar `displayFilters` e `displayProperties` do `viewDetails`,
2. Fazer GET extra em `this.viewService.getViewUserProperties(workspaceSlug, projectId, viewId)` para pegar `display_properties_order`.
3. Sanear via `computedDisplayPropertiesOrder`.
4. Setar em `this.filters[viewId].displayPropertiesOrder`.

A assinatura atual de `fetchFilters` é `(workspaceSlug, projectId, viewId)` — `projectId` está disponível. Confirmar a assinatura exata e ajustar.

Se a view é workspace-level (project é null), chamar `getWorkspaceViewUserProperties` em vez. Detectar via `projectId` falsy.

- [ ] **Step 3: Adicionar case no switch**

No `updateFilters`, switch, adicionar:

```ts
case EIssueFilterType.DISPLAY_PROPERTIES_ORDER: {
  const newOrder = this.computedDisplayPropertiesOrder(filters);
  runInAction(() => {
    set(this.filters, [viewId, "displayPropertiesOrder"], newOrder);
  });
  if (projectId) {
    await this.viewService.updateViewUserProperties(workspaceSlug, projectId, viewId, {
      display_properties_order: newOrder,
    });
  } else {
    await this.viewService.updateWorkspaceViewUserProperties(workspaceSlug, viewId, {
      display_properties_order: newOrder,
    });
  }
  break;
}
```

- [ ] **Step 4: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/core/store/issue/project-views/filter.store.ts
git commit -m "feat(web): persist display_properties_order per-user for custom views"
```

---

## Phase 4: UI — drag-and-drop nas colunas

### Task 12: Helper puro de DnD

**Files:**
- Create: `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-column-dnd.helpers.ts`

- [ ] **Step 1: Criar arquivo com função pura de reorder**

```ts
import type { IIssueDisplayProperties } from "@plane/types";

export type TSpreadsheetColumnKey = keyof IIssueDisplayProperties;

/**
 * Move a coluna `from` para a posição `to` na lista.
 * Retorna nova lista (não muta entrada).
 */
export function moveColumn(
  list: TSpreadsheetColumnKey[],
  from: number,
  to: number
): TSpreadsheetColumnKey[] {
  if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) {
    return list;
  }
  const result = [...list];
  const [moved] = result.splice(from, 1);
  result.splice(to, 0, moved);
  return result;
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-column-dnd.helpers.ts
git commit -m "feat(web): add moveColumn helper for spreadsheet DnD"
```

---

### Task 13: Tornar `SpreadsheetHeaderColumn` draggable

**Files:**
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header-column.tsx`

**Referência canônica de uso de `@atlaskit/pragmatic-drag-and-drop` no projeto:** `apps/web/core/components/labels/label-drag-n-drop-HOC.tsx`. Copiar o pattern de `combine(draggable({...}), dropTargetForElements({...}))` dentro de `useEffect`.

- [ ] **Step 1: Reescrever o componente**

Substituir o conteúdo de `spreadsheet-header-column.tsx` por:

```tsx
/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import type { IIssueDisplayFilterOptions, IIssueDisplayProperties } from "@plane/types";
import { DropIndicator } from "@plane/ui";
import { cn } from "@plane/utils";
import { shouldRenderColumn } from "@/helpers/issue-filter.helper";
import { WithDisplayPropertiesHOC } from "../properties/with-display-properties-HOC";
import { HeaderColumn } from "./columns/header-column";

interface Props {
  displayProperties: IIssueDisplayProperties;
  property: keyof IIssueDisplayProperties;
  index: number;
  isEstimateEnabled: boolean;
  displayFilters: IIssueDisplayFilterOptions;
  handleDisplayFilterUpdate: (data: Partial<IIssueDisplayFilterOptions>) => void;
  onReorder?: (from: number, to: number) => void;
  isReorderEnabled?: boolean;
  isEpic?: boolean;
}

type DragData = { property: string; index: number };

export const SpreadsheetHeaderColumn = observer(function SpreadsheetHeaderColumn(props: Props) {
  const {
    displayProperties,
    displayFilters,
    property,
    index,
    handleDisplayFilterUpdate,
    onReorder,
    isReorderEnabled = false,
    isEpic = false,
  } = props;

  const tableHeaderCellRef = useRef<HTMLTableCellElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dropEdge, setDropEdge] = useState<"left" | "right" | null>(null);

  const shouldRenderProperty = shouldRenderColumn(property);

  useEffect(() => {
    const element = tableHeaderCellRef.current;
    if (!element || !isReorderEnabled || !onReorder) return;

    return combine(
      draggable({
        element,
        getInitialData: (): DragData => ({ property, index }),
        onDragStart: () => setIsDragging(true),
        onDrop: () => setIsDragging(false),
      }),
      dropTargetForElements({
        element,
        canDrop: ({ source }) => {
          const data = source.data as Partial<DragData>;
          return typeof data.property === "string" && data.property !== property;
        },
        getData: (): DragData => ({ property, index }),
        onDragEnter: ({ source }) => {
          const sourceData = source.data as DragData;
          setDropEdge(sourceData.index < index ? "right" : "left");
        },
        onDragLeave: () => setDropEdge(null),
        onDrop: ({ source }) => {
          setDropEdge(null);
          const sourceData = source.data as DragData;
          if (sourceData.index === index) return;
          onReorder(sourceData.index, index);
        },
      })
    );
  }, [property, index, isReorderEnabled, onReorder]);

  return (
    <WithDisplayPropertiesHOC
      displayProperties={displayProperties}
      displayPropertyKey={property}
      shouldRenderProperty={() => shouldRenderProperty}
    >
      <th
        className={cn(
          "relative h-11 min-w-36 items-center border border-t-0 border-b-0 border-subtle bg-layer-1 py-1 text-13 font-medium",
          { "opacity-50": isDragging, "cursor-grab": isReorderEnabled }
        )}
        ref={tableHeaderCellRef}
        tabIndex={0}
      >
        {dropEdge === "left" && (
          <DropIndicator classNames="absolute inset-y-0 left-0 w-0.5" isVisible />
        )}
        <HeaderColumn
          displayFilters={displayFilters}
          handleDisplayFilterUpdate={handleDisplayFilterUpdate}
          property={property}
          onClose={() => {
            tableHeaderCellRef?.current?.focus();
          }}
          isEpic={isEpic}
        />
        {dropEdge === "right" && (
          <DropIndicator classNames="absolute inset-y-0 right-0 w-0.5" isVisible />
        )}
      </th>
    </WithDisplayPropertiesHOC>
  );
});
```

**Nota:** `DropIndicator` aceita `classNames` e `isVisible` no Plane (vide `LabelDndHOC`). Se a API for diferente no monorepo atual, ajustar.

- [ ] **Step 2: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header-column.tsx
git commit -m "feat(web): make spreadsheet header columns draggable"
```

---

### Task 14: Wire `onReorder` no `SpreadsheetHeader`

**Files:**
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header.tsx`

- [ ] **Step 1: Estender props**

```tsx
interface Props {
  displayProperties: IIssueDisplayProperties;
  displayFilters: IIssueDisplayFilterOptions;
  handleDisplayFilterUpdate: (data: Partial<IIssueDisplayFilterOptions>) => void;
  canEditProperties: (projectId: string | undefined) => boolean;
  isEstimateEnabled: boolean;
  spreadsheetColumnsList: (keyof IIssueDisplayProperties)[];
  selectionHelpers: TSelectionHelper;
  onReorder?: (from: number, to: number) => void;
  isReorderEnabled?: boolean;
  isEpic?: boolean;
}
```

E desestruturar `onReorder, isReorderEnabled = true` no início do componente.

- [ ] **Step 2: Passar para cada `SpreadsheetHeaderColumn`**

No `map`, alterar para:

```tsx
{spreadsheetColumnsList.map((property, index) => (
  <SpreadsheetHeaderColumn
    key={property}
    property={property}
    index={index}
    displayProperties={displayProperties}
    displayFilters={displayFilters}
    handleDisplayFilterUpdate={handleDisplayFilterUpdate}
    isEstimateEnabled={isEstimateEnabled}
    onReorder={onReorder}
    isReorderEnabled={isReorderEnabled}
    isEpic={isEpic}
  />
))}
```

- [ ] **Step 3: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-header.tsx
git commit -m "feat(web): wire onReorder through SpreadsheetHeader"
```

---

### Task 15: Conectar `SpreadsheetTable` → `SpreadsheetHeader`

**Files:**
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-table.tsx`

- [ ] **Step 1: Estender props da `SpreadsheetTable`**

Adicionar nas Props:

```ts
onReorderColumn?: (from: number, to: number) => void;
isReorderEnabled?: boolean;
```

- [ ] **Step 2: Passar pro `SpreadsheetHeader`**

No JSX, na chamada do `<SpreadsheetHeader>`, propagar `onReorder={onReorderColumn}` e `isReorderEnabled={isReorderEnabled}`.

- [ ] **Step 3: Typecheck e commit**

```bash
pnpm --filter web check:types
git add apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-table.tsx
git commit -m "feat(web): propagate column reorder through SpreadsheetTable"
```

---

### Task 16: Resolver ordem + handler em `SpreadsheetView`

**Files:**
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-view.tsx`

- [ ] **Step 1: Trazer a ordem do store + criar handler**

Olhar como o componente já acessa filtros. O `SpreadsheetView` recebe `displayProperties` por prop (vinda do filter store no root). Precisa receber também `displayPropertiesOrder` por prop **E** ter acesso ao filter store pra chamar `updateFilters`.

Padrão no projeto: cada root da spreadsheet (`project-root.tsx`, `cycle-root.tsx`, etc.) já consome o `issuesFilter` correspondente. Vamos passar por prop tanto a ordem quanto o handler, mantendo `SpreadsheetView` "burra".

Adicionar ao tipo `Props` de `SpreadsheetView`:

```ts
displayPropertiesOrder?: (keyof IIssueDisplayProperties)[];
onReorderColumns?: (newOrder: (keyof IIssueDisplayProperties)[]) => void;
```

- [ ] **Step 2: Calcular `spreadsheetColumnsList` aplicando a ordem**

Substituir o cálculo atual (linha ~72):

```tsx
import { moveColumn } from "./spreadsheet-column-dnd.helpers";

// ... dentro do componente:
const orderedAll = displayPropertiesOrder?.length ? displayPropertiesOrder : SPREADSHEET_PROPERTY_LIST;

const spreadsheetColumnsList = isWorkspaceLevel
  ? orderedAll
  : orderedAll.filter((property) => {
      if (property === "cycle" && !currentProjectDetails?.cycle_view) return false;
      if (property === "modules" && !currentProjectDetails?.module_view) return false;
      return true;
    });
```

- [ ] **Step 3: Handler local que invoca callback do pai**

```tsx
const handleReorderColumn = useCallback(
  (from: number, to: number) => {
    if (!onReorderColumns) return;
    const newOrder = moveColumn(spreadsheetColumnsList, from, to);
    onReorderColumns(newOrder);
  },
  [spreadsheetColumnsList, onReorderColumns]
);
```

- [ ] **Step 4: Passar pro `<SpreadsheetTable>`**

```tsx
<SpreadsheetTable
  ...
  onReorderColumn={handleReorderColumn}
  isReorderEnabled={Boolean(onReorderColumns)}
/>
```

- [ ] **Step 5: Typecheck e commit**

```bash
pnpm --filter web check:types
git add apps/web/core/components/issues/issue-layouts/spreadsheet/spreadsheet-view.tsx
git commit -m "feat(web): apply user column order and wire reorder handler in SpreadsheetView"
```

---

### Task 17: Conectar cada Root da Spreadsheet ao store

**Files:**
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/roots/project-root.tsx`
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/roots/cycle-root.tsx`
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/roots/module-root.tsx`
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/roots/workspace-root.tsx`
- Modify: `apps/web/core/components/issues/issue-layouts/spreadsheet/roots/project-view-root.tsx`

Em cada root:

- [ ] **Step 1: Project root**

Abrir `project-root.tsx`. Localizar onde `issuesFilter` é usado e onde `<SpreadsheetView>` é renderizado. Adicionar:

```tsx
const displayPropertiesOrder = issuesFilter?.issueFilters?.displayPropertiesOrder;

const handleReorderColumns = useCallback(
  (newOrder: (keyof IIssueDisplayProperties)[]) => {
    if (!workspaceSlug || !projectId) return;
    issuesFilter.updateFilters(
      workspaceSlug.toString(),
      projectId.toString(),
      EIssueFilterType.DISPLAY_PROPERTIES_ORDER,
      newOrder
    );
  },
  [issuesFilter, workspaceSlug, projectId]
);
```

Passar `displayPropertiesOrder` e `onReorderColumns={handleReorderColumns}` para `<SpreadsheetView>`.

Imports necessários: `EIssueFilterType` de `@plane/constants`, `IIssueDisplayProperties` de `@plane/types`, `useCallback` do React.

- [ ] **Step 2: Cycle root**

Mesmo padrão, mas a chamada do `updateFilters` precisa do `cycleId`. A assinatura do `updateFilters` no cycle store é `(workspaceSlug, projectId, cycleId, type, filters)` — verificar antes de chamar.

- [ ] **Step 3: Module root**

Idem com `moduleId`.

- [ ] **Step 4: Workspace root**

`updateFilters(workspaceSlug, type, filters)` provavelmente.

- [ ] **Step 5: Project view root**

`updateFilters(workspaceSlug, projectId, type, filters, viewId)` — confirmar e adaptar.

- [ ] **Step 6: Typecheck**

```bash
pnpm --filter web check:types
```

- [ ] **Step 7: Commit**

```bash
git add apps/web/core/components/issues/issue-layouts/spreadsheet/roots/
git commit -m "feat(web): connect spreadsheet roots to column reorder action"
```

---

## Phase 5: Smoke test manual e ajustes finais

### Task 18: Smoke test end-to-end

- [ ] **Step 1: Subir API e web local**

Backend:
```bash
cd apps/api && python manage.py migrate && python manage.py runserver
```

Frontend:
```bash
pnpm --filter web dev
```

- [ ] **Step 2: Caminhos felizes**

Logar na app. Abrir um projeto com >5 work items. Trocar layout para Spreadsheet:

1. **Reorder básico:** arrastar "Priority" pra antes de "State". Esperado: muda instantaneamente, todas as rows refletem.
2. **Persistência:** F5 (reload). Esperado: ordem persiste.
3. **Cross-context:** abrir outro projeto. Esperado: ordem padrão (não vaza do projeto anterior). Reordenar diferente. Voltar pro primeiro. Esperado: cada projeto mantém sua ordem.
4. **Cycle independente:** abrir cycle do mesmo projeto, layout Spreadsheet. Reordenar. Voltar pra view de projeto. Esperado: ordens independentes.
5. **View custom:** criar uma view custom no projeto, layout Spreadsheet, reordenar. F5. Esperado: persiste.
6. **Cross-device:** abrir janela anônima, logar como o mesmo user. Esperado: ordem do user é vista (vem do backend).
7. **Outro user:** logar como outro user. Esperado: ordem dele é independente (per-user).
8. **Toggle display properties:** abrir menu "Display" e desligar uma coluna que estava no meio. Esperado: coluna some, restante mantém ordem relativa.
9. **Nova propriedade hipotética:** (não dá pra testar sem mexer no código, mas confirmar via codereview que `computedDisplayPropertiesOrder` cobre.)

- [ ] **Step 3: Caminhos de falha**

- Desligar rede (DevTools → offline) e arrastar. Esperado: UI move otimisticamente; ao tentar persistir, falha; `fetchFilters` é chamado e reverte.
- Confirmar via DevTools que o PATCH é enviado com o payload correto.

- [ ] **Step 4: Verificar no banco**

```sql
SELECT user_id, project_id, display_properties_order FROM project_user_properties WHERE display_properties_order != '[]'::jsonb;
```

Esperado: linhas pros casos onde reordenamos.

- [ ] **Step 5: Documentar issues encontradas e ajustar**

Qualquer problema no smoke test → criar commit de fix. Se for grande, voltar ao plano (escrever nova task).

- [ ] **Step 6: Commit final (se houver ajustes)**

```bash
git add -A
git commit -m "fix(web): smoke test adjustments for column reordering"
```

---

### Task 19: Limpeza e checklist final

- [ ] **Step 1: Rodar typecheck completo**

```bash
pnpm --filter web check:types
```

Esperado: zero erros.

- [ ] **Step 2: Rodar lint**

```bash
pnpm --filter web check:lint
```

Esperado: zero warnings novos (ou dentro do `--max-warnings`).

- [ ] **Step 3: Rodar build**

```bash
pnpm --filter web build
```

Esperado: build passa.

- [ ] **Step 4: Backend lint/format (se configurado)**

Conforme o setup do fork. Tipicamente:

```bash
cd apps/api && ruff check . && ruff format --check .
```

- [ ] **Step 5: Conferir CT 105**

Empurrar branch e deployar no CT 105 (Plane fork). Refazer 2 testes do smoke (reorder + persistência) no ambiente de preview.

- [ ] **Step 6: Atualizar CHANGELOG / docs do fork (opcional)**

Se o fork tem um `CHANGELOG.md`, adicionar entrada.

---

## Notas de implementação

- **Concorrência:** se duas abas reordenarem ao mesmo tempo, last-write-wins (mesmo padrão do `display_properties` atual). Sem locking.
- **Permissões:** mantém as mesmas dos endpoints `*UserProperty` existentes (`ADMIN, MEMBER, GUEST`).
- **Backward-compatibility:** frontend antigo + backend novo → backend aceita payload sem o campo (campo é opcional). Backend antigo + frontend novo → PATCH com `display_properties_order` falha 400 ou ignora; frontend trata via catch + revert.
- **Rollback do deploy:** reverter a migration apenas remove a coluna/tabela. Frontend trata ausência via `?.`.
- **`shouldRenderColumn`:** o helper `shouldRenderColumn(property)` no `WithDisplayPropertiesHOC` continua sendo a fonte de verdade pra esconder coluna desligada. A ordem só afeta sequência, não visibilidade.
- **Não esquecer:** ao rodar `makemigrations`, se o Django gerar nomes ou ordering diferentes do esperado por causa do `unique_together` + `constraints` em `IssueViewUserProperty`, ajustar manualmente para casar com o pattern de outras `*UserProperty` (ver `CycleUserProperties` linhas 145-153 como referência).
