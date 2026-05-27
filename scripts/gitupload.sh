#!/bin/sh
set -eu

PACKAGE_NAME="foamplot"
BRANCH="main"

usage() {
    echo "Usage:"
    echo "  scripts/gitupload.sh test [patch|minor|major] [commit message]"
    echo "  scripts/gitupload.sh pypi"
    echo ""
    echo "Examples:"
    echo "  scripts/gitupload.sh test patch \"test release\""
    echo "  scripts/gitupload.sh test minor \"add new plotting option\""
    echo "  scripts/gitupload.sh pypi"
    echo ""
    echo "Meaning:"
    echo "  test  : bump version, commit, tag, push, upload to TestPyPI"
    echo "  pypi  : upload the current clean tagged version to official PyPI"
}

die() {
    echo "Error: $*"
    exit 1
}

need_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        die "$1 not found."
    fi
}

read_version() {
    grep -E '^version[[:space:]]*=' pyproject.toml | head -n 1 | sed 's/.*"\([^"]*\)".*/\1/'
}

validate_version() {
    version="$1"

    if ! echo "$version" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' >/dev/null 2>&1; then
        echo "Error: could not read semantic version X.Y.Z from pyproject.toml."
        echo "Found: $version"
        exit 1
    fi
}

git_is_clean() {
    git diff --quiet && git diff --cached --quiet
}

update_pyproject_version() {
    new_version="$1"
    tmp_file="pyproject.toml.tmp"

    awk -v new_version="$new_version" '
        BEGIN { done = 0 }
        /^version[[:space:]]*=/ && done == 0 {
            print "version = \"" new_version "\""
            done = 1
            next
        }
        { print }
    ' pyproject.toml > "$tmp_file"

    mv "$tmp_file" pyproject.toml
}

update_init_version() {
    new_version="$1"

    if [ -f "src/foamplot/__init__.py" ]; then
        tmp_init="src/foamplot/__init__.py.tmp"

        if grep -E '^__version__[[:space:]]*=' src/foamplot/__init__.py >/dev/null 2>&1; then
            awk -v new_version="$new_version" '
                BEGIN { done = 0 }
                /^__version__[[:space:]]*=/ && done == 0 {
                    print "__version__ = \"" new_version "\""
                    done = 1
                    next
                }
                { print }
            ' src/foamplot/__init__.py > "$tmp_init"

            mv "$tmp_init" src/foamplot/__init__.py
        else
            printf '\n__version__ = "%s"\n' "$new_version" >> src/foamplot/__init__.py
        fi
    fi
}

bump_version() {
    old_version="$1"
    bump_type="$2"

    major="$(echo "$old_version" | awk -F. '{print $1}')"
    minor="$(echo "$old_version" | awk -F. '{print $2}')"
    patch="$(echo "$old_version" | awk -F. '{print $3}')"

    case "$bump_type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            usage
            exit 2
            ;;
    esac

    echo "${major}.${minor}.${patch}"
}

clean_build_artifacts() {
    echo "Cleaning old build artifacts..."
    rm -rf dist build ./*.egg-info ./src/*.egg-info
}

install_build_tools() {
    echo "Installing/upgrading build tools..."
    python3 -m pip install --user --upgrade build twine
}

build_and_check() {
    echo "Building package..."
    python3 -m build

    echo "Checking package..."
    python3 -m twine check dist/*
}

upload_package() {
    repository="$1"

    echo ""
    echo "Upload target: $repository"
    echo ""

    python3 -m twine upload --repository "$repository" dist/*
}

print_install_command() {
    repository="$1"
    version="$2"

    echo ""
    echo "Done."
    echo ""

    if [ "$repository" = "testpypi" ]; then
        echo "Test install:"
        echo "python3 -m pip install --user --upgrade -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ${PACKAGE_NAME}==${version}"
    else
        echo "Install:"
        echo "python3 -m pip install --user --upgrade ${PACKAGE_NAME}==${version}"
    fi
}

run_testpypi_release() {
    if [ "$#" -lt 3 ]; then
        usage
        exit 2
    fi

    bump_type="$2"
    commit_message="$3"

    if [ "$bump_type" != "patch" ] && [ "$bump_type" != "minor" ] && [ "$bump_type" != "major" ]; then
        usage
        exit 2
    fi

    old_version="$(read_version)"
    validate_version "$old_version"

    new_version="$(bump_version "$old_version" "$bump_type")"

    echo "Mode: TestPyPI release"
    echo "Old version: $old_version"
    echo "New version: $new_version"

    update_pyproject_version "$new_version"
    update_init_version "$new_version"

    clean_build_artifacts
    install_build_tools
    build_and_check

    echo "Adding files to git..."
    git add .

    echo "Committing..."
    if git commit -m "$commit_message v$new_version"; then
        echo "Committed release v$new_version."
    else
        die "nothing was committed. Check git status."
    fi

    echo "Tagging..."
    if git rev-parse "v$new_version" >/dev/null 2>&1; then
        die "tag v$new_version already exists."
    fi

    git tag "v$new_version"

    echo "Pushing branch..."
    git push origin "$BRANCH"

    echo "Pushing tag..."
    git push origin "v$new_version"

    upload_package "testpypi"
    print_install_command "testpypi" "$new_version"
}

run_pypi_release() {
    if [ "$#" -ne 1 ]; then
        usage
        exit 2
    fi

    version="$(read_version)"
    validate_version "$version"

    echo "Mode: official PyPI release"
    echo "Version: $version"

    if ! git_is_clean; then
        echo ""
        echo "Error: working tree is not clean."
        echo "Official PyPI release must be made from a clean Git state."
        echo ""
        echo "Run:"
        echo "  git status"
        echo ""
        echo "Then either commit/test-release your changes first, or discard them."
        exit 1
    fi

    current_branch="$(git rev-parse --abbrev-ref HEAD)"
    if [ "$current_branch" != "$BRANCH" ]; then
        die "current branch is $current_branch, expected $BRANCH."
    fi

    if ! git rev-parse "v$version" >/dev/null 2>&1; then
        die "tag v$version does not exist. Official release must use an existing tested tag."
    fi

    current_commit="$(git rev-parse HEAD)"
    tag_commit="$(git rev-list -n 1 "v$version")"

    if [ "$current_commit" != "$tag_commit" ]; then
        echo ""
        echo "Error: current commit is not tag v$version."
        echo "Current commit: $current_commit"
        echo "Tag commit    : $tag_commit"
        echo ""
        echo "To release this version, checkout the exact tag or move to the tagged commit."
        exit 1
    fi

    echo "Fetching remote information..."
    git fetch origin "$BRANCH" --tags

    local_commit="$(git rev-parse "$BRANCH")"
    remote_commit="$(git rev-parse "origin/$BRANCH")"

    if [ "$local_commit" != "$remote_commit" ]; then
        echo ""
        echo "Error: local $BRANCH is not the same as origin/$BRANCH."
        echo "Local : $local_commit"
        echo "Remote: $remote_commit"
        echo ""
        echo "Push or pull first, then release."
        exit 1
    fi

    clean_build_artifacts
    install_build_tools
    build_and_check

    upload_package "pypi"
    print_install_command "pypi" "$version"
}

if [ ! -f "pyproject.toml" ]; then
    die "run this script from the project root."
fi

need_command git
need_command python3

if [ "$#" -lt 1 ]; then
    usage
    exit 2
fi

MODE="$1"

case "$MODE" in
    test)
        run_testpypi_release "$@"
        ;;
    pypi)
        run_pypi_release "$@"
        ;;
    *)
        usage
        exit 2
        ;;
esac