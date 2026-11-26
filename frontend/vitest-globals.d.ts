/// <reference types="vitest/globals" />

interface ViHoisted {
  <T>(factory: () => T): T;
}
interface ViNamespace {
  hoisted: ViHoisted;
  fn: <T extends (...args: unknown[]) => unknown>(
    implementation?: T
  ) => ReturnType<T> & {
    mockReturnValue: (value: unknown) => void;
    mockResolvedValue: (value: unknown) => void;
    mockRejectedValue: (value: unknown) => void;
  };
  clearAllMocks: () => void;
  Mock: new <T>(implementation?: (...args: unknown[]) => T) => {
    (...args: unknown[]): T;
    mockReturnValue: (value: unknown) => void;
    mockResolvedValue: (value: unknown) => void;
    mockRejectedValue: (value: unknown) => void;
  };
  mock: (moduleName: string, factory: () => unknown) => void;
}
declare const vi: ViNamespace;
