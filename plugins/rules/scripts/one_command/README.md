# One command per Bash call

Blocks a Bash call that chains commands with `;`, `&&`, `||`, `|`, `&` or a newline, with this message:

> Blocked: one command per Bash call. Find a single command or tool that does the whole job. Only if there isn't one, send the commands as separate calls.

Allowed, because it is not chaining:

- a separator inside quotes or after a backslash, which is an argument: `git commit -m "fix: a; b"`, `rg 'foo|bar' src`, `find . -name x -exec rm {} \;`
- a separator in a comment: `ls -la # list them; then stop`
- the body of a quoted heredoc, which is input: `git commit -m "$(cat <<'EOF' … EOF)"`
- `&` in a redirection (`2>&1`, `&>`), or a trailing `&` that runs one command in the background

Checked even though quoted, because it runs as commands:

- the argument to every shell's `-c` in the command, also after other options (`bash -o pipefail -c`, `bash -lc`, `bash -c --`), and to every `eval`
- every quoted string of a command that runs `ssh`, whose arguments become the remote command
- a `$(…)` or backticks inside double quotes, or in the body of an unquoted heredoc (`<<EOF`), which the shell expands
- a heredoc or here-string (`<<<`) fed to a shell or to `ssh`, also after `sudo` or `env`

Not checked: inside a `$(…)`, brackets nested more than two deep, after which the rest of that `$(…)` is read as text.
