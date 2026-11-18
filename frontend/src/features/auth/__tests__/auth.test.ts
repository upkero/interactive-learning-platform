import { describe, expect, it } from 'vitest';
import { sanitizeNextUrl } from '../model/sanitizeNext';
import { authCredentialsSchema } from '../model/schemas';

describe('sanitizeNextUrl', () => {
  it('allows valid internal paths', () => {
    expect(sanitizeNextUrl('/ru/materials')).toBe('/ru/materials');
    expect(sanitizeNextUrl('/en/documents/123/topics?topics=1,2')).toBe('/en/documents/123/topics?topics=1,2');
  });

  it('blocks external and protocol-relative open redirects', () => {
    expect(sanitizeNextUrl('https://evil.com')).toBe('/materials');
    expect(sanitizeNextUrl('//evil.com')).toBe('/materials');
    expect(sanitizeNextUrl('javascript:alert(1)')).toBe('/materials');
  });
});

describe('authCredentialsSchema', () => {
  it('validates correct email and password', () => {
    const res = authCredentialsSchema.safeParse({ email: 'user@example.com', password: 'password123' });
    expect(res.success).toBe(true);
  });

  it('rejects short passwords', () => {
    const res = authCredentialsSchema.safeParse({ email: 'user@example.com', password: '123' });
    expect(res.success).toBe(false);
  });
});
