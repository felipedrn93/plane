# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from django.db import models

from .base import BaseModel


class PushSubscription(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=1024, unique=True)
    p256dh_key = models.CharField(max_length=255)
    auth_key = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=512, blank=True, null=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "push_subscriptions"
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user"], name="push_sub_user_idx"),
        ]

    def __str__(self):
        return f"{self.user_id} <{self.endpoint[:48]}>"
