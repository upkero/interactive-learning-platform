// Make expect globally available for @testing-library/jest-dom
import { expect, vi } from 'vitest';
vi.stubGlobal('expect', expect);

// Now import jest-dom which will extend the global expect
// Use a conditional import to avoid type checking issues
if (typeof process !== 'undefined' && process.env.VITEST) {
  // eslint-disable-next-line @typescript-eslint/no-floating-promises
  import('@testing-library/jest-dom');
}