/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
import { observer } from "mobx-react";
import { Paperclip } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TIssueServiceType } from "@plane/types";
import { EIssueServiceType } from "@plane/types";
// hooks
import { useAttachmentOperations } from "@/components/issues/issue-detail-widgets/attachments/helper";
import { IssueAttachmentsListItem } from "@/components/issues/attachment/attachment-list-item";
import { IssueAttachmentDeleteModal } from "@/components/issues/attachment/delete-attachment-modal";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";

type TCommentAttachmentList = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  commentId: string;
  disabled?: boolean;
  issueServiceType?: TIssueServiceType;
};

export const CommentAttachmentList = observer(function CommentAttachmentList(props: TCommentAttachmentList) {
  const {
    workspaceSlug,
    projectId,
    issueId,
    commentId,
    disabled = false,
    issueServiceType = EIssueServiceType.ISSUES,
  } = props;
  const { t } = useTranslation();
  // refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  // store hooks
  const {
    attachment: { getAttachmentsByCommentId, getAttachmentById },
    attachmentDeleteModalId,
    toggleDeleteAttachmentModal,
  } = useIssueDetail(issueServiceType);
  const { operations: attachmentOperations } = useAttachmentOperations(
    workspaceSlug,
    projectId,
    issueId,
    issueServiceType
  );
  // derived values
  const attachmentIds = getAttachmentsByCommentId(issueId, commentId);
  const attachmentBeingDeleted = attachmentDeleteModalId ? getAttachmentById(attachmentDeleteModalId) : undefined;
  const shouldRenderDeleteModal = Boolean(attachmentDeleteModalId) && attachmentBeingDeleted?.comment === commentId;

  return (
    <div className="flex flex-col gap-1">
      {shouldRenderDeleteModal && attachmentDeleteModalId && (
        <IssueAttachmentDeleteModal
          isOpen={shouldRenderDeleteModal}
          onClose={() => toggleDeleteAttachmentModal(null)}
          attachmentOperations={attachmentOperations}
          attachmentId={attachmentDeleteModalId}
          issueServiceType={issueServiceType}
        />
      )}
      {attachmentIds.length > 0 && (
        <div className="flex flex-col">
          {attachmentIds.map((attachmentId) => (
            <IssueAttachmentsListItem
              key={attachmentId}
              attachmentId={attachmentId}
              disabled={disabled}
              issueServiceType={issueServiceType}
            />
          ))}
        </div>
      )}
      {!disabled && (
        <>
          <button
            type="button"
            className="flex w-fit items-center gap-1.5 py-1 text-13 text-tertiary hover:text-secondary"
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip className="size-3.5" strokeWidth={2} />
            {t("common.attach")}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              const files = e.target.files;
              if (files && files.length > 0) {
                Array.from(files).forEach((file) => attachmentOperations.create(file, commentId));
              }
              e.target.value = "";
            }}
          />
        </>
      )}
    </div>
  );
});
