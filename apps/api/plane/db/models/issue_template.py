# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

# Module imports
from .project import ProjectBaseModel


class IssueTemplate(ProjectBaseModel):
    """A saved work item tree (see plane.utils.issue_structure) used to create new work items in a project."""

    name = models.CharField(max_length=255)
    structure = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Issue Template"
        verbose_name_plural = "Issue Templates"
        db_table = "issue_templates"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "project",
                condition=Q(deleted_at__isnull=True),
                name="unique_issue_template_name_per_project_when_not_deleted",
            )
        ]

    def __str__(self):
        return self.name
