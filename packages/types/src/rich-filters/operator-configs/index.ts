/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { EQUALITY_OPERATOR, COLLECTION_OPERATOR, COMPARISON_OPERATOR } from "../operators";
import type {
  TCoreExactOperatorConfigs,
  TCoreInOperatorConfigs,
  TCoreOperatorSpecificConfigs,
  TCoreRangeOperatorConfigs,
} from "./core";
import type {
  TExtendedExactOperatorConfigs,
  TExtendedInOperatorConfigs,
  TExtendedOperatorSpecificConfigs,
  TExtendedRangeOperatorConfigs,
} from "./extended";

// ----------------------------- Composed Operator Configs -----------------------------

/**
 * EXACT operator - combines core and extended configurations
 */
export type TExactOperatorConfigs = TCoreExactOperatorConfigs | TExtendedExactOperatorConfigs;

/**
 * IN operator - combines core and extended configurations
 */
export type TInOperatorConfigs = TCoreInOperatorConfigs | TExtendedInOperatorConfigs;

/**
 * RANGE operator - combines core and extended configurations
 */
export type TRangeOperatorConfigs = TCoreRangeOperatorConfigs | TExtendedRangeOperatorConfigs;

// ----------------------------- Final Operator Specific Configs -----------------------------

/**
 * Type-safe mapping of specific operators to their supported filter type configurations.
 * Each operator maps to its composed (core + extended) configurations.
 */
export type TOperatorSpecificConfigs = {
  [EQUALITY_OPERATOR.EXACT]: TExactOperatorConfigs;
  [COLLECTION_OPERATOR.IN]: TInOperatorConfigs;
  [COMPARISON_OPERATOR.RANGE]: TRangeOperatorConfigs;
  [COMPARISON_OPERATOR.GTE]: TCoreOperatorSpecificConfigs[typeof COMPARISON_OPERATOR.GTE];
  [COMPARISON_OPERATOR.LTE]: TCoreOperatorSpecificConfigs[typeof COMPARISON_OPERATOR.LTE];
  [COMPARISON_OPERATOR.LTE_RELATIVE]: TCoreOperatorSpecificConfigs[typeof COMPARISON_OPERATOR.LTE_RELATIVE];
} & TExtendedOperatorSpecificConfigs;

/**
 * Operator filter configuration mapping - for different operators.
 * Provides type-safe mapping of operators to their specific supported configurations.
 */
export type TOperatorConfigMap = Map<
  keyof TOperatorSpecificConfigs,
  TOperatorSpecificConfigs[keyof TOperatorSpecificConfigs]
>;

// -------- RE-EXPORTS --------

export * from "./core";
export * from "./extended";
