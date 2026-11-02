import { useCallback, useState } from "react";

export function usePredict(correctId: string | undefined) {
  const [selectedId, setSelectedId] = useState<string>();
  const [checked, setChecked] = useState(false);
  const select = useCallback((id: string) => {
    setSelectedId(id);
    setChecked(false);
  }, []);
  const check = useCallback(() => {
    setChecked(true);
    return selectedId === correctId;
  }, [correctId, selectedId]);

  return { checked, correct: checked && selectedId === correctId, select, selectedId, check };
}
