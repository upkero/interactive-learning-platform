import tseslint from 'typescript-eslint';
import boundaries from 'eslint-plugin-boundaries';
import nextPlugin from '@next/eslint-plugin-next';

export default tseslint.config(
  { ignores: ['**/__tests__/**', '**/*.test.ts', '**/*.test.tsx'] },
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } },
    plugins: { boundaries, '@next/next': nextPlugin },
    settings: {
      'boundaries/alias': { '@': './src' },
      'boundaries/elements': [
        { type: 'app', pattern: 'src/app/**' },
        { type: 'widget', pattern: 'src/widgets/*', capture: ['widget'] },
        { type: 'feature', pattern: 'src/features/*', capture: ['feature'] },
        { type: 'entity', pattern: 'src/entities/*', capture: ['entity'] },
        { type: 'shared', pattern: 'src/shared/**' },
      ],
    },
    rules: {
      ...nextPlugin.configs['core-web-vitals'].rules,
      'boundaries/element-types': ['error', {
        default: 'disallow',
        rules: [
          { from: 'app', allow: ['app', 'widget', 'feature', 'entity', 'shared'] },
          { from: 'widget', allow: [['widget', { widget: '${from.widget}' }], 'feature', 'entity', 'shared'] },
          { from: 'feature', allow: [['feature', { feature: '${from.feature}' }], 'entity', 'shared'] },
          { from: 'entity', allow: ['entity', 'shared'] },
          { from: 'shared', allow: ['shared'] },
        ],
      }],
      'boundaries/entry-point': ['error', {
        default: 'disallow',
        rules: [
          { target: ['widget', 'feature', 'entity'], allow: 'index.ts' },
          { target: ['app', 'shared'], allow: '**' },
        ],
      }],
    },
  },
);
