# Modelos de tarefa por projeto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Salvar uma tarefa (com subtarefas e dependências) como modelo do projeto, invisível nas listas, e criar tarefas novas a partir dele por um dropdown "Modelos" no cabeçalho do projeto.

**Architecture:** Nova tabela `IssueTemplate` guarda uma foto JSON da árvore. `plane/utils/issue_structure.py` ganha `snapshot_issue_structure` / `instantiate_issue_structure`; a cópia existente passa a ser a composição das duas. O frontend reaproveita o modal de criação (`templateId`, como já faz com `sourceIssueId`).

**Tech Stack:** Django 4.2 + DRF, pytest-django; React Router v7 + MobX + SWR, `@plane/ui` `CustomMenu`, `@plane/i18n`.

**Spec:** `docs/superpowers/specs/2026-09-28-modelos-de-tarefa-design.md`

## Global Constraints

- Subtarefas criadas: sem datas, estado padrão do projeto de destino.
- Responsáveis só se forem membros ativos do projeto; labels só se existirem no projeto.
- Nome do modelo único por projeto (case-insensitive, entre não excluídos); POST com nome repetido substitui.
- Permissão: `ProjectEntityPermission` (convidado não cria/exclui).
- Docs em português; registrar em `mods.md` + `mods/modelos-de-tarefa.md`.
- Testes backend no container `plane-test` (`docker exec plane-test sh -c 'cd /code && python -m pytest ...'`).

## Review Focus

- Modelo salvo de tarefa sem subtarefas → aplicar cria só a tarefa, sem erro (teste em Task 1).
- Nome só com espaços → 400 (teste em Task 2).
- Aplicar modelo excluído → 404, e o front mostra `copy_sub_issues_failed` (teste 404 em Task 2).
- Label apagada depois de salvar o modelo → GET não devolve o id órfão, aplicar não quebra (Task 1 e 2).
- Salvar modelo de tarefa de outro projeto pela URL deste → 404 (Task 2).

---

### Task 1: snapshot / instantiate

**Files:**

- Modify: `apps/api/plane/utils/issue_structure.py`
- Test: `apps/api/plane/tests/unit/utils/test_issue_structure.py`

**Interfaces:**

- Produces: `snapshot_issue_structure(source: Issue) -> dict`; `instantiate_issue_structure(structure: dict, target: Issue, actor: User) -> int`; `copy_issue_structure(source, target, actor) -> int` (inalterado por fora).

- [ ] **Step 1: testes que falham**

```python
@pytest.mark.django_db
@patch("plane.utils.issue_structure.issue_activity")
def test_snapshot_then_instantiate(self, _mock, create_user, make, todo):
    source = make("Modelo")
    a = make("A", parent=source)
    b = make("B", parent=a)
    self._relate(b, a)
    structure = snapshot_issue_structure(source)
    assert structure["root"]["name"] == "Modelo"
    assert [n["name"] for n in structure["nodes"]] == ["A", "B"]
    assert structure["relations"] == [{"issue": str(b.id), "related_issue": str(a.id), "relation_type": "blocked_by"}]
    target = make("Nova")
    assert instantiate_issue_structure(structure, target, create_user) == 2

@pytest.mark.django_db
@patch("plane.utils.issue_structure.issue_activity")
def test_instantiate_skips_stale_assignees_and_labels(self, _mock, create_user, make, project, workspace):
    source = make("Modelo")
    make("A", parent=source)
    structure = snapshot_issue_structure(source)
    structure["nodes"][0]["assignee_ids"] = [str(create_user.id), str(uuid4())]
    structure["nodes"][0]["label_ids"] = [str(uuid4())]
    target = make("Nova")
    instantiate_issue_structure(structure, target, create_user)
    child = Issue.issue_objects.get(parent=target)
    assert list(child.assignees.all()) == [create_user]  # create_user é membro do projeto no fixture
    assert child.labels.count() == 0

@pytest.mark.django_db
def test_instantiate_empty_structure(self, create_user, make):
    source = make("Sem filhos")
    assert instantiate_issue_structure(snapshot_issue_structure(source), make("Nova"), create_user) == 0
```

O fixture `project` passa a criar `ProjectMember(member=create_user, role=20)`.

- [ ] **Step 2:** rodar `pytest plane/tests/unit/utils/test_issue_structure.py` → falha com ImportError.

- [ ] **Step 3: implementação**

```python
def _node_fields(issue):
    return {
        "name": issue.name,
        "description_html": issue.description_html,
        "priority": issue.priority,
        "assignee_ids": [str(i) for i in IssueAssignee.objects.filter(issue=issue).values_list("assignee_id", flat=True)],
        "label_ids": [str(i) for i in IssueLabel.objects.filter(issue=issue).values_list("label_id", flat=True)],
    }

def snapshot_issue_structure(source):
    keys = {source.id: "root"}
    nodes, level = [], [source.id]
    while level:
        children = list(Issue.issue_objects.filter(parent_id__in=level).exclude(id__in=keys.keys()).order_by("sequence_id"))
        for child in children:
            keys[child.id] = str(child.id)
            nodes.append({"key": str(child.id), "parent": keys[child.parent_id], **_node_fields(child)})
        level = [c.id for c in children]
    relations = [
        {"issue": keys[r.issue_id], "related_issue": keys[r.related_issue_id], "relation_type": r.relation_type}
        for r in IssueRelation.objects.filter(issue_id__in=keys.keys(), related_issue_id__in=keys.keys())
    ]
    return {"root": _node_fields(source), "nodes": nodes, "relations": relations}

def valid_member_ids(project, ids): ...  # ProjectMember ativos
def valid_label_ids(project, ids): ...   # Label do projeto

def instantiate_issue_structure(structure, target, actor):
    # transaction.atomic; id_map = {"root": target.id}; cria nodes em ordem;
    # IssueAssignee/IssueLabel com ids filtrados; IssueRelation remapeada; activity após commit
```

- [ ] **Step 4:** testes passam (incluindo os 3 antigos de cópia).
- [ ] **Step 5:** commit `refactor(issues): copia de estrutura via snapshot/instantiate`.

### Task 2: modelo `IssueTemplate` + endpoints

**Files:**

- Create: `apps/api/plane/db/models/issue_template.py`, `apps/api/plane/db/migrations/0129_issuetemplate.py`, `apps/api/plane/app/views/issue/template.py`, `apps/api/plane/tests/unit/views/test_issue_template.py`
- Modify: `apps/api/plane/db/models/__init__.py`, `apps/api/plane/app/views/__init__.py`, `apps/api/plane/app/urls/issue.py`, `apps/api/plane/app/views/issue/sub_issue.py`

**Interfaces:**

- Consumes: Task 1.
- Produces: `GET/POST .../projects/<pid>/issue-templates/`, `DELETE .../issue-templates/<uuid:pk>/`, `copy-structure` com `template_id`. Resposta do GET: `[{id, name, root, sub_issues_count}]`.

- [ ] **Step 1: testes que falham** (`test_issue_template.py`)

```python
def test_save_list_apply_delete(session_client, project, ...):
    # POST {issue_id, name:"Implantar BI"} -> 201; GET -> 1 item com sub_issues_count
    # POST mesmo nome (case diferente) -> ainda 1 item (substituiu)
    # POST copy-structure {template_id} -> 201 {"created": n}
    # DELETE -> 204; GET -> []
def test_blank_name_is_400(...)
def test_issue_from_other_project_is_404(...)
def test_guest_cannot_save(...)  # ProjectMember role=5 -> 403
def test_get_filters_stale_root_ids(...)
def test_apply_deleted_template_is_404(...)
```

- [ ] **Step 2:** rodar → falha (404 na rota).

- [ ] **Step 3: implementação**

```python
class IssueTemplate(ProjectBaseModel):
    name = models.CharField(max_length=255)
    structure = models.JSONField(default=dict)
    class Meta:
        db_table = "issue_templates"; ordering = ("name",)
        constraints = [models.UniqueConstraint(Lower("name"), "project", condition=Q(deleted_at__isnull=True),
                                               name="unique_issue_template_name_per_project_when_not_deleted")]
```

`makemigrations db` gera `0129`. View `IssueTemplateEndpoint(BaseAPIView)` com `get`, `post`, `delete(pk)`; `post` faz update-or-create por `name__iexact`.

- [ ] **Step 4:** testes passam; ruff limpo nos arquivos novos.
- [ ] **Step 5:** commit `feat(modelos): tabela e API de modelos de tarefa`.

### Task 3: frontend

**Files:**

- Modify: `packages/types/src/issues/issue.ts` (`templateId?: string`), `apps/web/core/services/issue/issue.service.ts`, `apps/web/core/components/issues/issue-modal/base.tsx`, `apps/web/core/components/issues/issue-layouts/quick-action-dropdowns/helper.tsx`, `apps/web/ce/components/issues/header.tsx`, `packages/i18n/src/locales/*/common.json`
- Create: `apps/web/core/components/issues/issue-templates-dropdown.tsx`

**Interfaces:**

- Consumes: API da Task 2.
- Produces: `IssueService.listTemplates/saveTemplate/deleteTemplate`, `copyStructure(ws, pid, id, {source_issue_id} | {template_id})`; SWR key `ISSUE_TEMPLATES_<projectId>`.

- [ ] **Step 1:** service + `templateId` no tipo; `base.tsx` captura `data?.templateId` junto com `sourceIssueId` e chama `copyStructure(..., { template_id })`.
- [ ] **Step 2:** `createSaveAsTemplateMenuItem` no factory (`window.prompt` com o nome da tarefa, `saveTemplate`, toast, `mutate(key)`), incluído nos menus de projeto, visão global, ciclo, módulo e detalhe; `shouldRender: isEditingAllowed`.
- [ ] **Step 3:** `IssueTemplatesDropdown` (`CustomMenu`, `useSWR`) com itens que abrem `CreateUpdateIssueModal` pré-preenchido e lixeira com `window.confirm`; estado vazio com a dica. Renderizado no `ce/components/issues/header.tsx` antes do botão "Adicionar".
- [ ] **Step 4:** chaves i18n (`issue_templates.*`) em todos os locales; `check:types` do i18n e do web; oxfmt.
- [ ] **Step 5:** commit `feat(modelos): salvar como modelo e dropdown Modelos`.

### Task 4: docs, deploy, verificação

- [ ] `mods.md` linha 17 + `mods/modelos-de-tarefa.md`.
- [ ] push `origin main`; no CT 105: `git pull`, `docker compose build api migrator web`, `docker compose up migrator`, `docker compose up -d api web`.
- [ ] `curl http://127.0.0.1:8080/api/instances/` → 200; smoke no shell do api: salvar BI-7221 como modelo numa transação com rollback e conferir 9 nós / 7 relações.
