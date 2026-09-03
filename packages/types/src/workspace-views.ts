/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type {
  IWorkspaceViewProps,
  IIssueDisplayFilterOptions,
  IIssueDisplayProperties,
  TWorkItemFilterExpression,
} from "./view-props";
import type { EViewAccess } from "./views";

export interface IWorkspaceView {
  id: string;
  access: EViewAccess;
  created_at: Date;
  updated_at: Date;
  is_favorite: boolean;
  created_by: string;
  updated_by: string;
  name: string;
  description: string;
  rich_filters: TWorkItemFilterExpression;
  display_filters: IIssueDisplayFilterOptions;
  display_properties: IIssueDisplayProperties;
  // FORK: ordem das colunas da spreadsheet, persistida por usuário. O backend já
  // serve o campo (IssueView.display_properties_order), mas a interface não tinha
  // sido atualizada — ver mods/reordenar-colunas-spreadsheet.md. Opcional porque
  // views criadas antes da migração não trazem o campo.
  display_properties_order?: string[];
  query: any;
  query_data: IWorkspaceViewProps;
  project: string;
  workspace: string;
  is_locked: boolean;
  owned_by: string;
  workspace_detail?: {
    id: string;
    name: string;
    slug: string;
  };
}

export const STATIC_VIEW_TYPES = [
  "all-issues",
  "assigned",
  "assigned-open",
  "assigned-overdue",
  "created",
  "subscribed",
];

export type TStaticViewTypes = (typeof STATIC_VIEW_TYPES)[number];
