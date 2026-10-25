#!/usr/bin/env node
// Hook UserPromptSubmit (#248): przypomnienie, że odpowiedzi idą w języku Profilu.
// Kit instaluje go tylko przy `language` ≠ en (scripts/bootstrap-project.sh, install_claude).
process.stdout.write("Odpowiedzi w języku z Profilu (language), niezależnie od języka wejścia.\n")
