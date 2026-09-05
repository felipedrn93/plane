/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { Pencil, Search, Trash2 } from "lucide-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CustomMenu, Input, Loader } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { PageHead } from "@/components/core/page-title";
// hooks
import { useClient } from "@/hooks/store/use-client";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { ClientFormModal } from "./client-form-modal";
import { normalizeCnpj } from "./cnpj";

export const ClientsListRoot = observer(function ClientsListRoot() {
  // router
  const { workspaceSlug: routerWorkspaceSlug } = useParams();
  const workspaceSlug = routerWorkspaceSlug?.toString();
  // hooks
  const { t } = useTranslation();
  const { clients, loader, fetchClients, updateClient, deleteClient } = useClient();
  const { allowPermissions } = useUserPermissions();
  // states
  const [searchQuery, setSearchQuery] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [modalClientId, setModalClientId] = useState<string | undefined>(undefined);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useSWR(workspaceSlug ? `WORKSPACE_CLIENTS_${workspaceSlug}` : null, () =>
    workspaceSlug ? fetchClients(workspaceSlug) : null
  );

  // derived values
  const canWrite = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE,
    workspaceSlug
  );
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const normalizedQueryDigits = normalizeCnpj(searchQuery);
  const filteredClients = clients.filter((client) => {
    if (!client.is_active && !showInactive) return false;
    if (normalizedQuery === "") return true;
    if (client.name.toLowerCase().includes(normalizedQuery)) return true;
    if (normalizedQueryDigits === "") return false;
    return client.companies.some((company) => normalizeCnpj(company.cnpj).includes(normalizedQueryDigits));
  });

  const handleOpenModal = (clientId?: string) => {
    setModalClientId(clientId);
    setIsModalOpen(true);
  };

  const handleDelete = async (clientId: string) => {
    if (!workspaceSlug) return;
    try {
      await deleteClient(workspaceSlug, clientId);
    } catch (error) {
      const issueCount = (error as { issue_count?: number } | undefined)?.issue_count;
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("common.error.label"),
        message: issueCount ? t("clients.delete_blocked") : t("common.error.message"),
        actionItems: issueCount ? (
          <Button variant="link" size="sm" onClick={() => updateClient(workspaceSlug, clientId, { is_active: false })}>
            {t("clients.deactivate")}
          </Button>
        ) : undefined,
      });
    }
  };

  return (
    <>
      <PageHead title={t("clients.title")} />
      <ClientFormModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} clientId={modalClientId} />
      <div className="flex h-full w-full flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-2 px-page-x py-4">
          <div className="flex items-center gap-3">
            <div className="flex w-64 items-center gap-1.5 rounded-md border border-strong px-2">
              <Search className="size-3.5 flex-shrink-0 text-tertiary" />
              <Input
                type="text"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder={t("common.search.label")}
                className="w-full border-none bg-transparent px-0 text-13 focus:ring-0"
              />
            </div>
            <label className="flex cursor-pointer items-center gap-1.5 text-13 text-secondary">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(event) => setShowInactive(event.target.checked)}
              />
              {t("clients.show_inactive")}
            </label>
          </div>
          {canWrite && (
            <Button variant="primary" size="sm" onClick={() => handleOpenModal(undefined)}>
              {t("clients.new_client")}
            </Button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-page-x pb-page-y">
          {loader && clients.length === 0 ? (
            <Loader className="space-y-2">
              <Loader.Item height="40px" />
              <Loader.Item height="40px" />
              <Loader.Item height="40px" />
            </Loader>
          ) : filteredClients.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <p className="text-14 text-tertiary">{t("clients.empty")}</p>
              {canWrite && (
                <Button variant="primary" size="sm" onClick={() => handleOpenModal(undefined)}>
                  {t("clients.new_client")}
                </Button>
              )}
            </div>
          ) : (
            <table className="w-full text-13">
              <thead className="border-b border-strong text-left text-tertiary">
                <tr>
                  <th className="py-2 font-medium">{t("clients.name")}</th>
                  <th className="w-32 py-2 font-medium">{t("clients.companies")}</th>
                  <th className="w-32 py-2 font-medium">{t("clients.issue_count")}</th>
                  <th className="w-32 py-2 font-medium">{t("clients.status.label")}</th>
                  <th className="w-10 py-2" />
                </tr>
              </thead>
              <tbody>
                {filteredClients.map((client) => (
                  <tr key={client.id} className="border-b border-subtle">
                    <td className="py-2.5">
                      <Link
                        href={`/${workspaceSlug}/clients/${client.id}`}
                        className="font-medium text-secondary hover:text-primary"
                      >
                        {client.name}
                      </Link>
                    </td>
                    <td className="py-2.5 text-tertiary">{client.companies.length}</td>
                    <td className="py-2.5 text-tertiary">{client.issue_count}</td>
                    <td className="py-2.5">
                      <span
                        className={cn("rounded-full px-2 py-0.5 text-11 font-medium", {
                          "bg-success-component-surface-dark text-success-text-medium": client.is_active,
                          "bg-neutral-component-surface-dark text-tertiary": !client.is_active,
                        })}
                      >
                        {client.is_active ? t("clients.status.active") : t("clients.status.inactive")}
                      </span>
                    </td>
                    <td className="py-2.5">
                      {canWrite && (
                        <CustomMenu placement="bottom-end" ellipsis closeOnSelect>
                          <CustomMenu.MenuItem
                            onClick={() => handleOpenModal(client.id)}
                            className="flex items-center gap-2"
                          >
                            <Pencil className="size-3 shrink-0" />
                            {t("common.actions.edit")}
                          </CustomMenu.MenuItem>
                          <CustomMenu.MenuItem
                            onClick={() => handleDelete(client.id)}
                            className="text-danger-text-medium flex items-center gap-2"
                          >
                            <Trash2 className="size-3 shrink-0" />
                            {t("common.actions.delete")}
                          </CustomMenu.MenuItem>
                        </CustomMenu>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
});
