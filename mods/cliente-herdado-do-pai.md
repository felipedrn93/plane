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
6. **Front: dropdown travado.** O `ClientDropdown` recebe `parentId`, sobe a cadeia de ancestrais pelo `issueMap` e, se algum tem cliente, mostra o cliente do ancestral mais alto, fica desabilitado e o tooltip diz "Herdado da tarefa pai". Ancestral fora do store é ignorado; o backend corrige de qualquer forma.

## Arquivos modificados

### Backend
- `apps/api/plane/db/models/issue.py` — `TRACKED_FIELDS`, `_inherit_parent_client`, `propagate_client`, chamadas no `save()`.
- `apps/api/plane/app/views/issue/sub_issue.py` — o "Adicionar subtarefas existentes" usa `bulk_update`, que pula o `save()`; chama `propagate_client` depois.
- `apps/api/plane/tests/unit/models/test_client.py` — `TestSubIssueInheritsClient` (5 casos).

### Frontend
- `apps/web/core/components/dropdowns/client.tsx` — prop `parentId`, valor herdado e trava.
- `apps/web/core/components/issues/issue-detail/sidebar.tsx`, `issues/peek-overview/properties.tsx`, `issue-layouts/properties/all-properties.tsx`, `issue-layouts/spreadsheet/columns/client-column.tsx` — passam `parentId={issue.parent_id}`.
- `packages/i18n/src/locales/*/clients.json` — chave `clients.inherited_from_parent`.

## Como testar

```bash
# backend (stack local: plane-db + plane-redis no ar, rede plane_dev_env)
docker run --rm --network plane_dev_env -v "$PWD/apps/api":/code -w /code --env-file apps/api/.env \
  -e DATABASE_URL=postgresql://plane:plane@plane-db:5432/plane -e REDIS_URL=redis://plane-redis:6379/ \
  --entrypoint sh plane-api -c 'pip install -q -r requirements/test.txt; python -m pytest -q -m unit plane/tests/unit'
```
Em 2026-10-19: 189 passaram, 10 falharam — as mesmas 10 falhas aparecem sem esta mod (ambiente: porta do RabbitMQ entre aspas no `--env-file`, banco de teste reaproveitado, e as falhas pré-existentes listadas em [clientes-cadastro.md](clientes-cadastro.md#pitfalls)).

Manual:
1. Pai com cliente "Acme" → criar subtarefa: ela já nasce com "Acme" e o dropdown fica travado com o tooltip "Herdado da tarefa pai".
2. Pai sem cliente → a subtarefa aceita qualquer cliente.
3. Trocar o cliente do pai → filhos e netos passam a mostrar o novo cliente (recarregar a lista se o filho não estiver no store junto com o pai).
4. "Adicionar subtarefas existentes" num pai com cliente → as tarefas adicionadas (e os filhos delas) herdam o cliente.

## Pitfalls

- **`UPDATE` em lote não gera atividade nem atualiza `updated_at`** dos descendentes. Atividade de cliente já não era rastreada na mod original.
- **Kanban agrupado por cliente:** arrastar uma subtarefa de pai com cliente para outra coluna é revertido pelo backend; o card só volta à coluna certa no próximo fetch.
- **Store desatualizado:** depois de trocar o cliente do pai, os filhos no store mantêm o `client_id` antigo até o refetch. O dropdown compensa mostrando o valor do ancestral quando ele está no store; agrupamentos e filtros no front só se acertam no refetch.
- `sub_issue.py` tem 2 imports não usados (`Func`, `Q`) apontados pelo ruff, pré-existentes do upstream; não mexi.
