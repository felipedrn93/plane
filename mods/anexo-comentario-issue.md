# Anexo vinculado a um comentário específico da issue

**Data:** 2026-07-09
**Autor:** felipedrn93
**Branch:** preview
**Plano:** [/Users/felip/.claude/plans/atualmente-ao-anexar-um-adaptive-journal.md](../../../../.claude/plans/atualmente-ao-anexar-um-adaptive-journal.md)

## Contexto

Até então, anexar um arquivo numa issue sempre criava um anexo "solto", vinculado só à tarefa — sem forma de indicar que aquele arquivo se refere a um comentário/discussão específica. O usuário pediu que, ao anexar a partir de um comentário, o arquivo apareça **tanto** na lista geral de anexos da issue **quanto** diretamente dentro daquele comentário.

O model real por trás de anexos (`FileAsset`) já tinha um FK `comment` para `IssueComment` desde a migration upstream `0078_fileasset_comment_fileasset_entity_type_and_more`, mas esse campo só era usado para o `entity_type=COMMENT_DESCRIPTION` (imagens embutidas no corpo rich-text do comentário, via editor). O fluxo de "anexo formal" (`entity_type=ISSUE_ATTACHMENT`, o que aparece na lista de anexos) nunca setava esse FK. O `IssueAttachment` legado (FK só para `issue`) está morto — não é usado em nenhuma view/serializer atual.

## Decisões de design

1. **Reaproveitar `entity_type=ISSUE_ATTACHMENT` com `comment` opcional, em vez de criar `COMMENT_ATTACHMENT`.** O endpoint que lista anexos da issue (`IssueAttachmentV2Endpoint.get`) já filtra só por `issue_id + entity_type=ISSUE_ATTACHMENT`; ao manter o mesmo `entity_type` e apenas setar `comment_id` quando o upload parte de um comentário, a lista geral continua automaticamente completa (sem precisar de union de queries ou endpoint novo). Um `entity_type` separado exigiria ensinar `asset_url`/`get_entity_id_field`/lista geral a tratar mais um caso sem ganho real.
2. **`FileAsset.comment` trocado de `on_delete=CASCADE` para `SET_NULL`** (migration `0125_alter_fileasset_comment.py`). Com `CASCADE`, apagar um comentário apagaria em cascata qualquer anexo vinculado a ele — o oposto do comportamento pedido (o anexo deve sobreviver e continuar na lista geral, só perdendo o vínculo com o comentário que sumiu).
3. **Sem endpoint/query param novo para "anexos por comentário".** O frontend já busca todos os anexos da issue de uma vez (`fetchAttachments`); um novo seletor no store (`getAttachmentsByCommentId`) filtra client-side por `attachment.comment === commentId`, evitando mais uma superfície de API.
4. **Dois pontos de entrada no frontend**: (a) anexar ao criar um comentário novo (`CommentCreate`) — os arquivos ficam "staged" localmente e só sobem depois que o comentário é criado (o `comment_id` só existe após o POST); (b) anexar a um comentário já existente, direto no card (`CommentCardDisplay` → novo `CommentAttachmentList`).
5. **Modal de exclusão duplicado — guarda por dono.** `IssueAttachmentDeleteModal` reage a um único `attachmentDeleteModalId` global no store. Como agora ele pode ser montado tanto pela lista geral (`IssueAttachmentItemList`) quanto pelo novo `CommentAttachmentList`, cada um só renderiza o modal se o anexo em questão "pertence" a ele: a lista geral só monta se `!attachment.comment`; o componente do comentário só monta se `attachment.comment === commentId`. Sem essa guarda, os dois tentariam abrir o mesmo modal ao mesmo tempo quando a exclusão parte do comentário.
6. **Progresso de upload não é filtrado por comentário.** `attachmentsUploadStatusMap` é indexado só por `issueId → tempId`; o item "enviando…" aparece apenas na lista geral enquanto o upload está em andamento, e só surge dentro do comentário quando o upload conclui e o registro definitivo cai no `attachmentMap`. Extensão do store para carregar `commentId` também no progresso ficou fora de escopo (ganho pequeno, mexe em mais um observable).
7. **Campo `comment` no tipo `TIssueAttachment` (não `comment_id`).** O DRF serializa o FK com o nome literal do campo do model (`comment`), não com sufixo `_id` — mesmo padrão (já inconsistente) do `issue_id` existente, que na prática sai como `issue` no JSON. Optamos por não repetir esse erro no campo novo.

## Arquivos criados

- `apps/api/plane/db/migrations/0125_alter_fileasset_comment.py` — `AlterField` trocando `on_delete` de `CASCADE` para `SET_NULL` no FK `FileAsset.comment`.
- `apps/web/core/components/comments/attachments/comment-attachment-list.tsx` — lista de anexos de um comentário específico + botão de anexar + modal de exclusão guardado.

## Arquivos modificados

- `apps/api/plane/db/models/asset.py` — `FileAsset.comment` com `on_delete=models.SET_NULL`.
- `apps/api/plane/app/views/issue/attachment.py` — `IssueAttachmentV2Endpoint.post` aceita `comment_id` opcional no payload, valida que o comentário pertence à mesma issue/projeto/workspace, e persiste no `FileAsset` criado.
- `packages/types/src/issues/issue_attachment.ts` — `TIssueAttachment.comment: string | null`.
- `apps/web/core/services/issue/issue_attachment.service.ts` — `uploadIssueAttachment` aceita `commentId` opcional e inclui `comment_id` no payload do POST quando presente.
- `apps/web/core/store/issue/issue-details/attachment.store.ts` — `createAttachment` repassa `commentId`; novo seletor `getAttachmentsByCommentId(issueId, commentId)`.
- `apps/web/core/components/issues/issue-detail-widgets/attachments/helper.tsx` — `TAttachmentOperations.create` aceita `commentId` opcional.
- `apps/web/core/components/comments/comment-create.tsx` — staging local de arquivos (`stagedFiles`), upload disparado após a criação do comentário, vinculando `comment.id`.
- `apps/web/core/components/comments/card/display.tsx` — renderiza `CommentAttachmentList` abaixo do corpo do comentário.
- `apps/web/core/components/issues/attachment/attachment-item-list.tsx` — guarda para só montar `IssueAttachmentDeleteModal` quando o anexo não tiver `comment` vinculado.

## Como testar

1. Backend: `python manage.py migrate --settings=plane.settings.local` (aplica a `0125`); via shell, criar um `IssueComment` e chamar `POST /api/assets/v2/workspaces/{ws}/projects/{p}/issues/{issue_id}/attachments/` com `comment_id` no payload — conferir que o `FileAsset` criado tem `comment_id` setado.
2. Frontend: abrir uma issue, comentar anexando um arquivo (via clipe abaixo do editor de novo comentário) e depois anexar um arquivo extra num comentário já existente. Confirmar que o anexo aparece na lista geral **e** dentro do comentário. Excluir pelo card do comentário e confirmar que some dos dois lugares. Excluir o comentário e confirmar que o anexo permanece na lista geral, sem vínculo.

## Pitfalls

- Se um novo lugar do código também montar `IssueAttachmentDeleteModal` reagindo a `attachmentDeleteModalId`, replicar a mesma guarda por dono (item 5 acima) — senão dois modais abrem ao mesmo tempo.
- O item de upload em progresso não aparece dentro do card do comentário enquanto sobe (só na lista geral) — comportamento esperado, ver decisão 6.
- `CommentCreate`/`CommentAttachmentList` só oferecem o controle de anexar quando `projectId` está disponível (sempre o caso no fluxo real de comentário de issue); o wrapper `CommentsWrapper` genérico (`apps/web/core/components/comments/comments.tsx`) não é usado em nenhuma tela hoje.
