"""Register a script as a git hook in the Bash commands of a Claude Code session: the one way every rule that git enforces does it."""
import shlex


def register(env_file, stdout, name, event, command, check):
    """Register command, a list of words, as git's hook for event under the name name, in the Bash commands of the session that owns env_file.

    With no env_file, tell Claude instead that check, such as "The Conventional Commits check", is not active.
    """
    if not env_file:
        # Claude Code adds a SessionStart hook's stdout to Claude's context; Claude never sees its stderr.
        print(f"{check} is not active: Claude Code gave this hook no CLAUDE_ENV_FILE to register it in.", file=stdout)
        return
    command = shlex.join(str(word) for word in command)  # git runs the command through a shell
    # Each entry goes after those already counted, so other rules' and the user's GIT_CONFIG_* entries stay. The command comes first:
    # git ignores a command with no event, but aborts on an event with no command, as a shell that stops partway through would leave.
    with open(env_file, "a") as session_env:
        session_env.write(
            f"export GIT_CONFIG_KEY_${{GIT_CONFIG_COUNT:-0}}=hook.{name}.command GIT_CONFIG_VALUE_${{GIT_CONFIG_COUNT:-0}}={shlex.quote(command)}\n"
            "export GIT_CONFIG_COUNT=$((${GIT_CONFIG_COUNT:-0} + 1))\n"
            f"export GIT_CONFIG_KEY_${{GIT_CONFIG_COUNT}}=hook.{name}.event GIT_CONFIG_VALUE_${{GIT_CONFIG_COUNT}}={event}\n"
            "export GIT_CONFIG_COUNT=$((GIT_CONFIG_COUNT + 1))\n"
        )
