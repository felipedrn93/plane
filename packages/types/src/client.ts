/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TClientCompany = {
  id: string;
  name: string;
  /** Apenas dígitos (14 caracteres). A máscara é aplicada na exibição. */
  cnpj: string;
  client: string;
  created_at: string;
  updated_at: string;
};

export type TClient = {
  id: string;
  name: string;
  is_active: boolean;
  companies: TClientCompany[];
  issue_count: number;
  workspace: string;
  created_at: string;
  updated_at: string;
};
