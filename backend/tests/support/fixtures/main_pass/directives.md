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

Indented code (after a blank line):

    ::widget{ref="w1"}

Invalid inline directive: Example :widget{ref="w1"} here.

A directive inside an ordered list remains a directive, not indented code:

100. Example

     ::quiz{ref="q1"}

A tab after a blank line starts an indented code block:

	::widget{ref="w1"}

Nested list directives are unsupported slots:

- - ::quiz{ref="q1"}

Indented code immediately following a leaf directive remains code:

::quiz{ref="q1"}
    ::widget{ref="w1"}

Unicode line separators inside a paragraph do not end a CommonMark line:

A B C

```
::widget{ref="w1"}
```

<!-- case: leaf-before-code -->

A regular paragraph before an unbound widget.
::widget{ref="w1"}
    :quiz[example]

<!-- case: quote-list-before-code -->

> - A paragraph in a quoted list.
>   ::quiz{ref="q1"}
>       :widget[example]

<!-- case: multiline-inline-code -->

Use ``a literal `
:widget[label]
end`` and :quiz[unsupported].

<!-- case: wide-container -->

::::widget[caption]{ref="w1" note="}"}
Keep this explanation.
::::
	:widget[example]

<!-- case: nested-containers -->

:::::note
::::quiz{ref="q1"}
Keep this explanation too.
::::
:::::

<!-- case: unclosed-container -->

::::::::image{id="img_1"}
Keep this explanation until the end of the page.

<!-- case: inline-syntax -->

Refer to :quiz.

Paragraph :quiz[first [nested]
second]{ title="x } y" } after.
<!-- cleaned -->
Refer to .

Paragraph  after.

<!-- case: preserved-urls -->

[lesson](/guide/:quiz[example]) and <https://example.com/:quiz[ok]>.

Paragraph :quiz[remove] after.
<!-- cleaned -->
[lesson](/guide/:quiz[example]) and <https://example.com/:quiz[ok]>.

Paragraph  after.
