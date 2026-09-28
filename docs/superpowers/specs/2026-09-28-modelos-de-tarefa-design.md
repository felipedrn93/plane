# Modelos de tarefa por projeto — design

**Data:** 2026-09-28
**Status:** aprovado no chat (design em 3 seções), implementação autorizada pelo usuário

## Objetivo

Criar tarefas repetitivas (ex.: "Implantar BI <cliente>", 9 subtarefas com responsáveis e 7 bloqueios encadeados) a partir de um **modelo guardado no projeto**, que **não aparece** em lista, kanban, busca ou contadores de tarefas.

## O que o usuário disse

- Quer um modelo "para sempre copiar do modelo", que não fique na lista de tarefas.
- Quer um dropdown no projeto com os modelos; clicar cria a tarefa a partir dele; modelos ligados ao projeto.
- Criação/manutenção por **"Salvar como modelo"** a partir de uma tarefa existente (não um editor de modelos).
- Datas das subtarefas: **limpar** (decisão anterior, vale aqui também).

## Premissas (não ditas, assumidas)

- Salvar com um nome que já existe no projeto **substitui** o modelo (é o fluxo de atualização).
- Membros do projeto (não convidados) criam, usam e excluem modelos.
- Não há cópia de modelo entre projetos.

## Modelo de dados

`IssueTemplate(ProjectBaseModel)` — tabela `issue_templates`:

| campo | tipo | nota |
|---|---|---|
| `name` | `CharField(255)` | único por projeto, case-insensitive, entre não excluídos |
| `structure` | `JSONField` | foto da estrutura (abaixo) |

Formato de `structure`:

```json
{
  "root":  {"name": "...", "description_html": "...", "priority": "none", "assignee_ids": [], "label_ids": []},
  "nodes": [{"key": "<id original>", "parent": "root" | "<key>", "name": "...", "description_html": "...",
             "priority": "...", "assignee_ids": [], "label_ids": []}],
  "relations": [{"issue": "root" | "<key>", "related_issue": "root" | "<key>", "relation_type": "blocked_by"}]
}
```

`nodes` é gravado em ordem de largura (pai sempre antes do filho). Relações só entram quando as duas pontas estão na árvore. Datas, estado, estimativa, tipo, comentários, anexos e links não entram.

## Backend

`plane/utils/issue_structure.py`:

- `snapshot_issue_structure(source) -> dict` — tira a foto.
- `instantiate_issue_structure(structure, target, actor) -> int` — cria os `nodes` sob `target` (a raiz mapeia para `target`) numa transação: estado padrão do projeto, sem datas, responsáveis filtrados pelos membros ativos do projeto, labels filtradas pelas existentes no projeto, relações remapeadas. Retorna o número de subtarefas criadas.
- `copy_issue_structure(source, target, actor)` passa a ser `instantiate(snapshot(source), ...)` — "Fazer uma cópia" e modelos compartilham o código.

Endpoints (`plane.app`, `ProjectEntityPermission`):

- `GET  /api/workspaces/<slug>/projects/<pid>/issue-templates/` → `[{id, name, root, sub_issues_count}]`; `root.assignee_ids/label_ids` já filtrados (para pré-preencher o formulário sem ids órfãos).
- `POST /api/workspaces/<slug>/projects/<pid>/issue-templates/` `{issue_id, name}` → 201, cria ou substitui por nome.
- `DELETE /api/workspaces/<slug>/projects/<pid>/issue-templates/<id>/` → 204.
- `POST .../issues/<id>/copy-structure/` aceita `{template_id}` além de `{source_issue_id}`.

## Frontend

- **"Salvar como modelo"** no menu de ações da tarefa (lista, ciclo, módulo, visão global e detalhe): pede o nome (`window.prompt`, padrão = nome da tarefa), grava, toast, atualiza a lista de modelos (SWR).
- **Dropdown "Modelos"** ao lado de "Adicionar item de trabalho" no cabeçalho do projeto: lista os modelos; clicar abre o formulário de criação pré-preenchido (`name`, `description_html`, `priority`, `assignee_ids`, `label_ids`, `templateId`); cada item tem lixeira com `window.confirm`. Estado vazio explica como criar um modelo.
- `base.tsx`: ao criar com `templateId`, chama `copy-structure` com `template_id` (mesmo caminho do `sourceIssueId`).
- i18n em todos os locales (pt-BR traduzido, demais em inglês).

## Erros

- Tarefa de origem inexistente/fora do projeto → 404. Nome vazio → 400.
- Falha ao aplicar o modelo depois de criar a tarefa → toast `copy_sub_issues_failed` (já existente).

## Testes

- snapshot→instantiate reproduz a árvore de 2 níveis e as relações; relação externa ignorada; datas limpas; estado padrão.
- responsável fora do projeto e label excluída são ignorados.
- POST com nome repetido substitui; GET filtra ids órfãos; DELETE; convidado recebe 403 no POST.
- `copy-structure` com `template_id`.

## Deploy

Migração nova → `docker compose build api migrator web`, `up migrator`, `up -d api web` no CT 105.
