#!/bin/sh
# Tag and publish a release: tools/tag-release.sh 1.2.3
#
# Checks that the default branch is clean and pushed, runs the tests and a
# local build, then creates the annotated tag v1.2.3 and pushes it. The tag
# starts the Release workflow, which tests, builds and publishes.
set -eu

fail() {
    printf 'tag-release: %s\n' "$*" >&2
    exit 1
}

[ "$#" -eq 1 ] || fail 'usage: tools/tag-release.sh <version>   (for example 1.2.3 or 1.2.3-rc.1)'
version=$1
printf '%s\n' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$' ||
    fail "'$version' is not a version like 1.2.3 or 1.2.3-rc.1 (no leading v)."
tag="v$version"

cd "$(dirname -- "$0")/.."
branch=$(git rev-parse --abbrev-ref HEAD)
[ -z "$(git status --porcelain)" ] || fail 'commit or stash your changes first.'
git fetch --quiet --tags origin "$branch"
[ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$branch")" ] || fail "$branch differs from origin/$branch; push or pull first."
if git rev-parse --quiet --verify "refs/tags/$tag" >/dev/null; then
    fail "$tag already exists."
fi

QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT INT TERM
python3 tools/build_release.py --version "$version" --out "$build"

git tag -a "$tag" -m "vpngo-gui $version"
git push origin "$tag"
printf 'Pushed %s. Follow the release in the Actions tab.\n' "$tag"
