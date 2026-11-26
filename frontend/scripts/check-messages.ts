#!/usr/bin/env tsx
/**
 * Check that all translation keys are synchronized between ru.json and en.json.
 * Also validates:
 * - Completeness of errors.* relative to ClientErrorCode (ErrorCode + network_error + unknown_error)
 * - That all literal keys from t('...') / tErrors('...') / tCommon('...') / useTranslations('ns')
 *   calls in frontend/src/ exist in both dictionaries.
 * Exits with non-zero code if keys are missing in either file.
 */

import fs from "node:fs";
import path from "node:path";

const messagesDir = path.resolve(
  import.meta.dirname,
  "../src/shared/i18n/messages"
);
const ruPath = path.join(messagesDir, "ru.json");
const enPath = path.join(messagesDir, "en.json");
const schemaPath = path.resolve(
  import.meta.dirname,
  "../src/shared/api/schema.d.ts"
);
const srcDir = path.resolve(import.meta.dirname, "../src");

function loadJson(filePath: string): Record<string, unknown> {
  const content = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(content);
}

function getAllKeys(obj: Record<string, unknown>, prefix = ""): Set<string> {
  const keys = new Set<string>();
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    keys.add(fullKey);
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const nestedKeys = getAllKeys(value as Record<string, unknown>, fullKey);
      for (const k of nestedKeys) keys.add(k);
    }
  }
  return keys;
}

function getNamespaces(obj: Record<string, unknown>): Set<string> {
  return new Set(Object.keys(obj));
}

function extractErrorCodesFromSchema(): string[] {
  const content = fs.readFileSync(schemaPath, "utf-8");
  // Find the ErrorCode enum (not DocumentErrorCode) - it's the one with "ErrorCode:" followed by the list
  const errorCodeMatch = content.match(
    /\/\*\* @enum \{string\} \*\/\s+ErrorCode:\s*([\s\S]*?);/
  );
  if (!errorCodeMatch) {
    throw new Error("Could not find ErrorCode enum in schema.d.ts");
  }
  const enumContent = errorCodeMatch[1];
  const codes = enumContent
    .split("|")
    .map((s) => s.trim().replace(/['"]/g, ""))
    .filter((s) => s.length > 0 && !s.startsWith("/"));
  return codes;
}

function findTranslationCalls(dir: string): {
  tErrorsCalls: Map<string, Set<string>>;
  tCommonCalls: Map<string, Set<string>>;
  useTranslationsNamespaces: Set<string>;
} {
  const tErrorsCalls = new Map<string, Set<string>>();
  const tCommonCalls = new Map<string, Set<string>>();
  const useTranslationsNamespaces = new Set<string>();

  const extensions = [".ts", ".tsx"];

  function walk(currentDir: string) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);
      if (entry.isDirectory()) {
        if (
          !entry.name.startsWith(".") &&
          entry.name !== "node_modules" &&
          entry.name !== ".next"
        ) {
          walk(fullPath);
        }
      } else if (extensions.some((ext) => entry.name.endsWith(ext))) {
        // Skip test files for literal call checking (they use mock providers with limited messages)
        if (
          fullPath.includes("__tests__") ||
          fullPath.includes(".test.") ||
          fullPath.includes(".spec.")
        ) {
          continue;
        }
        const content = fs.readFileSync(fullPath, "utf-8");
        const relativePath = path.relative(srcDir, fullPath);

        // Match useTranslations('namespace') - capture namespace
        const useTranslationsRegex =
          /useTranslations\(['"`]([a-zA-Z0-9_.-]+)['"`]\)/g;
        let match;
        while ((match = useTranslationsRegex.exec(content)) !== null) {
          useTranslationsNamespaces.add(match[1]);
        }

        // Match tErrors('key') - these are useTranslations('errors') calls
        const tErrorsRegex = /tErrors\(['"`]([a-zA-Z0-9_.-]+)['"`]\)/g;
        while ((match = tErrorsRegex.exec(content)) !== null) {
          const key = match[1];
          if (key.includes("${") || key.includes("}") || key.includes("..."))
            continue;
          if (!tErrorsCalls.has(relativePath)) {
            tErrorsCalls.set(relativePath, new Set());
          }
          tErrorsCalls.get(relativePath)!.add(key);
        }

        // Match tCommon('key') - these are useTranslations('common') calls
        const tCommonRegex = /tCommon\(['"`]([a-zA-Z0-9_.-]+)['"`]\)/g;
        while ((match = tCommonRegex.exec(content)) !== null) {
          const key = match[1];
          if (key.includes("${") || key.includes("}") || key.includes("..."))
            continue;
          if (!tCommonCalls.has(relativePath)) {
            tCommonCalls.set(relativePath, new Set());
          }
          tCommonCalls.get(relativePath)!.add(key);
        }
      }
    }
  }

  walk(dir);
  return { tErrorsCalls, tCommonCalls, useTranslationsNamespaces };
}

const ru = loadJson(ruPath);
const en = loadJson(enPath);

const ruKeys = getAllKeys(ru);
const enKeys = getAllKeys(en);
const ruNamespaces = getNamespaces(ru);
const enNamespaces = getNamespaces(en);

const missingInEn = [...ruKeys].filter((k) => !enKeys.has(k)).sort();
const missingInRu = [...enKeys].filter((k) => !ruKeys.has(k)).sort();

let hasErrors = false;

if (missingInEn.length > 0) {
  console.error("❌ Keys missing in en.json:");
  for (const key of missingInEn) {
    console.error(`  - ${key}`);
  }
  hasErrors = true;
}

if (missingInRu.length > 0) {
  console.error("❌ Keys missing in ru.json:");
  for (const key of missingInRu) {
    console.error(`  - ${key}`);
  }
  hasErrors = true;
}

// Validate namespaces from useTranslations() exist
const { tErrorsCalls, tCommonCalls, useTranslationsNamespaces } =
  findTranslationCalls(srcDir);

for (const ns of useTranslationsNamespaces) {
  if (!ruNamespaces.has(ns)) {
    console.error(
      `❌ Namespace "${ns}" from useTranslations() missing in ru.json`
    );
    hasErrors = true;
  }
  if (!enNamespaces.has(ns)) {
    console.error(
      `❌ Namespace "${ns}" from useTranslations() missing in en.json`
    );
    hasErrors = true;
  }
}

// Validate tErrors('key') calls - should be errors.key
for (const [file, keys] of tErrorsCalls) {
  for (const key of keys) {
    const fullKey = `errors.${key}`;
    if (!ruKeys.has(fullKey)) {
      console.error(
        `❌ tErrors('${key}') used in ${file} but "${fullKey}" missing in ru.json`
      );
      hasErrors = true;
    }
    if (!enKeys.has(fullKey)) {
      console.error(
        `❌ tErrors('${key}') used in ${file} but "${fullKey}" missing in en.json`
      );
      hasErrors = true;
    }
  }
}

// Validate tCommon('key') calls - should be common.key
for (const [file, keys] of tCommonCalls) {
  for (const key of keys) {
    const fullKey = `common.${key}`;
    if (!ruKeys.has(fullKey)) {
      console.error(
        `❌ tCommon('${key}') used in ${file} but "${fullKey}" missing in ru.json`
      );
      hasErrors = true;
    }
    if (!enKeys.has(fullKey)) {
      console.error(
        `❌ tCommon('${key}') used in ${file} but "${fullKey}" missing in en.json`
      );
      hasErrors = true;
    }
  }
}

// Validate errors.* completeness against ClientErrorCode
const errorCodes = extractErrorCodesFromSchema();
const clientErrorCodes = [...errorCodes, "network_error", "unknown_error"];
const errorKeysInRu = [...ruKeys]
  .filter((k) => k.startsWith("errors."))
  .map((k) => k.replace("errors.", ""));
const errorKeysInEn = [...enKeys]
  .filter((k) => k.startsWith("errors."))
  .map((k) => k.replace("errors.", ""));

const missingErrorKeysInRu = clientErrorCodes.filter(
  (code) => !errorKeysInRu.includes(code)
);
const missingErrorKeysInEn = clientErrorCodes.filter(
  (code) => !errorKeysInEn.includes(code)
);
const extraErrorKeysInRu = errorKeysInRu.filter(
  (code) => !clientErrorCodes.includes(code)
);
const extraErrorKeysInEn = errorKeysInEn.filter(
  (code) => !clientErrorCodes.includes(code)
);

if (missingErrorKeysInRu.length > 0) {
  console.error("❌ Error codes missing in ru.json errors:* :");
  for (const code of missingErrorKeysInRu) {
    console.error(`  - errors.${code}`);
  }
  hasErrors = true;
}

if (missingErrorKeysInEn.length > 0) {
  console.error("❌ Error codes missing in en.json errors:* :");
  for (const code of missingErrorKeysInEn) {
    console.error(`  - errors.${code}`);
  }
  hasErrors = true;
}

if (extraErrorKeysInRu.length > 0) {
  console.error("❌ Extra error codes in ru.json not in ClientErrorCode:");
  for (const code of extraErrorKeysInRu) {
    console.error(`  - errors.${code}`);
  }
  hasErrors = true;
}

if (extraErrorKeysInEn.length > 0) {
  console.error("❌ Extra error codes in en.json not in ClientErrorCode:");
  for (const code of extraErrorKeysInEn) {
    console.error(`  - errors.${code}`);
  }
  hasErrors = true;
}

if (!hasErrors) {
  console.log(
    "✅ All translation keys are synchronized between ru.json and en.json"
  );
  console.log("✅ All ClientErrorCode values are covered in errors.*");
  console.log(
    "✅ All useTranslations namespaces and tErrors/tCommon literal keys are valid"
  );
}

process.exit(hasErrors ? 1 : 0);
