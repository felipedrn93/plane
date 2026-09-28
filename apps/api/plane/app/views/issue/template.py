# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .. import BaseAPIView
from plane.app.permissions import ProjectEntityPermission
from plane.db.models import Issue, IssueTemplate, Project
from plane.utils.issue_structure import snapshot_issue_structure, valid_label_ids, valid_member_ids


class IssueTemplateEndpoint(BaseAPIView):
    """Project work item templates: saved from an existing work item, applied via copy-structure."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        templates = IssueTemplate.objects.filter(project=project)
        response = []
        for template in templates:
            root = dict(template.structure.get("root", {}))
            # Pre-fill the create form only with ids that still exist in the project.
            member_ids = valid_member_ids(project, root.get("assignee_ids", []))
            label_ids = valid_label_ids(project, root.get("label_ids", []))
            root["assignee_ids"] = [i for i in root.get("assignee_ids", []) if i in member_ids]
            root["label_ids"] = [i for i in root.get("label_ids", []) if i in label_ids]
            response.append(
                {
                    "id": template.id,
                    "name": template.name,
                    "root": root,
                    "sub_issues_count": len(template.structure.get("nodes", [])),
                }
            )
        return Response(response, status=status.HTTP_200_OK)

    def post(self, request, slug, project_id):
        name = (request.data.get("name") or "").strip()
        if not name or len(name) > 255:
            return Response({"error": "Name is required (max 255 characters)"}, status=status.HTTP_400_BAD_REQUEST)
        source = Issue.issue_objects.filter(
            pk=request.data.get("issue_id"), project_id=project_id, workspace__slug=slug
        ).first()
        if source is None:
            return Response({"error": "Issue not found"}, status=status.HTTP_404_NOT_FOUND)

        structure = snapshot_issue_structure(source)
        template = IssueTemplate.objects.filter(project_id=project_id, name__iexact=name).first()
        if template is None:
            template = IssueTemplate.objects.create(project_id=project_id, name=name, structure=structure)
        else:
            template.name = name
            template.structure = structure
            template.save(update_fields=["name", "structure", "updated_at"])
        return Response({"id": template.id, "name": template.name}, status=status.HTTP_201_CREATED)

    def delete(self, request, slug, project_id, pk):
        template = IssueTemplate.objects.filter(pk=pk, project_id=project_id, workspace__slug=slug).first()
        if template is None:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
