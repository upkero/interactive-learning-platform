import { useRef, type KeyboardEvent } from "react";

import styles from "./ModeTabs.module.css";

export interface ModeTab<Id extends string> {
  id: Id;
  label: string;
}

export interface ModeTabsProps<Id extends string> {
  tabs: readonly ModeTab<Id>[];
  value: Id;
  ariaLabel: string;
  onChange: (value: Id) => void;
}

export function ModeTabs<Id extends string>({
  tabs,
  value,
  ariaLabel,
  onChange,
}: ModeTabsProps<Id>) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const lastIndex = tabs.length - 1;
    const targetIndex =
      event.key === "ArrowRight"
        ? (index + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? lastIndex
              : undefined;

    if (targetIndex === undefined) return;
    event.preventDefault();
    const nextTab = tabs[targetIndex];
    onChange(nextTab.id);
    refs.current[targetIndex]?.focus();
  }

  return (
    <div aria-label={ariaLabel} className={styles.list} role="tablist">
      {tabs.map((tab, index) => {
        const selected = tab.id === value;
        return (
          <button
            aria-selected={selected}
            className={styles.tab}
            id={`mode-tab-${tab.id}`}
            key={tab.id}
            onClick={() => onChange(tab.id)}
            onKeyDown={(event) => moveFocus(event, index)}
            ref={(element) => {
              refs.current[index] = element;
            }}
            role="tab"
            tabIndex={selected ? 0 : -1}
            type="button"
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
