# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from plane.app.serializers import PushSubscriptionSerializer
from plane.db.models import PushSubscription

from ..base import BaseAPIView


class PushVapidKeyEndpoint(BaseAPIView):
    def get(self, request):
        return Response({"public_key": settings.VAPID_PUBLIC_KEY}, status=status.HTTP_200_OK)


class PushSubscriptionEndpoint(BaseAPIView):
    def get(self, request):
        subscriptions = PushSubscription.objects.filter(user=request.user)
        serializer = PushSubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        endpoint = request.data.get("endpoint")
        keys = request.data.get("keys") or {}
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")
        user_agent = request.data.get("user_agent") or request.META.get("HTTP_USER_AGENT", "")[:512]

        if not endpoint or not p256dh or not auth:
            return Response(
                {"error": "endpoint, keys.p256dh and keys.auth are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription, _ = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh_key": p256dh,
                "auth_key": auth,
                "user_agent": user_agent,
            },
        )
        serializer = PushSubscriptionSerializer(subscription)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        endpoint = request.data.get("endpoint") or request.query_params.get("endpoint")
        if not endpoint:
            return Response({"error": "endpoint is required"}, status=status.HTTP_400_BAD_REQUEST)
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
