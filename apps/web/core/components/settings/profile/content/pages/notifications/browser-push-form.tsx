/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { ToggleSwitch } from "@plane/ui";
import { SettingsControlItem } from "@/components/settings/control-item";
import { useBrowserPush } from "@/hooks/use-browser-push";

export const BrowserPushSettingsForm = observer(function BrowserPushSettingsForm() {
  const { supported, permission, isSubscribed, isLoading, subscribe, unsubscribe } = useBrowserPush();

  const handleToggle = async (next: boolean) => {
    if (next) await subscribe();
    else await unsubscribe();
  };

  let description =
    "Receba uma notificação do navegador quando uma tarefa for atribuída a você ou alguém te mencionar — mesmo com o Plane fechado.";
  if (!supported) description = "Seu navegador não suporta notificações push.";
  else if (permission === "denied")
    description = "Permissão de notificação bloqueada. Reabilite nas configurações do site no navegador para ativar.";

  return (
    <div className="flex flex-col gap-y-1">
      <SettingsControlItem
        title="Notificações no navegador"
        description={description}
        control={
          <ToggleSwitch
            value={isSubscribed && permission === "granted"}
            onChange={handleToggle}
            disabled={!supported || permission === "denied" || isLoading}
            size="sm"
          />
        }
      />
    </div>
  );
});
