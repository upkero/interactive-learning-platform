// Make expect globally available for @testing-library/jest-dom
import { expect, vi, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
vi.stubGlobal("expect", expect);

// Now import jest-dom which will extend the global expect
// Use a conditional import to avoid type checking issues
if (typeof process !== "undefined" && process.env.VITEST) {
  // eslint-disable-next-line @typescript-eslint/no-floating-promises
  import("@testing-library/jest-dom");
}

// Polyfill for HTMLDialogElement in jsdom (which doesn't support showModal/close)
if (
  typeof HTMLDialogElement !== "undefined" &&
  !HTMLDialogElement.prototype.showModal
) {
  HTMLDialogElement.prototype.showModal = vi.fn(function (
    this: HTMLDialogElement
  ) {
    this.open = true;
    this.dispatchEvent(new Event("show"));
  });
  HTMLDialogElement.prototype.close = vi.fn(function (
    this: HTMLDialogElement,
    returnValue?: string
  ) {
    this.open = false;
    this.returnValue = returnValue ?? "";
    this.dispatchEvent(new Event("close"));
  });
}

// Cleanup after each test
afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
  // Close any open dialogs
  document.querySelectorAll("dialog[open]").forEach((dialog) => {
    dialog.close();
  });
  // Cleanup testing-library
  cleanup();
});
