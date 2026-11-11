# No hard-wrapped Markdown

Blocks a Write or Edit to a `.md` or `.markdown` file that breaks a paragraph or list item across lines, with this message:

> Blocked: hard-wrapped Markdown. Write each paragraph and list item as one line; break lines only between blocks, list items and table rows, and inside code blocks.

A line continues the one before it when both hold text and the second does not start a block of its own. Allowed, because each line starts a block or is not prose:

- list items (`-`, `*`, `+`, `1.`, `1)`), headings, including underlined ones (a line of `=` or `-` under the title), rule lines (`---`, `***`, `___`), table rows, blockquotes (including GitHub alerts such as `> [!NOTE]`), HTML, every line of an HTML comment whose line starts with `<!--`, and link reference definitions
- anything inside a code block, fenced with backticks or tildes or indented four spaces or a tab after a blank line, or inside the YAML front matter at the top of the file, whether its lines end in LF or CRLF. As in CommonMark, a fence closes only at a line holding nothing but a run of the opening fence's character at least as long, indented at most three spaces more than the opening fence, so a code block can show another fence, such as a `~~~` fence inside a backtick one, a three-backtick fence inside a four-backtick one, a `` ```sh `` line inside a three-backtick one, or a fence indented four spaces more than the one around it

MDX files (`.mdx`) are not checked, because their `import` lines and JSX are not prose. Nor is a paragraph of a list item that is indented four spaces after a blank line, because the hook reads it as an indented code block.

For an Edit, the hook checks the file as it will be after the edit. It blocks the Edit when a line break in its `new_string` wraps, or when the file ends up with more wraps than it had, such as when the Edit turns a heading or list item into text, deletes the line between two lines of text, or wraps a later match of `replace_all`. So an Edit inside a paragraph someone else already wrapped is allowed, and so is a line added inside an existing code fence.

The hook finds `old_string` as Edit does: word for word first, and failing that with curly quotes made straight and `\uXXXX` escapes of non-ASCII characters decoded. With an empty `new_string`, it also deletes the line break after `old_string`, as Edit does.

Markdown renders the lines of a hard-wrapped paragraph as one line anyway, so the breaks only make the source harder to edit and diff.
