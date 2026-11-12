"""Register a script as a git hook in the Bash commands of a Claude Code session: the one way every rule that git enforces does it."""
import re
import shlex
import subprocess

MINIMUM_GIT_VERSION = (2, 54, 0)  # the first release with hooks defined in config


def git_version():
    """The version of the git on the PATH, such as (2, 54, 0) from git version 2.54.0 (Apple Git-157), or () if git cannot be run or gives no version."""
    try:
        output = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout
    except OSError:
        return ()
    version = re.match(r"git version (\d+)\.(\d+)\.(\d+)", output)
    return tuple(int(number) for number in version.groups()) if version else ()


def register(env_file, stdout, name, event, command, check):
    """Register command, a list of words, as git's hook for event under the name name, in the Bash commands of the session that owns env_file.

    With no env_file, or no git of MINIMUM_GIT_VERSION or later, tell Claude instead that check, such as "The Conventional Commits check", is not active.
    """
    # Claude Code adds a SessionStart hook's stdout to Claude's context; Claude never sees its stderr.
    if not env_file:
        print(f"{check} is not active: Claude Code gave this hook no CLAUDE_ENV_FILE to register it in.", file=stdout)
        return
    version = git_version()
    if version < MINIMUM_GIT_VERSION:  # an older git ignores the registration, so the check would silently never run
        found = f"git {'.'.join(map(str, version))}" if version else "no git whose version it could read"
        print(f"{check} is not active: the git-rules plugin requires git 2.54.0 or later, and found {found}.", file=stdout)
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
