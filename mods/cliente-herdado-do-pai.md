# Subtarefa herda o cliente do pai

**Data:** 2026-10-19
**Autor:** felipedrn93
**Branch:** main
**Relacionada:** [mods/clientes-cadastro.md](clientes-cadastro.md)

## Contexto

Uma subtarefa trabalha para o mesmo cliente da tarefa pai, mas o campo Cliente era independente: dava para ter pai em "Acme" e filhos sem cliente ou em outro cliente, o que bagunça filtros e agrupamentos por cliente. Regra pedida: **a subtarefa pega o cliente do pai; só pode ter cliente próprio se o pai não tiver cliente definido.**

## Decisões de design

1. **A regra mora no `Issue.save()`**, não no serializer. Assim vale para todos os caminhos que salvam tarefa: API interna, API pública `/api/v1/`, cópia de estrutura e modelos de tarefa, tarefas recorrentes.
2. **Herança ao salvar.** Se o pai tem cliente, o `client_id` da subtarefa é sobrescrito com o do pai, em silêncio (sem erro 400). Se o pai não tem cliente, o valor da subtarefa fica como está.
3. **Propagação para baixo.** Quando o cliente de uma tarefa muda para um valor não nulo, todos os descendentes (todos os níveis) recebem o mesmo cliente via `Issue.propagate_client` (BFS por nível, `UPDATE` em lote, com guarda contra ciclos). Mover uma tarefa para baixo de um pai com cliente também dispara a propagação, porque a herança muda o `client_id` dela.
4. **Limpar o cliente do pai não limpa os filhos.** Eles mantêm o último valor, que passa a ser "próprio" (o pai não tem mais cliente). Evita apagar dados sem querer.
5. **`client_id` entrou em `TRACKED_FIELDS`** para detectar a mudança via `ChangeTrackerMixin.has_changed`. O único outro uso do tracker é `state_id` em `_sync_completed_at`.
6. **Front: dropdown travado.** O `ClientDropdown` recebe `issue` (`id`, `project_id`, `parent_id`), sobe a cadeia de ancestrais pelo `issueMap` e, se algum tem cliente, mostra o cliente do ancestral mais alto, fica desabilitado e o tooltip diz "Herdado da tarefa pai". Ancestral fora do store é ignorado; o backend corrige de qualquer forma.

7. **Aviso antes de sobrescrever (2026-10-19).** Ao escolher um cliente, o dropdown consulta `GET .../issues/<id>/client-conflicts/?client_id=<novo>`, que conta os descendentes (todos os níveis) que **têm outro cliente** — subtarefas sem cliente não entram na conta, porque não perdem nada. Se a contagem for > 0, abre um `AlertModalCore` ("N subtarefas têm outro cliente e vão passar para o cliente escolhido") e só grava ao confirmar. Se a consulta falhar, grava sem aviso — o backend aplica a regra de qualquer forma. O aviso existe só no dropdown: arrastar card no Kanban agrupado por cliente e a API pública não avisam.
8. **`Issue.descendant_ids`** foi extraído do `propagate_client` para ser reaproveitado pela contagem.

## Alinhamento dos dados existentes (2026-10-19, CT 105)

A regra só age quando algo salva a tarefa, então as subtarefas antigas continuavam desalinhadas. Foi rodada uma correção única, via `manage.py shell`, com uma CTE recursiva que calcula o cliente efetivo de cada tarefa (`COALESCE(cliente efetivo do pai, cliente próprio)`, a partir das raízes, ignorando `deleted_at`) e faz `UPDATE` onde o valor difere:

- **171** subtarefas atualizadas, de 11.824. Todas estavam **sem cliente** debaixo de um pai com cliente; nenhuma tinha cliente diferente do pai, então nenhum valor foi perdido.
- Backup (id, cliente anterior, cliente novo) em `/root/alinhamento-cliente-2026-10-19.log` no CT 105 (linhas `BACKUP`). Para desfazer: `UPDATE issues SET client_id = NULL WHERE id IN (...)` com os ids do log.

## Arquivos modificados

### Backend
- `apps/api/plane/db/models/issue.py` — `TRACKED_FIELDS`, `_inherit_parent_client`, `propagate_client`, chamadas no `save()`.
- `apps/api/plane/app/views/issue/sub_issue.py` — o "Adicionar subtarefas existentes" usa `bulk_update`, que pula o `save()`; chama `propagate_client` depois.
- `apps/api/plane/tests/unit/models/test_client.py` — `TestSubIssueInheritsClient` (5 casos).
- `apps/api/plane/app/views/issue/sub_issue.py` — `IssueClientConflictsEndpoint`; `plane/app/urls/issue.py` e `plane/app/views/__init__.py` — registro da rota `client-conflicts/`.
- `apps/api/plane/tests/unit/views/test_client.py` — `TestIssueClientConflictsEndpoint`.

### Frontend
- `apps/web/core/components/dropdowns/client.tsx` — prop `issue`, valor herdado, trava e modal de confirmação.
- `packages/services/src/client/client.service.ts` — `countSubIssueConflicts`.
- `apps/web/core/components/issues/issue-detail/sidebar.tsx`, `issues/peek-overview/properties.tsx`, `issue-layouts/properties/all-properties.tsx`, `issue-layouts/spreadsheet/columns/client-column.tsx` — passam `issue={issue}`.
- `packages/i18n/src/locales/*/clients.json` — chaves `clients.inherited_from_parent` e `clients.change_subissues_{title,content,confirm}`.

## Como testar

```bash
# backend (stack local: plane-db + plane-redis no ar, rede plane_dev_env)
docker run --rm --network plane_dev_env -v "$PWD/apps/api":/code -w /code --env-file apps/api/.env \
  -e DATABASE_URL=postgresql://plane:plane@plane-db:5432/plane -e REDIS_URL=redis://plane-redis:6379/ \
  --entrypoint sh plane-api -c 'pip install -q -r requirements/test.txt; python -m pytest -q -m unit plane/tests/unit'
```
Em 2026-10-19: 190 passaram, 10 falharam — as mesmas 10 falhas aparecem sem esta mod (ambiente: porta do RabbitMQ entre aspas no `--env-file`, banco de teste reaproveitado, e as falhas pré-existentes listadas em [clientes-cadastro.md](clientes-cadastro.md#pitfalls)).

Manual:
1. Pai com cliente "Acme" → criar subtarefa: ela já nasce com "Acme" e o dropdown fica travado com o tooltip "Herdado da tarefa pai".
2. Pai sem cliente → a subtarefa aceita qualquer cliente.
3. Trocar o cliente do pai → filhos e netos passam a mostrar o novo cliente (recarregar a lista se o filho não estiver no store junto com o pai).
4. Pai sem cliente com um filho em "Globex" → escolher "Acme" no pai: aparece o aviso "1 subtarefa tem outro cliente…"; Cancelar não grava nada, Trocar grava e propaga.
5. "Adicionar subtarefas existentes" num pai com cliente → as tarefas adicionadas (e os filhos delas) herdam o cliente.

## Pitfalls

- **`UPDATE` em lote não gera atividade nem atualiza `updated_at`** dos descendentes. Atividade de cliente já não era rastreada na mod original.
- **Kanban agrupado por cliente:** arrastar uma subtarefa de pai com cliente para outra coluna é revertido pelo backend; o card só volta à coluna certa no próximo fetch.
- **Store desatualizado:** depois de trocar o cliente do pai, os filhos no store mantêm o `client_id` antigo até o refetch. O dropdown compensa mostrando o valor do ancestral quando ele está no store; agrupamentos e filtros no front só se acertam no refetch.
- `sub_issue.py` tem 2 imports não usados (`Func`, `Q`) apontados pelo ruff, pré-existentes do upstream; não mexi.
