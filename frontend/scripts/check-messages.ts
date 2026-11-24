#!/usr/bin/env tsx
/**
 * Check that all translation keys are synchronized between ru.json and en.json.
 * Exits with non-zero code if keys are missing in either file.
 */

import fs from 'node:fs';
import path from 'node:path';

const messagesDir = path.resolve(import.meta.dirname, '../src/shared/i18n/messages');
const ruPath = path.join(messagesDir, 'ru.json');
const enPath = path.join(messagesDir, 'en.json');

function loadJson(filePath: string): Record<string, unknown> {
  const content = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(content);
}

function getAllKeys(obj: Record<string, unknown>, prefix = ''): Set<string> {
  const keys = new Set<string>();
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    keys.add(fullKey);
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const nestedKeys = getAllKeys(value as Record<string, unknown>, fullKey);
      for (const k of nestedKeys) keys.add(k);
    }
  }
  return keys;
}

const ru = loadJson(ruPath);
const en = loadJson(enPath);

const ruKeys = getAllKeys(ru);
const enKeys = getAllKeys(en);

const missingInEn = [...ruKeys].filter((k) => !enKeys.has(k)).sort();
const missingInRu = [...enKeys].filter((k) => !ruKeys.has(k)).sort();

let hasErrors = false;

if (missingInEn.length > 0) {
  console.error('❌ Keys missing in en.json:');
  for (const key of missingInEn) {
    console.error(`  - ${key}`);
  }
  hasErrors = true;
}

if (missingInRu.length > 0) {
  console.error('❌ Keys missing in ru.json:');
  for (const key of missingInRu) {
    console.error(`  - ${key}`);
  }
  hasErrors = true;
}

if (!hasErrors) {
  console.log('✅ All translation keys are synchronized between ru.json and en.json');
}

process.exit(hasErrors ? 1 : 0);