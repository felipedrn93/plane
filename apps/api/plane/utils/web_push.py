# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush


logger = logging.getLogger(__name__)


GONE_STATUS_CODES = {404, 410}


def is_configured() -> bool:
    return bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY and settings.VAPID_CLAIM_EMAIL)


def send_web_push(subscription, payload: dict) -> bool:
    """Send a Web Push payload to a single PushSubscription.

    Returns True on delivery (or transient failure to retry later).
    Returns False when the subscription is permanently gone (404/410),
    signaling the caller to delete it.
    """
    if not is_configured():
        logger.warning("VAPID keys not configured; skipping web push")
        return True

    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh_key, "auth": subscription.auth_key},
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIM_EMAIL}"},
        )
        return True
    except WebPushException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in GONE_STATUS_CODES:
            return False
        logger.exception("Web push delivery failed: %s", exc)
        return True
    except Exception:
        logger.exception("Unexpected error sending web push")
        return True
