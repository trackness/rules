# One command per Bash call

Blocks a Bash call that chains commands with `;`, `&&`, `||`, `|`, `&` or a newline, with this message:

> Blocked: one command per Bash call. Find a single command or tool that does the whole job. Only if there isn't one, send the commands as separate calls.

Allowed, because it is not chaining:

- a separator inside quotes or after a backslash, which is an argument: `git commit -m "fix: a; b"`, `rg 'foo|bar' src`, `find . -name x -exec rm {} \;`
- a heredoc body, which is input: `git commit -m "$(cat <<'EOF' … EOF)"`
- `&` in a redirection (`2>&1`, `&>`), or a trailing `&` that runs one command in the background

Checked even though quoted, because it runs as commands:

- the argument to any shell's `-c` (including combined flags such as `-lc`), to `eval` or to `ssh`
- a `$(…)` or backticks inside double quotes
- a heredoc fed to a shell or to `ssh`
