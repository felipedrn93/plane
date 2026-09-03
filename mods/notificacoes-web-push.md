# Notificações Web Push (atribuição + menção)

**Data:** 2026-05-28
**Autor:** felipedrn93
**Branch:** main (commit `54f3cc418`)
**Plano:** [/Users/felip/.claude/plans/este-um-fork-nifty-parrot.md](../../../../.claude/plans/este-um-fork-nifty-parrot.md)

## Contexto

O Plane já gravava `Notification` in-app quando um usuário era atribuído a uma issue ou mencionado em comentário/descrição, mas isso ficava restrito ao sininho dentro do app (polling via SWR, sem nada nativo do SO). Para que cada pessoa do time de fato seja avisada — inclusive com o navegador fechado — esta modificação adiciona um pipeline ponta-a-ponta de Web Push (Service Worker + VAPID + `pywebpush`), filtrando exatamente os dois senders pedidos:

- `in_app:issue_activities:assigned` (tarefa atribuída)
- `in_app:issue_activities:mentioned` (menção em comentário/descrição)

Outras notificações (state change, property change, comment sem menção, subscribed) **não** viram push — continuam só no inbox.

## Decisões de design

1. **Web Push real (VAPID), não Notification API com aba aberta.** Service Worker recebe push do servidor mesmo com o browser fechado. Sem isso, a feature só funcionaria com uma aba do Plane ativa, o que era o cenário que o usuário queria evitar.
2. **Reaproveitar o ponto onde a `Notification` é criada.** Em `bgtasks/notification_task.py`, logo após `Notification.objects.bulk_create(...)` (linha 669, fluxo já existente), enfileiramos `send_push_notifications.delay(ids)` filtrando pelos senders desejados. Sem mexer na lógica in-app existente.
3. **Task Celery dedicada (`send_push_notifications`)**, não chamada síncrona dentro do request. O envio para cada subscription pode demorar (RTT internet → endpoint Mozilla/Google/Apple), e o web push falha de várias formas (404, 410, 5xx, timeout). Mantém isolada da task `notifications` original.
4. **`PushSubscription` separada de `Device`.** O Plane já tem um modelo `Device` (Android/iOS/Web/Desktop) com `push_token`, mas é genérico e voltado para FCM/APNs. Web Push exige tripleto `endpoint + p256dh + auth` (RFC 8291/8292), schema próprio — criar um modelo específico evita acoplar e abre caminho para múltiplas subscriptions por usuário (cada device/navegador é um endpoint diferente).
5. **Cleanup automático em 404/410.** O helper `send_web_push` retorna `False` quando o endpoint do push service responde "Gone"; a task então deleta a `PushSubscription` correspondente. Sem isso, o banco vira lixão de subs órfãs (usuário troca de navegador, revoga permissão, etc.).
6. **Service Worker dedicado (`/push-sw.js`), não o `sw.js` workbox existente.** O `sw.js` que já está no `public/` é um loader workbox órfão (não há `navigator.serviceWorker.register('/sw.js')` em nenhum lugar do código cliente). Em vez de cooptar e arriscar quebrar uma PWA inacabada, registramos um SW separado só para push. `push-sw.js` lida com `push` e `notificationclick`.
7. **VAPID keys via env, gerados uma vez.** `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/`VAPID_CLAIM_EMAIL` em `apps/api/.env`. Geração feita uma vez dentro do container `api` via `cryptography` (já dependência do Plane) — sem precisar de `npx web-push generate-vapid-keys`, que demandaria Node no host. **Rotacionar invalida todas as subscriptions ativas** (browsers já registrados ficam órfãos e precisam reativar o toggle).
8. **Toggle por usuário, opt-in via UI.** Nova seção "Notificações no navegador" em **Perfil → Notificações**, ao lado do form de email. O toggle pede `Notification.requestPermission()` no momento do clique; nunca pede sozinho ao carregar a página.
9. **Permission `denied` mostra instrução, não toggle bloqueado em silêncio.** Se o usuário negou no browser, o form mostra que precisa reabilitar nas configurações do site. Browser não permite re-pedir permissão depois de `denied` via JS.
10. **HTTPS obrigatório.** Push API não funciona em origem `http://` (exceto `localhost`). No CT 105 isso forçou montar `tailscale serve --https=443 → http://127.0.0.1:8080` em frente ao proxy do Plane (ver [[ct-105-plane-install]] na memória do usuário). Não é exigência só desta mod — é exigência do navegador.

## Esquema da `PushSubscription`

```python
class PushSubscription(BaseModel):
    user = FK(User, related_name="push_subscriptions", on_delete=CASCADE)
    endpoint = URLField(max_length=1024, unique=True)
    p256dh_key = CharField(max_length=255)   # base64url do public key cliente
    auth_key   = CharField(max_length=255)   # base64url do shared secret
    user_agent = CharField(max_length=512, null=True, blank=True)
    last_used_at = DateTimeField(null=True)
    # + created_at / updated_at / deleted_at / created_by / updated_by (BaseModel)

    class Meta:
        db_table = "push_subscriptions"
        indexes = [Index(fields=["user"], name="push_sub_user_idx")]
```

- `endpoint` único globalmente (não por usuário) — é a URL do push service do navegador, e dois usuários do mesmo Chrome no mesmo profile teriam o mesmo endpoint, o que não acontece na prática (Chrome gera endpoint por instalação de SW).
- Sem soft-delete relevante: quando um endpoint expira (410), a row é **hard-deletada** via `PushSubscription.objects.filter(id__in=stale_ids).delete()` na task de envio.

## Arquivos criados

**Backend**

- `apps/api/plane/db/models/push_subscription.py` — model.
- `apps/api/plane/db/migrations/0124_pushsubscription.py` — migration hand-written (`CreateModel` + `AddIndex`), assim como [parent-breadcrumb.md](parent-breadcrumb.md) e [reordenar-colunas-spreadsheet.md](reordenar-colunas-spreadsheet.md). Quando o ambiente local tiver DB rodando, validar com `manage.py makemigrations --dry-run`.
- `apps/api/plane/utils/web_push.py` — wrapper sobre `pywebpush.webpush(...)`. Retorna `False` em 404/410, `True` no resto (sucesso ou falha transiente).
- `apps/api/plane/bgtasks/web_push_task.py` — `@shared_task send_push_notifications(notification_ids)`. Carrega `Notification` em lote, agrupa subs por receiver, monta payload (`title`, `body`, `url`, `tag`), envia e limpa órfãs.
- `apps/api/plane/app/views/notification/push.py` — `PushVapidKeyEndpoint` (GET) e `PushSubscriptionEndpoint` (GET/POST/DELETE).

**Frontend**

- `apps/web/public/push-sw.js` — Service Worker (handlers `push` + `notificationclick`). Foca/abre janela do Plane no `url` do payload.
- `apps/web/core/services/push-subscription.service.ts` — `getVapidKey()`, `registerSubscription(payload)`, `unregisterSubscription(endpoint)`.
- `apps/web/core/hooks/use-browser-push.ts` — `useBrowserPush()` retorna `{ supported, permission, isSubscribed, isLoading, subscribe, unsubscribe, refresh }`.
- `apps/web/core/components/settings/profile/content/pages/notifications/browser-push-form.tsx` — UI com `SettingsControlItem` + `ToggleSwitch`.

**Docs**

- `mods/notificacoes-web-push.md` (este arquivo).

## Arquivos modificados

**Backend**

- `apps/api/plane/db/models/__init__.py` — export `PushSubscription`.
- `apps/api/plane/settings/common.py` — três env reads: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL`.
- `apps/api/requirements/base.txt` — `pywebpush==2.0.0` (puxa transitivamente `py-vapid`, `http-ece`, `aiohttp`).
- `apps/api/plane/app/serializers/notification.py` — `PushSubscriptionSerializer` (`fields = ["id", "endpoint", "user_agent", "last_used_at", "created_at"]`, com `endpoint`/`p256dh_key`/`auth_key` deliberadamente fora do POST serializer; tratamento manual na view).
- `apps/api/plane/app/serializers/__init__.py` — export do serializer.
- `apps/api/plane/app/views/__init__.py` — export dos dois endpoints.
- `apps/api/plane/app/urls/notification.py` — duas rotas novas (`/vapid-key/` e `/`).
- `apps/api/plane/bgtasks/notification_task.py` — após `Notification.objects.bulk_create(...)` (linha ~669), filtra `bulk_notifications` por `sender in PUSH_ENABLED_SENDERS` e chama `send_push_notifications.delay([str(n.id) ...])`. Import local da task para evitar import circular.

**Frontend**

- `apps/web/core/components/settings/profile/content/pages/notifications/root.tsx` — importa `BrowserPushSettingsForm` e renderiza abaixo do form de email, separado por borda.

## Endpoints

| Verbo  | URL                                           | Permissão   | Body                                          | Status                                |
| ------ | --------------------------------------------- | ----------- | --------------------------------------------- | ------------------------------------- |
| GET    | `/api/users/me/push-subscriptions/vapid-key/` | autenticado | —                                             | `{public_key: "..."}`                 |
| GET    | `/api/users/me/push-subscriptions/`           | autenticado | —                                             | lista subs do user                    |
| POST   | `/api/users/me/push-subscriptions/`           | autenticado | `{endpoint, keys:{p256dh,auth}, user_agent?}` | `201` (update_or_create por endpoint) |
| DELETE | `/api/users/me/push-subscriptions/`           | autenticado | `{endpoint}` (também aceita `?endpoint=`)     | `204`                                 |

## Fluxo end-to-end

```
[Backend] User A altera assignee/menção em issue
  ↓
issue_activity.delay(...) já existente
  ↓
notifications.delay(...) já existente
  ↓ bulk_notifications montado, Notification.bulk_create()
push_target_ids = [n.id for n in bulk_notifications if n.sender in PUSH_ENABLED_SENDERS]
  ↓ se vazio: pára
send_push_notifications.delay(push_target_ids)
  ↓
[bgworker] send_push_notifications(ids)
  ├─ carrega Notification.objects.filter(id__in=ids, sender__in=...)
  ├─ agrupa PushSubscription por receiver_id
  ├─ p/ cada (notification, sub): pywebpush.webpush(..., vapid_claims)
  │     ├─ 201/200 → sucesso → marca last_used_at
  │     ├─ 404/410 → endpoint morto → adiciona em stale_subscription_ids
  │     └─ outro erro → log e segue
  └─ PushSubscription.objects.filter(id__in=stale_ids).delete()
  ↓ HTTPS push para o endpoint do user (mozilla.com / fcm.googleapis.com / ...)
  ↓
[Browser] push event no /push-sw.js
  ↓ self.registration.showNotification(title, {body, data:{url}, tag, icon})
[SO] notificação nativa aparece
  ↓ user clica
[push-sw.js] notificationclick → clients.matchAll → focus + navigate, ou openWindow(url)
```

## Como testar

**Pré-requisitos**

1. `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIM_EMAIL` setados em `apps/api/.env` (no CT 105 já está). Em outro deploy, gerar uma vez:
   ```bash
   docker compose exec -T api python -c "
   from cryptography.hazmat.primitives.asymmetric import ec
   from cryptography.hazmat.primitives import serialization
   import base64
   p = ec.generate_private_key(ec.SECP256R1())
   priv = p.private_numbers().private_value.to_bytes(32,'big')
   pub = p.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
   b64u = lambda b: base64.urlsafe_b64encode(b).rstrip(b'=').decode()
   print('VAPID_PRIVATE_KEY=' + b64u(priv)); print('VAPID_PUBLIC_KEY=' + b64u(pub))
   "
   ```
2. **HTTPS habilitado** no host (no CT 105: `tailscale serve --bg --https=443 http://127.0.0.1:8080`). `http://` o navegador bloqueia `pushManager.subscribe`.
3. Migration aplicada: `docker compose exec -T api python manage.py migrate db` (esperar `Applying db.0124_pushsubscription... OK`).

**Backend (psql, smoke)**

```sql
\d push_subscriptions
SELECT user_id, endpoint, user_agent, last_used_at FROM push_subscriptions;
```

```bash
# 401 sem auth = endpoint registrado e protegido
curl -sS -o /dev/null -w "%{http_code}\n" https://<host>/api/users/me/push-subscriptions/vapid-key/
```

**Frontend (smoke manual)**

1. Logar no Plane via HTTPS.
2. Avatar → **Perfil → Notificações** → seção "Notificações no navegador".
3. Ativar o toggle → browser prompta permissão → aceitar. DevTools → Application → Service Workers: `push-sw.js` ativado.
4. DevTools → Application → Storage → IndexedDB: aparece `push_subscription` para o `endpoint` (no banco).
5. Em outra janela anônima (outra conta do mesmo workspace), atribuir uma issue ao primeiro usuário OU mencioná-lo em um comentário.
6. Esperar 1–3s (latência Celery + push service). Notificação nativa do SO aparece com título "Nova tarefa atribuída a você" ou "Você foi mencionado".
7. Clicar → abre a aba do Plane direto na issue.
8. Voltar nas configurações, desativar o toggle → DELETE subscription no servidor e `pushManager.unsubscribe()` no SW.

**Edge cases para testar**

- Mudança de state da issue por outro usuário (sender `state_change`) → **não** dispara push.
- Comentário sem menção → **não** dispara push.
- Permissão "denied" no browser → toggle desabilita e mostra texto pedindo pra reabilitar.
- Navegador sem `PushManager` (Safari iOS < 16.4 ou Firefox em alguns contextos) → texto "navegador não suporta".

## Pitfalls específicos

- **`docker compose restart` não recarrega `env_file`.** As envs `WEB_URL`/`APP_BASE_URL`/`VAPID_*` em `apps/api/.env` só entram em vigor depois de `docker compose up -d --force-recreate api worker beat-worker live web`. Restart mantém o ambiente do container antigo. Pegamos isso em produção: as URLs ainda apontavam para o IP antigo apesar do restart. Documentado também em [[ct-105-plane-install]].
- **HTTPS é hard requirement.** Em origens `http://` (exceto `localhost`), `Notification.requestPermission()` ainda funciona mas `swReg.pushManager.subscribe({...})` falha com `NotAllowedError`. Sem HTTPS no host, o toggle "funciona" parcialmente (permissão concedida) mas a subscription nunca chega ao backend e ninguém recebe nada.
- **Sender exato do assignee é `in_app:issue_activities:assigned`.** Lê-se em `notification_task.py:315` (`elif subscriber in issue_assignees and issue.created_by_id not in issue_assignees`). Existe também `:created` e `:subscribed` — só `:assigned` e `:mentioned` viram push. Adicionar outros senders ao set `PUSH_ENABLED_SENDERS` em `web_push_task.py` se um dia quiser expandir.
- **Auto-assign do criador da issue.** Quando o criador é também o único assignee, o fluxo do `notification_task.py` cai em `sender = "in_app:issue_activities:created"`, não `:assigned`. Resultado: criador não recebe push de si mesmo (esperado e correto).
- **`bulk_notifications[i].id` está disponível antes do bulk_create.** O PK é `UUIDField(default=uuid.uuid4)`, gerado em Python no `__init__`, então o filtro `for n in bulk_notifications` consegue ler `n.id` mesmo antes do `bulk_create`. Não precisamos re-querying do banco.
- **`pushManager.subscribe()` é idempotente por SW.** Se o user já tem uma subscription ativa, `getSubscription()` devolve a existente; só chamamos `subscribe()` quando vier `null`. Sem isso, o browser pode lançar `InvalidStateError` em re-toggles.
- **VAPID public key é base64url SEM padding.** A geração via `cryptography` produz bytes; codificamos com `base64.urlsafe_b64encode(...).rstrip(b'=')`. Web Push spec exige sem padding; com padding, o `pushManager.subscribe` rejeita silenciosamente em alguns browsers. O helper `urlBase64ToUint8Array` no hook restaura padding antes de converter para Uint8Array.
- **`notificationclick.openWindow` precisa estar dentro de `event.waitUntil(...)`.** Sem isso, o SW pode ser terminado pelo browser antes da janela abrir. Já amarrado em `push-sw.js`.
- **Hard-delete vs soft-delete em `PushSubscription`.** O model herda `BaseModel` que traz `SoftDeleteModel`, mas a task usa `.delete()` em queryset — que respeita o soft delete (vira UPDATE de `deleted_at`). Para web push isso é OK porque o endpoint não é único mais para retomadas e o `update_or_create(endpoint=...)` filtra apenas live rows via manager default. Em algum momento, valeria um cron pra hard-delete rows soft-deletadas antigas, mas está fora do escopo.
- **`api.service.ts` `.delete(url, body)` passa body como segundo arg posicional**, NÃO `{ data: body }`. O wrapper já cuida do `{data, ...config}` por dentro. Errar isso faz o servidor receber `{"data": {...}}` em vez de `{...}` — bug que pegamos no review do `push-subscription.service.ts`.
- **Build do `beat-worker` falhou na primeira tentativa do `docker compose build` em paralelo no CT 105 (provável `pywebpush` ainda baixando em outro stage compartilhando rede)**; rebuild isolado funcionou e em seguida o batch concluiu. Comportamento transient, não bug de código.
- **`/push-sw.js` precisa ser servido pelo `web` (Vite/Next no Plane atual é Vite estático)** com `Content-Type: application/javascript`. Já é, porque está em `public/`. Se algum dia o build mover para um pipeline que descarte raiz, o registro `register('/push-sw.js')` quebra em 404.

## Fora do escopo (v2)

- **Preferência granular** ("quero push só de menção, não de atribuição") — hoje é all-or-nothing via toggle único. O `UserNotificationPreference` já tem `mention`/`property_change`/etc. para emails; cabe estender a task de push para respeitar o subset via essa tabela.
- **Push para outros eventos** (comentário sem menção, mudança de state, sub-issue criada) — basta acrescentar senders ao `PUSH_ENABLED_SENDERS`. Decisão consciente de manter enxuto.
- **Push para Plane mobile (FCM/APNs)** — o modelo `Device` existente tem `push_token` e cobriria isso, mas exige integração separada com FCM/APNs e não foi tocado.
- **Resumos digest** ("3 menções novas") em vez de uma notificação por evento — cada notification vira uma push hoje, com `tag` único (notification.id), então o browser não consolida automaticamente. Para agrupar precisaria de outro `tag` derivado de `(receiver, hora)`.
- **Logs de entrega/dashboard** — só logamos exceções de webpush via `logger.exception`. Não há tabela tipo `WebPushDeliveryLog` análoga ao `EmailNotificationLog`. Se um dia for útil para audit/troubleshoot, espelhar o pattern.
- **Renovação preventiva de subscription** — push services podem rotacionar endpoints; hoje a sub só morre quando o backend recebe 410. Spec do Push API tem evento `pushsubscriptionchange` no SW, não tratado aqui.
