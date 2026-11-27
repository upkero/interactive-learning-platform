"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { OrderingQuiz } from "../model";
import styles from "./OrderingInput.module.css";

interface OrderingInputProps {
  quiz: OrderingQuiz;
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
  error?: string;
}

interface SortableItemProps {
  item: { id: string; text: string };
  index: number;
  disabled?: boolean;
}

function SortableItem({ item, index, disabled }: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={`${styles.item} ${isDragging ? styles.dragging : ""} ${disabled ? styles.disabled : ""}`}
      {...attributes}
    >
      <div className={styles.itemContent}>
        <span
          className={styles.dragHandle}
          {...listeners}
          aria-label="Drag to reorder"
        >
          ⋮⋮
        </span>
        <span
          className={`${styles.itemNumber} ${index < 9 ? styles.singleDigit : ""}`}
        >
          {index + 1}
        </span>
        <span className={styles.itemText}>{item.text}</span>
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          className={`${styles.moveBtn} ${styles.moveUp}`}
          onClick={() => {}}
          disabled={disabled || index === 0}
          aria-label="Move up"
        >
          ↑
        </button>
        <button
          type="button"
          className={`${styles.moveBtn} ${styles.moveDown}`}
          onClick={() => {}}
          disabled={disabled || index === 0}
          aria-label="Move down"
        >
          ↓
        </button>
      </div>
    </li>
  );
}

export function OrderingInput({
  quiz,
  value,
  onChange,
  disabled,
  error,
}: OrderingInputProps) {
  const t = useTranslations("quiz");
  const [items, setItems] = useState(() =>
    value
      .map((id) => quiz.items.find((i) => i.id === id))
      .filter((item): item is { id: string; text: string } => Boolean(item))
  );

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      if (disabled) return;
      const { active, over } = event;
      if (over && active.id !== over.id) {
        const newItems = [...items];
        const oldIndex = newItems.findIndex((item) => item.id === active.id);
        const newIndex = newItems.findIndex((item) => item.id === over.id);
        const activeItem = newItems[oldIndex];
        newItems.splice(oldIndex, 1);
        newItems.splice(newIndex, 0, activeItem);
        setItems(newItems);
        onChange(newItems.map((item) => item.id));
      }
    },
    [disabled, items, onChange]
  );

  const sortedItems = value
    .map((id) => quiz.items.find((i) => i.id === id))
    .filter((item): item is { id: string; text: string } => Boolean(item));

  return (
    <fieldset
      className={`${styles.fieldset} ${error ? styles.hasError : ""}`}
      disabled={disabled}
    >
      <legend className={styles.legend}>{quiz.prompt}</legend>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={sortedItems.map((item) => item.id)}
          strategy={verticalListSortingStrategy}
        >
          <ul
            className={styles.list}
            role="list"
            aria-label={t("optionsLabel")}
          >
            {sortedItems.map((item, index) => (
              <SortableItem
                key={item.id}
                item={item}
                index={index}
                disabled={disabled}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
