/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { usePopper } from "react-popper";
import useSWR from "swr";
import { Building2 } from "lucide-react";
import { Combobox } from "@headlessui/react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { CheckIcon, ChevronDownIcon, SearchIcon } from "@plane/propel/icons";
import { ComboDropDown } from "@plane/ui";
import { cn } from "@plane/utils";
// hooks
import { useClient } from "@/hooks/store/use-client";
import { useDropdown } from "@/hooks/use-dropdown";
import { usePlatformOS } from "@/hooks/use-platform-os";
// local imports
import { DropdownButton } from "./buttons";
import { BUTTON_VARIANTS_WITH_TEXT } from "./constants";
import type { TDropdownProps } from "./types";

type Props = TDropdownProps & {
  button?: ReactNode;
  dropdownArrow?: boolean;
  dropdownArrowClassName?: string;
  onChange: (val: string | null) => void;
  onClose?: () => void;
  value: string | null;
  renderByDefault?: boolean;
};

type TClientOptionsProps = {
  isOpen: boolean;
  referenceElement: HTMLButtonElement | null;
  placement: TDropdownProps["placement"];
};

const ClientOptions = observer(function ClientOptions(props: TClientOptionsProps) {
  const { isOpen, referenceElement, placement } = props;
  // router
  // hooks
  const { t } = useTranslation();
  const { activeClients } = useClient();
  const { isMobile } = usePlatformOS();
  // states
  const [query, setQuery] = useState("");
  const [popperElement, setPopperElement] = useState<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const { styles, attributes } = usePopper(referenceElement, popperElement, {
    placement: placement ?? "bottom-start",
    modifiers: [{ name: "preventOverflow", options: { padding: 12 } }],
  });

  useEffect(() => {
    if (!isOpen) return;
    if (!isMobile) inputRef.current?.focus();
  }, [isOpen, isMobile]);

  const searchInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (query !== "" && e.key === "Escape") {
      e.stopPropagation();
      setQuery("");
    }
  };

  const options = activeClients
    .filter((client) => client.name.toLowerCase().includes(query.toLowerCase()))
    .map((client) => ({ value: client.id as string | null, label: client.name }));
  options.unshift({ value: null, label: t("clients.none") });

  return (
    <Combobox.Options className="fixed z-10" static>
      <div
        className="my-1 w-48 rounded-sm border-[0.5px] border-strong bg-surface-1 px-2 py-2.5 text-11 shadow-raised-200 focus:outline-none"
        ref={setPopperElement}
        style={styles.popper}
        {...attributes.popper}
      >
        <div className="flex items-center gap-1.5 rounded-sm border border-subtle bg-surface-2 px-2">
          <SearchIcon className="h-3.5 w-3.5 text-placeholder" strokeWidth={1.5} />
          <Combobox.Input
            as="input"
            ref={inputRef}
            className="w-full bg-transparent py-1 text-11 text-secondary placeholder:text-placeholder focus:outline-none"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("common.search.label")}
            onKeyDown={searchInputKeyDown}
          />
        </div>
        <div className="mt-2 max-h-48 space-y-1 overflow-y-scroll">
          {options.length > 0 ? (
            options.map((option) => (
              <Combobox.Option
                key={option.value ?? "none"}
                value={option.value}
                className={({ active, selected }) =>
                  `flex w-full cursor-pointer items-center justify-between gap-2 truncate rounded-sm px-1 py-1.5 select-none ${
                    active ? "bg-layer-transparent-hover" : ""
                  } ${selected ? "text-primary" : "text-secondary"}`
                }
              >
                {({ selected }) => (
                  <>
                    <span className="flex flex-grow items-center gap-2 truncate">
                      <Building2 className="size-3 flex-shrink-0" />
                      <span className="flex-grow truncate">{option.label}</span>
                    </span>
                    {selected && <CheckIcon className="h-3.5 w-3.5 flex-shrink-0" />}
                  </>
                )}
              </Combobox.Option>
            ))
          ) : (
            <p className="px-1.5 py-1 text-placeholder italic">{t("common.search.no_matches_found")}</p>
          )}
        </div>
      </div>
    </Combobox.Options>
  );
});

export const ClientDropdown = observer(function ClientDropdown(props: Props) {
  const {
    button,
    buttonClassName,
    buttonContainerClassName,
    buttonVariant,
    className = "",
    disabled = false,
    dropdownArrow = false,
    dropdownArrowClassName = "",
    hideIcon = false,
    onChange,
    onClose,
    placeholder = "",
    placement,
    showTooltip = false,
    tabIndex,
    value,
    renderByDefault = true,
  } = props;
  // router
  const { workspaceSlug } = useParams();
  // hooks
  const { t } = useTranslation();
  const { getClientById, fetchClients } = useClient();
  // states
  const [isOpen, setIsOpen] = useState(false);
  const [referenceElement, setReferenceElement] = useState<HTMLButtonElement | null>(null);
  // refs
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  // sem isto o botao mostra o placeholder mesmo com um cliente vinculado: quem resolve o
  // nome e o clientMap, e ele so era preenchido quando o painel abria. A chave e a mesma
  // usada pelas telas de cliente, entao o SWR deduplica a busca entre todas as instancias.
  useSWR(workspaceSlug ? `WORKSPACE_CLIENTS_${workspaceSlug}` : null, () =>
    workspaceSlug ? fetchClients(workspaceSlug.toString()) : null
  );

  // getClientById tambem resolve clientes inativos, que ficam fora das opcoes mas
  // precisam continuar aparecendo no botao quando ja estao vinculados a tarefa
  const selectedName = value ? (getClientById(value)?.name ?? null) : null;

  const { handleClose, handleKeyDown, handleOnClick } = useDropdown({ dropdownRef, isOpen, onClose, setIsOpen });

  const dropdownOnChange = (val: string | null) => {
    onChange(val);
    handleClose();
  };

  const comboButton = button ? (
    <button
      ref={setReferenceElement}
      type="button"
      className={cn("clickable block h-full w-full outline-none hover:bg-layer-1", buttonContainerClassName)}
      onClick={handleOnClick}
      disabled={disabled}
      tabIndex={tabIndex}
    >
      {button}
    </button>
  ) : (
    <button
      ref={setReferenceElement}
      type="button"
      className={cn(
        "clickable block h-full max-w-full outline-none hover:bg-layer-1",
        {
          "cursor-not-allowed text-secondary": disabled,
          "cursor-pointer": !disabled,
        },
        buttonContainerClassName
      )}
      onClick={handleOnClick}
      disabled={disabled}
      tabIndex={tabIndex}
    >
      <DropdownButton
        className={buttonClassName}
        isActive={isOpen}
        tooltipHeading={t("clients.client")}
        tooltipContent={selectedName ?? placeholder}
        showTooltip={showTooltip}
        variant={buttonVariant}
        renderToolTipByDefault={renderByDefault}
      >
        {!hideIcon && <Building2 className="h-3 w-3 flex-shrink-0" />}
        {BUTTON_VARIANTS_WITH_TEXT.includes(buttonVariant) && (!!selectedName || !!placeholder) && (
          <span className="max-w-40 truncate">{selectedName ?? placeholder}</span>
        )}
        {dropdownArrow && (
          <ChevronDownIcon className={cn("h-2.5 w-2.5 flex-shrink-0", dropdownArrowClassName)} aria-hidden="true" />
        )}
      </DropdownButton>
    </button>
  );

  return (
    // o ComboDropDown ja renderiza um combobox acessivel; o onKeyDown fica no wrapper, igual ao dropdowns/cycle
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <ComboDropDown
      as="div"
      ref={dropdownRef}
      className={cn("h-full", className)}
      value={value}
      onChange={dropdownOnChange}
      disabled={disabled}
      onKeyDown={handleKeyDown}
      button={comboButton}
      renderByDefault={renderByDefault}
    >
      {isOpen && <ClientOptions isOpen={isOpen} referenceElement={referenceElement} placement={placement} />}
    </ComboDropDown>
  );
});
