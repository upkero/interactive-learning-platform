/** A flat locale dictionary with stable dot-separated keys, for example `common.next`. */
export type Labels = Readonly<Record<string, string>>;

/** Values interpolated into a translation template such as `Hello, {name}`. */
export type LabelVariables = Readonly<Record<string, string | number>>;

/**
 * Resolve one label and replace named `{variable}` placeholders.
 *
 * A missing key is returned unchanged so that an untranslated label is visible
 * during development instead of silently rendering an empty control.
 */
export function t(labels: Labels, key: string, vars: LabelVariables = {}): string {
  const template = labels[key] ?? key;

  return template.replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/g, (placeholder, name: string) => {
    const value = vars[name];
    return value === undefined ? placeholder : String(value);
  });
}
