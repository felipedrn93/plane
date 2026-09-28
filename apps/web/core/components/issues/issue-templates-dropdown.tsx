/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { ChevronDown, LayoutTemplate } from "lucide-react";
import useSWR, { mutate } from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { TrashIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIssueTemplate } from "@plane/types";
import { EIssuesStoreType } from "@plane/types";
import { CustomMenu } from "@plane/ui";
// services
import { IssueService } from "@/services/issue";
// local imports
import { CreateUpdateIssueModal } from "./issue-modal/modal";

const issueService = new IssueService();

export const getIssueTemplatesKey = (projectId: string) => `ISSUE_TEMPLATES_${projectId}`;

type Props = {
  workspaceSlug: string;
  projectId: string;
};

// Project work item templates (fork feature): pick one to open the create form pre-filled; saving it
// also creates the template's sub-work items and relations (see issue-modal/base.tsx).
export const IssueTemplatesDropdown = observer(function IssueTemplatesDropdown(props: Props) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const [selected, setSelected] = useState<TIssueTemplate | undefined>();
  const { data: templates } = useSWR(getIssueTemplatesKey(projectId), () =>
    issueService.listTemplates(workspaceSlug, projectId)
  );

  const handleDelete = async (template: TIssueTemplate) => {
    if (!window.confirm(t("issue_templates.delete_confirm", { name: template.name }))) return;
    try {
      await issueService.deleteTemplate(workspaceSlug, projectId, template.id);
      void mutate(getIssueTemplatesKey(projectId));
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("error"), message: t("issue_templates.delete_failed") });
    }
  };

  return (
    <>
      <CustomMenu
        placement="bottom-end"
        maxHeight="lg"
        closeOnSelect
        customButton={
          <div className="flex h-8 items-center gap-1.5 rounded-md border-[0.5px] border-strong px-3 text-body-xs-medium text-secondary hover:bg-layer-1">
            <LayoutTemplate className="size-3.5" />
            <span className="hidden sm:inline">{t("issue_templates.label")}</span>
            <ChevronDown className="size-3" />
          </div>
        }
      >
        {templates && templates.length > 0 ? (
          templates.map((template) => (
            <CustomMenu.MenuItem key={template.id} onClick={() => setSelected(template)}>
              <div className="flex w-64 items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate">{template.name}</p>
                  <p className="text-caption-sm-regular text-tertiary">
                    {t("issue_templates.sub_issues_count", { count: template.sub_issues_count })}
                  </p>
                </div>
                <span
                  // a real <button> would be nested inside the menu item, which already renders one
                  // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
                  role="button"
                  tabIndex={0}
                  aria-label={t("common.actions.delete")}
                  className="shrink-0 rounded p-1 text-tertiary hover:bg-layer-2 hover:text-danger-primary"
                  onClick={(e) => {
                    e.stopPropagation();
                    void handleDelete(template);
                  }}
                  onKeyDown={(e) => {
                    if (e.key !== "Enter") return;
                    e.stopPropagation();
                    void handleDelete(template);
                  }}
                >
                  <TrashIcon className="size-3.5" />
                </span>
              </div>
            </CustomMenu.MenuItem>
          ))
        ) : (
          <p className="w-64 px-2 py-1.5 text-caption-sm-regular text-tertiary">{t("issue_templates.empty")}</p>
        )}
      </CustomMenu>
      <CreateUpdateIssueModal
        isOpen={!!selected}
        onClose={() => setSelected(undefined)}
        storeType={EIssuesStoreType.PROJECT}
        fetchIssueDetails={false}
        data={
          selected && {
            project_id: projectId,
            name: selected.name,
            description_html: selected.root.description_html,
            priority: selected.root.priority,
            assignee_ids: selected.root.assignee_ids,
            label_ids: selected.root.label_ids,
            issueTemplateId: selected.id,
          }
        }
      />
    </>
  );
});
