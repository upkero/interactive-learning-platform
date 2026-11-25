import { describe, it, expect } from 'vitest';
import boundariesPlugin from 'eslint-plugin-boundaries';

describe('eslint-plugin-boundaries', () => {
  it('should export the plugin', () => {
    expect(boundariesPlugin).toBeDefined();
    expect(boundariesPlugin.rules).toBeDefined();
  });

  it('should have element-types rule', () => {
    expect(boundariesPlugin.rules['element-types']).toBeDefined();
    expect(typeof boundariesPlugin.rules['element-types'].create).toBe('function');
  });

  it('should have entry-point rule', () => {
    expect(boundariesPlugin.rules['entry-point']).toBeDefined();
    expect(typeof boundariesPlugin.rules['entry-point'].create).toBe('function');
  });

  it('should have no-unknown rule', () => {
    expect(boundariesPlugin.rules['no-unknown']).toBeDefined();
    expect(typeof boundariesPlugin.rules['no-unknown'].create).toBe('function');
  });
});