"use client";

import { useEffect, useState } from "react";

/**
 * Returns a debounced version of the given value.
 * The debounced value will only update after the specified delay has passed
 * without the value changing.
 *
 * @param value - The value to debounce
 * @param delayMs - The delay in milliseconds
 * @returns The debounced value
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debouncedValue;
}

/**
 * Hook that returns a debounced value and a setter for it.
 * Useful when you need to control the debounced value manually.
 */
export function useDebouncedValueWithSetter<T>(
  value: T,
  delayMs: number
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delayMs]);

  return [debouncedValue, setDebouncedValue];
}
