"""Prove scripts/deploy_to_pi.sh cannot delete Pi-side state.

The deploy script syncs with ``rsync --delete``. These tests run the exact filter
arguments the script uses (printed by scripts/deploy_rsync_filters.sh) against a
local rsync between two temporary directories that stand in for the repo and the
Pi's ~/payphone, then check what survived.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
FILTERS_SCRIPT = SCRIPTS_DIR / "deploy_rsync_filters.sh"
DEPLOY_SCRIPT = SCRIPTS_DIR / "deploy_to_pi.sh"
RULES_FILE = SCRIPTS_DIR / "deploy_protected_paths.rules"

requires_rsync = pytest.mark.skipif(shutil.which("rsync") is None, reason="rsync not installed")


def filter_args() -> list[str]:
    result = subprocess.run(
        ["bash", str(FILTERS_SCRIPT)], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.splitlines()


def write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def make_repo_checkout(root: Path) -> Path:
    """A minimal stand-in for this repo (the rsync source)."""
    write(root / "payphone" / "main.py")
    write(root / "plugins" / ".gitkeep", "")
    write(root / "plugins" / "LAM" / "system.py", "new LAM from repo")
    write(root / "audio_files" / "bios" / "main_menu.mp3", "generic prompt")
    write(root / "audio_files" / "dtmf" / "1.wav", "tracked tone")
    # A developer's local BIOS config must never reach the Pi.
    write(root / ".bios_config.json", '{"theme_path": "/Users/dev/theme"}')
    # Local plugin symlinks (TDTM, bm-info-line) point at sibling checkouts that
    # do not exist on the Pi.
    (root / "plugins" / "TDTM").symlink_to("../../TDTM/tdtm")
    return root


def make_pi_payphone(root: Path) -> Path:
    """A stand-in for ~/payphone on a Pi that has been running for a while."""
    write(root / "payphone" / "main.py", "old")
    write(root / "payphone" / "stale_module.py", "removed upstream")
    write(root / "plugins" / "LAM" / "system.py", "old LAM")
    write(root / "plugins" / "LAM" / "stale.py", "removed upstream")
    write(root / "audio_files" / "bios" / "main_menu.mp3", "theme pack override prompt")
    write(root / "audio_files" / "bios" / "stale.mp3", "removed upstream")
    # Pi-side state the deploy must leave alone.
    write(root / ".bios_config.json", '{"theme_path": "/home/pi/scary-fest-payphone-theme"}')
    write(root / "audio_files" / "lam_messages" / "001.wav", "caller message")
    write(root / "audio_files" / "bios" / "recorded.wav", "recording in tracked dir")
    write(root / "recordings" / "r1.wav", "tdtm recording")
    write(root / "user-instructions" / "note.txt", "tdtm instructions")
    # A theme pack installed with `install.py --copy`.
    write(root / "plugins" / "klaus-line" / "system.py", "theme plugin")
    write(root / "plugins" / "klaus-line" / "manifest.json", "{}")
    write(root / "audio_files" / "klaus-line" / "witness" / "ada.mp3", "theme audio")
    return root


def run_rsync(src: Path, dst: Path, extra: list[str]) -> subprocess.CompletedProcess:
    cmd = ["rsync", "-a", "--delete", *extra, f"{src}/", f"{dst}/"]
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def test_filter_script_protects_required_paths():
    args = filter_args()

    assert args[0] == f"--filter=. {RULES_FILE}", "protected rules must be merged before any include"
    assert "--include=/plugins/LAM/" in args
    assert "--include=/plugins/LAM/**" in args
    assert "--include=/audio_files/bios/**" in args
    assert args[-2:] == ["--exclude=/plugins/*", "--exclude=/audio_files/*/"]

    rules = [line.strip() for line in RULES_FILE.read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    assert "- /.bios_config.json" in rules
    assert "- /audio_files/lam_messages/" in rules
    assert "P /audio_files/**.wav" in rules


@requires_rsync
def test_deploy_without_filters_would_wipe_pi_state(tmp_path):
    """Document the hazard the filters exist for: a bare --delete removes everything."""
    src = make_repo_checkout(tmp_path / "repo")
    pi = make_pi_payphone(tmp_path / "pi")

    run_rsync(src, pi, [])

    assert not (pi / "audio_files" / "lam_messages").exists()
    assert not (pi / "plugins" / "klaus-line").exists()
    assert (pi / ".bios_config.json").read_text() == '{"theme_path": "/Users/dev/theme"}'


@requires_rsync
def test_deploy_filters_keep_pi_state_and_still_update_code(tmp_path):
    src = make_repo_checkout(tmp_path / "repo")
    pi = make_pi_payphone(tmp_path / "pi")

    run_rsync(src, pi, filter_args())

    # Code and tracked plugin/audio content is updated, stale files are removed.
    assert (pi / "payphone" / "main.py").read_text() == "x"
    assert not (pi / "payphone" / "stale_module.py").exists()
    assert (pi / "plugins" / "LAM" / "system.py").read_text() == "new LAM from repo"
    assert not (pi / "plugins" / "LAM" / "stale.py").exists()
    assert not (pi / "audio_files" / "bios" / "stale.mp3").exists()
    assert (pi / "audio_files" / "dtmf" / "1.wav").read_text() == "tracked tone"

    # Pi-side state survives untouched.
    assert (pi / ".bios_config.json").read_text() == '{"theme_path": "/home/pi/scary-fest-payphone-theme"}'
    assert (pi / "audio_files" / "lam_messages" / "001.wav").exists()
    assert (pi / "audio_files" / "bios" / "recorded.wav").exists()
    assert (pi / "recordings" / "r1.wav").exists()
    assert (pi / "user-instructions" / "note.txt").exists()
    assert (pi / "plugins" / "klaus-line" / "system.py").read_text() == "theme plugin"
    assert (pi / "audio_files" / "klaus-line" / "witness" / "ada.mp3").exists()

    # Dangling local plugin symlinks are not shipped.
    assert not (pi / "plugins" / "TDTM").is_symlink()

    # Known limitation: a theme pack's bios/*.mp3 overrides share names with
    # tracked files, so a deploy re-installs the generic prompt. Re-run the
    # pack's install.py --copy after deploying.
    assert (pi / "audio_files" / "bios" / "main_menu.mp3").read_text() == "generic prompt"


@requires_rsync
def test_dry_run_reports_deletions_without_changing_anything(tmp_path):
    src = make_repo_checkout(tmp_path / "repo")
    pi = make_pi_payphone(tmp_path / "pi")
    before = sorted(str(p.relative_to(pi)) for p in pi.rglob("*"))

    result = run_rsync(src, pi, ["--dry-run", "-v", *filter_args()])

    after = sorted(str(p.relative_to(pi)) for p in pi.rglob("*"))
    assert before == after
    deleting = [line for line in result.stdout.splitlines() if "deleting" in line.lower()]
    assert any("stale_module.py" in line for line in deleting)
    assert not any("lam_messages" in line or "klaus-line" in line for line in deleting)


@requires_rsync
def test_deploy_script_quotes_filter_patterns_for_eval(tmp_path):
    """deploy_to_pi.sh builds the rsync command with eval; glob patterns must survive it."""
    src = make_repo_checkout(tmp_path / "repo")
    pi = make_pi_payphone(tmp_path / "pi")
    snippet = f"""
set -e
RSYNC_CMD="rsync -a --delete"
RSYNC_FILTER_ARGS=""
while IFS= read -r filter_arg; do
    RSYNC_FILTER_ARGS="$RSYNC_FILTER_ARGS $(printf '%q' "$filter_arg")"
done < <("{FILTERS_SCRIPT}")
cd "{src}"
eval $RSYNC_CMD $RSYNC_FILTER_ARGS --exclude='.git' ./ "{pi}/"
"""
    subprocess.run(["bash", "-c", snippet], check=True, capture_output=True, text=True)

    assert (pi / "plugins" / "klaus-line" / "system.py").exists()
    assert (pi / "audio_files" / "lam_messages" / "001.wav").exists()
    assert not (pi / "plugins" / "LAM" / "stale.py").exists()


def test_deploy_script_accepts_dry_run_flag():
    subprocess.run(["bash", "-n", str(DEPLOY_SCRIPT)], check=True)

    env = {k: v for k, v in os.environ.items() if k not in {"PI_HOST", "PI_USER"}}
    result = subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), "--dry-run"], cwd=REPO_ROOT, env=env, capture_output=True, text=True
    )

    assert result.returncode == 1
    assert "Unknown option" not in result.stdout
    assert "DRY RUN" in result.stdout
    assert "PI_HOST and PI_USER must be set" in result.stdout
