/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IIssueDisplayProperties } from "@plane/types";

export type TSpreadsheetColumnKey = keyof IIssueDisplayProperties;

export function moveColumn(list: TSpreadsheetColumnKey[], from: number, to: number): TSpreadsheetColumnKey[] {
  if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) {
    return list;
  }
  const result = [...list];
  const [moved] = result.splice(from, 1);
  result.splice(to, 0, moved);
  return result;
}
