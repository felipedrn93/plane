# Busca inline em "Seu trabalho" (+ cliente, estado, etiqueta e responsável)

**Data:** 2026-10-27
**Autor:** felipedrn93
**Branch:** main

## Contexto

O campo de busca das listas de tarefas ([mods/busca-inline-view.md](busca-inline-view.md)) não existia na tela
"Seu trabalho" (`/:workspaceSlug/profile/:userId/{assigned,created,subscribed}`). Além disso, ele só casava
nome, ID e caminho do pai; o pedido era pesquisar nos campos visíveis do quadro, como o cliente.

## Decisões de design

1. **Reaproveita tudo da mod #6**: mesmo componente `WorkItemSearch`, mesmo param efêmero `search_text`, mesmo
   helper `search_issue_ids_by_text` (escopo por workspace, já que "Seu trabalho" é cross-project).
2. **Campos novos no helper compartilhado**: nome do cliente, nome do estado, nome das etiquetas e nome dos
   responsáveis (`display_name` ou `first_name last_name`). Vale para **todas** as telas com a busca.
3. **Campos novos não descem para as subtarefas.** Só nome/ID continuam puxando os descendentes; um match por
   estado ou etiqueta no pai não deve trazer a árvore inteira. (O cliente já é herdado pelas subtarefas — ver
   [mods/cliente-herdado-do-pai.md](cliente-herdado-do-pai.md) — então elas casam sozinhas.)

## Arquivos modificados

- `apps/api/plane/utils/grouper.py` — `search_issue_ids_by_text`: `UNION` com os matches por cliente, estado,
  etiqueta e responsável.
- `apps/api/plane/app/views/workspace/user.py` — `WorkspaceUserProfileIssuesEndpoint.get` lê `search_text`.
- `apps/web/core/store/issue/profile/filter.store.ts` — `searchQuery` observável, `updateSearchQuery`, e
  `getSearchQuery(userId)` passado ao `computedFilteredParams`.
- `apps/web/core/components/profile/profile-issues.tsx` — renderiza o `WorkItemSearch` acima da linha de filtros.

## Como testar

1. "Seu trabalho" → Atribuído: digitar parte do nome de um cliente → só as tarefas daquele cliente.
2. Digitar o nome de um estado ("Backlog"), de uma etiqueta ou de um responsável → filtra por eles.
3. Trocar entre Atribuído / Criado / Inscrito: a busca continua aplicada (é por usuário, não por aba).
4. Na lista de um projeto, buscar pelo cliente também funciona.

## Pitfalls / fora do escopo

- Prioridade não entra: no banco é `urgent/high/...` e a UI mostra em português; exigiria um mapa de tradução.
- Datas, estimativa e módulo/ciclo não entram na busca textual (use os filtros).
