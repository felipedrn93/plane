# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

from celery import shared_task
from django.utils import timezone

from plane.db.models import Notification, PushSubscription
from plane.utils.web_push import is_configured, send_web_push


logger = logging.getLogger(__name__)


PUSH_ENABLED_SENDERS = {
    "in_app:issue_activities:assigned",
    "in_app:issue_activities:mentioned",
}


def _build_payload(notification: Notification) -> dict:
    data = notification.data or {}
    issue = data.get("issue", {}) if isinstance(data, dict) else {}
    workspace_slug = issue.get("workspace_slug") or (notification.workspace.slug if notification.workspace else "")
    project_id = issue.get("project_id") or (str(notification.project_id) if notification.project_id else "")
    issue_id = issue.get("id") or (str(notification.entity_identifier) if notification.entity_identifier else "")

    identifier = issue.get("identifier")
    sequence_id = issue.get("sequence_id")
    issue_name = issue.get("name", "")
    ref = f"{identifier}-{sequence_id}" if identifier and sequence_id else issue_name

    if "mentioned" in notification.sender:
        title = "Você foi mencionado"
    else:
        title = "Nova tarefa atribuída a você"

    body = f"{ref}: {issue_name}" if ref and issue_name and ref != issue_name else (issue_name or ref or "")

    url = ""
    if workspace_slug and project_id and issue_id:
        url = f"/{workspace_slug}/projects/{project_id}/issues/{issue_id}"

    return {
        "title": title,
        "body": body,
        "url": url,
        "tag": str(notification.id),
    }


@shared_task
def send_push_notifications(notification_ids):
    if not notification_ids:
        return
    if not is_configured():
        return

    notifications = list(
        Notification.objects.filter(id__in=notification_ids)
        .select_related("workspace", "project")
        .filter(sender__in=PUSH_ENABLED_SENDERS)
    )
    if not notifications:
        return

    receiver_ids = {n.receiver_id for n in notifications}
    subscriptions_by_user: dict = {}
    for sub in PushSubscription.objects.filter(user_id__in=receiver_ids):
        subscriptions_by_user.setdefault(sub.user_id, []).append(sub)

    if not subscriptions_by_user:
        return

    stale_subscription_ids = []
    used_subscription_ids = []

    for notification in notifications:
        payload = _build_payload(notification)
        for sub in subscriptions_by_user.get(notification.receiver_id, []):
            ok = send_web_push(sub, payload)
            if ok:
                used_subscription_ids.append(sub.id)
            else:
                stale_subscription_ids.append(sub.id)

    if stale_subscription_ids:
        PushSubscription.objects.filter(id__in=stale_subscription_ids).delete()
    if used_subscription_ids:
        PushSubscription.objects.filter(id__in=used_subscription_ids).update(last_used_at=timezone.now())
