# Painel de perfil recolhível em "Seu trabalho"

**Data:** 2026-10-19
**Autor:** felipedrn93
**Branch:** main

## Contexto

Na página de perfil / "Seu trabalho" (`/:workspaceSlug/profile/:userId/*`), o painel lateral direito (capa, avatar, fuso horário, % por projeto) ficava sempre aberto no desktop e ocupava ~300px do board. No upstream:

- o botão de alternar no header tem `md:hidden` — só existe no mobile;
- o `useEffect` do `ProfileSidebar` reabre o painel sempre que a janela tem ≥ 768px;
- `toggleProfileSidebar` grava `profile_sidebar_collapsed` no `localStorage`, mas ninguém lê esse valor.

## Decisões de design

1. **Recolhido por padrão no desktop.** Abre só se a última escolha salva for `"false"`.
2. **Botão de alternar visível também no desktop** (ícone `PanelRight` no header, destacado quando aberto).
3. **`md:hidden` quando recolhido.** No desktop o painel é `relative`, e o truque de `marginLeft: innerWidth` (que funciona no overlay `fixed` do mobile) espremeria o conteúdo principal até largura zero.
4. Mobile continua como antes: recolhe ao montar e ao redimensionar para < 768px.

## Arquivos modificados

- `apps/web/core/components/profile/sidebar.tsx` — lê o `localStorage` ao montar no desktop; para de forçar a abertura; `md:hidden` quando recolhido.
- `apps/web/app/(all)/[workspaceSlug]/(projects)/profile/[userId]/header.tsx` — remove `md:hidden` do botão de alternar.

## Como testar

1. Abrir "Seu trabalho" → Atribuído no desktop: painel fechado, board ocupando a largura toda.
2. Clicar no ícone de painel no header: o painel abre. Recarregar a página: continua aberto.
3. Fechar, recarregar: continua fechado.
4. Mobile (< 768px): painel em overlay, fecha ao clicar fora (sem mudança).

## Pitfalls

- Reduzir a janela para < 768px grava `"true"`; ao voltar para o desktop, o painel fica fechado.
