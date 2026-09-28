# Copiar estrutura de tarefa (tarefa como modelo)

**Data:** 2026-09-28
**Autor:** felipedrn93
**Branch:** main
**Plano:** nenhum (mudança delimitada, design aprovado no chat)
**Atualizado:** 2026-09-28 — a cópia virou `instantiate(snapshot(...))`, compartilhada com [modelos-de-tarefa.md](modelos-de-tarefa.md); descrição copiada só em HTML e estimativa/tipo não são mais copiados.

## Contexto

A equipe de BI repete sempre o mesmo roteiro de implantação (ex.: BI-7221 "Implantar BI Prioneira": 9 subtarefas com responsável e 7 bloqueios encadeados — Enviar Contrato → Aguardar Assinatura → …, Pegar Usuário e Token API → Puxar Dados BI → Reunião de Calibração → Implantar BI → Reunião de Treinamento). O Plane open-source não tem templates de work item (é recurso pago; na edição comunitária o `WorkItemTemplateSelect` de `ce/` renderiza vazio), e o "Fazer uma cópia" nativo copia só a tarefa em si, sem subtarefas.

## Decisões de design

1. **Sem entidade "modelo".** Qualquer tarefa serve de modelo: o "Fazer uma cópia" ganhou a opção **"Copiar subtarefas e dependências"** (ligada por padrão). Para um modelo fixo, basta manter uma tarefa "📋 Modelo – …" e duplicá-la.
2. **O que é copiado em cada subtarefa:** nome, descrição, prioridade, estimativa, tipo, responsáveis e labels. **Todos os níveis** da árvore (sub-subtarefas também).
3. **O que não é copiado:** datas (ficam em branco — decisão do usuário), estado (entra no estado padrão do projeto), comentários, anexos, links, ciclo/módulo, `recurrence_pattern`.
4. **Relações:** copiadas apenas quando as duas pontas estão dentro da árvore copiada (a própria tarefa de origem mapeia para a nova). Relações com tarefas de fora são ignoradas. Os ids são remapeados via `id_map` antigo → novo.
5. **Atomicidade:** a árvore e as relações são criadas num único `transaction.atomic`. Se falhar, a tarefa pai (criada antes, pelo fluxo normal do modal) fica sem subtarefas e o front mostra o toast `copy_sub_issues_failed`.
6. **Mesmo projeto.** O endpoint exige origem e destino no projeto da URL (o modal de cópia já trava a troca de projeto) e recusa copiar para dentro da própria subárvore da origem (400).
7. **Helpers compartilhados com a recorrência.** `default_state_for_project` e `copy_assignees_and_labels` saíram de `recurring_issue_task.py` para `plane/utils/issue_structure.py` — ver [tarefas-recorrentes.md](tarefas-recorrentes.md).

## Arquivos criados

- `apps/api/plane/utils/issue_structure.py` — `copy_issue_structure(source, target, actor)` (BFS nível a nível, clona filhos e relações internas, emite `issue.activity.created` por clone) + helpers movidos da recorrência.
- `apps/api/plane/tests/unit/utils/test_issue_structure.py` — árvore de 2 níveis no formato da BI-7221, relação externa ignorada, datas limpas, estado padrão, responsáveis; endpoint (201 e recusa de cópia na própria subárvore).

## Arquivos modificados

- `apps/api/plane/app/views/issue/sub_issue.py` — `IssueCopyStructureEndpoint` (`POST .../issues/<id>/copy-structure/` com `{source_issue_id}` → `{created: n}`).
- `apps/api/plane/app/views/__init__.py`, `apps/api/plane/app/urls/issue.py` — registro da rota `issue-copy-structure`.
- `apps/api/plane/bgtasks/recurring_issue_task.py` — passa a importar os helpers de `plane.utils.issue_structure`.
- `apps/web/core/services/issue/issue.service.ts` — `copyStructure()`.
- `apps/web/core/components/issues/issue-modal/base.tsx` — estado `copyStructure`; captura o `sourceIssueId` **antes** do `delete data.sourceIssueId` existente; após criar a tarefa chama o endpoint, recarrega o detalhe (`fetchIssue`, que também busca as subtarefas) e a listagem do projeto.
- `apps/web/core/components/issues/issue-modal/form.tsx` — toggle "Copiar subtarefas e dependências", visível só em cópia (`sourceIssueId`) de tarefa com `sub_issues_count > 0`.
- `packages/i18n/src/locales/*/common.json` — chaves `copy_sub_issues_and_relations` e `copy_sub_issues_failed` (pt-BR traduzido, demais em inglês).

## Como testar

```bash
# backend (container plane-test — ver clientes-cadastro.md)
docker exec plane-test sh -c 'cd /code && python -m pytest plane/tests/unit/utils/test_issue_structure.py plane/tests/unit/bg_tasks/test_recurring_issue_task.py -q'

# frontend
pnpm turbo run check:types --filter=web
pnpm --filter @plane/i18n run check:sync
```

Roteiro manual:

1. Na BI-7221 (ou qualquer tarefa com subtarefas), menu de ações → **Fazer uma cópia**.
2. O rodapé do modal mostra "Copiar subtarefas e dependências" ligado. Renomear para "Implantar BI Cliente X" e salvar.
3. A nova tarefa tem as 9 subtarefas, todas em "A Fazer", sem datas, com os mesmos responsáveis.
4. Abrir "Reunião de Treinamento" da cópia → "Bloqueado por: Implantar BI" (a da cópia, não a original).
5. Repetir com o toggle desligado → cópia sem subtarefas (comportamento original).

## Pitfalls

- **O `delete data.sourceIssueId` do `handleFormSubmit` muta a prop.** Por isso o id da origem é lido antes. Com "Criar mais" ligado, só a primeira criação copia a estrutura.
- **O pre-commit bloqueia os arquivos do modal.** `base.tsx`/`form.tsx` já têm 10 avisos de oxlint do upstream (`no-shadow`, `exhaustive-deps`, `prefer-tag-over-role`); o toggle novo segue o mesmo padrão `div role="button"` do "Criar mais" (trocar por `<button>` aninharia botões, pois o `ToggleSwitch` do Headless UI já é um `<button>`). Mesmo caso de [divida-ci-web.md](divida-ci-web.md).
- **Suíte unitária no `plane-test` recriado:** as 3 falhas extras de `client` vinham das aspas no `--env-file`; ver o pitfall em [modelos-de-tarefa.md](modelos-de-tarefa.md).

## Fora de escopo

- Datas relativas (deslocar prazos a partir de uma data de início) — descartado em favor de limpar as datas.
- Copiar comentários, anexos, links, ciclo/módulo das subtarefas.
- Cópia entre projetos.
