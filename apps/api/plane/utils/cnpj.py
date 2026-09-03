# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Normalização e validação de CNPJ.

Módulo puro (sem Django) para poder ser importado tanto pelos serializers
quanto pelos models sem risco de import circular — mesmo motivo que levou
`plane/utils/recurrence_validator.py` a existir (ver mods/tarefas-recorrentes.md).
"""

import re

CNPJ_LENGTH = 14

_FIRST_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_SECOND_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def normalize_cnpj(value):
    """Devolve apenas os dígitos do CNPJ. `None` vira string vazia."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value))


def _check_digit(digits, weights):
    total = sum(int(digit) * weight for digit, weight in zip(digits, weights))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_cnpj(value):
    """True quando o CNPJ tem 14 dígitos e os dois verificadores conferem."""
    cnpj = normalize_cnpj(value)

    if len(cnpj) != CNPJ_LENGTH:
        return False

    # Sequências repetidas (00000000000000, 11111111111111, ...) passam no
    # cálculo dos dígitos mas não são CNPJs reais.
    if cnpj == cnpj[0] * CNPJ_LENGTH:
        return False

    if _check_digit(cnpj[:12], _FIRST_WEIGHTS) != int(cnpj[12]):
        return False

    return _check_digit(cnpj[:13], _SECOND_WEIGHTS) == int(cnpj[13])
