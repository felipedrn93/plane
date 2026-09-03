# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest

from plane.utils.issue_filters import issue_filters

CLIENT_ID = "6a1f7f9e-9b2b-4a4a-8f6e-2b1c3d4e5f60"


@pytest.mark.unit
class TestFilterClient:
    def test_get_single_client(self):
        # `filter_valid_uuids` converte para objetos UUID, como em todos os
        # outros filtros do arquivo (filter_state, filter_parent, ...).
        assert issue_filters({"client": CLIENT_ID}, "GET") == {"client_id__in": [uuid.UUID(CLIENT_ID)]}

    def test_get_none_means_unassigned(self):
        assert issue_filters({"client": "None"}, "GET") == {"client_id__isnull": True}

    def test_post_takes_list(self):
        assert issue_filters({"client": [CLIENT_ID]}, "POST") == {"client_id__in": [CLIENT_ID]}

    def test_absent_key_is_ignored(self):
        assert issue_filters({}, "GET") == {}
