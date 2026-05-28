/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import pushSubscriptionService from "@/services/push-subscription.service";

const SW_URL = "/push-sw.js";

type TPermission = NotificationPermission | "unsupported";

const urlBase64ToUint8Array = (base64String: string): Uint8Array => {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const output = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) output[i] = rawData.charCodeAt(i);
  return output;
};

const arrayBufferToBase64 = (buffer: ArrayBuffer): string => {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
};

const extractKeys = (sub: PushSubscription) => {
  const p256dhBuf = sub.getKey("p256dh");
  const authBuf = sub.getKey("auth");
  if (!p256dhBuf || !authBuf) return null;
  return { p256dh: arrayBufferToBase64(p256dhBuf), auth: arrayBufferToBase64(authBuf) };
};

const isSupported = () =>
  typeof window !== "undefined" &&
  "serviceWorker" in navigator &&
  "PushManager" in window &&
  "Notification" in window;

const getRegistration = async (): Promise<ServiceWorkerRegistration> => {
  const existing = await navigator.serviceWorker.getRegistration(SW_URL);
  if (existing) return existing;
  return navigator.serviceWorker.register(SW_URL);
};

export const useBrowserPush = () => {
  const supported = isSupported();
  const [permission, setPermission] = useState<TPermission>(supported ? Notification.permission : "unsupported");
  const [isSubscribed, setIsSubscribed] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const refresh = useCallback(async () => {
    if (!supported) return;
    setPermission(Notification.permission);
    try {
      const reg = await navigator.serviceWorker.getRegistration(SW_URL);
      const sub = reg ? await reg.pushManager.getSubscription() : null;
      setIsSubscribed(!!sub);
    } catch {
      setIsSubscribed(false);
    }
  }, [supported]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const subscribe = useCallback(async () => {
    if (!supported) return false;
    setIsLoading(true);
    try {
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== "granted") return false;

      const reg = await getRegistration();
      await navigator.serviceWorker.ready;

      const vapid = await pushSubscriptionService.getVapidKey();
      if (!vapid?.public_key) {
        console.warn("VAPID public key not configured on server");
        return false;
      }

      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapid.public_key),
        });
      }
      const keys = extractKeys(sub);
      if (!keys) return false;

      await pushSubscriptionService.registerSubscription({
        endpoint: sub.endpoint,
        keys,
        user_agent: typeof navigator !== "undefined" ? navigator.userAgent : undefined,
      });
      setIsSubscribed(true);
      return true;
    } catch (err) {
      console.error("Failed to subscribe to web push", err);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [supported]);

  const unsubscribe = useCallback(async () => {
    if (!supported) return;
    setIsLoading(true);
    try {
      const reg = await navigator.serviceWorker.getRegistration(SW_URL);
      const sub = reg ? await reg.pushManager.getSubscription() : null;
      if (sub) {
        const endpoint = sub.endpoint;
        try {
          await sub.unsubscribe();
        } catch (e) {
          console.warn("pushManager.unsubscribe failed", e);
        }
        try {
          await pushSubscriptionService.unregisterSubscription(endpoint);
        } catch (e) {
          console.warn("unregister on server failed", e);
        }
      }
      setIsSubscribed(false);
    } finally {
      setIsLoading(false);
    }
  }, [supported]);

  return { supported, permission, isSubscribed, isLoading, subscribe, unsubscribe, refresh };
};
