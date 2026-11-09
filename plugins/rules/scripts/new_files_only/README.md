# Write only for new files

Blocks a Write to a file that already exists, with this message:

> Blocked: Write is only for new files, and this one already exists. Change it with Edit, or NotebookEdit for a notebook.

Allowed: a Write that creates a new file.

Write replaces the whole file, so anything left out of the new content is lost, while Edit changes only the text it names. Claude Code's own check on Write refuses a file changed since Claude read it, but on current models it lets a Write replace a file Claude never read when the Write is allowed without asking. An empty file is blocked too, because Edit with an empty `old_string` fills it.
