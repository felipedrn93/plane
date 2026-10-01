/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { IProject, IUserLite, TOperatorConfigMap, TSupportedOperators } from "@plane/types";
import { COMPARISON_OPERATOR, EQUALITY_OPERATOR } from "@plane/types";
// local imports
import { getDatePickerConfig, getDateRangePickerConfig, getMultiSelectConfig, getSingleSelectConfig } from "../core";
import type { IFilterIconConfig, TCreateDateFilterParams, TCreateFilterConfigParams, TFilterIconType } from "../shared";
import { createOperatorConfigEntry } from "../shared";

// ------------ Base User Filter Types ------------

/**
 * User filter specific params
 */
export type TCreateUserFilterParams = TCreateFilterConfigParams &
  IFilterIconConfig<IUserLite> & {
    members: IUserLite[];
  };

/**
 * Helper to get the member multi select config
 * @param params - The filter params
 * @returns The member multi select config
 */
export const getMemberMultiSelectConfig = (params: TCreateUserFilterParams, singleValueOperator: TSupportedOperators) =>
  getMultiSelectConfig<IUserLite, string, IUserLite>(
    {
      items: params.members,
      getId: (member) => member.id,
      getLabel: (member) => member.display_name,
      getValue: (member) => member.id,
      getIconData: (member) => member,
    },
    {
      singleValueOperator,
      ...params,
    },
    {
      ...params,
    }
  );

// ------------ Date Operators ------------

/**
 * Relative date bounds, resolved by the backend at query time (so saved views keep moving with the calendar)
 */
const RELATIVE_DATE_OPTIONS: { id: string; label: string }[] = [
  { id: "today", label: "today" },
  { id: "end_of_week", label: "this week" },
  { id: "end_of_month", label: "this month" },
];

export const getSupportedDateOperators = (params: TCreateDateFilterParams): TOperatorConfigMap =>
  new Map([
    createOperatorConfigEntry(EQUALITY_OPERATOR.EXACT, params, (updatedParams) => getDatePickerConfig(updatedParams)),
    createOperatorConfigEntry(COMPARISON_OPERATOR.RANGE, params, (updatedParams) =>
      getDateRangePickerConfig(updatedParams)
    ),
    createOperatorConfigEntry(COMPARISON_OPERATOR.GTE, params, (updatedParams) => getDatePickerConfig(updatedParams)),
    createOperatorConfigEntry(COMPARISON_OPERATOR.LTE, params, (updatedParams) => getDatePickerConfig(updatedParams)),
    createOperatorConfigEntry(COMPARISON_OPERATOR.LTE_RELATIVE, params, (updatedParams) =>
      getSingleSelectConfig<{ id: string; label: string }, string>(
        {
          items: RELATIVE_DATE_OPTIONS,
          getId: (option) => option.id,
          getLabel: (option) => option.label,
          getValue: (option) => option.id,
        },
        { ...updatedParams }
      )
    ),
  ]);

// ------------ Project filter ------------

/**
 * Project filter specific params
 */
export type TCreateProjectFilterParams = TCreateFilterConfigParams &
  IFilterIconConfig<IProject> & {
    projects: IProject[];
  };

/**
 * Helper to get the project multi select config
 * @param params - The filter params
 * @returns The member multi select config
 */
export const getProjectMultiSelectConfig = (
  params: TCreateProjectFilterParams,
  singleValueOperator: TSupportedOperators
) =>
  getMultiSelectConfig<IProject, string, IProject>(
    {
      items: params.projects,
      getId: (project) => project.id,
      getLabel: (project) => project.name,
      getValue: (project) => project.id,
      getIconData: (project) => project,
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
 * Custom property filter specific params
 */
export type TCustomPropertyFilterParams<T extends TFilterIconType> = TCreateFilterConfigParams &
  IFilterIconConfig<T> & {
    propertyDisplayName: string;
  };
