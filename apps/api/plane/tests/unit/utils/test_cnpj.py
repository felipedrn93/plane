# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.utils.cnpj import is_valid_cnpj, normalize_cnpj


@pytest.mark.unit
class TestNormalizeCnpj:
    def test_strips_mask(self):
        assert normalize_cnpj("11.222.333/0001-81") == "11222333000181"

    def test_keeps_digits_only(self):
        assert normalize_cnpj(" 11222333000181 ") == "11222333000181"

    def test_none_returns_empty(self):
        assert normalize_cnpj(None) == ""


@pytest.mark.unit
class TestIsValidCnpj:
    def test_valid_cnpj_with_mask(self):
        assert is_valid_cnpj("11.222.333/0001-81") is True

    def test_valid_cnpj_without_mask(self):
        assert is_valid_cnpj("11222333000181") is True

    def test_wrong_check_digits(self):
        assert is_valid_cnpj("11222333000182") is False

    def test_wrong_length(self):
        assert is_valid_cnpj("1122233300018") is False

    def test_all_repeated_digits_rejected(self):
        assert is_valid_cnpj("00000000000000") is False
        assert is_valid_cnpj("11111111111111") is False

    def test_empty_and_none(self):
        assert is_valid_cnpj("") is False
        assert is_valid_cnpj(None) is False

    def test_letters_rejected(self):
        assert is_valid_cnpj("11.222.333/0001-8A") is False
