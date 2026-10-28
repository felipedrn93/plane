# Buscas sem distinção de acento

**Data:** 2026-10-28
**Autor:** felipedrn93
**Branch:** main

## Contexto

As buscas comparavam com `ILIKE`/`icontains`, que ignoram maiúsculas mas não acentos: buscar "uniao" não achava
a tarefa do cliente "União".

## Decisões de design

1. **Extensão `unaccent` do Postgres** (vem no contrib da imagem `postgres:15.7-alpine`), criada por migration.
   Os dois lados da comparação passam por `unaccent()`, então funciona nos dois sentidos ("uniao" ↔ "União").
2. **ORM:** `__icontains` → `__unaccent__icontains` (lookup do `django.contrib.postgres`, que entrou no
   `INSTALLED_APPS` só para isso).
3. Sem índice: `unaccent()` não é `IMMUTABLE`, mas `ILIKE '%x%'` já não usava índice, então não há regressão.

## Arquivos criados

- `apps/api/plane/db/migrations/0131_unaccent_extension.py` — `CREATE EXTENSION unaccent`.

## Arquivos modificados

- `apps/api/plane/settings/common.py` — `django.contrib.postgres` no `INSTALLED_APPS`.
- `apps/api/plane/utils/grouper.py` — `search_issue_ids_by_text` (busca inline das listas e de "Seu trabalho",
  ver [mods/busca-inline-view.md](busca-inline-view.md) e [mods/busca-seu-trabalho.md](busca-seu-trabalho.md)):
  nome da tarefa, cliente, estado, etiqueta e responsável com `unaccent`.
- `apps/api/plane/app/views/search/base.py` — busca global (Ctrl+K) e menções/seletores (`SearchEndpoint`).
- `apps/api/plane/utils/issue_search.py` — seletor de tarefas (pai, relações, subtarefas).

## Como testar

1. Deploy com migration: `docker compose build api migrator && docker compose up migrator && docker compose up -d api`.
2. "Seu trabalho" ou lista de projeto: buscar "uniao" → aparecem as tarefas do cliente "União".
3. Buscar "União" também acha registros gravados sem acento.
4. Ctrl+K: buscar uma tarefa/projeto acentuado digitando sem acento.

## Pitfalls / fora do escopo

- Filtros feitos no próprio navegador (busca dentro de dropdowns: lista de clientes, etiquetas, membros) não
  passam pelo backend e continuam sensíveis a acento.
- API pública (`/api/v1/`), notificações e stickies mantêm `icontains` puro.
- Se a migration não rodar, a busca inline cai no `except` e retorna vazio (contrato defensivo existente).

## Correção 2026-10-28 — Ctrl+K cortava tarefas recentes

O Ctrl+K (`GlobalSearchEndpoint.filter_issues`) devolve no máximo 100 tarefas e não tinha ordenação. Com o
acento ignorado, "uniao" passou a casar 142 tarefas e a BI-7582 (recente) ficava fora do corte. Agora ordena por
`-created_at` (igual ao `filter_intakes`), então as mais novas aparecem primeiro.

## Correção 2026-10-28 — Ctrl+K refiltrava no navegador com acento

O `<Command>` do Power-K (`apps/web/core/components/power-k/ui/modal/wrapper.tsx`) tem um `filter` próprio que
refiltra no navegador o que o backend devolveu, com `toLowerCase().includes()`. Ele descartava "União…" ao buscar
"uniao". O filtro agora remove acentos dos dois lados (`normalize("NFD")` + remoção dos diacríticos).
