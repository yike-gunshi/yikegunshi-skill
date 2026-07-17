#!/bin/bash
# yikegunshi-skill install script
# Creates symlinks for Claude Code and Codex-compatible skill directories.
# Adapted from forge-cookbook's install.sh (auto-discovery variant).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
CODEX_SKILLS_DIR="${CODEX_SKILLS_DIR:-$HOME/.agents/skills}"

TARGET="claude"
ACTION="install"
DRY_RUN=0
FORCE=0

# Skills: auto-discovered under skills/ (must contain SKILL.md; _* dirs excluded)
SKILLS=()
for _d in "$SCRIPT_DIR"/skills/*/; do
  _name="$(basename "$_d")"
  case "$_name" in _*) continue ;; esac
  [ -f "$_d/SKILL.md" ] || continue
  SKILLS+=("$_name")
done

usage() {
  cat <<'USAGE'
Usage: ./install.sh [options]

Options:
  --target <claude|codex|both>  Install target. Default: claude
                                claude -> ~/.claude/skills
                                codex  -> ~/.agents/skills
  --only <name>                 Only act on a single skill (repeatable)
  --uninstall                   Remove symlinks from the selected target
  --status                      Show install status for the selected target
  --dry-run                     Print actions without changing files
  --force                       Replace non-symlink paths if they block install
  -h, --help                    Show this help

Environment overrides:
  CLAUDE_SKILLS_DIR             Default: ~/.claude/skills
  CODEX_SKILLS_DIR              Default: ~/.agents/skills
USAGE
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

ONLY=()

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --target)
        [ "$#" -ge 2 ] || die "--target requires a value"
        TARGET="$2"
        shift 2
        ;;
      --target=*)
        TARGET="${1#*=}"
        shift
        ;;
      --only)
        [ "$#" -ge 2 ] || die "--only requires a value"
        ONLY+=("$2")
        shift 2
        ;;
      --uninstall)
        ACTION="uninstall"
        shift
        ;;
      --status)
        ACTION="status"
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --force)
        FORCE=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done

  case "$TARGET" in
    claude|codex|both) ;;
    *) die "Unsupported target '$TARGET'. Use claude, codex, or both." ;;
  esac

  if [ "${#ONLY[@]}" -gt 0 ]; then
    filtered=()
    for want in "${ONLY[@]}"; do
      found=0
      for skill in "${SKILLS[@]}"; do
        if [ "$skill" = "$want" ]; then
          filtered+=("$skill")
          found=1
        fi
      done
      [ "$found" -eq 1 ] || die "Unknown skill '$want'. Available: ${SKILLS[*]}"
    done
    SKILLS=("${filtered[@]}")
  fi
}

target_dirs() {
  case "$TARGET" in
    claude) printf '%s\n' "$CLAUDE_SKILLS_DIR" ;;
    codex) printf '%s\n' "$CODEX_SKILLS_DIR" ;;
    both)
      printf '%s\n' "$CLAUDE_SKILLS_DIR"
      printf '%s\n' "$CODEX_SKILLS_DIR"
      ;;
  esac
}

validate_sources() {
  [ "${#SKILLS[@]}" -gt 0 ] || die "No skills discovered under $SCRIPT_DIR/skills/"
}

link_one() {
  src="$1"
  dst="$2"

  if [ -L "$dst" ]; then
    current="$(readlink "$dst" || true)"
    if [ "$current" = "$src" ]; then
      echo "  ok  $(basename "$dst") -> $src"
      return
    fi
    run rm "$dst"
  elif [ -e "$dst" ]; then
    if [ "$FORCE" -ne 1 ]; then
      die "$dst exists and is not a symlink. Re-run with --force if you want to replace it."
    fi
    run rm -rf "$dst"
  fi

  run ln -s "$src" "$dst"
  echo "  add $(basename "$dst") -> $src"
}

install_to_dir() {
  skills_dir="$1"
  echo "Installing skills into: $skills_dir"
  run mkdir -p "$skills_dir"

  for skill in "${SKILLS[@]}"; do
    link_one "$SCRIPT_DIR/skills/$skill" "$skills_dir/$skill"
  done
}

remove_one() {
  dst="$1"
  if [ -L "$dst" ]; then
    run rm "$dst"
    echo "  remove $(basename "$dst")"
  elif [ -e "$dst" ]; then
    if [ "$FORCE" -eq 1 ]; then
      run rm -rf "$dst"
      echo "  remove $(basename "$dst") (forced)"
    else
      echo "  skip $(basename "$dst") (not a symlink)"
    fi
  else
    echo "  missing $(basename "$dst")"
  fi
}

uninstall_from_dir() {
  skills_dir="$1"
  echo "Uninstalling skills from: $skills_dir"
  for skill in "${SKILLS[@]}"; do
    remove_one "$skills_dir/$skill"
  done
}

status_one() {
  src="$1"
  dst="$2"
  name="$(basename "$dst")"

  if [ -L "$dst" ]; then
    current="$(readlink "$dst" || true)"
    if [ ! -e "$dst" ]; then
      echo "  broken  $name -> $current (target missing)"
    elif [ "$current" = "$src" ]; then
      echo "  ok      $name -> $current"
    else
      echo "  drift   $name -> $current (expected $src)"
    fi
  elif [ -e "$dst" ]; then
    echo "  blocked $name exists but is not a symlink"
  else
    echo "  missing $name"
  fi
}

status_for_dir() {
  skills_dir="$1"
  echo "Status for: $skills_dir"
  for skill in "${SKILLS[@]}"; do
    status_one "$SCRIPT_DIR/skills/$skill" "$skills_dir/$skill"
  done
}

parse_args "$@"
validate_sources

case "$ACTION" in
  install)
    for dir in $(target_dirs); do
      install_to_dir "$dir"
    done
    echo ""
    echo "Installed ${#SKILLS[@]} skill(s) for target: $TARGET"
    echo "Restart your agent, or open a new session, to refresh skill discovery."
    ;;
  uninstall)
    for dir in $(target_dirs); do
      uninstall_from_dir "$dir"
    done
    ;;
  status)
    for dir in $(target_dirs); do
      status_for_dir "$dir"
    done
    ;;
esac
