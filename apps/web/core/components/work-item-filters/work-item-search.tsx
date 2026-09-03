/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Search, X } from "lucide-react";
// i18n
import { useTranslation } from "@plane/i18n";
// helpers
import { cn } from "@plane/utils";
// hooks
import useDebounce from "@/hooks/use-debounce";

/**
 * Minimal structural contract satisfied by every issue filter store (project,
 * project-views, cycle, module). Lets this component stay agnostic of which store
 * it drives. See mods/busca-inline-view.md.
 */
export interface IWorkItemSearchFilterStore {
  getSearchQuery: (entityId: string) => string;
  updateSearchQuery: (workspaceSlug: string, entityId: string, query: string) => void;
}

type TWorkItemSearchProps = {
  filterStore: IWorkItemSearchFilterStore;
  workspaceSlug: string;
  entityId: string;
  className?: string;
};

/**
 * Inline search box rendered next to the filters row. Filters the current
 * view/project/cycle/module by work-item name, parent path (any ancestor) and
 * identifier (e.g. "PROJ-123"). The query is ephemeral: it triggers a debounced
 * server refetch but is never persisted to the saved view.
 */
export const WorkItemSearch = observer(function WorkItemSearch(props: TWorkItemSearchProps) {
  const { filterStore, workspaceSlug, entityId, className } = props;
  // i18n
  const { t } = useTranslation();
  // local input state, debounced before it reaches the store / triggers a refetch
  const [value, setValue] = useState(() => filterStore.getSearchQuery(entityId));
  const debouncedValue = useDebounce(value, 300);

  useEffect(() => {
    // refetch only when the debounced value actually differs from the store's
    // (skips the no-op refetch on mount and avoids loops)
    if (debouncedValue !== filterStore.getSearchQuery(entityId)) {
      filterStore.updateSearchQuery(workspaceSlug, entityId, debouncedValue);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedValue]);

  return (
    <div
      className={cn("flex h-7 w-56 items-center gap-1.5 rounded-sm border border-subtle bg-surface-2 px-2", className)}
    >
      <Search className="h-3.5 w-3.5 flex-shrink-0 text-tertiary" aria-hidden="true" />
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape" && value !== "") {
            e.stopPropagation();
            setValue("");
          }
        }}
        placeholder={t("issue.search.placeholder")}
        className="text-xs w-full bg-transparent text-secondary placeholder:text-placeholder focus:outline-none"
      />
      {value !== "" && (
        <button
          type="button"
          onClick={() => setValue("")}
          className="flex-shrink-0 text-tertiary transition-colors hover:text-secondary"
          aria-label={t("issue.search.clear")}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
});
