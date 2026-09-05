/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// components
import { ClientDetailRoot } from "@/components/clients";

const ClientDetailPage = observer(function ClientDetailPage() {
  const { clientId } = useParams();
  if (!clientId) return null;
  return <ClientDetailRoot clientId={clientId.toString()} />;
});

export default ClientDetailPage;
