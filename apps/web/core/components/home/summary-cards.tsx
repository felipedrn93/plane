/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { AtSign } from "lucide-react";
import useSWR from "swr";
// plane imports
import { ENotificationTab } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { DueDatePropertyIcon, WorkItemsIcon } from "@plane/propel/icons";
import { cn } from "@plane/utils";
// hooks
import { useWorkspaceNotifications } from "@/hooks/store/notifications";
import { useHome } from "@/hooks/store/use-home";
import { useAppRouter } from "@/hooks/use-app-router";

type THomeSummaryCardsProps = {
  workspaceSlug: string;
};

type TSummaryCardProps = {
  count: number | undefined;
  description: string;
  icon: React.ReactNode;
  onClick: () => void;
  tone: "accent" | "danger" | "info";
};

const toneClasses: Record<TSummaryCardProps["tone"], string> = {
  accent: "bg-accent-primary/10 text-accent-primary",
  danger: "bg-danger-primary/10 text-danger-primary",
  info: "bg-blue-500/10 text-blue-500",
};

function SummaryCard({ count, description, icon, onClick, tone }: TSummaryCardProps) {
  return (
    <button
      type="button"
      className="group focus-visible:outline-accent-primary flex min-h-28 w-full items-center gap-4 rounded-lg border border-subtle bg-surface-1 p-4 text-left transition-colors hover:border-strong hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
      onClick={onClick}
    >
      <span className={cn("grid size-10 flex-shrink-0 place-items-center rounded-lg", toneClasses[tone])}>{icon}</span>
      <span className="min-w-0">
        <span className="block text-24 leading-7 font-semibold text-primary">{count ?? "—"}</span>
        <span className="mt-1 block text-13 font-medium text-secondary group-hover:text-primary">{description}</span>
      </span>
    </button>
  );
}

export const HomeSummaryCards = observer(function HomeSummaryCards({ workspaceSlug }: THomeSummaryCardsProps) {
  const router = useAppRouter();
  const { t } = useTranslation();
  const { homeSummary, fetchHomeSummary } = useHome();
  const { unreadNotificationsCount, getUnreadNotificationsCount, setCurrentNotificationTab } =
    useWorkspaceNotifications();

  useSWR(`WORKSPACE_HOME_SUMMARY_${workspaceSlug}`, () => fetchHomeSummary(workspaceSlug), {
    revalidateOnFocus: true,
  });
  useSWR(`WORKSPACE_UNREAD_NOTIFICATION_COUNT_${workspaceSlug}`, () => getUnreadNotificationsCount(workspaceSlug));

  const openView = (view: "assigned-open" | "assigned-overdue") =>
    router.push(`/${workspaceSlug}/workspace-views/${view}`);

  const openMentions = () => {
    setCurrentNotificationTab(ENotificationTab.MENTIONS);
    router.push(`/${workspaceSlug}/notifications`);
  };

  return (
    <section aria-label={t("home.summary.title")} className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
      <SummaryCard
        count={homeSummary?.assigned_open_count}
        description={t("home.summary.assigned_open")}
        icon={<WorkItemsIcon className="size-5" />}
        onClick={() => openView("assigned-open")}
        tone="accent"
      />
      <SummaryCard
        count={homeSummary?.assigned_overdue_count}
        description={t("home.summary.assigned_overdue")}
        icon={<DueDatePropertyIcon className="size-5" />}
        onClick={() => openView("assigned-overdue")}
        tone="danger"
      />
      <SummaryCard
        count={unreadNotificationsCount.mention_unread_notifications_count}
        description={t("home.summary.unread_mentions")}
        icon={<AtSign className="size-5" />}
        onClick={openMentions}
        tone="info"
      />
    </section>
  );
});
