/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import type { IIssueDisplayFilterOptions, IIssueDisplayProperties } from "@plane/types";
import { cn } from "@plane/utils";
import { shouldRenderColumn } from "@/helpers/issue-filter.helper";
import { WithDisplayPropertiesHOC } from "../properties/with-display-properties-HOC";
import { HeaderColumn } from "./columns/header-column";

interface Props {
  displayProperties: IIssueDisplayProperties;
  property: keyof IIssueDisplayProperties;
  index: number;
  isEstimateEnabled: boolean;
  displayFilters: IIssueDisplayFilterOptions;
  handleDisplayFilterUpdate: (data: Partial<IIssueDisplayFilterOptions>) => void;
  onReorder?: (from: number, to: number) => void;
  isReorderEnabled?: boolean;
  isEpic?: boolean;
}

type DragData = { property: string; index: number };

export const SpreadsheetHeaderColumn = observer(function SpreadsheetHeaderColumn(props: Props) {
  const {
    displayProperties,
    displayFilters,
    property,
    index,
    handleDisplayFilterUpdate,
    onReorder,
    isReorderEnabled = false,
    isEpic = false,
  } = props;

  const tableHeaderCellRef = useRef<HTMLTableCellElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dropEdge, setDropEdge] = useState<"left" | "right" | null>(null);

  const shouldRenderProperty = shouldRenderColumn(property);

  useEffect(() => {
    const element = tableHeaderCellRef.current;
    if (!element || !isReorderEnabled || !onReorder) return;

    return combine(
      draggable({
        element,
        getInitialData: (): DragData => ({ property, index }),
        onDragStart: () => setIsDragging(true),
        onDrop: () => setIsDragging(false),
      }),
      dropTargetForElements({
        element,
        canDrop: ({ source }) => {
          const data = source.data as Partial<DragData>;
          return typeof data.property === "string" && data.property !== property;
        },
        getData: (): DragData => ({ property, index }),
        onDragEnter: ({ source }) => {
          const sourceData = source.data as DragData;
          setDropEdge(sourceData.index < index ? "right" : "left");
        },
        onDragLeave: () => setDropEdge(null),
        onDrop: ({ source }) => {
          setDropEdge(null);
          const sourceData = source.data as DragData;
          if (sourceData.index === index) return;
          onReorder(sourceData.index, index);
        },
      })
    );
  }, [property, index, isReorderEnabled, onReorder]);

  return (
    <WithDisplayPropertiesHOC
      displayProperties={displayProperties}
      displayPropertyKey={property}
      shouldRenderProperty={() => shouldRenderProperty}
    >
      <th
        className={cn(
          "relative h-11 min-w-36 items-center border border-t-0 border-b-0 border-subtle bg-layer-1 py-1 text-13 font-medium",
          {
            "opacity-50": isDragging,
            "cursor-grab": isReorderEnabled,
          }
        )}
        ref={tableHeaderCellRef}
        tabIndex={0}
      >
        {dropEdge === "left" && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 left-0 w-[2px] bg-accent-primary"
          />
        )}
        {dropEdge === "right" && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 right-0 w-[2px] bg-accent-primary"
          />
        )}
        <HeaderColumn
          displayFilters={displayFilters}
          handleDisplayFilterUpdate={handleDisplayFilterUpdate}
          property={property}
          onClose={() => {
            tableHeaderCellRef?.current?.focus();
          }}
          isEpic={isEpic}
        />
      </th>
    </WithDisplayPropertiesHOC>
  );
});
