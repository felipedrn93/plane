/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLanguage, ILanguageOption } from "../types";

/**
 * FORK: este fork é usado internamente apenas em português. O idioma padrão (e o
 * fallback de qualquer chave/valor desconhecido) é `pt-BR`, não `en`.
 */
export const FALLBACK_LANGUAGE: TLanguage = "pt-BR";

/**
 * FORK: apenas `pt-BR` é oferecido. Esta lista alimenta tanto os seletores de
 * idioma da UI (perfil e Power-K) quanto `supportedLngs` do i18next — com um
 * único item, qualquer idioma salvo anteriormente (no localStorage ou no perfil
 * do usuário) é coagido de volta para `pt-BR`.
 *
 * Os arquivos dos outros 18 locales continuam em `src/locales/` de propósito:
 * removê-los criaria conflito em todo merge com o upstream. Para reativar
 * idiomas, basta acrescentá-los aqui — as traduções já existem (menos as 48
 * chaves das mods deste fork, ver `scripts/sync-check.ts`).
 */
export const SUPPORTED_LANGUAGES: ILanguageOption[] = [{ label: "Português Brasil", value: "pt-BR" }];

export const LANGUAGE_STORAGE_KEY = "userLanguage";

/**
 * FORK: ponto único de coerção de idioma. Usuários criados antes desta mudança
 * têm `en` (ou outro idioma) salvo no perfil do backend, e o perfil sobrescreve
 * o localStorage no login — sem esta função, esses usuários continuariam vendo o
 * sistema em inglês. Qualquer valor fora de SUPPORTED_LANGUAGES vira
 * FALLBACK_LANGUAGE.
 */
export function resolveLanguage(lng: string | null | undefined): TLanguage {
  return SUPPORTED_LANGUAGES.some((l) => l.value === lng) ? (lng as TLanguage) : FALLBACK_LANGUAGE;
}
