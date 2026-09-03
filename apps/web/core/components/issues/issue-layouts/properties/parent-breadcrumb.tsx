/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MouseEvent } from "react";
import { observer } from "mobx-react";
import { ChevronRight } from "lucide-react";
// i18n
import { useTranslation } from "@plane/i18n";
// propel
import { Tooltip } from "@plane/propel/tooltip";
// types
import type { TIssue, TIssueParentChainNode } from "@plane/types";
// ui
import { ControlLink } from "@plane/ui";
// helpers
import { cn, generateWorkItemLink } from "@plane/utils";
// hooks
import { useProject } from "@/hooks/store/use-project";
import useIssuePeekOverviewRedirection from "@/hooks/use-issue-peek-overview-redirection";
import { usePlatformOS } from "@/hooks/use-platform-os";

type Props = {
  chain: TIssueParentChainNode[] | undefined;
  workspaceSlug: string | undefined;
  className?: string;
  // When the chain has more than `collapseAfter` nodes, only the first and the
  // immediate parent are kept inline; intermediates collapse into "…".
  collapseAfter?: number;
};

const stopEventPropagation = (event: MouseEvent<HTMLElement>) => {
  event.stopPropagation();
  event.preventDefault();
};

export const ParentBreadcrumb = observer(function ParentBreadcrumb(props: Props) {
  const { chain, workspaceSlug, className, collapseAfter = 3 } = props;
  const { t } = useTranslation();
  const { handleRedirection } = useIssuePeekOverviewRedirection();
  const { isMobile } = usePlatformOS();
  const { getProjectIdentifierById } = useProject();

  if (!chain || chain.length === 0) return null;

  const shouldCollapse = chain.length > collapseAfter;
  const visible: Array<{ node: TIssueParentChainNode; collapsed?: false } | { collapsed: true }> = shouldCollapse
    ? [{ node: chain[0] }, { collapsed: true }, { node: chain[chain.length - 1] }]
    : chain.map((node) => ({ node }));

  const fullPath = chain.map((n) => n.name).join(" > ");

  const openPeek = (node: TIssueParentChainNode) => {
    handleRedirection(
      workspaceSlug,
      {
        id: node.id,
        project_id: node.project_id,
        sequence_id: node.sequence_id,
      } as unknown as TIssue,
      isMobile
    );
  };

  return (
    <Tooltip tooltipHeading={t("issue.parent_breadcrumb.tooltip_full")} tooltipContent={fullPath} isMobile={isMobile}>
      <div
        className={cn(
          "flex max-w-full items-center gap-0.5 overflow-hidden text-caption-sm-regular text-secondary",
          className
        )}
        onClick={stopEventPropagation}
      >
        {visible.map((entry, index) => {
          if ("collapsed" in entry) {
            return (
              <span key={`ellipsis-${index}`} className="px-1 text-placeholder">
                …
              </span>
            );
          }
          const { node } = entry;
          const projectIdentifier = getProjectIdentifierById(node.project_id) ?? node.identifier;
          const workItemLink = generateWorkItemLink({
            workspaceSlug,
            projectId: node.project_id,
            issueId: node.id,
            projectIdentifier,
            sequenceId: node.sequence_id,
          });
          const isLast = index === visible.length - 1;
          return (
            <span key={node.id} className="flex min-w-0 items-center gap-0.5">
              <ControlLink
                href={workItemLink}
                onClick={(event) => {
                  stopEventPropagation(event);
                  openPeek(node);
                }}
                className="min-w-0 truncate rounded px-1 text-secondary hover:bg-layer-1 hover:text-primary"
              >
                <span className="truncate">{node.name}</span>
              </ControlLink>
              {!isLast && <ChevronRight className="h-3 w-3 flex-shrink-0 text-placeholder" strokeWidth={2} />}
            </span>
          );
        })}
      </div>
    </Tooltip>
  );
});
