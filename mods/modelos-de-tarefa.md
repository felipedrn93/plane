# Modelos de tarefa por projeto

**Data:** 2026-09-28
**Autor:** felipedrn93
**Branch:** main
**Spec:** [docs/superpowers/specs/2026-09-28-modelos-de-tarefa-design.md](../docs/superpowers/specs/2026-09-28-modelos-de-tarefa-design.md)
**Plano:** [docs/superpowers/plans/2026-09-28-modelos-de-tarefa.md](../docs/superpowers/plans/2026-09-28-modelos-de-tarefa.md)

## Contexto

Roteiros repetitivos (ex.: "Implantar BI <cliente>" — 9 subtarefas com responsável e 7 bloqueios encadeados, como a BI-7221) precisavam de um **modelo guardado no projeto** que não polua a lista de tarefas. A edição comunitária do Plane não tem templates de work item (recurso pago). Esta mod estende [copiar-estrutura-tarefa.md](copiar-estrutura-tarefa.md), que já copiava a árvore de uma tarefa viva.

## Decisões de design

1. **O modelo é uma foto, não uma tarefa.** Tabela nova `issue_templates` (`IssueTemplate`, por projeto) com `name` e `structure` (JSON). Por não ser `Issue`, não aparece em lista, kanban, busca, ciclos ou contadores — sem mexer nos managers/filtros de `Issue`.
2. **Criação por "Salvar como modelo"** no menu de ações de qualquer tarefa (sem editor de modelos — decisão do usuário). Pede o nome via `window.prompt` (padrão: nome da tarefa). **Mesmo nome (case-insensitive) substitui** — é o fluxo de atualização: cria uma tarefa pelo modelo, ajusta, salva de novo com o mesmo nome.
3. **Uso pelo dropdown "Modelos"** ao lado de "Adicionar item de trabalho" no cabeçalho do projeto. Clicar abre o formulário de criação pré-preenchido (título = nome do modelo, descrição, prioridade, responsáveis e labels da tarefa raiz); ao salvar, as subtarefas e relações são criadas. Lixeira por item com `window.confirm`.
4. **Formato da foto:** `root` (campos da tarefa raiz), `nodes` em ordem de largura (`key`, `parent`, nome, descrição HTML, prioridade, responsáveis, labels) e `relations` (`issue`/`related_issue` como chaves, `"root"` = a tarefa criada). Datas, estado, estimativa, tipo, comentários, anexos e links não entram.
5. **Ids envelhecem:** na aplicação, responsáveis que não são mais membros ativos do projeto e labels apagadas são ignorados; o GET da lista já devolve o `root` filtrado, para o formulário não receber ids órfãos. Labels de workspace (`project` nulo) valem.
6. **Um só caminho de cópia.** `copy_issue_structure` (o "Fazer uma cópia") virou `instantiate_issue_structure(snapshot_issue_structure(origem))`: cópia e modelos usam o mesmo código.
7. **Campo `issueTemplateId` no `TIssue`, não `templateId`.** O `IssuesModalProps.templateId` já existe no upstream para os templates pagos (ignorado na CE); um nome próprio evita confundir os dois.

## Arquivos criados

- `apps/api/plane/db/models/issue_template.py` — model `IssueTemplate` (nome único por projeto entre não excluídos, `Lower(name)`).
- `apps/api/plane/db/migrations/0129_issuetemplate.py` — só a tabela e a constraint (o `makemigrations` trouxe dois `AlterField` de `pushsubscription`, drift antigo sem SQL; foram removidos para não misturar escopo).
- `apps/api/plane/app/views/issue/template.py` — `IssueTemplateEndpoint` (`GET`/`POST .../projects/<pid>/issue-templates/`, `DELETE .../issue-templates/<id>/`).
- `apps/api/plane/tests/unit/views/test_issue_template.py` — salvar/substituir/listar/aplicar/excluir, nome em branco, tarefa de outro projeto, convidado, ids órfãos, modelo excluído.
- `apps/web/core/components/issues/issue-templates-dropdown.tsx` — dropdown + modal de criação pré-preenchido; exporta `getIssueTemplatesKey` (chave SWR).

## Arquivos modificados

- `apps/api/plane/utils/issue_structure.py` — `snapshot_issue_structure`, `instantiate_issue_structure`, `valid_member_ids`, `valid_label_ids`.
- `apps/api/plane/app/views/issue/sub_issue.py` — `copy-structure` aceita `{template_id}`.
- `apps/api/plane/db/models/__init__.py`, `apps/api/plane/app/views/__init__.py`, `apps/api/plane/app/urls/issue.py` — registros.
- `apps/api/plane/tests/unit/utils/test_issue_structure.py` — testes de snapshot/instantiate.
- `packages/types/src/issues/issue.ts` — `TIssueTemplate` e `TIssue.issueTemplateId`.
- `apps/web/core/services/issue/issue.service.ts` — `listTemplates`, `saveTemplate`, `deleteTemplate`; `copyStructure` recebe `{source_issue_id} | {template_id}`.
- `apps/web/core/components/issues/issue-modal/base.tsx` — decide a origem da estrutura (modelo ou cópia) antes de limpar os campos auxiliares de `data`.
- `apps/web/core/components/issues/issue-layouts/quick-action-dropdowns/helper.tsx` — item "Salvar como modelo" nos menus de projeto, visão global, ciclo, módulo e detalhe.
- `apps/web/ce/components/issues/header.tsx` — dropdown no cabeçalho do projeto.
- `packages/i18n/src/locales/*/common.json` — objeto `issue_templates` (pt-BR traduzido, demais em inglês).

## Como testar

```bash
docker exec plane-test sh -c 'cd /code && python -m pytest plane/tests/unit/views/test_issue_template.py plane/tests/unit/utils/test_issue_structure.py -q'
pnpm turbo run check:types --filter=web
pnpm --filter @plane/i18n run check:sync
```

Roteiro manual:

1. BI-7221 → menu ⋯ → **Salvar como modelo** → "Implantar BI".
2. A BI-7221 continua na lista; nenhuma tarefa nova aparece.
3. Cabeçalho do projeto → **Modelos** → "Implantar BI · 9 subtarefas" → o formulário abre com "Implantar BI"; completar com o cliente e salvar.
4. A tarefa nova tem as 9 subtarefas em "A Fazer", sem datas, e "Reunião de Treinamento" bloqueada por "Implantar BI" (as novas).
5. Salvar de novo como "implantar bi" → o dropdown continua com um só modelo.
6. Lixeira no item → confirma → some do dropdown.

## Pitfalls

- **Deploy com migração.** `docker compose build api migrator web` e `docker compose up migrator` antes de `up -d api web`, senão o `api` fica esperando migração (502).
- **Container `plane-test`:** o `--env-file` do Docker não remove aspas (`RABBITMQ_PORT="5672"` vira a string `"5672"`), e aí qualquer teste que dispara task Celery (ex.: `delete()` com soft-delete em cascata) quebra. Gerar um env sem aspas (`sed -E 's/^([A-Z_]+)="(.*)"$/\1=\2/'`) e passar `DATABASE_URL`/`REDIS_URL` já expandidos. Com isso a suíte fica só com as 5 falhas antigas documentadas em [clientes-cadastro.md](clientes-cadastro.md).
- **Subtarefas de outros projetos ficam de fora.** O Plane permite filho em outro projeto do workspace; a foto só leva filhos do projeto da origem, senão nome/descrição de tarefas de um projeto que o usuário não vê vazariam para a cópia e para todos os membros via modelo (achado da revisão).
- **Foto congelada:** mudar a tarefa de origem depois não altera o modelo; é preciso salvar de novo.

## Fora de escopo

- Editor de modelos (montar a árvore sem uma tarefa de origem).
- Modelos compartilhados entre projetos.
- Datas relativas nas subtarefas.
