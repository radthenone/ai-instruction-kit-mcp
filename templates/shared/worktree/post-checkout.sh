# Nowy worktree (`git worktree add`, też z Orci i agentów): poprzedni HEAD to same zera,
# a `.git` jest plikiem. Pliki z sekcji `worktree:` Profilu kopiuje `worktree.mjs`
# z głównego checkoutu — worktree ze starszego brancha może go nie mieć (#439).
# Subshell: `exit` i zmienne nie wychodzą poza blok, więc reszta hooka działa dalej.
case "$1" in
  '' | *[!0]*) ;;
  *)
    (
      unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
      [ -f .git ] || exit 0
      # `worktree.mjs add` ustawia KIT_WORKTREE_HOOK=0: sam kopiuje pliki i robi setup:.
      [ "${KIT_WORKTREE_HOOK:-1}" = 0 ] && exit 0
      if ! command -v node >/dev/null 2>&1; then
        echo "[worktree] brak node w PATH, pomijam sync" >&2
        exit 0
      fi
      main="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)" || exit 0
      if [ "$(git config --bool core.bare)" = true ]; then
        echo "[worktree] repo bare: kit nie ma głównego checkoutu, pomijam sync" >&2
        exit 0
      fi
      [ -f "$main/.ai/worktree.mjs" ] || exit 0
      node "$main/.ai/worktree.mjs" sync . \
        || echo "[worktree] sync nie powiódł się, worktree zostaje" >&2
    )
    ;;
esac
