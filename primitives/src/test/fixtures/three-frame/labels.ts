export const threeFrameLabels = {
  en: {
    "three-frame.start": "Start with {left} counters.",
    "three-frame.predict": "We are about to add {right} counters.",
    "three-frame.question": "Will the quantity increase when we add {right}?",
    "three-frame.explanation":
      "Adding {right} to {left} gives {sum}. Adding zero leaves the quantity unchanged.",
    "three-frame.result": "Result: {left} + {right} = {sum}.",
    "three-frame.initial": "Initial quantity: {left}",
    "three-frame.scene": "{left} plus {right} equals {result}",
  },
  ru: {
    "three-frame.start": "Начинаем с {left} фишек.",
    "three-frame.predict": "Сейчас добавим {right} фишек.",
    "three-frame.question": "Увеличится ли количество, если добавить {right}?",
    "three-frame.explanation":
      "Если к {left} прибавить {right}, получится {sum}. Прибавление нуля не меняет количество.",
    "three-frame.result": "Результат: {left} + {right} = {sum}.",
    "three-frame.initial": "Начальное количество: {left}",
    "three-frame.scene": "{left} плюс {right} равно {result}",
  },
} as const;
