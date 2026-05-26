# Limite de upload de anexos: 5 MB → 100 MB

**Data:** 2026-05-26
**Autor:** felipedrn93

## Contexto

O Plane upstream limita uploads a 5 MB (`FILE_SIZE_LIMIT=5242880`), o que era pequeno demais para os anexos típicos do nosso uso (PDFs de relatórios, planilhas, prints anotados). Subimos o default do fork para **100 MB** (`104857600` bytes) em todos os pontos onde o valor aparece — defaults de código, `.env.example`, compose files, scripts de deploy AIO e mensagem de erro do validador.

A env var `FILE_SIZE_LIMIT` continua respeitada: quem quiser sobrescrever em runtime pode definir no `.env` do compose normalmente. A mudança aqui é só do **default**.

## Por que mudar em vários lugares

O limite é aplicado em duas camadas independentes:

1. **Caddy proxy** (`apps/proxy/Caddyfile.ce` e `Caddyfile.aio.ce`): `request_body { max_size {$FILE_SIZE_LIMIT} }` — corta o request antes mesmo de chegar na API.
2. **Django/API**: validação em todas as views de upload (`asset/v2.py`, `issue/attachment.py`, `api/views/asset.py`, `api/views/issue.py`) + `DATA_UPLOAD_MAX_MEMORY_SIZE` do próprio Django + validador `file_size` dos models.

Os dois lados consomem a **mesma env**, então um único `FILE_SIZE_LIMIT` no `.env` cobre tudo — mas o **default** estava espalhado em cada compose/script/settings, e precisava ser atualizado em cada um para que uma instalação nova do fork (sem `.env` customizado) já viesse com 100 MB.

## Arquivos modificados

**Backend — defaults Python:**

- `apps/api/plane/settings/common.py`
  - `FILE_SIZE_LIMIT = int(os.environ.get("FILE_SIZE_LIMIT", 104857600))`
  - `DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("FILE_SIZE_LIMIT", 104857600))` (limite do próprio Django para tamanho de request — se ficar menor que `FILE_SIZE_LIMIT`, o Django rejeita o body antes da view rodar).
- `apps/api/plane/license/api/views/instance.py`
  - `data["file_size_limit"] = float(os.environ.get("FILE_SIZE_LIMIT", 104857600))` — valor exposto no endpoint `GET /api/instances/` que o frontend lê pra saber o limite a mostrar na UI de upload.

**Backend — mensagens de erro hardcoded:**

- `apps/api/plane/db/models/asset.py` — `ValidationError("File too large. Size should not exceed 100 MB.")`
- `apps/api/plane/db/models/issue.py` — mesma mensagem no validador do `IssueAttachment`.
- Detalhe: as duas mensagens diziam **"5 MB"** literal mesmo que o `FILE_SIZE_LIMIT` fosse outro. Continua hardcoded (não usa f-string com o valor real) — atualizei pra refletir o novo default, mas se um dia mudar de novo, lembrar de tocar esses dois arquivos.

**Compose / env de raiz e deploy:**

- `.env.example` — `FILE_SIZE_LIMIT=104857600`
- `apps/api/.env.example` — idem
- `docker-compose.yml` — `FILE_SIZE_LIMIT: ${FILE_SIZE_LIMIT:-104857600}` (serviço `proxy`, usado pelo Caddy).
- `deployments/cli/community/variables.env` — `FILE_SIZE_LIMIT=104857600`
- `deployments/cli/community/docker-compose.yml` — âncora `x-proxy-env: &proxy-env` com `${FILE_SIZE_LIMIT:-104857600}`.
- `deployments/aio/community/variables.env` — `FILE_SIZE_LIMIT=104857600`
- `deployments/aio/community/start.sh` — duas ocorrências: o `echo` da help message (`(default: 104857600)`) e o `update_env_value` que grava no `.env` final.
- `deployments/aio/community/README.md` — exemplo de `docker run` (`-e FILE_SIZE_LIMIT=104857600`) e a linha de documentação (`default: 104857600 = 100MB`).

## Como aplicar em uma instância já rodando (CT 105)

O default novo só vale para instalações novas que **não** tenham `.env` customizado. Se já existe um `.env` com `FILE_SIZE_LIMIT=5242880`, ele continua valendo. Para subir o limite numa instância existente:

```bash
# No CT 105, dentro do diretório do compose
sed -i 's/^FILE_SIZE_LIMIT=.*/FILE_SIZE_LIMIT=104857600/' .env
docker compose down
docker compose up -d
```

Precisa ser `down`/`up` (não `restart`) porque a env só é injetada no Caddy e no API na criação do container.

## Como verificar

Após aplicar:

1. `docker compose exec api env | grep FILE_SIZE_LIMIT` → deve mostrar `104857600`.
2. `curl -s http://<host>/api/instances/ | jq .file_size_limit` → deve devolver `104857600.0`.
3. Subir um arquivo de ~50 MB pela UI — deve passar. Arquivo de 150 MB deve falhar com mensagem "File too large. Size should not exceed 100 MB." (validador do model) ou ser cortado pelo Caddy (`413 Request Entity Too Large`) se for o proxy a barrar primeiro.

## Fora do escopo

- Aumentar o limite acima de 100 MB. Se precisar, é só editar a env — o ceto teórico é o que o Caddy/Django aguentam segurar em memória durante o upload, então cuidado com RAM do CT.
- Streaming/multipart resumable upload. O fluxo atual é POST direto pra S3-compat (MinIO) via signed URL, então tamanho grande de verdade pediria mudança no fluxo, não só na env.
- Mensagem de erro dinâmica (atualmente hardcoded "100 MB" no `ValidationError`). Idealmente seria f-string usando `settings.FILE_SIZE_LIMIT`, mas mantive o padrão original do upstream pra não criar diff desnecessário.
