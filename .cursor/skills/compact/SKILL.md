---
name: compact
description: >-
  Cursor IDE only: unify Chat Summarize under slash /compact in this project.
  Use when user types /compact or asks to summarize this Cursor chat thread.
  Do NOT use for Claude Code, Codex, or other CLIs — those have their own compact.
disable-model-invocation: true
---

# /compact — Cursor only (alias Summarize)

Ten skill należy **wyłącznie do Cursor IDE** w tym repo (`.cursor/skills/compact/`).

Cel: **jedna komenda `/compact` w Cursorze** zamiast szukania UI **Summarize**.  
To **nie** jest wspólna komenda kita dla Claude / Codex / innych klientów i **nie** zastępuje ich wbudowanego `/compact`.

## Zakres klienta

| Klient | Ten skill |
|--------|-----------|
| Cursor (czat IDE) | tak — tu |
| Claude Code / Claude CLI | nie |
| Codex | nie |
| Inne | nie |

Jeśli nie jesteś w Cursorze — **zignoruj** ten skill; użyj native compact danego narzędzia.

## Zachowanie (Cursor)

1. Zostań w **tej samej** rozmowie Cursor (jak Summarize). Bez nowego czatu, bez pliku handoff.
2. Język prozy: MCP `get_language` / `--language` (domyślnie PL). Tytuły issue/PR zawsze EN.
3. Nie skanuj całego repo. Tylko wątek + opcjonalnie `git status -sb` / branch.
4. Wypisz wyłącznie format poniżej. Zero implementacji, commitów, push, PR.
5. Nie myl z `/handoff` (fork + plik + nowy wątek).

## Format

```markdown
# Compact (Cursor)

## Status
- Cel:
- Branch / baza:
- Issue (jeśli jest):

## Zrobione
- …

## Otwarte / decyzje
- …

## Następne kroki
1. …

## Kontynuuj stąd
<5–10 linii>
```

## Silnikowe Summarize

Ten skill daje **skrót w odpowiedzi**. Jeśli okno kontekstu dalej puchnie: użyj w Cursorze UI **Summarize** (ucięcie po stronie produktu). Nadal nie przenoś tej komendy na Claude/Codex.
