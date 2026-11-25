import tseslint from 'typescript-eslint';
import boundaries from 'eslint-plugin-boundaries';
import nextPlugin from '@next/eslint-plugin-next';

export default tseslint.config(
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } },
    plugins: { boundaries, '@next/next': nextPlugin },
    settings: {
      'import/resolver': {
        typescript: {
          project: './tsconfig.json',
        },
      },
      'boundaries/elements': [
        { type: 'app', pattern: 'src/app/**' },
        { type: 'widget', pattern: 'src/widgets/**', capture: ['widget'] },
        { type: 'feature', pattern: 'src/features/**', capture: ['feature'] },
        { type: 'entity', pattern: 'src/entities/**', capture: ['entity'] },
        { type: 'shared', pattern: 'src/shared/**' },
      ],
      'boundaries/flag-as-external': {
        customSourcePatterns: ['@grasp/primitives/**'],
      },
    },
    rules: {
      ...nextPlugin.configs['core-web-vitals'].rules,
      'boundaries/element-types': ['error', {
        default: 'disallow',
        rules: [
          { from: 'app', allow: ['app', 'widget', 'feature', 'entity', 'shared', 'external'] },
          { from: 'widget', allow: [['widget', { widget: '${from.widget}' }], 'feature', 'entity', 'shared', 'external'] },
          { from: 'feature', allow: ['entity', 'shared', 'external'] },
          { from: 'entity', allow: ['entity', 'shared', 'external'] },
          { from: 'shared', allow: ['shared', 'external'] },
        ],
      }],
      'boundaries/entry-point': ['error', {
        default: 'disallow',
        rules: [
          { target: ['widget', 'feature', 'entity'], allow: ['index.ts', '*/index.ts'] },
          { target: ['app', 'shared'], allow: '**' },
        ],
      }],
      'boundaries/no-unknown': 'error',
    },
  },
);
