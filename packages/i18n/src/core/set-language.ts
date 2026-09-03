/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { initPromise, i18nInstance } from "./instance";
import { LANGUAGE_STORAGE_KEY, resolveLanguage } from "../constants/language";
import type { TLanguage } from "../types";

export async function setLanguage(lng: TLanguage): Promise<void> {
  // FORK: o perfil vindo do backend pode trazer um idioma que este fork não
  // oferece mais (usuários antigos gravados com "en"). resolveLanguage coage
  // para pt-BR em vez de deixar o i18next cair num locale sem tradução.
  const resolved = resolveLanguage(lng);
  await initPromise;
  await i18nInstance.changeLanguage(resolved);
  if (typeof window !== "undefined") {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, resolved);
    document.documentElement.lang = resolved;
  }
}
