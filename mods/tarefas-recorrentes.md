# Tarefas recorrentes

**Data:** 2026-05-24
**Autor:** felipedrn93
**Atualizado:** 2026-06-11 — cascata de subtarefas (ver seção "Cascata de subtarefas").

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
- `apps/api/plane/bgtasks/recurring_issue_task.py` — task Celery `create_next_recurring_issue` + utilitários `compute_next_date`, `compute_next_dates`. Usa `dateutil.rrule`. Re-exporta `validate_recurrence_pattern` de `plane.utils.recurrence_validator` para manter compatibilidade com os testes. Desde 2026-06-11 inclui também os helpers da cascata de subtarefas (`shift_dates`, `_default_state_for_project`, `_copy_issue_relations`, `_emit_created_activity`).
- `apps/api/plane/utils/recurrence_validator.py` — função `validate_recurrence_pattern` (schema do JSONB) extraída do `recurring_issue_task.py` para um módulo dependency-free. Necessário porque os serializers de Issue precisam validar o campo, e importar direto do `recurring_issue_task.py` (que importa `issue_activities_task`, que importa `IssueActivitySerializer` do pacote serializers) fechava um ciclo durante o boot do Django.
- `apps/api/plane/tests/unit/bg_tasks/test_recurring_issue_task.py` — 16 testes pytest cobrindo cálculo de próxima data (diário, semanal com/sem weekdays + wrap, mensal monthday, mensal Nª/última weekday, anual), `compute_next_dates` (preserva delta start↔target) e validação do schema. Atualizado em 2026-06-11 com `TestShiftDates` (4 testes puros) e `TestRecurringIssueCascade` (2 testes `django_db`: cascata pai→subtarefas e regressão da subtarefa recorrente sob o mesmo pai).

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
  - `IssueCreateSerializer.validate` chama `validate_recurrence_pattern` quando o campo está presente no payload. Import de `plane.utils.recurrence_validator` (não de `plane.bgtasks.recurring_issue_task`, pra evitar circular import — ver módulo `recurrence_validator.py` em "Arquivos criados").
- `apps/api/plane/api/serializers/issue.py`
  - `IssueSerializer.validate` chama `validate_recurrence_pattern` (o `exclude` do Meta já incluía o campo automaticamente). Mesmo import de `plane.utils.recurrence_validator`.
- `apps/api/plane/app/views/issue/base.py` e `apps/api/plane/app/views/issue/sub_issue.py`
  - `IssueListEndpoint.get` (`.values()`), `IssueViewSet.create` (response pós-create `.values()`), `IssuePaginatedViewSet.list` (`required_fields`) e `SubIssuesEndpoint.get` (`.values()`) listam manualmente os campos a devolver — `recurrence_pattern` adicionado em todos eles, senão o frontend recebe o issue sem o campo no GET de listagem (e o painel "apaga" o que foi configurado, mesmo estando no banco).
- `apps/api/plane/settings/common.py`
  - `recurring_issue_task` adicionado em `CELERY_IMPORTS`. Sem isso o worker boota sem importar o módulo, o `@shared_task` em `create_next_recurring_issue` nunca registra e a mensagem enfileirada por `Issue.save()` cai como "Received unregistered task" — a próxima ocorrência nunca é criada. Outras bgtasks evitam isso porque estão em `CELERY_IMPORTS` ou são puxadas transitivamente por algo que está; o `recurring_issue_task` só era importado lazy dentro de `Issue.save()`, que roda no processo da API, não no worker.
- `apps/web/core/store/issue/issue-details/issue.store.ts`
  - `addIssueToStore` monta o objeto `TIssue` no store com allowlist explícita campo a campo (`id`, `name`, `state_id`, …). `recurrence_pattern` faltava — o `IssueDetailSerializer` do backend devolve o campo, mas o store o jogava fora ao popular. Resultado: ao abrir uma issue recorrente o dropdown mostrava "sem recorrência" mesmo com o JSONB salvo no banco. Fix: incluir `recurrence_pattern: issue?.recurrence_pattern` no payload.
- `apps/web/core/components/issues/issue-layouts/properties/all-properties.tsx`
  - Pequeno badge com ícone `Repeat` adicionado entre os indicadores extras (sub-issues, attachments, links). Renderiza só quando `issue.recurrence_pattern` está setado. Tooltip mostra "Recorrência" como heading e a frequência traduzida (`daily/weekly/monthly/yearly`) como content. Sem gate de display-properties — o ícone só aparece em issues recorrentes então é discreto e serve como pista visual sem precisar de toggle no settings de layout.
- `apps/api/plane/utils/grouper.py`
  - `issue_on_results` (usado pelo `IssueViewSet.list`, o endpoint principal do kanban/list/spreadsheet) projeta a queryset com uma lista hardcoded de `required_fields`. Ainda outra "shadow allowlist" sem `recurrence_pattern` — o ícone que adicionei em `all-properties.tsx` nunca renderizava porque o store recebia issues sem o campo. Fix: adicionar `"recurrence_pattern"` na lista.

**Infra do fork (necessárias pra rodar a partir do código, não estritamente da feature)**

- `docker-compose.yml` (raiz)
  - Serviço `live`: adicionado `env_file: ./apps/api/.env` e `environment: API_BASE_URL: http://api:8000`. Sem isso o Hocuspocus crashava com `Invalid environment variables: { API_BASE_URL: "Required", LIVE_SERVER_SECRET_KEY: "Required" }`.
  - Serviço `proxy`: adicionado `env_file: .env`. Sem isso o `SITE_ADDRESS` não chegava no Caddyfile, ele renderizava como bloco global vazio e Caddy recusava com `server block without any key is global configuration`.
  - Bug existe só no compose da raiz (usado para build a partir do código). O `deployments/cli/community/docker-compose.yml` (usado pelo `setup.sh` oficial) já cabeia isso via âncoras YAML `*live-env` e `*proxy-env`.
- `.gitignore`
  - Adicionado `meu proxmox/` (notas locais do CT do Proxmox, fora do escopo do repo) e `*/*.stackdump` (crash dumps do Cygwin no Windows).

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
2. Backend recebe o PATCH em `IssueViewSet.partial_update`, valida via `validate_recurrence_pattern` (chamado dentro de `IssueCreateSerializer.validate`, que é o serializer usado para create/update/partial_update — ver `IssueViewSet.get_serializer_class`), persiste no campo JSONB.
3. Usuário marca a issue como concluída (state vira grupo `completed`). `Issue.save()` detecta a transição e enfileira `create_next_recurring_issue.delay(issue_id)` via `transaction.on_commit`.
4. O worker Celery executa a task: calcula `next_target_date` (e `next_start_date` preservando o delta) com `dateutil.rrule`, escolhe o state default do projeto, e cria uma nova `Issue` clonando name/description/priority/assignees/labels/parent/recurrence_pattern.
5. A nova issue aparece na lista; ao ser concluída, gera a próxima, e assim por diante.

## Cascata de subtarefas (atualização 2026-06-11)

Estende a recorrência para **copiar as subtarefas junto com o pai**, cobrindo dois cenários:

1. **Recorrência no pai → subtarefas acompanham.** Quando um pai recorrente é concluído e a próxima ocorrência é criada, todas as suas **subtarefas diretas** (`Issue.issue_objects.filter(parent_id=...)`) são clonadas sob a nova ocorrência. As datas de cada subtarefa são deslocadas pelo **mesmo delta** que o pai andou (`delta = novo_target_pai − target_pai_antigo`), preservando o intervalo relativo: pai dia 20 → dia 20 do próximo período, subtarefa dia 15 → dia 15.
2. **Recorrência direto numa subtarefa → nova subtarefa filha do mesmo pai.** Já era o comportamento da task original (cria a nova ocorrência com `parent=issue.parent`); agora coberto por teste de regressão. Quando a issue recorrente é ela mesma uma subtarefa, a nova ocorrência herda o mesmo `parent`.

### Implementação (`recurring_issue_task.py`)
- `shift_dates(start_date, target_date, delta)` — helper puro: desloca ambas as datas por um `timedelta`, preservando `None`.
- `_default_state_for_project(project)` e `_copy_issue_relations(source, new_issue)` — extraídos da criação do pai para reuso nas subtarefas (state default não-triage + cópia de assignees/labels via `bulk_create`).
- `_emit_created_activity(new_issue, source)` — emite `issue.activity.created` (com `recurring_source_id`) para cada clone.
- Depois de criar o novo pai, a task itera os filhos diretos e cria um clone de cada (`parent` = novo pai, datas deslocadas pelo delta, state default, `recurrence_pattern` do próprio filho preservado, assignees/labels copiados). Tudo dentro do mesmo `transaction.atomic`.

### Decisões (confirmadas com o usuário)
- **Datas:** mesmo deslocamento (delta) do pai — não reaplica o rrule do pai sobre a data da subtarefa (isso jogaria o dia 15 para o dia 20).
- **Escopo:** copia **todas** as subtarefas diretas, mesmo as já concluídas; entram em estado inicial (grupo não-completed) e por isso **não** disparam recorrência própria na criação.
- **Recorrência própria da subtarefa:** preservada na cópia.

### Limitações
- **Profundidade 1:** apenas filhos diretos são copiados; netos (subtarefas de subtarefas) não são recursados.
- **Pai + filho ambos recorrentes:** se uma subtarefa tem recorrência própria **e** o pai também recorre, podem surgir subtarefas duplicadas (a subtarefa se recria sob o pai antigo via cenário 2 e também é copiada quando o pai recorre via cenário 1). Combinação não recomendada.
- **Delta em meses de tamanhos diferentes:** o deslocamento é em dias corridos; em meses com tamanhos diferentes (ex.: jan→fev) a data da subtarefa pode variar ±1 dia em relação ao "mesmo dia do mês". Aceito nesta versão.
- Comentários e anexos das subtarefas **não** são copiados.

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

## Pitfalls — todos os lugares onde um campo novo de `Issue` precisa aparecer

Lições da implementação de `recurrence_pattern`. O Plane espalha o conhecimento de "quais campos uma Issue tem" por várias listas hardcoded. Adicionar um novo campo no model **não basta** — precisa ser declarado em cada uma das seguintes:

**Backend — model e migration:**
- `apps/api/plane/db/models/issue.py` — declaração do campo.
- `apps/api/plane/db/migrations/0xxx_<nome>.py` — migration.

**Backend — serializers (formato de I/O):**
- `apps/api/plane/app/serializers/issue.py` → `IssueSerializer.Meta.fields` (lista de retorno).
- `apps/api/plane/app/serializers/issue.py` → `IssueListDetailSerializer.to_representation` (constrói o dict manualmente).
- `apps/api/plane/app/serializers/issue.py` → `IssueCreateSerializer.validate` (validação no PATCH/POST). Esse é o serializer usado por create/update/partial_update do `IssueViewSet`.
- `apps/api/plane/api/serializers/issue.py` → `IssueSerializer.validate` (rota `/api/v1/...`, se quiser que a public API também aceite o campo).

**Backend — `.values()` projections em views de listagem (shadow allowlists):**
- `apps/api/plane/utils/grouper.py` → `issue_on_results.required_fields` — **o mais fácil de esquecer**. É o que `IssueViewSet.list` usa para projetar a queryset que vai pro kanban/list/spreadsheet. Sem o campo aqui, o frontend nunca recebe na listagem principal.
- `apps/api/plane/app/views/issue/base.py:163` → `IssueListEndpoint.get` (`.values()` no fallback sem fields/expand).
- `apps/api/plane/app/views/issue/base.py:428` → `IssueViewSet.create` (response pós-create — `.values()` para retornar a issue recém-criada).
- `apps/api/plane/app/views/issue/base.py:859` → `IssuePaginatedViewSet.list` (`required_fields` da v2).
- `apps/api/plane/app/views/issue/sub_issue.py:141` → `SubIssuesEndpoint.get` (`.values()` para sub-issues).

**Backend — Celery (se o `save()` enfileirar task):**
- `apps/api/plane/settings/common.py` → `CELERY_IMPORTS` (lista explícita de módulos de task que o worker importa no boot). Sem o módulo aqui, o `@shared_task` nunca registra no worker e mensagens enfileiradas pelo API caem como `Received unregistered task` e são descartadas. **Não confiar** que `autodiscover_tasks()` resolve — o do Plane procura `<app>.tasks` que não existe pro `plane.bgtasks`.

**Frontend — tipos:**
- `packages/types/src/issues/issue.ts` → `TBaseIssue` (adicionar o campo opcional/nullable).

**Frontend — stores (shadow allowlists do lado JS):**
- `apps/web/core/store/issue/issue-details/issue.store.ts` → `addIssueToStore` — outra allowlist explícita campo-a-campo. O backend pode estar mandando o campo certinho, mas se ele não estiver listado aqui o detail/peek-overview nunca vê. O root `addIssue` em `apps/web/core/store/issue/issue.store.ts` usa spread, então não precisa de mudança lá.

**Frontend — UI (onde o campo deve aparecer):**
- `apps/web/core/components/issues/peek-overview/properties.tsx` — sidebar do peek-overview (campo editável).
- `apps/web/core/components/issues/issue-layouts/properties/all-properties.tsx` — indicadores compactos no kanban/list/spreadsheet (badge com ícone).
- (futuro) settings de "Display properties" se quiser deixar o usuário esconder o indicador.

**Como detectar shadow allowlists novas:** `grep -rn '"target_date"' apps/api/plane apps/web/core` mostra a maioria delas — onde aparece `target_date` literal numa lista, provavelmente é uma allowlist que precisa do campo novo também.

## Idempotência e edge cases tratados

- Re-salvar uma issue já concluída (ex.: editar título) **não** dispara nova ocorrência: o trigger só roda na transição `was_completed_before=False → completed_at=now()`.
- Issue criada já com state "Done" e `recurrence_pattern` setado: dispara uma vez na criação (aceito como comportamento válido para v1).
- Issue sem `target_date` não pode ativar recorrência (UI desabilita; backend retorna sem ação se chegasse mesmo assim).
- A task ignora a issue se `recurrence_pattern` for null no momento da execução (caso o usuário tenha desativado entre o save e o commit).

## Fora do escopo (v2)

- Cópia de comentários e anexos para a nova instância. (Sub-tasks **passaram a ser copiadas** em 2026-06-11 — ver "Cascata de subtarefas".)
- Manter `cycle`/`module` na nova issue (atualmente fica em branco).
- Limite por número de ocorrências ou data-fim.
- "Pular fim de semana" / próximo dia útil.
- Edição em massa da série (alterar todas as futuras de uma vez).
- Link explícito entre instâncias da série (campo `recurrence_source_id` ou uso de `parent`).
- Componente standalone de "gerenciar tarefas recorrentes" (settings) — as strings i18n existentes em `recurring_work_items.settings.*` ainda não estão conectadas a nenhuma UI.
