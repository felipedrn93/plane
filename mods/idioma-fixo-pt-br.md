# Idioma fixo em português + sync check de i18n só exigido para pt-BR

**Data:** 2026-09-03
**Autor:** Felipe
**Branch:** main
**Plano:** —

## Contexto

Este fork roda numa instância interna, usada por um time que trabalha só em português. O upstream, porém, atende 19 idiomas, e trouxe junto duas consequências indesejadas:

1. **O seletor de idioma** deixava qualquer pessoa mudar a interface para japonês, alemão etc. — inclusive sem querer. Pior: os textos das mods deste fork (tarefas recorrentes, caminho do pai, filtro de finalização/bloqueio) só existem em `en` e `pt-BR`, então nesses idiomas a UI ficava meio traduzida.
2. **O CI reprovava todo PR.** O workflow `i18n sync check` exige que os 19 locales estejam 100% sincronizados com `en`; as 48 chaves criadas pelas mods nunca foram traduzidas para os outros 17 idiomas. Isso passou despercebido por meses porque o GitHub desativa os workflows automáticos em forks — só apareceu quando o Actions foi habilitado (ver [mods/renomear-branch-preview-para-main.md](renomear-branch-preview-para-main.md)).

## Decisões de design

- **`SUPPORTED_LANGUAGES` reduzido a `pt-BR`, em vez de remover o seletor da UI.** A constante alimenta os dois seletores (perfil e Power-K) _e_ o `supportedLngs` do i18next, então uma edição resolve os três lugares. Reativar idiomas volta a ser uma linha.
- **Os 18 diretórios de locale continuam em `src/locales/`.** Apagá-los geraria conflito em todo merge com o upstream, e o ganho seria só cosmético.
- **`resolveLanguage()` como ponto único de coerção.** Um idioma pode chegar de três origens: `localStorage`, o perfil vindo do backend, e a chamada direta de `changeLanguage`. O perfil sobrescreve o `localStorage` no login (`profile.store.ts`), então tratar só o `localStorage` deixaria usuários antigos presos no inglês. As três origens passam pela mesma função.
- **Migração de dados, não só troca de `default`.** Trocar o `default` do campo só afeta perfis novos. A `RunPython` converte os existentes.
- **O sync check continua relatando os outros locales, só não reprova.** `ENFORCED_LOCALES = ["pt-BR"]`; `null` restaura o comportamento do upstream. A intenção é não _esconder_ o gap — ele fica visível no log caso um dia se queira contribuir de volta.

## Arquivos criados

- `apps/api/plane/db/migrations/0126_profile_language_pt_br.py` — `AlterField` do default + `RunPython` convertendo os perfis existentes para `pt-BR`

## Arquivos modificados

- `packages/i18n/src/constants/language.ts` — `FALLBACK_LANGUAGE` → `pt-BR`; `SUPPORTED_LANGUAGES` reduzido a um item; nova função `resolveLanguage()`
- `packages/i18n/src/core/instance.ts` — o idioma inicial passa por `resolveLanguage()` e o `localStorage` é reescrito quando o valor salvo não é mais válido
- `packages/i18n/src/core/set-language.ts` — coage o idioma recebido (é por aqui que o perfil do backend entra)
- `packages/i18n/src/hooks/use-translation.ts` — mesma coerção em `changeLanguage`
- `packages/i18n/src/index.ts` — exporta `resolveLanguage`
- `packages/i18n/scripts/sync-check.ts` — `ENFORCED_LOCALES`; locales não exigidos aparecem com `·` e a nota "(nao exigido neste fork)", e o detalhamento de chaves faltantes fica restrito aos exigidos
- `apps/api/plane/db/models/user.py` — `Profile.language` default `en` → `pt-BR`

## Como testar

```bash
# 1. o CI de i18n passa
pnpm --filter @plane/i18n run check:sync        # exit 0, "Locales exigidos (pt-BR) ..."

# 2. nao introduz erro de tipo
pnpm --filter @plane/i18n run check:types
pnpm turbo run check:types --filter=web         # os 2 erros restantes sao pre-existentes,
                                                # ver secao Pitfalls
```

Na UI, após o deploy:

- Perfil → Preferências: o select de idioma mostra só "Português Brasil".
- Num navegador que já tinha outro idioma salvo: abrir o sistema deve cair em português sozinho (o `localStorage` é reescrito no boot).
- Usuário criado antes da migração: fazer login e confirmar que continua em português (é o caso que a `RunPython` cobre).

No backend:

```bash
docker compose exec api python manage.py migrate     # aplica a 0126
docker compose exec -T api python manage.py shell <<'EOF'
from plane.db.models import Profile
print(Profile.objects.exclude(language="pt-BR").count())   # esperado: 0
EOF
```

## Pitfalls

- **A migração é destrutiva para a preferência individual.** Ela sobrescreve o idioma de todos os perfis; o `backward` não restaura os valores antigos (eles se perdem). Aceitável porque o fork só oferece pt-BR, mas não reverta esperando recuperar as escolhas.
- **`pnpm --filter @plane/i18n run check:format` acusa ~548 arquivos no checkout Windows.** É artefato de CRLF (`core.autocrlf`), não formatação de verdade — o CI usa LF e não reclama. **Não** rode `fix:format` para "resolver": ele reescreveria o pacote inteiro. O hook de pre-commit já normaliza os arquivos que você tocou.
- **Os dois erros de tipo e o `check:format` do `web`** que apareceram junto com esta mod foram corrigidos em commit separado — ver [mods/divida-ci-web.md](divida-ci-web.md). Não tinham relação com o i18n.
- **Fora de escopo:** o e-mail transacional e os textos gerados pelo backend não passam por este i18n; continuam como estavam.
