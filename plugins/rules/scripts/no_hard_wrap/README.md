# No hard-wrapped Markdown

Blocks a Write or Edit to a `.md` or `.markdown` file that breaks a paragraph or list item across lines, with this message:

> Blocked: hard-wrapped Markdown. Write each paragraph and list item as one line; break lines only between blocks, list items and table rows, and inside code blocks.

A line continues the one before it when both hold text and the second does not start a block of its own. Allowed, because each line starts a block or is not prose:

- list items (`-`, `*`, `+`, `1.`, `1)`), headings, table rows, blockquotes (including GitHub alerts such as `> [!NOTE]`), HTML and link reference definitions
- anything inside a code block fenced with backticks or tildes, or inside the YAML front matter at the top of the file, whether its lines end in LF or CRLF. As in CommonMark, a fence closes only at a line of the same character at least as long as the one that opened it, so a code block can show another fence, such as a `~~~` fence inside a backtick one or a three-backtick fence inside a four-backtick one

MDX files (`.mdx`) are not checked, because their `import` lines and JSX are not prose.

Only line breaks the call writes are checked, so an Edit inside a paragraph someone else already wrapped is allowed. For an Edit, the hook checks the file as it will be after the edit, so a line added inside an existing code fence is allowed. With `replace_all`, only the first replacement is checked.

Markdown renders the lines of a hard-wrapped paragraph as one line anyway, so the breaks only make the source harder to edit and diff.
