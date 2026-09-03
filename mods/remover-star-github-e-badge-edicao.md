# Remover botão "Star us on GitHub" e badge de edição ("Community")

- **Data:** 2026-09-03
- **Autor:** Felipe (com Claude Code)
- **Branch:** `main`

## Contexto

A interface do Plane expõe dois elementos de branding do projeto open-source que não fazem sentido na instalação interna:

1. **"Star us on GitHub"** — link no topo da navegação apontando para `https://github.com/makeplane/plane`.
2. **Badge de edição** — botão no rodapé da sidebar com o texto **"Community"** e tooltip `Version: v<versão do package.json>`, que ao ser clicado abria o modal de upgrade de plano pago.

Ambos revelam para os usuários finais que o sistema é um Plane Community e qual versão está rodando. A decisão foi remover os dois da UI.

## Decisões de design

- **Remoção apenas nos pontos de renderização**, não dos componentes em si. `StarUsOnGitHubLink` (`app/(all)/[workspaceSlug]/(projects)/star-us-link.tsx`) e `WorkspaceEditionBadge` (`ce/components/workspace/edition-badge.tsx`) continuam existindo, sem nenhum uso. Isso mantém o diff mínimo em relação ao upstream e facilita futuros merges/rebases — se o upstream mexer nesses arquivos, não há conflito.
- **O rodapé inteiro da sidebar foi removido**, não só o badge. A `<div>` de rodapé (`h-12` com `border-t`) existia exclusivamente para hospedar o badge; mantê-la deixaria uma faixa vazia com borda no pé da sidebar. O bloco comentado `{/* TODO: To be checked if we need this */}` que vinha junto (HelpMenu / AppSidebarToggleButton) também saiu, já que era código morto do upstream dentro dessa mesma div.
- **O modal de plano pago (`PaidPlanUpgradeModal`) deixou de ter gatilho na sidebar** — era acionado só pelo badge. Não foi movido para outro lugar (comportamento desejado).
- A entrada "Community" na tela de **billing** (`ce/components/workspace/billing/root.tsx`) foi mantida: é uma tela de configurações administrativas, não algo exposto no dia a dia.

## Arquivos modificados

- `apps/web/ce/components/navigations/top-navigation-root.tsx` — removidos o import e o uso de `<StarUsOnGitHubLink />` da barra de ações do topo.
- `apps/web/core/components/sidebar/sidebar-wrapper.tsx` — removidos o import de `WorkspaceEditionBadge` e o bloco de rodapé completo que o renderizava.

## Como testar

1. `pnpm dev` (ou acessar o deploy) e abrir qualquer workspace.
2. Na barra superior, ao lado do menu de ajuda, **não deve mais existir** o botão com o logo do GitHub / "Star us on GitHub".
3. No pé da sidebar de navegação, **não deve mais existir** o botão "Community" nem a borda superior do rodapé — a lista de navegação vai até o fim do painel.
4. Verificar que nada mais aciona o modal de upgrade a partir da sidebar.

## Pitfalls

- Os componentes órfãos podem ser sinalizados por lint de "unused export" no futuro; hoje o oxlint do projeto não reclama.
- Se o upstream passar a renderizar `WorkspaceEditionBadge` em outro lugar (ex.: novo header), a remoção precisará ser reaplicada no novo ponto — vale um `grep -rn "WorkspaceEditionBadge\|StarUsOnGitHubLink"` após cada merge do upstream.
