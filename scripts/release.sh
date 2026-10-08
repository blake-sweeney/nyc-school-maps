#!/usr/bin/env bash
# NYC School Zones · cut a release: bump VERSION, rebuild, commit, tag and push.
#
#   scripts/release.sh patch      # 1.13.0 -> 1.13.1  (fixes and wording)
#   scripts/release.sh minor      # 1.13.0 -> 1.14.0  (a new feature)
#   scripts/release.sh major      # 1.13.0 -> 2.0.0   (a new kind of view)
#   scripts/release.sh minor --dry-run   # show what would happen, change nothing
#   scripts/release.sh minor --yes       # don't ask before pushing
#
# Before running: commit your work, and describe it under a "## Unreleased" heading at the top of
# CHANGELOG.md. The script renames that heading to the new version and today's date.
set -euo pipefail

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

part="" dry=0 yes=0
for a in "$@"; do
  case "$a" in
    major|minor|patch) part="$a" ;;
    --dry-run|-n) dry=1 ;;
    --yes|-y) yes=1 ;;
    -h|--help) usage ;;
    *) echo "Unknown argument: $a"; usage ;;
  esac
done
[ -n "$part" ] || usage

cd "$(git rev-parse --show-toplevel)"
die() { echo "release: $*" >&2; exit 1; }

# --- checks --------------------------------------------------------------------------------------
[ -z "$(git status --porcelain)" ] || die "you have uncommitted changes. Commit (or stash) them first, then run this again."
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] || die "you're on '$branch'. Releases go out from main (merge first)."
git fetch --quiet origin main --tags || die "couldn't reach GitHub (git fetch failed)."
[ -z "$(git rev-list HEAD..origin/main)" ] || die "GitHub has commits you don't. Run 'git pull' first."

old="$(tr -d '[:space:]' < VERSION)"
[[ "$old" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || die "VERSION should look like 1.2.3, but it says '$old'."
maj="${BASH_REMATCH[1]}" min="${BASH_REMATCH[2]}" pat="${BASH_REMATCH[3]}"
case "$part" in
  major) new="$((maj + 1)).0.0" ;;
  minor) new="$maj.$((min + 1)).0" ;;
  patch) new="$maj.$min.$((pat + 1))" ;;
esac
tag="v$new"
git rev-parse -q --verify "refs/tags/$tag" >/dev/null && die "tag $tag already exists."

grep -q '^## Unreleased' CHANGELOG.md || die "CHANGELOG.md needs a '## Unreleased' section describing this release (put it above the newest version)."
today="$(date +%Y-%m-%d)"

echo "Release $old -> $new ($part) as $tag on $branch"
echo
echo "Changelog for this release:"
awk '/^## Unreleased/{on=1;next} /^## /{if(on)exit} on' CHANGELOG.md | sed 's/^/  /'
echo
if [ "$dry" = 1 ]; then echo "(dry run: nothing changed)"; exit 0; fi

# --- bump, rebuild, commit, tag ------------------------------------------------------------------
printf '%s\n' "$new" > VERSION
python3 - "$new" "$today" <<'PY'
import sys
new, today = sys.argv[1], sys.argv[2]
p = "CHANGELOG.md"
s = open(p, encoding="utf-8").read()
s = s.replace("## Unreleased", f"## {new} ({today})", 1)
open(p, "w", encoding="utf-8").write(s)
PY
echo "Rebuilding (the footer shows the version)..."
python3 scripts/build.py > /dev/null

git add -A
git commit --quiet -m "Release $tag"
git tag -a "$tag" -m "$tag"
echo "Committed and tagged $tag locally."

# --- push ----------------------------------------------------------------------------------------
if [ "$yes" != 1 ]; then
  read -r -p "Push $tag to GitHub now? [y/N] " ok
  case "$ok" in
    y|Y|yes) ;;
    *) echo "Not pushed. When ready: git push origin main && git push origin $tag"
       echo "To undo instead: git tag -d $tag && git reset --hard HEAD~1"
       exit 0 ;;
  esac
fi
git push --quiet origin main
git push --quiet origin "$tag"
echo "Pushed $tag. GitHub Pages will update in a minute or two."
