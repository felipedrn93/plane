# Tarefas recorrentes

**Data:** 2026-05-24
**Autor:** felipedrn93

## Contexto

O Plane open-source não tem feature de tarefas recorrentes — apenas strings i18n preparadas para a versão Cloud paga (`recurring_work_items.*`), sem código. Esta modificação adiciona recorrência diretamente no fork, no modelo "estilo Asana clássico": quando uma tarefa marcada como recorrente é concluída, uma nova instância é criada automaticamente com as datas deslocadas pelo padrão configurado.

## Decisões de design

1. **Gatilho:** ao concluir a atual (cria a próxima imediatamente). Sem scheduler periódico.
2. **Padrões suportados:** diário, semanal, mensal, anual + dias específicos da semana (Seg/Qua/Sex), dia X do mês, "Nª segunda do mês", "última sexta do mês".
3. **Término:** apenas manual (usuário desativa quando quiser). Sem limite por contagem ou data.
4. **Modelo de dados:** recorrência vive em um campo JSON da própria `Issue`, sem entidade `RecurringWorkItem` separada. Mais simples de migrar; o trade-off é que editar a regra afeta só as ocorrências criadas dali em diante.

## Esquema do `recurrence_pattern`

JSONField nullable no model `Issue`:

```json
{
  "frequency": "daily" | "weekly" | "monthly" | "yearly",
  "interval": 1,
  "by_weekday": ["MO", "WE", "FR"],
  "by_monthday": 15,
  "by_setpos": -1
}
```

`by_weekday`, `by_monthday` e `by_setpos` são opcionais. Combinações típicas:

- Toda terça-feira → `frequency: "weekly", interval: 1, by_weekday: ["TU"]`
- A cada 2 semanas seg/qua/sex → `frequency: "weekly", interval: 2, by_weekday: ["MO","WE","FR"]`
- Dia 15 de todo mês → `frequency: "monthly", interval: 1, by_monthday: 15`
- Última sexta do mês → `frequency: "monthly", interval: 1, by_weekday: ["FR"], by_setpos: -1`
- 1ª segunda de cada mês → `frequency: "monthly", interval: 1, by_weekday: ["MO"], by_setpos: 1`

## Arquivos criados

**Backend**

- `apps/api/plane/db/migrations/0122_issue_recurrence_pattern.py` — adiciona a coluna JSONB em `issues`.
- `apps/api/plane/bgtasks/recurring_issue_task.py` — task Celery `create_next_recurring_issue` + utilitários `compute_next_date`, `compute_next_dates`, `validate_recurrence_pattern`. Usa `dateutil.rrule`.
- `apps/api/plane/tests/unit/bg_tasks/test_recurring_issue_task.py` — 16 testes pytest cobrindo cálculo de próxima data (diário, semanal com/sem weekdays + wrap, mensal monthday, mensal Nª/última weekday, anual), `compute_next_dates` (preserva delta start↔target) e validação do schema.

**Frontend**

- `apps/web/core/components/dropdowns/recurrence.tsx` — `RecurrenceDropdown` (painel ancorado ao botão via `react-popper` + `createPortal`, mesmo padrão de `DateDropdown`/`StateDropdown`. Toggle de recorrência, input de intervalo, select de frequência, chips de dias da semana para semanal, radios "dia X do mês" / "Nª weekday do mês" para mensal, preview da próxima ocorrência). Versão inicial usava `Popover` do Headless UI com `absolute right-0`, mas no peek overview (sidebar de 400px com `overflow-hidden`) o painel "saltava" pra borda direita da página — trocado pelo padrão portal+popper do projeto.

## Arquivos modificados

**Backend**

- `apps/api/plane/db/models/issue.py`
  - Novo campo `recurrence_pattern = models.JSONField(null=True, blank=True)`.
  - `save()` detecta a transição "não-completed → completed" e enfileira `create_next_recurring_issue` via `transaction.on_commit`. Idempotente: re-salvar uma issue já concluída não dispara de novo.
- `apps/api/plane/app/serializers/issue.py`
  - `IssueSerializer.Meta.fields` inclui `recurrence_pattern`.
  - `IssueListDetailSerializer.to_representation` retorna o campo.
  - `IssueCreateSerializer.validate` chama `validate_recurrence_pattern` quando o campo está presente no payload.
- `apps/api/plane/api/serializers/issue.py`
  - `IssueSerializer.validate` chama `validate_recurrence_pattern` (o `exclude` do Meta já incluía o campo automaticamente).
- `apps/api/plane/app/views/issue/base.py` e `apps/api/plane/app/views/issue/sub_issue.py`
  - `IssueViewSet.list` (fallback `.values()`), `IssueViewSet.create` (response pós-create), `IssuePaginatedViewSet.list` (`required_fields`) e `SubIssuesEndpoint` (`.values()`) listam manualmente os campos a devolver — `recurrence_pattern` adicionado em todos eles, senão o frontend recebe o issue sem o campo no GET de listagem (e o painel "apaga" o que foi configurado, mesmo estando no banco).
- `apps/api/plane/settings/common.py`
  - `recurring_issue_task` adicionado em `CELERY_IMPORTS`. Sem isso o worker boota sem importar o módulo, o `@shared_task` em `create_next_recurring_issue` nunca registra e a mensagem enfileirada por `Issue.save()` cai como "Received unregistered task" — a próxima ocorrência nunca é criada. Outras bgtasks evitam isso porque estão em `CELERY_IMPORTS` ou são puxadas transitivamente por algo que está; o `recurring_issue_task` só era importado lazy dentro de `Issue.save()`, que roda no processo da API, não no worker.

**Frontend / Tipos**

- `packages/types/src/issues/issue.ts`
  - Tipos `TRecurrenceFrequency`, `TRecurrenceWeekday`, `TRecurrencePattern`.
  - `TBaseIssue.recurrence_pattern: TRecurrencePattern | null`.
- `apps/web/core/components/issues/peek-overview/properties.tsx`
  - Renderiza `RecurrenceDropdown` logo abaixo do `DateDropdown` de `target_date`, com label `issue.recurrence.label`.
  - Desabilitado quando `issue.target_date` é null (tooltip explica).
  - Reusa `issueOperations.update(...)` para persistir — service/store não precisaram mudar (já aceitam `Partial<TIssue>`).

**i18n**

- `packages/i18n/src/locales/en/work-item.json` e `packages/i18n/src/locales/pt-BR/work-item.json`
  - Nova seção `issue.recurrence.*` com: `label`, `no_recurrence`, `needs_target_date`, `enable`, `disable`, `repeat_every`, `next_occurrence`, `frequency.{daily,weekly,monthly,yearly}`, `unit.{day,week,month,year}` (com plural ICU), `weekday.short/long.{MO..SU}`, `monthly.{option_monthday,option_setpos,monthday_prefix,monthday_suffix,setpos_prefix,setpos_suffix}`, `setpos.{first..fourth,last}`, `summary.{weekly_with_days,monthly_on_day,monthly_on_setpos,interval}`.
  - Demais locales (zh-CN, es, ja, etc.) caem no fallback i18next para `en`.

## Fluxo end-to-end

1. Usuário abre uma issue, define `target_date`, abre o dropdown "Recorrência", liga o toggle e configura o padrão. O `RecurrenceDropdown` chama `issueOperations.update(ws, project, issue, { recurrence_pattern: {...} })`.
2. Backend recebe o PATCH em `IssuePaginatedViewSet`, valida via `validate_recurrence_pattern`, persiste.
3. Usuário marca a issue como concluída (state vira grupo `completed`). `Issue.save()` detecta a transição e enfileira `create_next_recurring_issue.delay(issue_id)` via `transaction.on_commit`.
4. O worker Celery executa a task: calcula `next_target_date` (e `next_start_date` preservando o delta) com `dateutil.rrule`, escolhe o state default do projeto, e cria uma nova `Issue` clonando name/description/priority/assignees/labels/parent/recurrence_pattern.
5. A nova issue aparece na lista; ao ser concluída, gera a próxima, e assim por diante.

## Como testar

```bash
# Backend
cd apps/api
python manage.py migrate
pytest plane/tests/unit/bg_tasks/test_recurring_issue_task.py -v

# Frontend
yarn install
yarn dev   # em apps/web
```

**Smoke manual:**
1. Criar issue → setar `target_date` → abrir "Recorrência" → escolher "Semanal Seg/Qua/Sex" → salvar.
2. Marcar como concluída.
3. Confirmar que aparece nova issue com:
   - Mesmo nome, descrição, prioridade, assignees, labels, parent.
   - `target_date` deslocado para o próximo Seg/Qua/Sex.
   - `state` no default do projeto (Backlog/Todo).
   - `recurrence_pattern` preservado (para continuar a série).

## Idempotência e edge cases tratados

- Re-salvar uma issue já concluída (ex.: editar título) **não** dispara nova ocorrência: o trigger só roda na transição `was_completed_before=False → completed_at=now()`.
- Issue criada já com state "Done" e `recurrence_pattern` setado: dispara uma vez na criação (aceito como comportamento válido para v1).
- Issue sem `target_date` não pode ativar recorrência (UI desabilita; backend retorna sem ação se chegasse mesmo assim).
- A task ignora a issue se `recurrence_pattern` for null no momento da execução (caso o usuário tenha desativado entre o save e o commit).

## Fora do escopo (v2)

- Cópia de sub-tasks, comentários e anexos para a nova instância.
- Manter `cycle`/`module` na nova issue (atualmente fica em branco).
- Limite por número de ocorrências ou data-fim.
- "Pular fim de semana" / próximo dia útil.
- Edição em massa da série (alterar todas as futuras de uma vez).
- Link explícito entre instâncias da série (campo `recurrence_source_id` ou uso de `parent`).
- Componente standalone de "gerenciar tarefas recorrentes" (settings) — as strings i18n existentes em `recurring_work_items.settings.*` ainda não estão conectadas a nenhuma UI.
