/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { TClient, TFilterProperty, TSupportedOperators } from "@plane/types";
import { EQUALITY_OPERATOR, COLLECTION_OPERATOR } from "@plane/types";
// local imports
import type { TCreateFilterConfigParams, IFilterIconConfig, TCreateFilterConfig } from "../../../rich-filters";
import { createFilterConfig, getMultiSelectConfig, createOperatorConfigEntry } from "../../../rich-filters";

/**
 * Client filter specific params
 */
export type TCreateClientFilterParams = TCreateFilterConfigParams &
  IFilterIconConfig<TClient> & {
    clients: TClient[];
  };

/**
 * Helper to get the client multi select config
 * @param params - The filter params
 * @returns The client multi select config
 */
export const getClientMultiSelectConfig = (
  params: TCreateClientFilterParams,
  singleValueOperator: TSupportedOperators
) =>
  getMultiSelectConfig<TClient, string, TClient>(
    {
      items: params.clients,
      getId: (client) => client.id,
      getLabel: (client) => client.name,
      getValue: (client) => client.id,
      getIconData: (client) => client,
    },
    {
      singleValueOperator,
      ...params,
    },
    {
      ...params,
    }
  );

/**
 * Get the client filter config
 * @template K - The filter key
 * @param key - The filter key to use
 * @returns A function that takes parameters and returns the client filter config
 */
export const getClientFilterConfig =
  <P extends TFilterProperty>(key: P): TCreateFilterConfig<P, TCreateClientFilterParams> =>
  (params: TCreateClientFilterParams) =>
    createFilterConfig<P>({
      id: key,
      label: "Client",
      ...params,
      icon: params.filterIcon,
      supportedOperatorConfigsMap: new Map([
        createOperatorConfigEntry(COLLECTION_OPERATOR.IN, params, (updatedParams) =>
          getClientMultiSelectConfig(updatedParams, EQUALITY_OPERATOR.EXACT)
        ),
      ]),
    });
