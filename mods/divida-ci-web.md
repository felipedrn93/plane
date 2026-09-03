# Dívida de CI do `apps/web` acumulada com o Actions desligado

**Data:** 2026-09-03
**Autor:** Felipe
**Branch:** main
**Plano:** —

## Contexto

O GitHub desativa os workflows automáticos em forks até o dono habilitá-los na aba Actions. Neste fork isso só foi feito em 2026-09-03, durante a validação do rename da branch ([mods/renomear-branch-preview-para-main.md](renomear-branch-preview-para-main.md)) — o repositório tinha **uma única execução automática em toda a sua existência**, e ela era do Dependabot.

Ou seja: nenhuma mod deste fork jamais passou por `check:types` ou `check:format`. Quando o CI finalmente rodou, o job `Build and lint web apps` reprovou em dois dos quatro sub-jobs, com erros acumulados de três mods diferentes.

Nada disso quebrava o sistema em execução — são erros de *tipagem* e de *formatação*, invisíveis em runtime. Mas deixavam todo PR vermelho.

## Decisões de design

- **Corrigir a tipagem no ponto certo, não silenciar.** Os dois erros apontavam para campos que existem de verdade (no `TIssue` e no modelo `IssueView` do backend) e que só não tinham sido declarados no TypeScript. A correção é declarar, não `as any`.
- **`display_properties_order` opcional em `IWorkspaceView`.** Views criadas antes da migração que adicionou o campo não o trazem no payload; obrigar levaria a `undefined` em runtime sob um tipo que promete `string[]`.
- **Formatação aplicada com `oxfmt` nos 13 arquivos apontados pelo CI**, sem tocar em mais nada. O diff é só quebra de linha.
- **`Branch Build CE` perdeu o gatilho de push.** Ele publica imagens no DockerHub da makeplane e falha no `docker login` — o fork não tem essas credenciais, e o CT 105 compila do código-fonte. O workflow foi mantido em `workflow_dispatch` (com o bloco `push` comentado) em vez de deletado, para o caso de um dia existir um registry próprio.

## Arquivos criados

- `mods/divida-ci-web.md` (este arquivo)

## Arquivos modificados

- `apps/web/core/store/issue/helpers/base-issues.store.ts` — `ISSUE_ORDERBY_KEY` ganhou `completed_at` e `-completed_at`. O `Record<TIssueOrderByOptions, keyof TIssue>` exige uma entrada por opção de ordenação, e a mod de filtro por data de finalização acrescentou as duas opções sem mapeá-las.
- `packages/types/src/workspace-views.ts` — `IWorkspaceView.display_properties_order?: string[]`, campo que a mod de reordenar colunas passou a ler em `workspace/filter.store.ts:199`.
- 13 arquivos do `apps/web` reformatados com `oxfmt` (componentes de recorrência, breadcrumb do pai, spreadsheet DnD, push notifications, busca inline e três `filter.store.ts`).
- `.github/workflows/build-branch.yml` — gatilho `push` removido.

## Como testar

```bash
pnpm turbo run check:types --filter=web     # 11 successful, 11 total
cd apps/web && pnpm exec oxfmt --check .    # sem "Format issues found"
```

No CI: o job `Build and lint web apps` do PR deve ficar verde nos quatro sub-jobs (`Build packages`, `check:lint`, `check:format`, `check:types`).

## Pitfalls

- **`oxfmt --check` acusa centenas de arquivos num checkout Windows.** É artefato de CRLF (`core.autocrlf`), não formatação de verdade. Rode a verificação por arquivo (ou confie no CI, que usa LF) e **nunca** rode `fix:format` no pacote inteiro nessa máquina — reescreveria tudo.
- **`git status` mostra `packages/*/package.json` modificados sem diff nenhum** pelo mesmo motivo. `git checkout --` neles antes de commitar.
- **O hook de pre-commit é mais rígido que o CI.** `lint-staged` roda `oxlint --fix --deny-warnings` nos arquivos staged, enquanto o gate real do projeto é `oxlint --max-warnings=11957` (que passa). Commitar alterações no `base-issues.store.ts` esbarra em 15 avisos pré-existentes do upstream (`no-shadow`, `no-unused-expressions`) e o `parent-breadcrumb.tsx` tem mais 3 (a11y e key por índice). Este commit foi feito com `--no-verify`, com autorização explícita: renomear variáveis sombreadas no store central de carregamento de issues é risco de regressão sem cobertura de teste, para ganho cosmético. Se voltar a acontecer, a decisão é a mesma — não é um bypass casual.
- **Não confunda com o `i18n sync check`**, que foi resolvido de outra forma (restringindo os locales exigidos) — ver [mods/idioma-fixo-pt-br.md](idioma-fixo-pt-br.md).
