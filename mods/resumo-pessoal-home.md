# Resumo pessoal de tarefas e menções na página inicial

- **Data:** 2026-09-03
- **Autor:** Felipe (com Codex)
- **Branch:** `main`

## Contexto

A página inicial mostrava a saudação, a data e em seguida os widgets, começando normalmente por
"Links rápidos". Faltava uma visão imediata do trabalho que exige atenção do usuário. Foram
adicionados três cartões entre a saudação e os widgets: tarefas atribuídas em aberto, tarefas
atribuídas em atraso e menções ainda não lidas.

Para esta mod, uma tarefa em aberto precisa ter `target_date` definida, estar atribuída ao usuário
logado e não pertencer aos grupos de estado `completed` ou `cancelled`. As atrasadas são o
subconjunto cuja `target_date` é anterior à data atual; tarefas com vencimento hoje não contam como
atrasadas.

## Decisões de design

- Um endpoint enxuto (`/api/workspaces/{slug}/home-summary/`) devolve somente os dois totais de
  tarefas e executa uma única agregação no banco.
- O total de menções reutiliza `mention_unread_notifications_count`, evitando duplicar consulta ou
  regra de leitura de notificações.
- Os cartões de tarefas abrem as views estáticas `assigned-open` e `assigned-overdue`. O escopo é
  reaplicado obrigatoriamente pelo backend por meio de `home_assignment_scope`; portanto, filtros de
  visualização salvos pelo usuário não conseguem remover as condições essenciais.
- A mesma função de queryset atende o endpoint e as listas, mantendo contagem e destino coerentes.
  Ela também reutiliza as regras de visibilidade por projeto da listagem global, inclusive para
  convidados.
- A atribuição é validada pela relação ativa (`IssueAssignee.deleted_at IS NULL`), para não contar
  usuários que já foram removidos da tarefa.
- O cartão de menções seleciona a aba Menções no store antes de navegar para `/notifications`.
- Não há migração de banco de dados.

## Arquivos criados

- `apps/api/plane/app/views/workspace/home_summary.py` — endpoint, escopos fixos e filtros comuns.
- `apps/api/plane/tests/unit/views/test_home_summary.py` — testes dos escopos e do contrato resumido.
- `apps/web/core/components/home/summary-cards.tsx` — os três cartões responsivos e clicáveis.

## Arquivos modificados

- `apps/api/plane/app/urls/workspace.py` e `apps/api/plane/app/views/__init__.py` — registro do endpoint.
- `apps/api/plane/app/views/view/base.py` — aplicação dos escopos fixos na listagem global.
- `apps/web/core/components/home/root.tsx` e `index.ts` — inclusão e exportação do resumo.
- `apps/web/core/services/workspace.service.ts` e `store/workspace/home.ts` — busca e estado do resumo.
- `apps/web/core/store/issue/helpers/issue-filter-helper.store.ts` e
  `store/issue/workspace/filter.store.ts` — parâmetros e preferências das novas views estáticas.
- `packages/types/src/{workspace.ts,workspace-views.ts,view-props.ts}` — tipos do payload e das views.
- `packages/constants/src/workspace.ts` — registro das views estáticas na navegação.
- `packages/i18n/src/locales/{en,pt-BR}/{common,home}.json` — rótulos dos cartões e views.

## Como testar

1. Abrir a home de um workspace e confirmar os três cartões entre a data e os widgets.
2. Criar ou localizar tarefas atribuídas ao usuário com: data futura, data de hoje, data passada,
   sem data, concluída e cancelada. O cartão em aberto inclui as três primeiras; o cartão em atraso
   inclui somente a de data passada.
3. Clicar em cada total de tarefas e confirmar que a lista aberta contém exatamente o mesmo escopo.
4. Clicar em menções e confirmar a abertura de Notificações diretamente na aba Menções.
5. Executar `pnpm turbo run check:types --filter=@plane/types --filter=@plane/constants --filter=web`,
   lint do frontend, `ruff` e o teste unitário do backend.

## Deploy (CT 105)

Rebuild de `api` e `web`, sem migrator, worker ou beat-worker:

```bash
cd /opt/plane
git pull origin main
docker compose build api web
docker compose up -d api web
```

## Pitfalls

- "Em aberto" inclui tarefas atrasadas; "em atraso" é deliberadamente um subconjunto.
- `target_date` é um campo de data. A comparação usa `timezone.localdate()` para não classificar uma
  tarefa que vence hoje como atrasada.
- Os outros locales não são exigidos neste fork porque a interface é fixada em `pt-BR`; `en` é
  mantido como fonte/fallback, conforme [mods/idioma-fixo-pt-br.md](idioma-fixo-pt-br.md).
