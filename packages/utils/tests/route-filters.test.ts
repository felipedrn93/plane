/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import {
  getRichFiltersFromSearchParams,
  mergeRouteFiltersIntoExpression,
} from "../src/work-item-filters/route-filters";

describe("getRichFiltersFromSearchParams", () => {
  it("converte um id em condicao __in", () => {
    expect(getRichFiltersFromSearchParams(new URLSearchParams("client_id=abc"))).toEqual({ client_id__in: "abc" });
  });
  it("mantem varios ids separados por virgula", () => {
    expect(getRichFiltersFromSearchParams(new URLSearchParams("client_id=abc,def"))).toEqual({
      client_id__in: "abc,def",
    });
  });
  it("limpa espacos e entradas vazias", () => {
    expect(getRichFiltersFromSearchParams(new URLSearchParams("client_id=abc, ,def "))).toEqual({
      client_id__in: "abc,def",
    });
  });
  it("ignora parametro desconhecido", () => {
    expect(getRichFiltersFromSearchParams(new URLSearchParams("foo=bar"))).toBeUndefined();
  });
  it("ignora valor vazio", () => {
    expect(getRichFiltersFromSearchParams(new URLSearchParams("client_id="))).toBeUndefined();
  });
  it("ignora propriedade que nao e de colecao", () => {
    expect(getRichFiltersFromSearchParams(new URLSearchParams("target_date=2026-01-01"))).toBeUndefined();
  });
  it("aceita mais de uma propriedade", () => {
    expect(getRichFiltersFromSearchParams(new URLSearchParams("client_id=abc&state_id=s1&foo=x"))).toEqual({
      client_id__in: "abc",
      state_id__in: "s1",
    });
  });
});

describe("mergeRouteFiltersIntoExpression", () => {
  const cond = { client_id__in: "abc" };
  it("usa so a condicao da URL quando a view esta vazia", () => {
    expect(mergeRouteFiltersIntoExpression({}, cond)).toEqual(cond);
  });
  it("devolve a view intacta quando nao ha condicao na URL", () => {
    expect(mergeRouteFiltersIntoExpression({ state_id__in: "s1" }, undefined)).toEqual({ state_id__in: "s1" });
  });
  it("agrupa em and quando a view tem uma condicao solta", () => {
    expect(mergeRouteFiltersIntoExpression({ state_id__in: "s1" }, cond)).toEqual({
      and: [{ state_id__in: "s1" }, cond],
    });
  });
  it("faz append quando a view ja e um grupo and", () => {
    expect(mergeRouteFiltersIntoExpression({ and: [{ state_id__in: "s1" }] }, cond)).toEqual({
      and: [{ state_id__in: "s1" }, cond],
    });
  });
});
