/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, computed, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import { ClientService } from "@plane/services";
import type { TClient, TClientCompany } from "@plane/types";

export interface IClientStore {
  // observables
  loader: boolean;
  clientMap: Record<string, TClient>;
  // computed
  clients: TClient[];
  activeClients: TClient[];
  // helpers
  getClientById: (clientId: string | null | undefined) => TClient | undefined;
  // actions
  fetchClients: (workspaceSlug: string) => Promise<TClient[]>;
  createClient: (workspaceSlug: string, data: Partial<TClient>) => Promise<TClient>;
  updateClient: (workspaceSlug: string, clientId: string, data: Partial<TClient>) => Promise<TClient>;
  deleteClient: (workspaceSlug: string, clientId: string) => Promise<void>;
  createCompany: (workspaceSlug: string, clientId: string, data: Partial<TClientCompany>) => Promise<TClientCompany>;
  updateCompany: (
    workspaceSlug: string,
    clientId: string,
    companyId: string,
    data: Partial<TClientCompany>
  ) => Promise<TClientCompany>;
  deleteCompany: (workspaceSlug: string, clientId: string, companyId: string) => Promise<void>;
}

export class ClientStore implements IClientStore {
  loader: boolean = false;
  clientMap: Record<string, TClient> = {};

  clientService: ClientService;

  constructor() {
    makeObservable(this, {
      loader: observable.ref,
      clientMap: observable,
      clients: computed,
      activeClients: computed,
      fetchClients: action,
      createClient: action,
      updateClient: action,
      deleteClient: action,
      createCompany: action,
      updateCompany: action,
      deleteCompany: action,
    });
    this.clientService = new ClientService();
  }

  get clients(): TClient[] {
    return Object.values(this.clientMap).toSorted((a, b) => a.name.localeCompare(b.name, "pt-BR"));
  }

  get activeClients(): TClient[] {
    return this.clients.filter((client) => client.is_active);
  }

  getClientById = computedFn((clientId: string | null | undefined) =>
    clientId ? this.clientMap[clientId] : undefined
  );

  fetchClients = async (workspaceSlug: string): Promise<TClient[]> => {
    try {
      runInAction(() => {
        this.loader = true;
      });
      const response = await this.clientService.list(workspaceSlug);
      runInAction(() => {
        this.clientMap = response.reduce<Record<string, TClient>>((acc, client) => {
          acc[client.id] = client;
          return acc;
        }, {});
        this.loader = false;
      });
      return response;
    } catch (error) {
      runInAction(() => {
        this.loader = false;
      });
      throw error;
    }
  };

  createClient = async (workspaceSlug: string, data: Partial<TClient>): Promise<TClient> => {
    const response = await this.clientService.create(workspaceSlug, data);
    runInAction(() => {
      this.clientMap[response.id] = response;
    });
    return response;
  };

  updateClient = async (workspaceSlug: string, clientId: string, data: Partial<TClient>): Promise<TClient> => {
    const previous = this.clientMap[clientId];
    runInAction(() => {
      if (previous) this.clientMap[clientId] = { ...previous, ...data } as TClient;
    });
    try {
      const response = await this.clientService.update(workspaceSlug, clientId, data);
      runInAction(() => {
        this.clientMap[clientId] = { ...response, companies: previous?.companies ?? response.companies };
      });
      return response;
    } catch (error) {
      runInAction(() => {
        if (previous) this.clientMap[clientId] = previous;
      });
      throw error;
    }
  };

  deleteClient = async (workspaceSlug: string, clientId: string): Promise<void> => {
    const previous = this.clientMap[clientId];
    runInAction(() => {
      delete this.clientMap[clientId];
    });
    try {
      await this.clientService.destroy(workspaceSlug, clientId);
    } catch (error) {
      runInAction(() => {
        if (previous) this.clientMap[clientId] = previous;
      });
      throw error;
    }
  };

  createCompany = async (
    workspaceSlug: string,
    clientId: string,
    data: Partial<TClientCompany>
  ): Promise<TClientCompany> => {
    const response = await this.clientService.createCompany(workspaceSlug, clientId, data);
    runInAction(() => {
      const client = this.clientMap[clientId];
      if (client) client.companies = [...client.companies, response];
    });
    return response;
  };

  updateCompany = async (
    workspaceSlug: string,
    clientId: string,
    companyId: string,
    data: Partial<TClientCompany>
  ): Promise<TClientCompany> => {
    const response = await this.clientService.updateCompany(workspaceSlug, clientId, companyId, data);
    runInAction(() => {
      const client = this.clientMap[clientId];
      if (client) client.companies = client.companies.map((company) => (company.id === companyId ? response : company));
    });
    return response;
  };

  deleteCompany = async (workspaceSlug: string, clientId: string, companyId: string): Promise<void> => {
    const client = this.clientMap[clientId];
    const previous = client?.companies ?? [];
    runInAction(() => {
      if (client) client.companies = previous.filter((company) => company.id !== companyId);
    });
    try {
      await this.clientService.destroyCompany(workspaceSlug, clientId, companyId);
    } catch (error) {
      runInAction(() => {
        if (client) client.companies = previous;
      });
      throw error;
    }
  };
}
