/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Usage:
//   tsx packages/i18n/scripts/sync-check.ts          # Report only
//   tsx packages/i18n/scripts/sync-check.ts --ci     # Exit 1 if issues found
//
// FORK: upstream exige que os 19 locales estejam 100% sincronizados com `en`.
// Este fork e usado internamente apenas em portugues (ver SUPPORTED_LANGUAGES em
// src/constants/language.ts), entao so `pt-BR` reprova o CI. Os demais locales
// continuam sendo relatados, para nao esconder o gap caso um dia se queira
// contribuir de volta para o upstream.

import type { LocaleData } from "./lib/locale-io.js";
import { LOCALES_DIR, listLocales, loadLocale } from "./lib/locale-io.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * FORK: locales cujo gap reprova o CI. Os que ficam de fora aparecem no relatorio
 * como informativo. Para voltar ao comportamento do upstream, use `null`.
 */
const ENFORCED_LOCALES: string[] | null = ["pt-BR"];

function isEnforced(locale: string): boolean {
  return ENFORCED_LOCALES === null || ENFORCED_LOCALES.includes(locale);
}

/** Format a number with commas (e.g. 7712 -> "7,712"). */
function fmt(n: number): string {
  return n.toLocaleString("en-US");
}

// ---------------------------------------------------------------------------
// Checks
// ---------------------------------------------------------------------------

interface CollisionEntry {
  key: string;
  files: string[];
}

/** Cross-namespace collision check: same flattened key in multiple namespace files. */
function findCollisions(localeData: LocaleData): CollisionEntry[] {
  const keyToFiles = new Map<string, string[]>();
  for (const ns of localeData.namespaces) {
    for (const key of ns.keys) {
      const existing = keyToFiles.get(key);
      if (existing) {
        existing.push(`${ns.name}.json`);
      } else {
        keyToFiles.set(key, [`${ns.name}.json`]);
      }
    }
  }

  const collisions: CollisionEntry[] = [];
  for (const [key, files] of keyToFiles) {
    if (files.length > 1) {
      collisions.push({ key, files });
    }
  }
  return collisions.toSorted((a, b) => a.key.localeCompare(b.key));
}

interface PathConflict {
  leaf: string;
  branch: string;
}

/** Path conflict check: a key is both a leaf AND a prefix of another key. */
function findPathConflicts(localeData: LocaleData): PathConflict[] {
  const allKeysArray = [...localeData.allKeys].toSorted();
  const conflicts: PathConflict[] = [];

  // Build a set of all prefixes used in the keys
  const prefixes = new Set<string>();
  for (const key of allKeysArray) {
    const parts = key.split(".");
    for (let i = 1; i < parts.length; i++) {
      prefixes.add(parts.slice(0, i).join("."));
    }
  }

  // A conflict exists when a leaf key is also a prefix
  for (const key of allKeysArray) {
    if (prefixes.has(key)) {
      // Find one example of a key that extends this prefix
      const extending = allKeysArray.find((k) => k.startsWith(key + "."));
      if (extending) {
        conflicts.push({ leaf: key, branch: extending });
      }
    }
  }

  return conflicts;
}

interface LocaleComparison {
  locale: string;
  totalKeys: number;
  missingKeys: string[];
  staleKeys: string[];
  coverage: number; // 0-100
}

function compareToEnglish(enKeys: Set<string>, other: LocaleData): LocaleComparison {
  const missingKeys: string[] = [];
  const staleKeys: string[] = [];

  for (const key of enKeys) {
    if (!other.allKeys.has(key)) {
      missingKeys.push(key);
    }
  }

  for (const key of other.allKeys) {
    if (!enKeys.has(key)) {
      staleKeys.push(key);
    }
  }

  const coverage = enKeys.size > 0 ? ((enKeys.size - missingKeys.length) / enKeys.size) * 100 : 100;

  return {
    locale: other.locale,
    totalKeys: other.allKeys.size,
    missingKeys: missingKeys.toSorted(),
    staleKeys: staleKeys.toSorted(),
    coverage,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  const ciMode = process.argv.includes("--ci");

  // Discover all locale directories
  const localeDirs = listLocales();

  if (!localeDirs.includes("en")) {
    console.error("ERROR: English locale (en) not found in", LOCALES_DIR);
    process.exit(1);
  }

  // Load all locales
  const localeDataMap = new Map<string, LocaleData>();
  for (const locale of localeDirs) {
    localeDataMap.set(locale, loadLocale(locale));
  }

  const enData = localeDataMap.get("en")!;

  // Run checks
  const collisions = findCollisions(enData);
  const pathConflicts = findPathConflicts(enData);

  const comparisons: LocaleComparison[] = [];
  for (const locale of localeDirs) {
    if (locale === "en") continue;
    comparisons.push(compareToEnglish(enData.allKeys, localeDataMap.get(locale)!));
  }

  // -------------------------------------------------------------------------
  // Print report
  // -------------------------------------------------------------------------

  let hasFailure = false;

  console.log("\n=== Sync Check Results ===\n");
  console.log(`  en:    ${fmt(enData.allKeys.size)} keys (source)\n`);

  for (const comp of comparisons) {
    const enforced = isEnforced(comp.locale);
    const inSync = comp.missingKeys.length === 0;
    // ✓ ok | ✗ reprova o CI | · gap conhecido, nao exigido neste fork
    const status = inSync ? "✓" : enforced ? "✗" : "·";
    const missingStr = comp.missingKeys.length > 0 ? ` — ${fmt(comp.missingKeys.length)} missing` : "";
    const staleStr = comp.staleKeys.length > 0 ? `, ${fmt(comp.staleKeys.length)} stale` : "";
    const notEnforcedStr = !inSync && !enforced ? " (nao exigido neste fork)" : "";
    console.log(
      `  ${status} ${comp.locale.padEnd(10)} ${fmt(comp.totalKeys)} keys (${comp.coverage.toFixed(1)}%)${missingStr}${staleStr}${notEnforcedStr}`
    );
    if (comp.missingKeys.length > 0 && enforced) {
      hasFailure = true;
    }
  }

  // Cross-namespace collisions
  if (collisions.length > 0) {
    hasFailure = true;
    console.log("\nCROSS-NAMESPACE COLLISIONS:");
    for (const c of collisions) {
      console.log(`  ✗ "${c.key}" exists in: ${c.files.join(", ")}`);
    }
  }

  // Path conflicts
  if (pathConflicts.length > 0) {
    hasFailure = true;
    console.log("\nPATH CONFLICTS:");
    for (const pc of pathConflicts) {
      console.log(`  ✗ "${pc.leaf}" is a leaf but "${pc.branch}" extends it`);
    }
  }

  // Missing keys detail
  const withMissing = comparisons.filter((c) => c.missingKeys.length > 0 && isEnforced(c.locale));
  if (withMissing.length > 0) {
    console.log("\n--- Missing Keys Detail ---\n");
    for (const comp of withMissing) {
      console.log(`${comp.locale} (${fmt(comp.missingKeys.length)} missing):`);
      const show = comp.missingKeys.slice(0, 20);
      for (const key of show) {
        console.log(`  - ${key}`);
      }
      if (comp.missingKeys.length > 20) {
        console.log(`  ... and ${fmt(comp.missingKeys.length - 20)} more`);
      }
      console.log();
    }
  }

  // Stale keys detail
  const withStale = comparisons.filter((c) => c.staleKeys.length > 0 && isEnforced(c.locale));
  if (withStale.length > 0) {
    console.log("--- Stale Keys Detail ---\n");
    for (const comp of withStale) {
      console.log(`${comp.locale} (${fmt(comp.staleKeys.length)} stale):`);
      const show = comp.staleKeys.slice(0, 20);
      for (const key of show) {
        console.log(`  - ${key}`);
      }
      if (comp.staleKeys.length > 20) {
        console.log(`  ... and ${fmt(comp.staleKeys.length - 20)} more`);
      }
      console.log();
    }
  }

  // CI exit code
  if (ciMode && hasFailure) {
    console.log("CI mode: exiting with code 1 due to missing keys, collisions, or path conflicts.");
    process.exit(1);
  }

  if (!hasFailure) {
    console.log(
      ENFORCED_LOCALES === null
        ? "\nAll locales are in sync with English. No issues found."
        : `\nLocales exigidos (${ENFORCED_LOCALES.join(", ")}) em sincronia com o ingles. Nenhum problema bloqueante.`
    );
  }
}

try {
  main();
} catch (err) {
  console.error("Sync check failed:", err);
  process.exit(1);
}
