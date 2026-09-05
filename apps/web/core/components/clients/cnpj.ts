/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const CNPJ_LENGTH = 14;
const FIRST_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
const SECOND_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];

export const normalizeCnpj = (value: string | null | undefined): string => (value ?? "").replace(/\D/g, "");

/** Formata para 00.000.000/0000-00, tolerando entradas parciais (usado no onChange do input). */
export const formatCnpj = (value: string | null | undefined): string => {
  const digits = normalizeCnpj(value).slice(0, CNPJ_LENGTH);
  return digits
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
};

const checkDigit = (digits: string, weights: number[]): number => {
  const total = digits.split("").reduce((sum, digit, index) => sum + Number(digit) * weights[index], 0);
  const remainder = total % 11;
  return remainder < 2 ? 0 : 11 - remainder;
};

export const isValidCnpj = (value: string | null | undefined): boolean => {
  const cnpj = normalizeCnpj(value);
  if (cnpj.length !== CNPJ_LENGTH) return false;
  if (cnpj === cnpj[0].repeat(CNPJ_LENGTH)) return false;
  if (checkDigit(cnpj.slice(0, 12), FIRST_WEIGHTS) !== Number(cnpj[12])) return false;
  return checkDigit(cnpj.slice(0, 13), SECOND_WEIGHTS) === Number(cnpj[13]);
};
