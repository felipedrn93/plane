/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// types
import type { TIssue } from "@plane/types";
// ui
import { Row } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { ParentBreadcrumb } from "@/components/issues/issue-layouts/properties/parent-breadcrumb";

type Props = {
  issue: TIssue;
};

export const SpreadsheetParentBreadcrumbColumn = observer(function SpreadsheetParentBreadcrumbColumn(props: Props) {
  const { issue } = props;
  const { workspaceSlug } = useParams();

  return (
    <Row
      className={cn(
        "flex h-11 w-full items-center border-b-[0.5px] border-subtle py-1 group-[.selected-issue-row]:bg-accent-primary/5 hover:bg-surface-2 group-[.selected-issue-row]:hover:bg-accent-primary"
      )}
    >
      <ParentBreadcrumb chain={issue.parent_chain} workspaceSlug={workspaceSlug?.toString()} />
    </Row>
  );
});
