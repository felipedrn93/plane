# Persistência do pin no menu "Espaço de trabalho" + "Seu trabalho" abre na aba Atribuído

**Data:** 2026-06-02
**Autor:** felipedrn93
**Branch:** main

## Contexto

Duas alterações de comportamento dos menus da sidebar (app `web`):

1. **Bug do pin (menu "Espaço de trabalho").** Os itens dinâmicos desse menu — **Visualizações**
   (`views`), **Análises** (`analytics`) e **Arquivos** (`archives`); Projetos é fixo/pinado —
   ficam ocultos por padrão e podem ser "pinados" para aparecerem na sidebar. O pin funcionava na
   sessão, **mas sumia ao recarregar a página**.

2. **"Seu trabalho".** Ao clicar em "Seu trabalho" o usuário caía por padrão na aba **Resumo**
   (`/profile/{userId}/`). Agora cai direto na aba **Atribuído** (`/profile/{userId}/assigned/`),
   continuando com a aba Resumo acessível por clique.

## Causa raiz do bug do pin (back-end)

O pin é persistido por `PATCH /api/workspaces/{slug}/sidebar-preferences/` e relido no load
(SWR em `workspace-wrapper.tsx`). O front estava correto (update otimista no store MobX +
releitura via API). O defeito estava no handler `patch` da view:

```python
# apps/api/plane/app/views/workspace/user_preference.py (antes)
preference = WorkspaceUserPreference.objects.filter(key=key, workspace__slug=slug).first()
```

O filtro **não incluía `user`**. `WorkspaceUserPreference` tem uma linha por
`(workspace, user, key)` e `Meta.ordering = ("-created_at",)`, então o `.first()` retornava a
preferência daquele `key` **mais recente entre TODOS os usuários** do workspace — não
necessariamente a do usuário logado. Num workspace com vários usuários (caso do CT 105), o PATCH
acabava alterando a linha de **outro** usuário; no refresh o `get` (que filtra
`user=request.user`) devolvia a linha do usuário logado, ainda com `is_pinned=False` → **pin
perdido**. Num workspace de 1 usuário só, o bug não aparece (por isso era intermitente).

## Decisões de design

1. **Correção mínima e escopada no back-end:** adicionar `user=request.user` ao filtro do PATCH,
   espelhando exatamente o escopo já usado no `get` (linhas 29 e 64 da mesma view). Sem migração
   (nenhuma mudança de schema). A correção vale para **todos** os itens pináveis
   (Visualizações/Análises/Arquivos e também os itens pessoais), por ser o mesmo endpoint.
2. **"Seu trabalho" no nível do link, não da rota.** Apontamos o **href** do item `your_work` para
   `/profile/{userId}/assigned/`, em vez de criar redirect na rota base. Um redirect de
   `/profile/{userId}/` deixaria a aba **Resumo** inacessível (ela vive na rota base, sem rota
   alternativa). Mantendo no link, a aba Resumo continua clicável e abrindo `/profile/{userId}/`.
   As rotas e os tabs (`PROFILE_VIEWER_TAB`/`PROFILE_ADMINS_TAB`) ficam intocados.
3. **Highlight preservado na base do perfil.** Em `SidebarItemBase`, mantivemos `itemHref` (base
   `/profile/{userId}`) para o cálculo de `highlight` e criamos um `linkHref` separado (com
   `/assigned`) só para o `<Link>`. Assim o item "Seu trabalho" segue destacado em **qualquer** aba
   do perfil (Resumo/Atribuído/etc.), não só na Atribuído.
4. **Permissão coerente.** O item `your_work` só é exibido para ADMIN/MEMBER (constante `access`),
   que são exatamente os usuários `isAuthorized` no `profile/[userId]/layout.tsx` — logo a aba
   Atribuído sempre existe e renderiza para quem vê o link. GUEST não vê "Seu trabalho".
5. **`user-menu.tsx` (`SidebarUserMenu`) é código morto** (não é importado em lugar nenhum; o link
   real é o item pessoal `your_work` montado por `SidebarItemBase`). Não foi alterado.

## Arquivos modificados

**Backend**

- `apps/api/plane/app/views/workspace/user_preference.py`
  - `WorkspaceUserPreferenceViewSet.patch`: filtro passa a incluir `user=request.user`.

**Frontend**

- `apps/web/core/components/workspace/sidebar/sidebar-item.tsx` (`SidebarItemBase`)
  - Novo `linkHref` (= `joinUrlPath(itemHref, "assigned")` para `your_work`) usado no `<Link>`;
    `isActive`/`highlight` continuam usando `itemHref` (base do perfil).
- `apps/web/ce/components/workspace/sidebar/extended-sidebar-item.tsx` (painel "Mais")
  - Novo `linkHref` (= `${itemHref}/assigned` para `your_work`) usado no `<Link>`, por consistência.

**Docs**

- `mods/menu-pin-persistencia-e-seu-trabalho-atribuido.md` (este arquivo) + linha em `mods.md`.

## Como testar

**Bug do pin (precisa de workspace com >1 usuário para reproduzir o comportamento antigo):**

1. No menu "Espaço de trabalho", pinar **Visualizações** (ou Análises/Arquivos).
2. Recarregar a página → o item **permanece** visível na sidebar.
3. Despinar → recarregar → item some. (Antes da correção, o pin sumia no refresh.)

**Smoke back-end** (sem credenciais; `docker compose exec -T api python manage.py shell`, via
heredoc — **não** usar `python -c`): após o PATCH, conferir que a linha de
`WorkspaceUserPreference` do **usuário logado** para aquele `key` está com `is_pinned=True`
(e não a de outro usuário).

**"Seu trabalho":**

1. Clicar em "Seu trabalho" na sidebar → cai em `/profile/{userId}/assigned/` com a aba
   **Atribuído** ativa.
2. Clicar na aba **Resumo** → abre `/profile/{userId}/` normalmente.
3. Em qualquer aba do perfil, o item "Seu trabalho" da sidebar continua destacado (highlight).

**Verificação geral:**

- `pnpm check` (format + lint + types) no front.
- `ruff` em `apps/api` para o back-end.

## Deploy (CT 105)

Após merge em `main`: `git pull` no `/opt/plane`, então
`docker compose build api web && docker compose up -d api web`. **Sem migração**. `worker`/
`beat-worker` **não** precisam ser reconstruídos (a mudança é em view, não em task Celery).

## Pitfalls / fora do escopo

- A correção do PATCH depende de a linha de preferência do usuário já existir — o `get` a cria no
  primeiro load (com defaults), o que o `workspace-wrapper.tsx` dispara via SWR antes de o usuário
  conseguir pinar. Não foi adicionado `update_or_create` para manter a correção mínima.
- Não mexemos em rotas, tabs nem no redirect de perfil — só no destino do link da sidebar. A aba
  default da URL base `/profile/{userId}/` continua sendo Resumo (intencional).
