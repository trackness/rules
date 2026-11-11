"""What the tests of the rules that git enforces share: git kept apart from the user's own config, and a Claude Code session to run it in."""
import json
import os
import re
import shutil
import subprocess

import pytest

GIT_VERSION = tuple(int(part) for part in re.findall(r"\d+", subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)[:3])
needs_config_hooks = pytest.mark.skipif(GIT_VERSION < (2, 54, 0), reason="git runs hooks defined in config from 2.54.0")
needs_zsh = pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is not installed")
# git in the tests reads none of the user's config, global, system or in the environment, such as a global core.hooksPath, and commits as a test identity.
GIT_ENV = {
    **{name: value for name, value in os.environ.items() if not name.startswith("GIT_CONFIG")}, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com", "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
}
# Git config the session's environment already holds, such as the user's own or another rule's.
EXISTING_GIT_CONFIG = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "test.kept", "GIT_CONFIG_VALUE_0": "yes"}


def git(*args):
    """Run git with the given arguments for a test's setup, and return its output."""
    return subprocess.run(["git", *map(str, args)], env=GIT_ENV, check=True, capture_output=True, text=True).stdout


def start_session(env_file, script):
    """Run script as Claude Code's SessionStart hook does, with env_file as its CLAUDE_ENV_FILE, and return env_file."""
    env_file.touch()  # Claude Code hands the hook an existing file to append to
    hook_input = json.dumps({"hook_event_name": "SessionStart", "source": "startup"})
    result = subprocess.run([script], input=hook_input, env={**os.environ, "CLAUDE_ENV_FILE": str(env_file)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return env_file


def run_with_env_files(env_files, *command, shell="bash", env=GIT_ENV):
    """Run the command as Claude's Bash tool would, after sourcing the session's env files one after another."""
    sources = " && ".join(f'. "${number}"' for number in range(1, len(env_files) + 1))
    script = f'{sources} && shift {len(env_files)} && "$@"'
    return subprocess.run([shell, "-c", script, "_", *env_files, *map(str, command)], env=env, capture_output=True, text=True)


def run_in_session(tmp_path, script, *command, shell="bash"):
    """Start a session whose SessionStart hook is script, then run the command as Claude's Bash tool would, with the env file sourced."""
    return run_with_env_files([start_session(tmp_path / "session.env", script)], *command, shell=shell)
