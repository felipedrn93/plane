/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TClient, TClientCompany } from "@plane/types";
// api service
import { APIService } from "../api.service";

/**
 * Service class for managing workspace clients and their companies.
 * @extends {APIService}
 */
export class ClientService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  async list(workspaceSlug: string): Promise<TClient[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/clients/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, data: Partial<TClient>): Promise<TClient> {
    return this.post(`/api/workspaces/${workspaceSlug}/clients/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(workspaceSlug: string, clientId: string, data: Partial<TClient>): Promise<TClient> {
    return this.patch(`/api/workspaces/${workspaceSlug}/clients/${clientId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async destroy(workspaceSlug: string, clientId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/clients/${clientId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createCompany(workspaceSlug: string, clientId: string, data: Partial<TClientCompany>): Promise<TClientCompany> {
    return this.post(`/api/workspaces/${workspaceSlug}/clients/${clientId}/companies/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateCompany(
    workspaceSlug: string,
    clientId: string,
    companyId: string,
    data: Partial<TClientCompany>
  ): Promise<TClientCompany> {
    return this.patch(`/api/workspaces/${workspaceSlug}/clients/${clientId}/companies/${companyId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async destroyCompany(workspaceSlug: string, clientId: string, companyId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/clients/${clientId}/companies/${companyId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
