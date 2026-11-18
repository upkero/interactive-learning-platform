import fs from 'node:fs';
import path from 'node:path';

const ruPath = path.resolve(__dirname, '../src/shared/i18n/messages/ru.json');
const enPath = path.resolve(__dirname, '../src/shared/i18n/messages/en.json');

function getKeys(obj: any, prefix = ''): string[] {
  return Object.keys(obj).reduce((acc: string[], key: string) => {
    const currentKey = prefix ? `${prefix}.${key}` : key;
    if (typeof obj[key] === 'object' && obj[key] !== null) {
      return acc.concat(getKeys(obj[key], currentKey));
    }
    return acc.concat(currentKey);
  }, []);
}

try {
  const ru = JSON.parse(fs.readFileSync(ruPath, 'utf-8'));
  const en = JSON.parse(fs.readFileSync(enPath, 'utf-8'));

  const ruKeys = getKeys(ru).sort();
  const enKeys = getKeys(en).sort();

  const missingInEn = ruKeys.filter((k) => !enKeys.includes(k));
  const missingInRu = enKeys.filter((k) => !ruKeys.includes(k));

  if (missingInEn.length > 0 || missingInRu.length > 0) {
    console.error('Ошибка локализации: ключи в словарях не совпадают!');
    if (missingInEn.length > 0) console.error('Отсутствуют в en.json:', missingInEn);
    if (missingInRu.length > 0) console.error('Отсутствуют в ru.json:', missingInRu);
    process.exit(1);
  }

  console.log('Словари локализации (ru.json и en.json) полностью синхронизированы.');
} catch (error) {
  console.error('Ошибка при чтении словарей:', error);
  process.exit(1);
}