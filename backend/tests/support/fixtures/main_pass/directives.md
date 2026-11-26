# Shared directive examples

Only these unindented leaf directives on separate lines are supported:

::widget{ref="w1"}
::image{id="img_1"}
::quiz{ref="q1"}

Extra attributes, indentation, nested lists, container directives and inline
`:widget[...]` are violations. Hints belong only in the directive list.

The following lines are code, not directives (the inner fence is shorter):

````markdown
```
::widget{ref="w9"}
````

Invalid examples:

   ::widget{ref="w2"}
- item
  ::quiz{ref="q2"}
:::widget{ref="w3"}
::widget{ref="w4" mode_hint="watch"}

The ordinary text `::before inserts content` is not a directive.
