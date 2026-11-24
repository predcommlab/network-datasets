#!/usr/bin/env bash
# Commits what is staged, with the message given, and pushes it to main, with
# the generated parts of the forms (the label questions, the list of studies,
# the list of categories) brought up to date on top. Used by the Forms and
# Deploy workflows.
#
# Several runs can push at about the same time, for example when two forms
# are approved one after the other. Each run started from main as it was
# then, so the push is preceded by a rebase onto the newest main. The data is
# checked again after the rebase (two forms could, say, have added studies of
# the same name), and the generated parts are written only then, from the data
# as it is then, so two runs never collide over them. A rebase that fails (two
# forms changed the same file) is undone and tried again on the newer main.
#
# Usage: publish.sh "<commit message>"    Exit status 1 if nothing could be pushed.
set -u
message=$1
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
if ! git diff --cached --quiet; then
  git commit -q -m "$message"
fi
for attempt in 1 2 3 4 5; do
  if git pull -q --rebase origin main; then
    if ! python3 .github/scripts/predictindex.py check; then
      echo "::error::After the rebase onto the newest main the data does not pass the checks."
      exit 1
    fi
    python3 .github/scripts/predictindex.py sync >/dev/null
    git add .github/ISSUE_TEMPLATE
    lists=false
    if ! git diff --cached --quiet; then
      git commit -q -m "Forms: lists brought up to date"
      lists=true
    fi
    if [ "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)" ]; then
      echo "Nothing to push."
      exit 0
    fi
    if git push -q origin HEAD:main; then
      exit 0
    fi
    # Someone pushed in the meantime: drop the lists, they are written again.
    if [ "$lists" = true ]; then
      git reset -q --hard HEAD~1
    fi
  else
    git rebase --abort 2>/dev/null || true
  fi
  sleep $((attempt * 5))
done
echo "::error::Could not push to main."
exit 1
