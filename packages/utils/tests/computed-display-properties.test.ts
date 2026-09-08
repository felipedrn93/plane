/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { getComputedDisplayProperties } from "../src/work-item/base";

describe("getComputedDisplayProperties", () => {
  // o helper monta um objeto explicito: uma chave ausente dele e descartada silenciosamente,
  // mesmo vindo `true` da API, e a propriedade nunca renderiza nos layouts
  it("preserva client habilitado", () => {
    expect(getComputedDisplayProperties({ client: true }).client).toBe(true);
  });

  it("preserva client desabilitado", () => {
    expect(getComputedDisplayProperties({ client: false }).client).toBe(false);
  });

  it("usa true como padrao para client, como o backend", () => {
    expect(getComputedDisplayProperties({}).client).toBe(true);
    expect(getComputedDisplayProperties().client).toBe(true);
  });

  it("nao descarta nenhuma chave conhecida de display property", () => {
    const todas: (keyof ReturnType<typeof getComputedDisplayProperties>)[] = [
      "assignee",
      "start_date",
      "due_date",
      "labels",
      "priority",
      "state",
      "sub_issue_count",
      "attachment_count",
      "link",
      "estimate",
      "key",
      "created_on",
      "updated_on",
      "completed_on",
      "modules",
      "cycle",
      "issue_type",
      "parent_breadcrumb",
      "client",
    ];
    const computado = getComputedDisplayProperties({});
    for (const chave of todas) expect(computado, `faltou ${chave}`).toHaveProperty(chave);
  });
});
