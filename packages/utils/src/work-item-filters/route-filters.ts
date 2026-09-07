/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { TWorkItemFilterConditionData, TWorkItemFilterExpression, TWorkItemFilterProperty } from "@plane/types";
import { COLLECTION_OPERATOR, LOGICAL_OPERATOR } from "@plane/types";

/**
 * Propriedades que a query string pode filtrar. Sao as de colecao (id-ish), as unicas
 * em que o operador `in` faz sentido — datas e booleanos ficam de fora de proposito.
 */
const ROUTE_FILTERABLE_PROPERTIES = [
  "state_id",
  "state_group",
  "priority",
  "label_id",
  "cycle_id",
  "client_id",
  "module_id",
  "project_id",
  "assignee_id",
  "mention_id",
  "created_by_id",
  "subscriber_id",
] as const satisfies readonly TWorkItemFilterProperty[];

type TRouteFilterableProperty = (typeof ROUTE_FILTERABLE_PROPERTIES)[number];

const isRouteFilterable = (key: string): key is TRouteFilterableProperty =>
  (ROUTE_FILTERABLE_PROPERTIES as readonly string[]).includes(key);

/**
 * Le os parametros da URL e monta as condicoes de rich filter correspondentes.
 *
 * Aceita um id (`?client_id=<uuid>`) ou varios separados por virgula
 * (`?client_id=<uuid>,<uuid>`), que e o formato que o `UUIDInFilter` do backend espera.
 * Parametros desconhecidos e valores vazios sao ignorados.
 *
 * @param searchParams - os parametros da URL
 * @returns as condicoes encontradas, ou `undefined` se nao houver nenhuma
 */
export const getRichFiltersFromSearchParams = (
  searchParams: URLSearchParams
): TWorkItemFilterConditionData | undefined => {
  const conditions: TWorkItemFilterConditionData = {};

  searchParams.forEach((value, key) => {
    if (!isRouteFilterable(key)) return;
    const values = value
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean);
    if (values.length === 0) return;
    conditions[`${key}__${COLLECTION_OPERATOR.IN}`] = values.join(",");
  });

  return Object.keys(conditions).length > 0 ? conditions : undefined;
};

/**
 * Combina as condicoes vindas da URL com a expressao ja salva na view.
 *
 * Um grupo de rich filters nao aninha (`TWorkItemFilterAndGroup` guarda condicoes, nao
 * grupos), entao ha tres casos: expressao vazia, grupo `and` existente e condicao solta.
 *
 * @param viewExpression - a expressao salva na view
 * @param routeConditions - as condicoes vindas da URL
 * @returns a expressao combinada
 */
export const mergeRouteFiltersIntoExpression = (
  viewExpression: TWorkItemFilterExpression,
  routeConditions: TWorkItemFilterConditionData | undefined
): TWorkItemFilterExpression => {
  if (!routeConditions) return viewExpression;

  const hasViewExpression = Object.keys(viewExpression).length > 0;
  if (!hasViewExpression) return routeConditions;

  const andGroup = (viewExpression as { [LOGICAL_OPERATOR.AND]?: TWorkItemFilterConditionData[] })[
    LOGICAL_OPERATOR.AND
  ];
  if (andGroup) return { [LOGICAL_OPERATOR.AND]: [...andGroup, routeConditions] };

  return { [LOGICAL_OPERATOR.AND]: [viewExpression as TWorkItemFilterConditionData, routeConditions] };
};
