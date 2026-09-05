/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { Plus, X } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TClient, TClientCompany } from "@plane/types";
import { EModalPosition, EModalWidth, Input, ModalCore, ToggleSwitch } from "@plane/ui";
// hooks
import { useClient } from "@/hooks/store/use-client";
// local imports
import { formatCnpj, isValidCnpj, normalizeCnpj } from "./cnpj";

type TCompanyRow = {
  /** Ausente nas empresas ainda nao persistidas. */
  id?: string;
  name: string;
  cnpj: string;
};

type TClientFormValues = {
  name: string;
  is_active: boolean;
  companies: TCompanyRow[];
};

type Props = {
  isOpen: boolean;
  onClose: () => void;
  clientId?: string;
};

const EMPTY_COMPANY: TCompanyRow = { name: "", cnpj: "" };

const defaultValues: TClientFormValues = { name: "", is_active: true, companies: [EMPTY_COMPANY] };

/** Extrai a primeira mensagem util de um erro devolvido pelo DRF. */
const firstErrorMessage = (error: unknown): string | undefined => {
  if (!error || typeof error !== "object") return undefined;
  for (const key of ["name", "cnpj", "detail", "error"]) {
    const value = (error as Record<string, unknown>)[key];
    if (typeof value === "string") return value;
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return undefined;
};

export const ClientFormModal = observer(function ClientFormModal(props: Props) {
  const { isOpen, onClose, clientId } = props;
  // router
  const { workspaceSlug } = useParams();
  // hooks
  const { t } = useTranslation();
  const { getClientById, createClient, updateClient, createCompany, updateCompany, deleteCompany } = useClient();
  // derived values
  const client = getClientById(clientId);
  const isEditing = Boolean(clientId);
  // form
  const {
    control,
    formState: { errors, isSubmitting },
    handleSubmit,
    reset,
  } = useForm<TClientFormValues>({ defaultValues });
  const { fields, append, remove } = useFieldArray({ control, name: "companies" });

  useEffect(() => {
    if (!isOpen) return;
    reset(
      client
        ? {
            name: client.name,
            is_active: client.is_active,
            companies: client.companies.map((company) => ({
              id: company.id,
              name: company.name,
              cnpj: formatCnpj(company.cnpj),
            })),
          }
        : defaultValues
    );
  }, [isOpen, client, reset]);

  const handleClose = () => {
    onClose();
    setTimeout(() => reset(defaultValues), 350);
  };

  const handleFormSubmit = async (data: TClientFormValues) => {
    if (!workspaceSlug) return;
    const slug = workspaceSlug.toString();
    const rows = data.companies.filter((company) => company.name.trim() !== "" || normalizeCnpj(company.cnpj) !== "");

    try {
      if (isEditing && client) {
        // snapshot: deleteCompany altera client.companies e o diff abaixo precisa da lista original
        const previousCompanies = [...client.companies];
        await updateClient(slug, client.id, { name: data.name, is_active: data.is_active });
        const keptIds = new Set(rows.map((row) => row.id).filter(Boolean));
        // remove as empresas que sumiram da lista
        await Promise.all(
          previousCompanies
            .filter((company) => !keptIds.has(company.id))
            .map((company) => deleteCompany(slug, client.id, company.id))
        );
        await Promise.all(
          rows.map((row) => {
            const payload: Partial<TClientCompany> = { name: row.name, cnpj: normalizeCnpj(row.cnpj) };
            if (!row.id) return createCompany(slug, client.id, payload);
            const previous = previousCompanies.find((company) => company.id === row.id);
            if (previous && (previous.name !== payload.name || previous.cnpj !== payload.cnpj))
              return updateCompany(slug, client.id, row.id, payload);
            return Promise.resolve();
          })
        );
      } else {
        const payload: Partial<TClient> = { name: data.name };
        const created = await createClient(slug, payload);
        await Promise.all(
          rows.map((row) => createCompany(slug, created.id, { name: row.name, cnpj: normalizeCnpj(row.cnpj) }))
        );
      }
      handleClose();
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("common.error.label"),
        message: firstErrorMessage(error) ?? t("common.error.message"),
      });
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.TOP} width={EModalWidth.XXL}>
      <form onSubmit={handleSubmit(handleFormSubmit)}>
        <div className="space-y-4 p-5">
          <h3 className="text-18 font-medium text-secondary">
            {isEditing ? t("clients.edit_client") : t("clients.new_client")}
          </h3>

          <div className="space-y-1">
            <Controller
              control={control}
              name="name"
              rules={{
                required: t("clients.name_is_required"),
                validate: (value) => value.trim() !== "" || t("clients.name_is_required"),
              }}
              render={({ field: { value, onChange } }) => (
                <Input
                  type="text"
                  value={value}
                  onChange={onChange}
                  hasError={Boolean(errors.name)}
                  placeholder={t("clients.name")}
                  className="w-full text-14"
                />
              )}
            />
            {errors.name && <span className="text-11 text-danger-primary">{errors.name.message}</span>}
          </div>

          <div className="space-y-2">
            <span className="text-13 font-medium text-secondary">{t("clients.companies")}</span>
            {fields.map((field, index) => (
              <div key={field.id} className="flex items-start gap-2">
                <div className="flex-1 space-y-1">
                  <Controller
                    control={control}
                    name={`companies.${index}.name`}
                    rules={{ validate: (value) => value.trim() !== "" || t("clients.company_name_is_required") }}
                    render={({ field: { value, onChange } }) => (
                      <Input
                        type="text"
                        value={value}
                        onChange={onChange}
                        hasError={Boolean(errors.companies?.[index]?.name)}
                        placeholder={t("clients.company_name")}
                        className="w-full text-14"
                      />
                    )}
                  />
                  {errors.companies?.[index]?.name && (
                    <span className="text-11 text-danger-primary">{errors.companies[index]?.name?.message}</span>
                  )}
                </div>
                <div className="w-52 space-y-1">
                  <Controller
                    control={control}
                    name={`companies.${index}.cnpj`}
                    rules={{ validate: (value) => isValidCnpj(value) || t("clients.invalid_cnpj") }}
                    render={({ field: { value, onChange } }) => (
                      <Input
                        type="text"
                        value={value}
                        onChange={(event) => onChange(formatCnpj(event.target.value))}
                        hasError={Boolean(errors.companies?.[index]?.cnpj)}
                        placeholder="00.000.000/0000-00"
                        className="w-full text-14"
                      />
                    )}
                  />
                  {errors.companies?.[index]?.cnpj && (
                    <span className="text-11 text-danger-primary">{errors.companies[index]?.cnpj?.message}</span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => remove(index)}
                  disabled={fields.length === 1}
                  className="mt-2 text-tertiary hover:text-secondary disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={t("clients.remove_company")}
                >
                  <X className="size-4" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => append({ ...EMPTY_COMPANY })}
              className="flex items-center gap-1 text-13 font-medium text-primary hover:underline"
            >
              <Plus className="size-3.5" />
              {t("clients.add_company")}
            </button>
          </div>

          {isEditing && (
            <Controller
              control={control}
              name="is_active"
              render={({ field: { value, onChange } }) => (
                <div className="flex items-center gap-2">
                  <ToggleSwitch value={value} onChange={onChange} />
                  <span className="text-13 text-secondary">
                    {value ? t("clients.status.active") : t("clients.status.inactive")}
                  </span>
                </div>
              )}
            />
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-strong px-5 py-4">
          <Button variant="secondary" size="sm" onClick={handleClose} type="button">
            {t("common.cancel")}
          </Button>
          <Button variant="primary" size="sm" type="submit" loading={isSubmitting}>
            {isEditing ? t("common.update") : t("common.create")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
