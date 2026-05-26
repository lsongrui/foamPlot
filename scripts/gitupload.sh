#!/bin/sh
set -eu

PACKAGE_NAME="foamplot"
BRANCH="main"
UPLOAD_REPOSITORY="${UPLOAD_REPOSITORY:-testpypi}"

BUMP_TYPE="${1:-patch}"
COMMIT_MESSAGE="${2:-Release new version}"

usage() {
    echo "Usage:"
    echo "  scripts/gitupload.sh [patch|minor|major] [commit message]"
    echo ""
    echo "Examples:"
    echo "  scripts/gitupload.sh patch"
    echo "  scripts/gitupload.sh patch \"add gitupload\""
    echo "  UPLOAD_REPOSITORY=pypi scripts/gitupload.sh patch \"release to PyPI\""
}

if [ "$BUMP_TYPE" != "patch" ] && [ "$BUMP_TYPE" != "minor" ] && [ "$BUMP_TYPE" != "major" ]; then
    usage
    exit 2
fi

if [ ! -f "pyproject.toml" ]; then
    echo "Error: run this script from the project root."
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo "Error: git not found."
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found."
    exit 1
fi

echo "Checking git status..."
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "There are uncommitted changes. They will be included."
else
    echo "No uncommitted source changes detected."
fi

OLD_VERSION="$(grep -E '^version[[:space:]]*=' pyproject.toml | head -n 1 | sed 's/.*"\([^"]*\)".*/\1/')"

if ! echo "$OLD_VERSION" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' >/dev/null 2>&1; then
    echo "Error: could not read semantic version X.Y.Z from pyproject.toml."
    echo "Found: $OLD_VERSION"
    exit 1
fi

MAJOR="$(echo "$OLD_VERSION" | awk -F. '{print $1}')"
MINOR="$(echo "$OLD_VERSION" | awk -F. '{print $2}')"
PATCH="$(echo "$OLD_VERSION" | awk -F. '{print $3}')"

case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"

echo "Old version: $OLD_VERSION"
echo "New version: $NEW_VERSION"

TMP_FILE="pyproject.toml.tmp"
awk -v new_version="$NEW_VERSION" '
    BEGIN { done = 0 }
    /^version[[:space:]]*=/ && done == 0 {
        print "version = \"" new_version "\""
        done = 1
        next
    }
    { print }
' pyproject.toml > "$TMP_FILE"
mv "$TMP_FILE" pyproject.toml

if [ -f "src/foamplot/__init__.py" ]; then
    TMP_INIT="src/foamplot/__init__.py.tmp"

    if grep -E '^__version__[[:space:]]*=' src/foamplot/__init__.py >/dev/null 2>&1; then
        awk -v new_version="$NEW_VERSION" '
            BEGIN { done = 0 }
            /^__version__[[:space:]]*=/ && done == 0 {
                print "__version__ = \"" new_version "\""
                done = 1
                next
            }
            { print }
        ' src/foamplot/__init__.py > "$TMP_INIT"
        mv "$TMP_INIT" src/foamplot/__init__.py
    else
        printf '\n__version__ = "%s"\n' "$NEW_VERSION" >> src/foamplot/__init__.py
    fi
fi

echo "Cleaning old build artifacts..."
rm -rf dist build ./*.egg-info ./src/*.egg-info

echo "Installing/upgrading build tools..."
python3 -m pip install --user --upgrade build twine

echo "Building package..."
python3 -m build

echo "Checking package..."
python3 -m twine check dist/*

echo "Adding files to git..."
git add .

echo "Committing..."
if git commit -m "$COMMIT_MESSAGE v$NEW_VERSION"; then
    echo "Committed release v$NEW_VERSION."
else
    echo "Nothing to commit."
fi

echo "Tagging..."
if git rev-parse "v$NEW_VERSION" >/dev/null 2>&1; then
    echo "Tag v$NEW_VERSION already exists."
else
    git tag "v$NEW_VERSION"
fi

echo "Pushing branch..."
git push origin "$BRANCH"

echo "Pushing tag..."
git push origin "v$NEW_VERSION" || true

echo "Uploading to $UPLOAD_REPOSITORY..."
python3 -m twine upload --repository "$UPLOAD_REPOSITORY" dist/*

echo ""
echo "Done."
echo ""
echo "Test install:"
echo "python3 -m pip install --user --upgrade -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ${PACKAGE_NAME}==${NEW_VERSION}"
