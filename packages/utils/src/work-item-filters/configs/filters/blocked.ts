/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { TFilterProperty } from "@plane/types";
import { EQUALITY_OPERATOR } from "@plane/types";
// local imports
import type { IFilterIconConfig, TCreateFilterConfig, TCreateFilterConfigParams } from "../../../rich-filters";
import { createFilterConfig, getSingleSelectConfig, createOperatorConfigEntry } from "../../../rich-filters";

// ------------ Blocked filter ------------

/**
 * Blocked filter specific params
 */
export type TCreateBlockedFilterParams = TCreateFilterConfigParams & IFilterIconConfig<string>;

/**
 * Static options for the blocked single-select filter.
 * Values map to the backend `is_blocked` BooleanFilter ("true"/"false").
 */
const BLOCKED_FILTER_OPTIONS: { id: string; label: string; value: string }[] = [
  { id: "true", label: "Blocked", value: "true" },
  { id: "false", label: "Not blocked", value: "false" },
];

/**
 * Get the blocked filter config
 * @template K - The filter key
 * @param key - The filter key to use
 * @returns A function that takes parameters and returns the blocked filter config
 */
export const getBlockedFilterConfig =
  <P extends TFilterProperty>(key: P): TCreateFilterConfig<P, TCreateBlockedFilterParams> =>
  (params: TCreateBlockedFilterParams) =>
    createFilterConfig<P>({
      id: key,
      label: "Blocked",
      ...params,
      icon: params.filterIcon,
      supportedOperatorConfigsMap: new Map([
        createOperatorConfigEntry(EQUALITY_OPERATOR.EXACT, params, (updatedParams) =>
          getSingleSelectConfig<{ id: string; label: string; value: string }, string>(
            {
              items: BLOCKED_FILTER_OPTIONS,
              getId: (option) => option.id,
              getLabel: (option) => option.label,
              getValue: (option) => option.value,
            },
            { ...updatedParams }
          )
        ),
      ]),
    });
