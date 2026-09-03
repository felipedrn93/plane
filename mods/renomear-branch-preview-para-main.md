# Renomear a branch padrão do fork: `preview` → `main`

**Data:** 2026-09-03
**Autor:** Felipe
**Branch:** main
**Plano:** —

## Contexto

O fork nasceu de `upstream/preview` e manteve o nome da branch de pré-release do Plane. Como este repositório é a linha principal do fork (e não um canal de pré-release do upstream), o nome `preview` era confuso: a branch de trabalho, a branch de deploy do CT 105 e a base de todo PR eram a mesma coisa — a "main" do fork. Renomeada para `main`.

## Decisões de design

- **Rename, não branch nova.** `git branch -m preview main` preserva o histórico e os SHAs; a branch é a mesma, só o nome mudou. Por isso os cabeçalhos `**Branch:**` dos mods antigos foram atualizados para `main` (os commits deles vivem em `main` hoje).
- **`origin/preview` foi deletada** e o default branch do GitHub (`felipedrn93/plane`) apontado para `main`, para não deixar duas referências vivas divergindo.
- **`upstream/preview` e `upstream/master` não foram tocados.** PRs para o upstream continuam mirando `preview` lá.
- **Workflows do GitHub Actions** que disparavam em PR/push para `preview` foram repontados para `main`; sem isso, CI (lint, copyright, i18n, CodeQL, build-branch) simplesmente pararia de rodar.
- **Registros históricos** em memórias e specs ganharam a anotação "à época `preview`" em vez de serem reescritos, para não falsear a linha do tempo.

## Arquivos criados

- `mods/renomear-branch-preview-para-main.md` (este arquivo)

## Arquivos modificados

- `.github/workflows/build-branch.yml` — push trigger `preview` → `main` e, na sequência, removido: o workflow publica imagens no DockerHub da makeplane e falha no `docker login` por falta de credenciais no fork. Sobrou só `workflow_dispatch`
- `.github/workflows/codeql.yml` — push/PR triggers `["preview", "canary", "master"]` → `["main", "canary", "master"]`
- `.github/workflows/copyright-check.yml` — PR base `preview` → `main`
- `.github/workflows/i18n-sync-check.yml` — PR base e push trigger `preview` → `main`
- `.github/workflows/pull-request-build-lint-api.yml` — PR base `preview` → `main`
- `.github/workflows/pull-request-build-lint-web-apps.yml` — PR base `preview` → `main`
- `.claude/skills/pr-description.md` — base padrão de feature PRs → `main`
- `CLAUDE.md` (gitignored, local) — branch padrão e procedimento de redeploy do CT 105
- `mods/*.md` — cabeçalhos `**Branch:** preview` → `main`; instrução de redeploy em `mods/menu-pin-persistencia-e-seu-trabalho-atribuido.md`
- `docs/superpowers/specs/2026-05-27-spreadsheet-column-reordering-design.md` — cabeçalho de autor
- Memórias do usuário (`ct-105-plane-install`, `plane-fork-bugs`, `MEMORY.md`)

Fora do escopo deste commit (feito direto no GitHub / no CT 105):

- Default branch do repositório alterada via `gh repo edit felipedrn93/plane --default-branch main`
- `origin/preview` deletada; `origin/HEAD` repontado para `origin/main`

## Como testar

```bash
git branch -a                      # main local, remotes/origin/main, HEAD -> origin/main
gh repo view felipedrn93/plane --json defaultBranchRef -q .defaultBranchRef.name   # main
grep -rn "preview" .github/workflows/   # só sobra 'feature-preview'/'base_tag_name', que são tags Docker
```

CI: abrir um PR de teste contra `main` e confirmar que copyright-check, i18n-sync-check e os dois build-lint disparam.

## Pitfalls

- **CT 105 quebra até ser ajustado.** `/opt/plane` é um clone **shallow single-branch**: `remote.origin.fetch` era `+refs/heads/preview:refs/remotes/origin/preview`, então `git fetch` falha com `fatal: couldn't find remote ref refs/heads/preview` — não basta renomear a branch local, é preciso reescrever o refspec. Receita aplicada (2026-09-03):
  ```bash
  cd /opt/plane
  git config remote.origin.fetch "+refs/heads/main:refs/remotes/origin/main"
  git fetch origin
  git branch -m preview main
  git branch -u origin/main main
  git update-ref -d refs/remotes/origin/preview
  git merge --ff-only origin/main
  ```
  Sem rebuild: o commit só toca docs/CI. Containers seguiram de pé (`curl http://127.0.0.1:8080/api/instances/` → 200).
- **Clones/worktrees locais antigos** precisam do mesmo tratamento (`git fetch origin --prune` + rename local).
- **Não confundir com `upstream/preview`**: ao abrir PR para o upstream, a base continua sendo `preview` lá.
- Referências a "preview" na UI (`preview-card`, hover preview, `feature-preview` Helm/Docker) não têm relação com a branch — não mexer.
