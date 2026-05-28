/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/* eslint-disable no-useless-catch */

import { API_BASE_URL } from "@plane/constants";
// services
import { APIService } from "@/services/api.service";

export type TPushSubscriptionPayload = {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  user_agent?: string;
};

export class PushSubscriptionService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getVapidKey(): Promise<{ public_key: string } | undefined> {
    try {
      const { data } = await this.get(`/api/users/me/push-subscriptions/vapid-key/`);
      return data || undefined;
    } catch (error) {
      throw error;
    }
  }

  async registerSubscription(payload: TPushSubscriptionPayload): Promise<unknown> {
    try {
      const { data } = await this.post(`/api/users/me/push-subscriptions/`, payload);
      return data;
    } catch (error) {
      throw error;
    }
  }

  async unregisterSubscription(endpoint: string): Promise<unknown> {
    try {
      const { data } = await this.delete(`/api/users/me/push-subscriptions/`, { endpoint });
      return data;
    } catch (error) {
      throw error;
    }
  }
}

const pushSubscriptionService = new PushSubscriptionService();
export default pushSubscriptionService;
