# Filtros traduzidos + operadores de data "a partir de" / "até" / "até o fim de"

**Data:** 2026-10-01
**Autor:** felipedrn93
**Branch:** main

## Contexto

Os filtros avançados (rich filters) da lista de tarefas exibiam tudo em inglês — nomes das propriedades ("State Group", "Start date"...) e operadores ("is", "between") — porque os rótulos são strings fixas em `packages/utils`/`packages/constants`, fora do i18n. Além disso, filtros de data só aceitavam **é** (data exata) ou **entre** (intervalo), sem como filtrar "a partir de" ou "antes de" uma data.

## Decisões de design

1. **Tradução na renderização, não nas configs.** As configs continuam com o rótulo em inglês (upstream intacto); os componentes do `web` traduzem por chave `rich_filters.property.<id>` / `rich_filters.operator.<operador>` via `translateFilterLabel`, que cai no rótulo original quando não há tradução (ex.: propriedades customizadas).
2. **Chaves no namespace `common`**, bloco `rich_filters`, em todos os locales (inglês como placeholder; pt-BR traduzido).
3. **Novos operadores core `gte` / `lte`** (`COMPARISON_OPERATOR.GTE/LTE`), com o seletor de data única, habilitados em todos os filtros de data. Rótulos: "a partir de" / "até" — **ambos inclusivos**.
4. **"até o fim de" hoje / esta semana / este mês** (operador `lte_relative`): o valor salvo é o token (`today`, `end_of_week`, `end_of_month`), não uma data — o backend resolve na hora da consulta, então uma visão salva "até o fim desta semana" acompanha o calendário. Reaproveita o seletor single-select (o mesmo do filtro "Bloqueado").
   - Resolvido **no fuso do usuário** (`User.user_timezone`) e com o **início de semana do perfil** (`Profile.start_of_the_week`: domingo → semana termina sábado; segunda → domingo). Por isso o `ComplexFilterBackend` passa `request` ao FilterSet.
   - Campos datetime: `< início do dia seguinte` no fuso do usuário; campos date: `<= último dia`.
5. **Valores das opções traduzidos** pelo `value` (`rich_filters.value.<value>`) em `loadOptions`: prioridades, grupos de estado, Bloqueado/Não bloqueado e os tokens relativos. Valores que são UUID (estados, etiquetas, membros…) caem no rótulo original.
6. **Backend:** filtros explícitos `<campo>__gte` / `<campo>__lte` no `IssueFilterSet`. Nos campos datetime (`created_at`, `updated_at`, `completed_at`) o lookup é `date__gte`/`date__lte`, para que "até 01/10" inclua o dia 01/10 inteiro (comparar datetime com `2026-10-01` cortaria em 00:00).

## Arquivos criados

- `apps/api/plane/tests/unit/utils/test_issue_filterset_dates.py`
- `mods/filtros-ptbr-e-datas.md`

## Arquivos modificados

- `packages/types/src/rich-filters/operators/core.ts` — `GTE`/`LTE`
- `packages/types/src/rich-filters/operator-configs/{core,index}.ts` — config (data única) dos novos operadores
- `packages/constants/src/rich-filters/operator-labels/core.ts` — rótulos em inglês dos novos operadores
- `packages/utils/src/rich-filters/factories/configs/properties/shared.ts` e `packages/utils/src/work-item-filters/configs/filters/shared.ts` — `getSupportedDateOperators` inclui `gte`/`lte`
- `apps/web/core/components/rich-filters/shared.ts` — `translateFilterLabel`
- `apps/web/core/components/rich-filters/add-filters/dropdown.tsx`, `filter-item/root.tsx` — rótulos traduzidos
- `packages/i18n/src/locales/*/common.json` — bloco `rich_filters`
- `apps/api/plane/utils/filters/filterset.py` — lookups `gte`/`lte` de data, `<campo>__lte_relative` + `resolve_relative_date`
- `apps/api/plane/utils/filters/filter_backend.py` — passa `request` ao FilterSet
- `apps/web/core/components/rich-filters/filter-value-input/select/{shared,single,multi}.tsx` — tradução dos valores das opções

## Como testar

1. Lista de tarefas → **Filtros**: propriedades em português (Grupo de estado, Responsáveis, Data de início...).
2. Adicionar "Data de vencimento": operadores **é / entre / a partir de / até**; escolher "até" e uma data → só tarefas com vencimento até aquele dia (inclusive).
3. "Criado em" **até** hoje deve incluir tarefas criadas hoje.
4. "Data de vencimento" **até o fim de** → **esta semana**: tarefas vencendo até sábado (perfil com semana começando no domingo), incluindo atrasadas. Salvar como visão e conferir que na semana seguinte a data limite avança sozinha.
5. Filtro "Prioridade"/"Grupo de estado": opções em português.
6. Backend: `python -m pytest plane/tests/unit/utils/test_issue_filterset_dates.py`.

## Pitfalls / fora do escopo

- "até o fim de" só tem **limite superior** (inclui atrasadas). "A partir de" relativo (ex.: "a partir do início da semana") não foi feito — mesmo padrão, com `gte_relative`, se precisar.
- O `t` do `useTranslation` é recriado a cada render: **não** colocá-lo nas deps do `useEffect` de `loadOptions` (vira loop de recarga).
- Textos de botões da barra ("Clear all", "Save view") não foram traduzidos.
- O `space` (páginas públicas) não usa esses operadores novos.
