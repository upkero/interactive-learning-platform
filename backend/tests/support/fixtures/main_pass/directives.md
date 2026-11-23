# Shared directive examples

This fixture is the single set of remark-directive examples used by the
backend parser tests and by the frontend (screen Э6) tests. Every example
below must be understood identically by both sides.

The three slots the main pass may emit:

::widget{ref="w1" primitive_hint="three-frame" mode_hint="steps"}
::image{ref="i1" image_alias="img-1"}
::quiz{ref="q1"}

Only the `ref` attribute is required. Extra attributes are allowed and
ignored by the parser, but `remark-directive` keeps them for the renderer.

The same lines inside a fenced code block are text, not slots:

```markdown
::widget{ref="w9"}
::quiz{ref="q9"}
```

An inline directive is not a slot either: `::widget{ref="w7"}` inside a
sentence stays text.
