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
import { ChevronLeft } from "lucide-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Loader } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { PageHead } from "@/components/core/page-title";
// hooks
import { useClient } from "@/hooks/store/use-client";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { ClientFormModal } from "./client-form-modal";
import { formatCnpj } from "./cnpj";

type Props = {
  clientId: string;
};

export const ClientDetailRoot = observer(function ClientDetailRoot(props: Props) {
  const { clientId } = props;
  // router
  const { workspaceSlug: routerWorkspaceSlug } = useParams();
  const workspaceSlug = routerWorkspaceSlug?.toString();
  // hooks
  const { t } = useTranslation();
  const { getClientById, loader, fetchClients } = useClient();
  const { allowPermissions } = useUserPermissions();
  // states
  const [isModalOpen, setIsModalOpen] = useState(false);

  // o mesmo fetch da lista, para que o acesso direto pela URL popule o clientMap
  useSWR(workspaceSlug ? `WORKSPACE_CLIENTS_${workspaceSlug}` : null, () =>
    workspaceSlug ? fetchClients(workspaceSlug) : null
  );

  // derived values
  const client = getClientById(clientId);
  const canWrite = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE,
    workspaceSlug
  );

  if (!client) {
    if (loader)
      return (
        <Loader className="space-y-2 px-page-x py-4">
          <Loader.Item height="40px" />
          <Loader.Item height="40px" />
        </Loader>
      );
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <p className="text-14 text-tertiary">{t("clients.not_found")}</p>
        <Link href={`/${workspaceSlug}/clients`} className="text-13 font-medium text-primary hover:underline">
          {t("clients.back_to_list")}
        </Link>
      </div>
    );
  }

  return (
    <>
      <PageHead title={client.name} />
      <ClientFormModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} clientId={clientId} />
      <div className="flex h-full w-full flex-col overflow-y-auto px-page-x py-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Link href={`/${workspaceSlug}/clients`} className="text-tertiary hover:text-secondary">
              <ChevronLeft className="size-4" />
            </Link>
            <h2 className="text-18 font-medium text-secondary">{client.name}</h2>
            <span
              className={cn("rounded-full px-2 py-0.5 text-11 font-medium", {
                "bg-success-component-surface-dark text-success-text-medium": client.is_active,
                "bg-neutral-component-surface-dark text-tertiary": !client.is_active,
              })}
            >
              {client.is_active ? t("clients.status.active") : t("clients.status.inactive")}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {/* o layout global de work items e acoplado ao globalViewId da rota, entao em vez de embutir
                a lista aqui, mandamos para a view "all-issues" ja filtrada pela query string (routeFilters) */}
            <Link href={`/${workspaceSlug}/workspace-views/all-issues/?client=${clientId}`}>
              <Button variant="secondary" size="sm">
                {t("clients.view_issues", { count: client.issue_count })}
              </Button>
            </Link>
            {canWrite && (
              <Button variant="secondary" size="sm" onClick={() => setIsModalOpen(true)}>
                {t("common.actions.edit")}
              </Button>
            )}
          </div>
        </div>

        <div className="mt-6">
          <h3 className="text-14 font-medium text-secondary">{t("clients.companies")}</h3>
          {client.companies.length === 0 ? (
            <p className="mt-2 text-13 text-tertiary">{t("clients.no_companies")}</p>
          ) : (
            <table className="mt-2 w-full text-13">
              <thead className="border-b border-strong text-left text-tertiary">
                <tr>
                  <th className="py-2 font-medium">{t("clients.company_name")}</th>
                  <th className="w-60 py-2 font-medium">{t("clients.cnpj")}</th>
                </tr>
              </thead>
              <tbody>
                {client.companies.map((company) => (
                  <tr key={company.id} className="border-b border-subtle">
                    <td className="py-2.5 text-secondary">{company.name}</td>
                    <td className="py-2.5 text-tertiary">{formatCnpj(company.cnpj)}</td>
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
