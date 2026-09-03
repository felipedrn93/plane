# Design — Módulo Clientes

**Data:** 2026-09-03
**Autor:** felipedrn93
**Status:** aprovado (brainstorming), pendente plano de implementação

## Contexto

O fork precisa relacionar tarefas a clientes reais do negócio. Hoje não existe nenhuma entidade de cliente no Plane — o mais próximo são rótulos, que não modelam CNPJ nem a relação "um cliente, várias empresas".

Um cliente pode ter mais de um CNPJ. Portanto o cadastro é em dois níveis: **Cliente** (nome guarda-chuva) e **Empresa** (nome + CNPJ) pertencente a um cliente.

## Decisões de design

1. **Escopo workspace.** Clientes são do workspace, compartilhados por todos os projetos.
2. **Vínculo com a tarefa é com o Cliente, não com a Empresa.** As empresas são dados cadastrais; a tarefa aponta para o cliente.
3. **Um cliente por tarefa** — FK única em `Issue`, comportando-se como Estado/Responsável (filtrável e agrupável), não como Rótulos.
4. **Entidades próprias com FK**, em vez de rótulos reaproveitados ou JSON genérico na `Issue`. Motivo: filtro e agrupamento nativos exigem coluna real (o group-by do Plane assume colunas), e FK dá integridade referencial.
5. **Status Ativo/Inativo no Cliente**, não em cada empresa. Cliente inativo não aparece no dropdown de tarefas, mas continua visível nas tarefas que já o referenciam.
6. **Exclusão bloqueada quando há tarefas vinculadas** — a UI oferece "Inativar" no lugar.
7. **CNPJ validado** (dígitos verificadores) e único por workspace; guardado só com dígitos, exibido com máscara.
8. **Escrita para Admin e Membro**; Convidado apenas lê.
9. **URL em inglês (`/clients`), rótulo em português ("Clientes")** — consistência com o restante do código, tradução via i18n.

## Modelo de dados

Novos models em `apps/api/plane/db/models/client.py`, herdando `BaseModel`.

### `Client`

| Campo       | Tipo         | Notas                                              |
| ----------- | ------------ | -------------------------------------------------- |
| `workspace` | FK Workspace | `related_name="clients"`                           |
| `name`      | CharField    | obrigatório; único por workspace, case-insensitive |
| `is_active` | BooleanField | default `True`                                     |

### `ClientCompany`

| Campo       | Tipo          | Notas                                                                        |
| ----------- | ------------- | ---------------------------------------------------------------------------- |
| `workspace` | FK Workspace  |                                                                              |
| `client`    | FK Client     | `related_name="companies"`, `on_delete=CASCADE`                              |
| `name`      | CharField     | obrigatório                                                                  |
| `cnpj`      | CharField(14) | só dígitos; `unique_together (workspace, cnpj)` desconsiderando soft-deleted |

### `Issue.client`

FK nullable para `Client`, `on_delete=SET_NULL`, `related_name="issues"`.

Migration: `0127_client_clientcompany_issue_client.py` (a última atual é `0126_profile_language_pt_br`).

## API

Views em `apps/api/plane/app/views/client/base.py`, rotas em `apps/api/plane/app/urls/client.py` (registrado em `plane/app/urls/__init__.py`).

| Método               | Rota                                                         | Acesso                              |
| -------------------- | ------------------------------------------------------------ | ----------------------------------- |
| GET                  | `/api/workspaces/<slug>/clients/`                            | Admin, Membro, Convidado            |
| POST                 | `/api/workspaces/<slug>/clients/`                            | Admin, Membro                       |
| GET / PATCH / DELETE | `/api/workspaces/<slug>/clients/<pk>/`                       | leitura todos; escrita Admin/Membro |
| POST                 | `/api/workspaces/<slug>/clients/<client_id>/companies/`      | Admin, Membro                       |
| PATCH / DELETE       | `/api/workspaces/<slug>/clients/<client_id>/companies/<pk>/` | Admin, Membro                       |

- Permission class: `WorkspaceEntityPermission` (mesmo padrão de labels/estados de workspace).
- O GET de listagem devolve `companies` aninhadas (evita N+1) e `issue_count` anotado — usado no card da lista e na regra de exclusão.
- `DELETE` de cliente com `issue_count > 0` responde **400** com mensagem orientando a inativar.
- **Tarefas de um cliente:** sem endpoint novo. `client` entra nos filtros em `plane/utils/issue_filters.py`; a aba de tarefas do cliente consome o endpoint de issues de workspace com `?client=<id>`.

### Allowlists de campo (pitfall conhecido do fork)

`client` precisa ser adicionado em **todos** estes pontos, senão o campo some nas listagens — mesmo problema documentado em `mods/tarefas-recorrentes.md`:

- `plane/app/serializers/issue.py` — `IssueSerializer.Meta.fields` e `IssueListDetailSerializer.to_representation`
- `plane/app/views/issue/base.py` — `.values()` de `IssueListEndpoint.get` e de `IssueViewSet.create`, `required_fields` de `IssuePaginatedViewSet.list`
- `plane/app/views/issue/sub_issue.py` — `.values()` de `SubIssuesEndpoint.get`
- `plane/utils/grouper.py` — `required_fields` de `issue_on_results`
- `apps/web/core/store/issue/issue-details/issue.store.ts` — allowlist de `addIssueToStore`

## Frontend

### Sidebar

- `packages/constants/src/workspace.ts`: entrada `clients` em `WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS` (href `/clients/`, acesso Admin/Membro/Convidado) e inclusão em `WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS_LINKS` **logo após `home`**.
- `apps/web/ce/components/workspace/sidebar/helper.tsx`: case `"clients"` retornando o ícone `Building2` (lucide).
- `apps/web/core/components/workspace/sidebar/sidebar-item.tsx`: `"clients"` na lista `staticItems` — sem isso o item é escondido por não estar "pinado".

### Rota

`/:workspaceSlug/clients` e `/:workspaceSlug/clients/:clientId` em `app/routes/core.ts`, com `layout.tsx` + `page.tsx` espelhando o padrão de `stickies`.

### Camada de dados

- `ClientService` em `packages/services` (`workspace/client.service.ts`).
- Tipos `TClient` / `TClientCompany` em `packages/types`.
- `ClientStore` MobX registrado no `core/store/root.store.ts`, no formato dos stores de `label`/`state`: `clientMap` por id, `fetchClients`, `createClient`, `updateClient`, `deleteClient`, `createCompany`, `updateCompany`, `deleteCompany`, com update otimista e rollback no erro.

### Telas

1. **Lista** (`/clients`): tabela com Nome, nº de empresas, nº de tarefas e status; busca por nome/CNPJ; toggle "mostrar inativos" (padrão: só ativos); botão "Novo cliente" oculto para Convidado.
2. **Modal de cliente**: nome + status + lista editável de empresas (Nome e CNPJ mascarado por linha, "+ Adicionar empresa", remover). Cliente e empresas criados na mesma tela.
3. **Detalhe** (`/clients/:clientId`): cabeçalho com nome/status, bloco de empresas e **aba Tarefas** reusando o layout de spreadsheet de issues com `?client=<id>`.

### Integração nas tarefas

- **Dropdown:** `core/components/dropdowns/client.tsx`, padrão portal + `react-popper` — o `Popover` do Headless UI quebra no peek de 400px (pitfall registrado em `mods/tarefas-recorrentes.md`). Lista só clientes ativos, com busca, mais a opção "Nenhum". Usado no sidebar do detalhe da tarefa e no peek overview.
- **Planilha:** `issue-layouts/spreadsheet/columns/client-column.tsx` + registro nos constants de propriedades da spreadsheet; herda o reordenamento persistente de colunas do fork (`mods/reordenar-colunas-spreadsheet.md`).
- **Display properties:** `client: boolean` em `IIssueDisplayProperties` (`@plane/types`) e no default de `display_properties` do backend.
- **Filtro e agrupamento:** `client` nas opções de filtro (com o componente de filtro aplicado correspondente) e de _group by_; `client_id` no `FIELD_MAPPER` de `utils/grouper.py`; o cabeçalho do grupo resolve o nome via `ClientStore`. Views salvas funcionam por serializarem os mesmos filtros.

## i18n

Chaves novas em **todos** os `packages/i18n/src/locales/<lang>/translations.json` (inglês como placeholder, pt-BR traduzido): `clients.title`, `clients.new`, `clients.companies`, `clients.cnpj`, `clients.invalid_cnpj`, `clients.status.active`, `clients.status.inactive`, `clients.delete_blocked`.

## Testes

**Backend (pytest, marcador `unit`):**

- Validador de CNPJ: dígitos verificadores corretos e incorretos, tamanho errado, sequências repetidas (`00000000000000`).
- Unicidade de CNPJ por workspace.
- Unicidade case-insensitive do nome do cliente por workspace.
- `DELETE` bloqueado (400) com tarefas vinculadas; permitido sem tarefas.
- Permissões: Convidado recebe 403 em POST/PATCH/DELETE.

**Frontend:** `apps/web` não tem suíte de testes de componente — verificação manual via `pnpm dev` (criar cliente com 2 empresas, vincular a uma tarefa, filtrar, agrupar, inativar, tentar excluir).

`pnpm check` deve passar sem elevar o teto de warnings do `apps/web`.

## Entrega

1. Linha #15 em `mods.md` + `mods/clientes-cadastro.md` (em português), cruzando com `mods/tarefas-recorrentes.md` e `mods/reordenar-colunas-spreadsheet.md`.
2. Deploy no CT 105 — há migration, então: `docker compose build api migrator web` → `docker compose up migrator` → `docker compose up -d api web`.

## Fora de escopo

- Vincular tarefa a uma **empresa** específica (só ao cliente).
- Múltiplos clientes por tarefa.
- Campos extras de cadastro (razão social, endereço, contatos, observações).
- Relatórios e analytics por cliente.
- Importação em massa de clientes.
