#!/usr/bin/env node
/**
 * Wrapper `/headless` — uruchamia innego klienta kitu w trybie headless i sprząta po nim.
 *
 *   node .ai/headless.mjs --host <klient> <wykonawca> [--model <id>] [--timeout <min>] [--heartbeat <min>] [--ctx <katalog>] [treść…]
 *
 * Treść: argumenty po fladze albo (bez nich) stdin — słowo w słowo, plus stała stopka.
 * `--host` wstawia bootstrap w pliku agenta każdego klienta; wykonawca musi być w tabeli
 * EXECUTORS, w `clients:` Profilu i różny od hosta. Model: `--model` > projektowy config
 * wykonawcy (np. `model` w opencode.json) > domyślny model wykonawcy.
 *
 * Po zakończeniu, błędzie albo timeoucie wrapper zabija całe drzewo procesów wykonawcy
 * (Unix: grupa procesów, Windows: `taskkill /T /F`) — razem z jego LSP i serwerami MCP.
 * Kody wyjścia: kod wykonawcy, 124 = timeout, 2 = błędne wywołanie albo błąd konfiguracji
 * (np. nieznany model agy; linia `## nieznany model:` w raporcie), 75 = pauza limitu
 * dostawcy wykonawcy (nie błąd; linia `PAUSE=rate-limit reset=<ISO|brak>` w raporcie).
 * Pierwszeństwo: limit w ogonie wyjścia wygrywa też z timeoutem (75, nie 124).
 *
 * Wyjście wykonawcy idzie dalej i do logu w katalogu runu `.ai/headless-runs/<start>/`
 * (ścieżka w pierwszej linii). Co `--heartbeat` minut linia `[headless] ♥` ze stanem repo,
 * po 2 interwałach ciszy ostrzeżenie o zacięciu. Na końcu (także 124) raport: status, commity
 * od startu, nowe wpisy stasha, ostatnie linie wykonawcy. Liczy to Node — zero tokenów.
 *
 * Każde wywołanie kończy się wierszem JSON jako ostatnią linią wyjścia (#396). Z `--ctx <katalog>`
 * (noc) wiersz dopisuje się też do `<katalog>/headless-rows.jsonl`, a przy klasie innej niż OK wycinek
 * logu trafia do `<katalog>/headless-excerpt-<run>.txt` — log runu znika przy sprzątaniu.
 * `--report --ctx <katalog>` składa z bufora HEADLESS REPORT po tickecie i listę wywołań w kolejności;
 * bufor kasuje dopiero po wypisaniu.
 */
import { execFile, spawn, spawnSync } from "node:child_process"
import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs"
import { constants } from "node:os"
import { basename, delimiter, dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const KNOWN_CLIENTS = ["cursor", "claude", "codex", "vscode", "kiro", "kilo", "antigravity", "opencode"]
const FLAGS = ["--model", "--timeout", "--heartbeat", "--ctx"]
const DEFAULT_TIMEOUT_MIN = 60
const DEFAULT_HEARTBEAT_MIN = 10
const TAIL_LINES = 20
// Pauza limitu dostawcy wykonawcy (nie błąd): kod wyjścia 75 (EX_TEMPFAIL).
const PAUSE_CODE = 75
// Komunikaty limitu opencode/Codex/agy i innych (watchdog.sh czyta limit Claude z pól JSON
// transkryptu, nie z tekstu — tam wzorca nie ma). agy sprawdza też `/quota` (`quota` w EXECUTORS).
const LIMIT_PATTERN = /usage limit|\brate[ _-]limit|session limit|quota exceeded|quota exhausted|resource_exhausted|too many requests|api error: 429/i
// Błędny model agy (tylko wykonawca antigravity): kod wyjścia 1, komunikat odrzucenia modelu i lista
// od początku linii — format z logu agy: `error: invalid model selection (...): model X is not
// recognized ...` + `Available models:`. Błąd konfiguracji: kod wyjścia 2, bez fallbacku.
const AGY_MODEL_ERROR = /invalid model selection|is not recognized/i
const AGY_MODEL_LIST = /^Available models:?/im

// Parsowanie listy dostępnych modeli z wyjścia agy („Available models: ...”).
export function parseAvailableModels(text) {
  const match = /^Available models:?([^\n]*)(?:\r?\n([\s\S]*))?/im.exec(text)
  if (!match) return []
  const inline = match[1].trim()
  if (inline) {
    return inline.split(",").map((s) => s.trim()).filter(Boolean)
  }
  if (!match[2]) return []
  const list = []
  for (const line of match[2].split(/\r?\n/)) {
    if (/^\s+/.test(line) || /^\s*[-*]\s+/.test(line)) {
      const item = line.replace(/^\s*[-*]\s*/, "").trim()
      if (item) list.push(item)
    } else if (line.trim() === "") {
      continue
    } else {
      break
    }
  }
  return list
}

// Wykrycie nazwy nieznanego modelu z wyjścia lub fallback na model z wywołania/configu.
export function detectUnknownModel(text, fallbackModel = "") {
  const match = /(?:--model\s+"([^"]+)"|model\s+([^\s:]+)\s+is not recognized)/i.exec(text)
  return match?.[1] || match?.[2] || fallbackModel || ""
}
const LIMIT_TAIL_LINES = 20
const OUTPUT_TAIL_BYTES = 65_536
// Okno godziny resetu jak MAX_RESET_AHEAD_SEC w watchdog.sh (dalsza godzina = brak, nie zgadujemy).
const MAX_RESET_AHEAD_MS = 6 * 3_600_000
const QUOTA_TIMEOUT_MS = 60_000

// Numer ticketu z brancha `typ/<N>-slug`; inny branch (dev, detached, brak gita) — linia pominięta.
const ticketNumber = () => /^[a-z]+\/(\d+)-/.exec(git("branch", "--show-current") || "")?.[1]

// Godzina resetu z komunikatu limitu → ISO. Formy jak w watchdog.sh: „resets 3pm”, „resets 3:30pm”,
// „try again at 15:30” (czas lokalny, najbliższa taka godzina ≤ MAX_RESET_AHEAD_MS) albo ISO
// po „reset”/„try again”. Brak lub za daleko → null (w raporcie `reset=brak`).
export function resetIso(text, now = Date.now()) {
  const iso = /(?:reset\w*|try again(?: at| after)?)\D{0,20}?(\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:?\d{2})?)/i.exec(text)
  if (iso && !Number.isNaN(Date.parse(iso[1]))) return new Date(iso[1]).toISOString()
  // Grupy: 1 godzina; 2 minuty + 3 am/pm (z `:MM`); 4 am/pm bez minut. Bez `:MM` i bez am/pm — nie zgadujemy.
  const clock = /(?:resets?|try again)(?: at)? (\d{1,2})(?::(\d{2}) ?([ap]m)?| ?([ap]m))\b/i.exec(text)
  if (!clock) return null
  const ampm = (clock[3] || clock[4] || "").toLowerCase()
  const h = ampm ? (Number(clock[1]) % 12) + (ampm === "pm" ? 12 : 0) : Number(clock[1])
  const at = new Date(now)
  at.setHours(h, Number(clock[2] || 0), 0, 0)
  if (at.getTime() <= now) at.setDate(at.getDate() + 1)
  return at.getTime() - now <= MAX_RESET_AHEAD_MS ? at.toISOString() : null
}

// Ostatnie linie wyjścia — tam siedzi komunikat limitu; reszta (kod, diffy, logi) nie liczy się.
const tailLines = (text) => text.split("\n").slice(-LIMIT_TAIL_LINES).join("\n")

// Trailer autorstwa, którego kit wymaga w każdym commicie wykonawcy (#398).
const COAUTHOR_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"
// Klucz trailera porównujemy bez wielkości liter; wartość musi być dokładna (#408).
const COAUTHOR_KEY = "co-authored-by"
const COAUTHOR_VALUE = "Claude <noreply@anthropic.com>"

function isCoauthorTrailer(line) {
  const match = /^([^:]+):(.*)$/.exec(line.trim())
  return Boolean(match) && match[1].toLowerCase() === COAUTHOR_KEY && match[2].trim() === COAUTHOR_VALUE
}

// Temat commita po polsku albo angielsku wg `language` z Profilu (#398); inny kod — podany wprost.
const topicLanguage = (language) => ({ pl: "po polsku", en: "po angielsku" })[language] ?? `w języku ${language}`

const footer = (runDir, ticket, language) => `

---
Zasady tej sesji (headless, bez użytkownika):${ticket ? `
- Ticket #${ticket}: przeczytaj \`gh issue view ${ticket} --comments\` — to specyfikacja zadania.` : ""}
- Katalog runu: ${runDir} — logi testów, skrypty i pliki robocze tylko tam, nie w repo.
- Nie używaj \`git stash\`, \`git checkout\` ani \`git reset\`. Porównanie z bazą: \`node .ai/worktree.mjs add ${join(runDir, 'base')} --detach <ref> --plain\` (nie gołym \`git worktree add --detach\`), na końcu \`node .ai/worktree.mjs remove ${join(runDir, 'base')}\` (nie \`git worktree remove\`).
- Ticket z więcej niż 3 kryteriami akceptacji albo więcej niż jedną aplikacją/pakietem: najpierw plan 5–10 kroków.
- Praca test-first: test czerwony → kod → test zielony → lokalny commit po każdym zielonym kroku.
- Commity: temat ${topicLanguage(language)} (język \`${language}\` z Profilu), na końcu każdego commita trailer \`${COAUTHOR_TRAILER}\`.
- Lokalnie tylko testy dotknięte zmianą i szybkie bramki; pełny zestaw zrobi CI.
- Na VPS \`uv run\` zawsze z \`--no-sync\`.
- Maks. 2 próby naprawy tego samego błędu, potem stop i opis w sekcji Problemy raportu.
- Nie pushuj i nie otwieraj PR — zrobi to host po review.
- Język odpowiedzi i raportu: język \`language\` z Profilu (\`get_language\`), niezależnie od języka wejścia.
- Na końcu raport w tym formacie:
## Zmiany
<pliki i co w nich zmieniono>
## Testy
<komenda i wynik>
## Problemy
<co nie wyszło albo „brak”>`

// Tabela wykonawców: klient → binarki (pierwsza znaleziona w PATH) i argumenty.
// Nowy wykonawca = nowy wiersz; tylko klienci z guardami kita (patrz README /headless).
const EXECUTORS = {
  claude: {
    bins: ["claude"],
    // Treść przez stdin — bez limitu długości linii poleceń i bez cytowania.
    args: (model) => ["-p", "--permission-mode", "bypassPermissions", ...(model ? ["--model", model] : [])],
    stdin: true,
  },
  opencode: {
    // `--standalone`: prywatny serwer jako proces potomny, nie usługa w tle — inaczej
    // ubicie drzewa nie sięga LSP i MCP wykonawcy.
    bins: ["opencode2", "opencode"],
    // Projektowy config jest w `.gitignore`, więc linked worktree go nie ma. Wtedy
    // wskazujemy plik z głównego checkoutu natywnie (`OPENCODE_CONFIG`), a wrapper czyta
    // z niego `model` (#300). Sam plik w worktree ma pierwszeństwo i nie wymaga fallbacku.
    config: { file: "opencode.json", env: "OPENCODE_CONFIG" },
    // Treść od `-` (np. lista markdown) parser opencode wziąłby za flagę — nowa linia na
    // początku tego nie zmienia dla modelu.
    args: (model, prompt) => [
      "run", "--standalone", "--auto", ...(model ? ["--model", model] : []),
      prompt.startsWith("-") ? `\n${prompt}` : prompt,
    ],
    stdin: false,
  },
  antigravity: {
    // `-p` bierze następny argument jako prompt, więc prompt idzie zaraz po nim.
    // `--dangerously-skip-permissions` (agy 1.4.8) auto-approve narzędzi; deny z hooków guardów
    // `.agents/hooks.json` przebija tę flagę (sprawdzone: git-guard blokuje `git reset --hard`).
    bins: ["agy"],
    // agy nie ma projektowego configu z modelem — `.agents/agy.json` (gitignored) czyta wrapper.
    // Poziom siedzi w sufiksie nazwy (`-medium`); `--effort` niezgodny z sufiksem agy odrzuca,
    // więc idzie tylko jawny `effort` z configu (przy nazwie bazowej, np. `gemini-3.8-flash`).
    args: (model, prompt) => {
      const cfg = agyConfig()
      return [
        "-p", prompt.startsWith("-") ? `\n${prompt}` : prompt,
        "--dangerously-skip-permissions",
        "--model", model || cfg.model || "gemini-3.8-flash-medium",
        ...(cfg.effort ? ["--effort", cfg.effort] : []),
      ]
    },
    stdin: false,
    // Komunikat limitu agy nieznany (#293), więc po błędzie pytamy wprost: `agy -p /quota` daje
    // wiersze `<grupa>\t<limit>\t<procent>%\t<ISO reset>`. Grupa `Gemini Models` na 0% = limit.
    quota: (bin) => {
      const r = spawnSync(bin, ["-p", "/quota"], { encoding: "utf8", timeout: QUOTA_TIMEOUT_MS, windowsHide: true })
      if (r.status !== 0 || !r.stdout) return null
      const empty = lines(r.stdout).map((l) => l.trimEnd().split("\t"))
        .filter(([group, , left]) => group === "Gemini Models" && /^0+%$/.test(left?.trim() || ""))
      if (!empty.length) return null
      const resets = empty.map(([, , , at]) => Date.parse(at)).filter((t) => !Number.isNaN(t))
      return { reset: resets.length ? new Date(Math.min(...resets)).toISOString() : null }
    },
  },
}

const EXECUTOR_ALIASES = { gemini: "antigravity" }
// Zastępcy przy limicie, w tej kolejności, po wywołanym wykonawcy; po ostatnim przejmuje host.
const FALLBACK_ORDER = ["opencode", "antigravity"]

function agyConfig() {
  const path = join(".agents", "agy.json")
  if (!existsSync(path)) return {}
  try {
    return JSON.parse(readFileSync(path, "utf8"))
  } catch (err) {
    fail(`${path}: niepoprawny JSON (${err.message})`)
  }
}

// Katalog głównego checkoutu, gdy cwd to linked worktree (`--git-dir` ≠ `--git-common-dir`);
// null poza worktree. Worktree ma własny `.git/worktrees/<id>`, wspólny jest `<główny>/.git`.
function mainCheckout() {
  const gitDir = git("rev-parse", "--git-dir")
  const commonDir = git("rev-parse", "--git-common-dir")
  if (!gitDir || !commonDir) return null
  const cwd = process.cwd()
  try {
    if (norm(resolve(cwd, gitDir)) === norm(resolve(cwd, commonDir))) return null
    return dirname(norm(resolve(cwd, commonDir)))
  } catch {
    return null
  }
}

// Config wykonawcy, którego w worktree nie ma: bierzemy plik z głównego checkoutu.
// Wykonawcy bez mechanizmu env dostają tylko ostrzeżenie — bez fallbacku (#300).
function configFor(executor) {
  const main = mainCheckout()
  if (!main) return null
  if (!executor.config) return { line: "CONFIG=missing — executor default model" }
  // Jawnie wskazany config (env) wygrywa — nie nadpisujemy decyzji użytkownika.
  if (process.env[executor.config.env]) return null
  if (existsSync(join(process.cwd(), executor.config.file))) return null
  const path = join(main, executor.config.file)
  if (!existsSync(path)) return { line: "CONFIG=missing — executor default model" }
  return { env: executor.config.env, path, model: configModel(path), line: `CONFIG=main-checkout ${path}` }
}

// `model` z projektowego configu (JSON). Niepoprawny plik nie wywraca runu — tylko brak modelu.
function configModel(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8")).model || ""
  } catch {
    return ""
  }
}

function fail(message, klasa = "ERROR") {
  process.stderr.write(`[headless] ${message}\n`)
  // Synchronicznie: `fail` nie wraca, więc kod po nim nie może dopisać drugiego wiersza.
  if (call) {
    process.stdout.write(finishRow(2, klasa, {
      sprawdz: message,
      dzialanie: klasa === "POLITYKA" ? "odrzucono przed startem" : "przerwano: błąd wywołania",
    }))
  }
  process.exit(2)
}

function which(bin) {
  const exts = process.platform === "win32" ? (process.env.PATHEXT || ".EXE;.CMD;.BAT").split(";") : [""]
  for (const dir of (process.env.PATH || "").split(delimiter)) {
    for (const ext of exts) {
      const path = join(dir, bin + ext.toLowerCase())
      if (dir && existsSync(path)) return path
    }
  }
  return null
}

// Shim npm (`opencode2.cmd`) wskazuje prawdziwą binarkę jako `"%dp0%\…\x.exe"` (stary
// cmd-shim, pnpm, yarn: `"%~dp0\…\x.exe"`). Uruchomiona
// wprost omija cmd.exe — Node od CVE-2024-27980 nie startuje `.cmd` bez powłoki, a powłoka
// rozbiłaby wieloliniową treść. `%dp0%\node.exe` to sonda shima skryptu JS, nie wykonawca.
export function resolveShim(shim) {
  let text = ""
  try {
    text = readFileSync(shim, "utf8")
  } catch {
    return null
  }
  for (const [, rel] of text.matchAll(/"%(?:~dp0|dp0%)\\([^"%]+\.exe)"/gi)) {
    const exe = join(dirname(shim), ...rel.split("\\"))
    if (basename(exe).toLowerCase() !== "node.exe" && existsSync(exe)) return exe
  }
  return null
}

function profileClients() {
  let text = ""
  try {
    text = readFileSync(join(".ai", "project.profile.yaml"), "utf8")
  } catch {
    fail("brak .ai/project.profile.yaml — uruchom z roota projektu z kitem")
  }
  // `clients: a,b`, `clients: [a, b]` albo lista blokowa `- a` — jak `_clients_value` w cli.py.
  const match = /^clients:[ \t]*([^#\n]*)((?:\n[ \t]+-[^\n]*)*)/m.exec(text)
  const raw = match ? `${match[1]},${match[2].replace(/^[ \t]+-/gm, ",")}` : ""
  const list = raw.split(/[,\n]/).map((c) => c.replace(/[[\]'"\s]/g, "").toLowerCase()).filter(Boolean)
  return list.includes("all") ? KNOWN_CLIENTS : list.map((c) => (c === "copilot" ? "vscode" : c))
}

// Język tematu commitów z Profilu (`language:`); bez klucza albo pliku — `pl`, jak w bootstrapie kita (#398).
function profileLanguage() {
  try {
    const match = /^language:[ \t]*["']?([\w-]+)/m.exec(readFileSync(join(".ai", "project.profile.yaml"), "utf8"))
    return match ? match[1].toLowerCase() : "pl"
  } catch {
    return "pl"
  }
}

function profileText() {
  try {
    return readFileSync(join(".ai", "project.profile.yaml"), "utf8")
  } catch {
    return ""
  }
}

// `models.<klient>.<tier>` z Profilu (#397): tani model checkera zacięcia. Bez klucza albo pliku — null.
// Klucze klienta na wcięciu 2, tier na 4; `agents: light:` to inna sekcja i nie jest modelem.
export function profileModel(client, tier, text = profileText()) {
  let inModels = false
  let inClient = false
  for (const raw of lines(text)) {
    const line = raw.replace(/\s+#.*$/, "")
    if (/^\S/.test(line)) {
      inModels = line.trimEnd() === "models:"
      inClient = false
      continue
    }
    const key = /^(\s+)([\w-]+):(?:[ \t]+(.*?))?[ \t]*$/.exec(line)
    if (!inModels || !key) continue
    if (key[1].length <= 2) {
      inClient = key[2] === client
    } else if (inClient && key[2] === tier) {
      return key[3]?.replace(/^["']|["']$/g, "") || null
    }
  }
  return null
}

const KEEP_RUNS = 5

// Plik wycinka runu w CTX (#396).
const excerptFile = (ctx, runName) => join(ctx, `headless-excerpt-${runName}.txt`)

// Runy z klasą inną niż OK, których wycinka nie ma w CTX (#396): ich logi zostają, dopóki wycinek nie
// trafi do bufora nocy. Bez CTX nie ma bufora, więc nic nie chronimy.
function failedRunsWithoutExcerpt(ctx) {
  if (!ctx) return new Set()
  return new Set(readRows(ctx)
    .filter((row) => row.klasa && row.klasa !== "OK" && row.log)
    .map((row) => basename(dirname(row.log)))
    .filter((name) => !existsSync(excerptFile(ctx, name))))
}

// Nazwa runu zaczyna się od ISO-czasu, więc sort leksykograficzny = chronologiczny.
// ponytail: >5 równoległych runów skasuje katalog żywego runu; lock per run, gdy to realne.
// Bieżący run poza sortem: przy cofniętym zegarze też zostaje.
function pruneRuns(runsDir, current, ctx) {
  const keep = failedRunsWithoutExcerpt(ctx)
  const runs = readdirSync(runsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name !== current)
    .map((entry) => entry.name)
    .sort()
  for (const name of runs.slice(0, -(KEEP_RUNS - 1))) {
    if (keep.has(name)) continue
    try {
      rmSync(join(runsDir, name), { recursive: true, force: true })
    } catch {
      // Sprzątanie best-effort: zablokowany katalog nie może zatrzymać zadania.
    }
  }
}

function parse(argv) {
  const opts = { host: "", executor: "", model: "", ctx: "", timeoutMin: DEFAULT_TIMEOUT_MIN, heartbeatMin: DEFAULT_HEARTBEAT_MIN, words: [] }
  // Wartość flagi nie może być kolejną flagą — `--model --timeout 5` to błąd, nie model.
  const value = (i) => {
    const v = argv[i + 1]
    if (!v || v.startsWith("--")) fail(`${argv[i]} wymaga wartości`)
    return v
  }
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === "--host") opts.host = value(i++).toLowerCase()
    else if (arg === "--model") opts.model = value(i++)
    else if (arg === "--timeout") {
      opts.timeoutMin = Number(value(i++))
      if (!(opts.timeoutMin > 0)) fail(`--timeout wymaga liczby minut > 0, dostał: ${argv[i]}`)
    } else if (arg === "--heartbeat") {
      opts.heartbeatMin = Number(value(i++))
      if (!(opts.heartbeatMin > 0)) fail(`--heartbeat wymaga liczby minut > 0, dostał: ${argv[i]}`)
    } else if (arg === "--ctx") {
      opts.ctx = resolve(value(i++))
    } else if (arg === "--") opts.words.push(...argv.splice(i + 1))
    else if (arg.startsWith("--")) fail(`nieznana flaga ${arg}. Dozwolone: ${FLAGS.join(", ")}`)
    else if (!opts.executor) opts.executor = arg.toLowerCase()
    else opts.words.push(arg)
  }
  return opts
}

// Windows nie ma grup procesów, a `taskkill /T` po wyjściu wykonawcy nie znajdzie już
// jego dzieci (rodzic martwy). Dlatego w trakcie zbieramy potomków co kilka sekund.
// ponytail: polling co 5 s — proces żyjący krócej niż odstęp może umknąć; Job Object
// wymagałby natywnego modułu.
const descendants = new Set()

function snapshotDescendants(rootPid) {
  const script = "Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId)\" }"
  execFile("powershell", ["-NoProfile", "-NonInteractive", "-Command", script], { windowsHide: true }, (err, out) => {
    if (err) return
    const children = new Map()
    for (const line of out.split(/\r?\n/)) {
      const [pid, parent] = line.trim().split(/\s+/).map(Number)
      if (pid && parent) children.set(parent, [...(children.get(parent) || []), pid])
    }
    const queue = [rootPid, ...descendants]
    while (queue.length) {
      for (const pid of children.get(queue.shift()) || []) {
        if (!descendants.has(pid)) {
          descendants.add(pid)
          queue.push(pid)
        }
      }
    }
  })
}

const KILL_GRACE_MS = 2000

function groupAlive(pid) {
  try {
    process.kill(-pid, 0)
    return true
  } catch {
    return false
  }
}

// Unix: najpierw SIGTERM, żeby wykonawca zamknął to, co ma poza grupą (serwer opencode
// ma własną grupę i po samym SIGKILL zostaje osierocony); po KILL_GRACE_MS — SIGKILL.
// Jedno zabijanie na dziecko: timeout, handler sygnału i `finally` czekają na tę samą obietnicę.
// SIGTERM idzie synchronicznie, jeszcze przed pierwszym `await`.
function killTree(child) {
  return (child.killing ??= killTreeOnce(child))
}

async function killTreeOnce(child) {
  if (!child.pid) return
  if (process.platform === "win32") {
    for (const pid of [child.pid, ...descendants]) {
      spawnSync("taskkill", ["/T", "/F", "/PID", String(pid)], { stdio: "ignore", windowsHide: true })
    }
    return
  }
  try {
    process.kill(-child.pid, "SIGTERM")
  } catch {
    return // Grupa już pusta — nie ma czego sprzątać.
  }
  const deadline = Date.now() + KILL_GRACE_MS
  while (groupAlive(child.pid) && Date.now() < deadline) await new Promise((done) => setTimeout(done, 100))
  try {
    process.kill(-child.pid, "SIGKILL")
  } catch {
    // Grupa skończyła się sama po SIGTERM.
  }
}

// Node nie zna PID nadawcy sygnału, więc log dostaje migawkę podejrzanych: przodków wrappera
// i grupę wykonawcy. Tylko `comm`, bez argumentów — w argumentach wykonawcy jest prompt.
function processSnapshot(childPid) {
  if (process.platform === "win32") return ""
  const r = spawnSync("ps", ["-A", "-o", "pid=,ppid=,pgid=,lstart=,comm="], { encoding: "utf8", timeout: 3000 })
  if (r.status !== 0 || !r.stdout) return "(ps niedostępne)\n"
  const rows = r.stdout.split("\n").filter((l) => l.trim()).map((line) => {
    const [pid, ppid, pgid, ...rest] = line.trim().split(/\s+/)
    return { pid: Number(pid), ppid: Number(ppid), pgid: Number(pgid), line: [pid, ppid, pgid, ...rest].join(" ") }
  })
  const byPid = new Map(rows.map((row) => [row.pid, row]))
  const picked = []
  for (let pid = process.pid; byPid.has(pid) && !picked.includes(byPid.get(pid)); pid = byPid.get(pid).ppid) {
    picked.push(byPid.get(pid))
  }
  if (childPid) picked.push(...rows.filter((row) => row.pgid === childPid && !picked.includes(row)))
  return "PID PPID PGID START COMM\n" + picked.map((row) => row.line).join("\n") + "\n"
}

// Git w katalogu roboczym; poza repo (albo bez gita) — null, raport pomija pola.
// `--no-optional-locks`: `status` z heartbeatu nie bierze index.lock, więc nie wywraca
// commita wykonawcy. Limit 15 s — zawieszony git nie blokuje event loop ani `--timeout`.
function git(...args) {
  const r = spawnSync("git", ["--no-optional-locks", ...args], { encoding: "utf8", windowsHide: true, timeout: 15_000, killSignal: "SIGKILL" })
  return r.status === 0 ? r.stdout.trimEnd() : null
}

// Stan gita jako źródło postępu: HEAD i git status (#397). Poza repo — pusty, stały tekst.
const gitState = () => [git("rev-parse", "HEAD"), git("status", "--porcelain")].join("\n")

const lines = (text) => (text ? text.split("\n") : [])

// Kontrola postępu co 30 min (#397): jeden próg dla całego wywołania.
export const STALL_CHECK_MIN = 30
// `HEADLESS_STALL_CHECK_MS` skraca interwał w testach integracyjnych (#408); produkcja bez zmiany.
const stallCheckMs = () => {
  const ms = Number(process.env.HEADLESS_STALL_CHECK_MS)
  return ms > 0 ? ms : STALL_CHECK_MIN * 60_000
}

// Czas CPU (utime + stime, w tickach) procesu wykonawcy i jego potomków z /proc. Bez /proc
// (macOS, Windows) — null: wtedy postęp liczą log i git. Rodzic liczymy z pola ppid, nie z grupy
// procesów, bo serwer opencode ma własną grupę.
export function cpuTicksOfTree(rootPid, proc = "/proc") {
  let names
  try {
    names = readdirSync(proc)
  } catch {
    return null
  }
  const children = new Map()
  const ticks = new Map()
  for (const name of names) {
    if (!/^\d+$/.test(name)) continue
    let stat
    try {
      stat = readFileSync(join(proc, name, "stat"), "utf8")
    } catch {
      continue // proces zniknął między listą katalogu a odczytem
    }
    // Po `)` zamykającym nazwę: stan (0), ppid (1), …, utime (11), stime (12).
    const fields = stat.slice(stat.lastIndexOf(")") + 2).split(" ")
    const pid = Number(name)
    children.set(Number(fields[1]), [...(children.get(Number(fields[1])) || []), pid])
    ticks.set(pid, Number(fields[11]) + Number(fields[12]))
  }
  let total = 0
  const queue = [rootPid]
  for (const pid of queue) {
    total += ticks.get(pid) ?? 0
    queue.push(...(children.get(pid) || []))
  }
  return total
}

// Kontrola postępu co `intervalMs` (#397). Postęp = wzrost bajtów wyjścia wykonawcy, zmiana HEAD
// albo git status, wzrost CPU potomków (spadek to koniec procesu, nie praca). Brak postępu w oknie
// → `onStall({ idleMs })`, czyli czas od ostatniej zmiany. Źródła, zegar i harmonogram są wstrzyknięte.
export function watchProgress({
  read,
  onStall,
  intervalMs = STALL_CHECK_MIN * 60_000,
  now = Date.now,
  schedule = setInterval,
  unschedule = clearInterval,
}) {
  let previous = read()
  let changedAt = now()
  const tick = () => {
    const current = read()
    const progressed = current.output > previous.output
      || current.git !== previous.git
      || (current.cpu ?? 0) > (previous.cpu ?? 0)
    previous = current
    if (progressed) changedAt = now()
    const idleMs = now() - changedAt
    if (!progressed) onStall({ idleMs })
    return { progressed, idleMs }
  }
  const timer = schedule(tick, intervalMs)
  return { tick, stop: () => unschedule(timer) }
}

// Checker zacięcia (#397): tani model z `models.claude.light` tylko opisuje, co robi wykonawca.
// Nie decyduje o zabiciu — brak postępu zabija zawsze, a opis trafia do raportu.
export const CHECKER_TIMEOUT_MS = 60_000
export const CHECKER_LOG_LINES = 40
// Asynchronicznie: spawnSync wstrzymałby event loop na czas checkera — sygnały hosta i SIGKILL po
// SIGTERM czekałyby do 60 s. Bez narzędzi i MCP: checker tylko pisze, niczego nie wywołuje i o nic nie pyta.
const runChecker = (args, input, { timeout }) => new Promise((done) => {
  const child = spawn("claude", args, { stdio: ["pipe", "pipe", "ignore"], timeout, killSignal: "SIGKILL", windowsHide: true })
  let stdout = ""
  child.stdout.setEncoding("utf8").on("data", (text) => { stdout += text })
  child.on("error", (error) => done({ error, status: null, stdout }))
  child.on("close", (status, signal) => done({ status: status ?? signal, stdout }))
  child.stdin.on("error", () => {})
  child.stdin.end(input)
})

export async function describeStall({ tail, status, idleMs, model, run = runChecker }) {
  if (!model) return "checker wyłączony: brak models.claude.light w Profilu"
  const log = (Array.isArray(tail) ? tail : lines(tail)).slice(-CHECKER_LOG_LINES).join("\n")
  const prompt = [
    `Wykonawca headless nie dał postępu przez ${Math.round(idleMs / 60_000)} min (bez nowych bajtów wyjścia, zmiany HEAD i git status, wzrostu CPU).`,
    "Opisz po polsku w 1–3 zdaniach, co wykonawca robi i czy wygląda na zawieszonego. Nie decyduj o zabiciu.",
    "",
    "git status --short:",
    status || "(czysto)",
    "",
    `ostatnie ${CHECKER_LOG_LINES} linii wyjścia:`,
    log,
  ].join("\n")
  const r = await run(["-p", "--model", model, "--tools", "", "--strict-mcp-config"], prompt, { timeout: CHECKER_TIMEOUT_MS })
  if (r.error || r.status !== 0) return `checker niedostępny: ${r.error?.message ?? `kod ${r.status}`}`
  const text = lines(r.stdout).map((l) => l.trim()).filter(Boolean).slice(0, 3).join(" ")
  return text.slice(0, 600) || "checker bez odpowiedzi"
}

// Wiersz wywołania (#396): jedna linia JSON na końcu każdego wywołania, także przy sygnale, błędzie
// i odmowie przed startem. Stan wywołania zbiera się po drodze, wiersz składa się na końcu.
// Klasy: OK, LIMIT (pauza), HANG (timeout albo sygnał), ERROR (kod ≠ 0 albo błąd wywołania),
// MODEL (nieznany model agy), SUSPECT (exit 0 bez zmian), POLITYKA (wpis stasha, commit bez trailera albo odmowa wykonawcy).
let call = null
const CHECK_HINT = {
  OK: "-",
  LIMIT: "wznowić po resecie z linii PAUSE",
  HANG: "sprawdzić ostatnie linie logu (zacięcie albo timeout)",
  ERROR: "sprawdzić wycinek logu (kod i ostatnie linie)",
  MODEL: "wybrać model z listy dostępnych w raporcie",
  SUSPECT: "sprawdzić, czy wykonawca cokolwiek zrobił",
  POLITYKA: "sprawdzić złamanie zasad kitu (wpis stasha, commit bez trailera) albo odmowę wywołania",
}

function startCall(opts) {
  return {
    ctx: opts.ctx || null,
    ticket: ticketNumber(),
    start: new Date(),
    chain: [],
    model: null,
    log: null,
    klasa: null,
    actions: [],
    untrailed: [],
  }
}

function callRow(code, klasa, { sprawdz, dzialanie } = {}) {
  return {
    ticket: call.ticket ?? "-",
    wykonawca: call.chain.at(-1) ?? "-",
    lancuch: call.chain.join(">") || "-",
    model: call.model,
    kod: code,
    klasa,
    start: call.start.toISOString(),
    koniec: new Date().toISOString(),
    log: call.log,
    sprawdz: sprawdz ?? CHECK_HINT[klasa] ?? "-",
    dzialanie: dzialanie ?? (call.actions.join("; ") || "-"),
  }
}

const ROW_FILE = "headless-rows.jsonl"
const EXCERPT_LINES = 40

// Składa wiersz, zapisuje go w buforze nocy (gdy jest CTX) i zwraca linię do wypisania.
function finishRow(code, klasa, extra) {
  const row = callRow(code, klasa, extra)
  recordRow(row)
  return `${JSON.stringify(row)}\n`
}

// Bufor nocy: wiersz dopisany do `<ctx>/headless-rows.jsonl`, a przy klasie innej niż OK wycinek logu.
// Błąd zapisu nie wywraca wywołania — tylko ostrzeżenie na stderr.
function recordRow(row) {
  if (!call.ctx) return
  try {
    mkdirSync(call.ctx, { recursive: true })
    appendFileSync(join(call.ctx, ROW_FILE), `${JSON.stringify(row)}\n`)
  } catch (err) {
    process.stderr.write(`[headless] bufor nocy ${call.ctx} niedostępny: ${err.message}\n`)
    return
  }
  if (row.klasa === "OK" || !row.log) return
  try {
    writeExcerpt(call.ctx, row.log)
  } catch (err) {
    process.stderr.write(`[headless] wycinek logu nie zapisany w ${call.ctx}: ${err.message}\n`)
  }
}

// Wycinek: ostatnie EXCERPT_LINES linii logu; gdy raport końcowy leży wcześniej, zaczynamy od niego.
function writeExcerpt(ctx, logPath) {
  const all = lines(readFileSync(logPath, "utf8"))
  const tailStart = Math.max(0, all.length - EXCERPT_LINES)
  const reportStart = all.lastIndexOf("[headless] raport końcowy")
  const start = reportStart >= 0 ? Math.min(reportStart, tailStart) : tailStart
  writeFileSync(excerptFile(ctx, basename(dirname(logPath))), `${all.slice(start).join("\n")}\n`)
}

// Wiersz jako ostatnia linia wyjścia; callback przed `exit` — stdout do potoku bywa asynchroniczny
// (macOS, Windows).
function exitWithRow(code, klasa = "ERROR", extra) {
  if (!call) process.exit(code)
  process.stdout.write(finishRow(code, klasa, extra), () => process.exit(code))
}

// Wiersze bufora nocy; zepsuta linia nie blokuje raportu.
function readRows(ctx) {
  const path = join(ctx, ROW_FILE)
  if (!existsSync(path)) return []
  return lines(readFileSync(path, "utf8")).flatMap((line) => {
    try {
      return [JSON.parse(line)]
    } catch {
      return []
    }
  })
}

const ticketHeading = (row) => (row.ticket && row.ticket !== "-" ? `#${row.ticket}` : "bez ticketu")

// Jedno wywołanie w HEADLESS REPORT: wynik w jednej linii, uwaga i log pod spodem.
// Wycinek w CTX przeżywa `pruneRuns`, więc wskazujemy go obok logu.
function callEntry(row, ctx) {
  const model = row.model ?? "domyślny"
  const note = row.sprawdz && row.sprawdz !== "-" ? `\n  - sprawdź: ${row.sprawdz}` : ""
  const excerpt = ctx && row.log ? excerptFile(ctx, basename(dirname(row.log))) : null
  const cut = excerpt && existsSync(excerpt) ? `\n  - wycinek: ${excerpt}` : ""
  return `- ${row.start} · ${row.wykonawca} (${row.lancuch}) · model ${model} · kod ${row.kod} · ${row.klasa} · ${row.dzialanie}${note}\n  - log: ${row.log ?? "brak"}${cut}`
}

// HEADLESS REPORT po tickecie i lista wszystkich wywołań w kolejności (#396).
function buildReport(rows, ctx) {
  const calls = [...rows].sort((a, b) => String(a.start).localeCompare(String(b.start)))
  if (!calls.length) return "## HEADLESS REPORT\nbrak wywołań headless w tej nocy\n\n## Raport listy\nbrak wywołań\n"
  const groups = new Map()
  for (const row of calls) {
    const heading = ticketHeading(row)
    groups.set(heading, [...(groups.get(heading) || []), row])
  }
  const out = ["## HEADLESS REPORT"]
  for (const [heading, group] of groups) out.push("", `### ${heading}`, ...group.map((row) => callEntry(row, ctx)))
  out.push("", "## Raport listy (wszystkie wywołania w kolejności)")
  calls.forEach((row, i) => out.push(`${i + 1}. ${row.start} · ${ticketHeading(row)} · ${row.wykonawca} · ${row.klasa} (kod ${row.kod})`))
  return `${out.join("\n")}\n`
}

// `--report --ctx <katalog>` (#396): raport nocy z bufora. Bufor kasujemy dopiero po udanym wypisaniu,
// więc przerwany raport go zostawia.
function reportMain(argv) {
  const at = argv.indexOf("--ctx")
  if (at < 0 || !argv[at + 1] || argv[at + 1].startsWith("--")) fail("--report wymaga --ctx <katalog>")
  const ctx = resolve(argv[at + 1])
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.once(signal, () => process.exit(128 + constants.signals[signal]))
  }
  process.stdout.write(buildReport(readRows(ctx), ctx), (err) => {
    if (err) process.exit(1)
    rmSync(join(ctx, ROW_FILE), { force: true })
    process.exit(0)
  })
}

async function main() {
  // Wiersz także przy błędzie flag; CTX znany dopiero po parsowaniu.
  call = startCall({})
  const opts = parse(process.argv.slice(2))
  call.ctx = opts.ctx || null
  if (Object.hasOwn(EXECUTOR_ALIASES, opts.executor)) opts.executor = EXECUTOR_ALIASES[opts.executor]
  // Nazwa binarki (`opencode2`) działa jak nazwa wykonawcy.
  if (!EXECUTORS[opts.executor]) {
    opts.executor = Object.keys(EXECUTORS).find((k) => EXECUTORS[k].bins.includes(opts.executor)) || opts.executor
  }
  if (!KNOWN_CLIENTS.includes(opts.host)) fail(`--host musi być klientem kitu (${KNOWN_CLIENTS.join(", ")}), dostał: ${opts.host || "brak"}`)
  const allowed = profileClients().filter((c) => c !== opts.host && EXECUTORS[c])
  if (!opts.executor) fail(`podaj wykonawcę. Dozwoleni z ${opts.host}: ${allowed.join(", ") || "brak"}`)
  if (!allowed.includes(opts.executor)) {
    const why = opts.executor === opts.host
      ? `${opts.host} nie wywołuje sam siebie`
      : !EXECUTORS[opts.executor]
        ? `${opts.executor} nie ma trybu headless z guardami kita`
        : `${opts.executor} nie jest w clients: Profilu`
    fail(`${why}. Dozwoleni wykonawcy z ${opts.host}: ${allowed.join(", ") || "brak"}`, "POLITYKA")
  }

  let prompt = opts.words.join(" ")
  if (!prompt && !process.stdin.isTTY) prompt = readFileSync(0, "utf8")
  prompt = prompt.trim()
  if (!prompt) fail("pusta treść zadania — podaj ją w cudzysłowie albo na stdin")
  // Limit albo brak binarki → ta sama treść 1:1 do pozostałych tanich wykonawców; potem host.
  const chain = [opts.executor, ...FALLBACK_ORDER.filter((e) => e !== opts.executor && allowed.includes(e))]
    .map(resolveBin)
  if (!chain.some((c) => !c.why)) fail(`${chain[0].why}. Dozwoleni wykonawcy z ${opts.host}: ${allowed.join(", ")}`)
  // Zły `.agents/agy.json` ma wyjść od razu, nie po limicie pierwszego wykonawcy.
  if (chain.some((c) => c.name === "antigravity" && !c.why)) agyConfig()

  // Katalog runu sam się ignoruje w gicie — log i pliki robocze wykonawcy nie brudzą statusu.
  const runsDir = resolve(".ai", "headless-runs")
  const runDir = join(runsDir, `${new Date().toISOString().replace(/[:.]/g, "-")}-${opts.executor}`)
  mkdirSync(runDir, { recursive: true })
  writeFileSync(join(runsDir, ".gitignore"), "*\n")
  pruneRuns(runsDir, basename(runDir), call.ctx)
  const logPath = join(runDir, "headless.log")
  call.log = logPath
  const basePrompt = prompt
  const sessionFooter = footer(runDir, call.ticket, profileLanguage())
  prompt += sessionFooter

  // Wszystko, co wrapper i wykonawca piszą, trafia też do logu.
  const log = (text, stream = process.stdout) => {
    stream.write(text)
    appendFileSync(logPath, text)
  }
  process.stdout.write(`[headless] log: ${logPath}\n`)
  // Prompt nie trafia do logu — numer ticketu tak, żeby run dało się przypisać do issue.
  if (call.ticket) log(`[headless] ticket #${call.ticket}\n`)

  // Host, który zabija wrapper (koniec sesji, własny timeout), nie może zostawić wykonawcy
  // z uprawnieniami na edycje i bash.
  // `stopping`: po sygnale wyjście należy do handlera — runOnce i pętla zastępców stają.
  const current = { child: null, started: 0, stopping: false, report: () => "" }
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, async () => {
      if (current.stopping) return
      current.stopping = true
      const hadChild = !!current.child
      const killing = current.child ? killTree(current.child) : null
      const after = current.started ? ` po ${((Date.now() - current.started) / 1000).toFixed(1)} s od startu wykonawcy` : ""
      log(`[headless] sygnał ${signal}${after} (wrapper pid ${process.pid}, ppid ${process.ppid})\n`)
      log(processSnapshot(current.child?.pid))
      await killing
      log(current.report())
      if (hadChild) call.actions.push(`zabito drzewo procesów (sygnał ${signal})`)
      exitWithRow(128 + constants.signals[signal], hadChild ? "HANG" : "ERROR")
    })
  }

  let code = null
  for (const [i, { name, executor, bin, needsShell, why }] of chain.entries()) {
    const next = chain.slice(i + 1).find((c) => !c.why)?.name
    if (why) {
      log(`[headless] ${why}${next ? ` — przekazuję zadanie: ${name} → ${next}` : ""}\n`)
      if (!next) break
      continue
    }
    // `--model` dotyczy wykonawcy z wywołania; zastępca bierze swój domyślny model.
    const outcome = await runOnce({ opts, name, executor, bin, needsShell, model: i === 0 ? opts.model : "", prompt, log, current, last: !next })
    code = outcome.code
    // Zły model agy to błąd konfiguracji, nie wykonawcy: zastępca go nie naprawi, więc kończymy od razu.
    if (code === 0 || !next || call.klasa === "MODEL") {
      if (code !== 0 && !next) for (const c of chain.slice(i + 1)) log(`[headless] brak zastępcy ${c.name}: ${c.why}\n`)
      break
    }
    // Każdy błąd przekazuje zadanie 1:1 zastępcy: limit (75), HANG (timeout albo brak postępu), inny kod (#397).
    const reason = code === PAUSE_CODE ? `limit ${name}` : `${name} zakończony klasą ${call.klasa} (kod ${code})`
    call.actions.push(`przekazano 1:1: ${name} → ${next}`)
    log(`[headless] ${reason} — przekazuję zadanie 1:1: ${name} → ${next}\n`)
    // Zadanie 1:1 plus raport zabitego wykonawcy (#397, #408).
    prompt = `${basePrompt}\n\n---\nRaport zabitego wykonawcy (${name}, kod ${code}):\n${outcome.report}${sessionFooter}`
  }
  if (current.stopping) return
  // Sygnał w trakcie zapisu wiersza nie może dopisać drugiego.
  current.stopping = true
  log(`[headless] kod wyjścia: ${code}\n`)
  exitWithRow(code, call.klasa ?? "ERROR")
}

function resolveBin(name) {
  const executor = EXECUTORS[name]
  const found = executor.bins.map(which).find(Boolean)
  const bin = (process.platform === "win32" && /\.(cmd|bat)$/i.test(found || "") && resolveShim(found)) || found
  // `.cmd`/`.bat` (shim npm na Windows) idzie przez cmd.exe, który rozbija wieloliniowy
  // argument i interpretuje `& | >` — treść w argumencie byłaby niebezpieczna.
  const needsShell = process.platform === "win32" && /\.(cmd|bat)$/i.test(bin || "")
  const why = !bin
    ? `nie znaleziono ${executor.bins.join(" ani ")} w PATH`
    : needsShell && !executor.stdin
      ? `${bin} to skrypt cmd — treść w argumencie nie przejdzie bezpiecznie. Dodaj do PATH binarkę .exe ${name}`
      : ""
  return { name, executor, bin, needsShell, why }
}

async function runOnce({ opts, name, executor, bin, needsShell, model, prompt, log, current, last }) {
  // Fallback configu tylko w linked worktree; poza nim null i zachowanie bez zmian.
  const config = configFor(executor)
  const args = executor.args(model || config?.model || "", prompt)
  const shownArgs = args.map((a) => (a.includes(prompt) ? "<prompt>" : a))
  log(`[headless] ${opts.host} → ${name}: ${bin} ${shownArgs.join(" ")} (timeout ${opts.timeoutMin} min)\n`)

  const startHead = git("rev-parse", "HEAD")
  // SUSPECT tylko przy czystym starcie — przy brudnym `status` nie odróżni dopisania do już zmienionego pliku.
  const startClean = git("status", "--porcelain") === ""
  const startStash = new Set(lines(git("stash", "list", "--format=%H")))
  const started = Date.now()

  // Unix: własna grupa procesów (setsid), żeby zabić ją w całości. Windows: powłoka tylko dla
  // shima `.cmd` bez exe (wykonawca ze stdin); drzewo i tak sprząta taskkill /T.
  call.chain.push(name)
  call.model = model || config?.model || null
  const child = spawn(bin, args, {
    detached: process.platform !== "win32",
    shell: needsShell,
    stdio: [executor.stdin ? "pipe" : "ignore", "pipe", "pipe"],
    windowsHide: true,
    // Natywny mechanizm wskazania configu (opencode: `OPENCODE_CONFIG`), gdy worktree go nie ma.
    env: config?.env ? { ...process.env, [config.env]: config.path } : process.env,
  })
  const closed = new Promise((done) => child.on("close", done))
  // Ostatnie linie wykonawcy do heartbeatu i raportu; `partial` = linia bez `\n` jeszcze,
  // osobno per strumień. `setEncoding` nie tnie znaków UTF-8 na granicy chunków.
  const tail = []
  const partial = new Map()
  let lastOutput = Date.now()
  let stallReported = false
  // Ogon wyjścia (64 KB) — komunikat limitu rozpoznajemy dopiero po zakończeniu wykonawcy.
  let outputTail = ""
  // Bajty wyjścia wykonawcy (bez heartbeatu wrappera) — źródło postępu kontroli co 30 min (#397).
  let outBytes = 0
  const capture = (source, stream) => {
    source.setEncoding("utf8")
    partial.set(source, "")
    source.on("data", (text) => {
      log(text, stream)
      outBytes += Buffer.byteLength(text)
      outputTail = (outputTail + text).slice(-OUTPUT_TAIL_BYTES)
      lastOutput = Date.now()
      stallReported = false
      const parts = (partial.get(source) + text).split(/\r?\n/)
      partial.set(source, parts.pop())
      tail.push(...parts.filter((l) => l.trim()))
      tail.splice(0, tail.length - TAIL_LINES)
    })
  }
  capture(child.stdout, process.stdout)
  capture(child.stderr, process.stderr)
  const fullTail = () => [...tail, ...[...partial.values()].filter((l) => l.trim())]
  const lastLine = () => (fullTail().at(-1) || "").trim()
  const minutes = (ms) => Math.round(ms / 6000) / 10
  current.child = child
  current.started = started
  current.report = () => finalReport({
    startHead,
    tail: fullTail(),
    config: config?.line,
    stall: stallNote,
    tree: stallTree,
    changes: noteUntrailed(repoChanges({ startHead, startStash, checkNoChanges: false })),
  })

  const heartbeatMs = opts.heartbeatMin * 60_000
  const heartbeat = setInterval(() => {
    const status = git("status", "--short")
    const commits = startHead ? git("rev-list", "--count", `${startHead}..HEAD`) : null
    log(`[headless] ♥ ${minutes(Date.now() - started)} min | pliki: ${status === null ? "?" : lines(status).length}`
      + ` | commity: ${commits ?? "?"} | ostatnio: ${lastLine() || "—"}\n`)
    const silent = Date.now() - lastOutput
    // Tylko ostrzeżenie — zabija kontrola postępu albo `--timeout`. Raz na okres ciszy, żeby host budził się raz.
    if (silent >= 2 * heartbeatMs && !stallReported) {
      stallReported = true
      log(`[headless] możliwe zacięcie: brak wyjścia od ${minutes(silent)} min\n`)
    }
  }, heartbeatMs)
  if (executor.stdin) {
    // Wykonawca, który skończy przed odczytem treści, daje EPIPE — nie może wywrócić wrappera.
    child.stdin.on("error", () => {})
    child.stdin.end(prompt)
  }

  const poll = process.platform === "win32" ? setInterval(() => snapshotDescendants(child.pid), 5000) : undefined
  if (poll) snapshotDescendants(child.pid)

  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    killTree(child)
  }, opts.timeoutMin * 60_000)
  // Brak postępu przez STALL_CHECK_MIN min: zrzut drzewa i zabicie jak przy timeoucie, klasa HANG (#397).
  // Najpierw zrzut i zabicie, potem opis checkera w tle; raport końcowy czeka na `stallDescribed`.
  let stalled = false
  let stallNote = null
  let stallTree = null
  let stallDescribed = null
  const progress = watchProgress({
    intervalMs: stallCheckMs(),
    read: () => ({ output: outBytes, git: gitState(), cpu: cpuTicksOfTree(child.pid) }),
    onStall: ({ idleMs }) => {
      stalled = true
      const checkerInput = { tail: outputTail, status: git("status", "--short"), idleMs, model: profileModel("claude", "light") }
      stallTree = processSnapshot(child.pid)
      log(`[headless] brak postępu przez ${minutes(idleMs)} min — zabijam drzewo ${name}\n`)
      log(stallTree)
      killTree(child)
      stallDescribed = describeStall(checkerInput).then((note) => {
        stallNote = note
        log(`[headless] zacięcie: ${note}\n`)
      })
    },
  })

  let code
  try {
    code = await new Promise((resolve) => {
      child.on("error", (err) => {
        process.stderr.write(`[headless] nie uruchomiono ${bin}: ${err.message}\n`)
        resolve(2)
      })
      child.on("exit", (status, signal) => resolve(status ?? 128 + (constants.signals[signal] || 0)))
    })
  } finally {
    clearTimeout(timer)
    clearInterval(poll)
    clearInterval(heartbeat)
    progress.stop()
    await killTree(child)
  }
  if (current.stopping) await new Promise(() => {})
  // Po ubiciu drzewa potoki się zamykają — dociągamy resztę wyjścia (maks. 3 s).
  // `closed` złapany od startu — `close` mógł już przyjść przed `exit`.
  await Promise.race([closed, new Promise((done) => setTimeout(done, 3000))])
  current.child = null
  if (timedOut) {
    call.actions.push(`zabito drzewo procesów (timeout ${opts.timeoutMin} min)`)
    log(`[headless] timeout po ${opts.timeoutMin} min — drzewo procesów ${name} zabite\n`)
  }
  await stallDescribed
  if (stalled) call.actions.push(`zabito drzewo procesów (brak postępu ${minutes(stallCheckMs())} min)`)
  const hung = timedOut || stalled
  // Limit dostawcy to pauza do resetu, nie błąd — host ponawia po godzinie z linii PAUSE.
  // Limit wygrywa z timeoutem: wykonawca mógł wisieć na limicie do końca czasu.
  let pause = null
  let invalidModel = null
  const failed = hung || code !== 0
  const outTail = tailLines(outputTail)
  // Limit ma pierwszeństwo przed nieznanym modelem — pauza, nie błąd konfiguracji.
  const textLimit = failed && LIMIT_PATTERN.test(outTail)
  const isInvalidModel = failed && !hung && !textLimit && name === "antigravity"
    && AGY_MODEL_LIST.test(outTail) && AGY_MODEL_ERROR.test(outTail)
  if (isInvalidModel) {
    const available = parseAvailableModels(outTail)
    const detectedModel = detectUnknownModel(outTail, model || agyConfig().model)
    invalidModel = `${detectedModel ? `model ${detectedModel}` : "model"} nieznany wykonawcy agy${available.length ? `; dostępne: ${available.join(", ")}` : ""}`
    log(`[headless] ${invalidModel}\n`)
    code = 2
  }
  const quota = failed && !isInvalidModel && !textLimit && executor.quota ? executor.quota(bin) : null
  if (quota) log(`[headless] /quota ${name}: limit wyczerpany\n`)
  if (textLimit || quota) {
    pause = `PAUSE=rate-limit reset=${(quota ? quota.reset : resetIso(outTail)) ?? "brak"}`
    code = PAUSE_CODE
  } else if (hung) {
    code = 124
  }
  // PAUSE tylko u ostatniego — host czyta ją jako „przejmij”, a zastępca jeszcze nie ruszył.
  // Timeout i limit dają kod ≠ 0, więc `code === 0` wystarcza do oceny SUSPECT.
  const changes = noteUntrailed(repoChanges({ startHead, startStash, checkNoChanges: code === 0 && startClean }))
  const report = finalReport({ startHead, tail: fullTail(), pause: last ? pause : null, config: config?.line, invalidModel, stall: stallNote, tree: stallTree, changes })
  log(report)
  // Klasa wykonawcy idzie do wiersza (#396); kolejność jak w rozstrzyganiu wyniku: limit, model, timeout.
  call.klasa = pause ? "LIMIT" : invalidModel ? "MODEL" : hung ? "HANG" : code !== 0 ? "ERROR"
    : changes.added.length || call.untrailed.length ? "POLITYKA" : changes.suspect ? "SUSPECT" : "OK"
  return { code, report }
}

// Commity bez trailera zostają w wywołaniu także po przekazaniu 1:1 i po sygnale — klasa wiersza i dzialanie (#398).
function noteUntrailed(changes) {
  call.untrailed.push(...changes.untrailed)
  if (changes.untrailed.length) call.actions.push(`commity bez trailera: ${changes.untrailed.join(", ")}`)
  return changes
}

// Commity z `start..HEAD` bez trailera `Co-Authored-By` (#398), skróty hashów. Temat i język kontroluje
// review; historii nie przepisujemy. Błąd gita daje pustą listę — bez fałszywego naruszenia.
function untrailedCommits(startHead) {
  const records = (git("log", "--format=%h%x1f%B%x1e", `${startHead}..HEAD`) ?? "").split("\x1e")
  return records.flatMap((record) => {
    const cut = record.indexOf("\x1f")
    if (cut < 0) return []
    const hash = record.slice(0, cut).trim()
    const hasTrailer = record.slice(cut + 1).split("\n").some(isCoauthorTrailer)
    return hash && !hasTrailer ? [hash] : []
  })
}

// Stan repo po wykonawcy: status, nowe wpisy stasha i SUSPECT. Z tego powstają raport i klasa wiersza (#396).
function repoChanges({ startHead, startStash, checkNoChanges }) {
  const status = git("status", "--short")
  // Po hashach, nie po liczbie — `drop` + nowy wpis nie zmienia liczby.
  const added = lines(git("stash", "list", "--format=%H%x09%gd: %gs"))
    .map((l) => l.split("\t"))
    .filter(([hash]) => !startStash.has(hash))
    .map(([, entry]) => entry)
  // Exit 0, a w drzewie, historii i stashu nic nowego — wykonawca mógł nic nie zrobić.
  const suspect = checkNoChanges && status === "" && !added.length
    && startHead !== null && git("rev-parse", "HEAD") === startHead
  const untrailed = startHead !== null ? untrailedCommits(startHead) : []
  return { status, added, suspect, untrailed }
}

// Raport końcowy — zawsze, także po timeoucie: co wykonawca zostawił w drzewie, w historii
// i w stashu. Stasha nie zdejmujemy (`pop` może dać konflikt) — tylko ostrzeżenie.
export function finalReport({ startHead, tail, pause, config, invalidModel, stall, tree, changes }) {
  const { status, added, suspect, untrailed } = changes
  const out = ["[headless] raport końcowy"]
  if (pause) out.push(`## ${pause}`)
  if (invalidModel) out.push(`## nieznany model: ${invalidModel}`)
  if (stall) out.push(`## zacięcie: ${stall}`)
  if (tree) out.push("## drzewo procesów przy zabiciu", tree.trimEnd())
  if (suspect) out.push("## SUSPECT=no-changes")
  // Skąd wzięty config wykonawcy (worktree): główny checkout albo brak — nigdy cicho.
  if (config) out.push(`## ${config}`)
  if (status !== null) out.push("## git status --short", status || "(czysto)")
  if (startHead) out.push(`## git log ${startHead.slice(0, 7)}..HEAD --oneline`, git("log", `${startHead}..HEAD`, "--oneline") || "(brak commitów)")
  if (added.length) {
    out.push("## UWAGA: nowe wpisy stasha — praca wykonawcy może tam być; nie zdjęte automatycznie (`git stash pop` ręcznie)", ...added)
  }
  if (untrailed.length) out.push(`## UWAGA: commity bez trailera \`${COAUTHOR_TRAILER}\` — poprawić na branchu ticketu przed push (nie na dev): ${untrailed.join(" ")}`)
  out.push(`## ostatnie ${TAIL_LINES} linii wykonawcy`, ...tail.slice(-TAIL_LINES))
  return `${out.join("\n")}\n`
}

// Import (testy `resolveShim`) nie uruchamia wykonawcy — tylko start wprost z `node`.
// Porównanie realpath, nie URL: `--preserve-symlinks-main` zostawia w URL ścieżkę symlinka,
// a Windows różni się wielkością liter (litera dysku).
const norm = (p) => {
  const real = realpathSync(p)
  return process.platform === "win32" ? real.toLowerCase() : real
}
const isMain = (() => {
  try {
    return !!process.argv[1] && norm(fileURLToPath(import.meta.url)) === norm(process.argv[1])
  } catch {
    return false
  }
})()
if (isMain) {
  const argv = process.argv.slice(2)
  if (argv.includes("--report")) {
    reportMain(argv.filter((a) => a !== "--report"))
  } else {
    await main().catch((err) => {
      // Błąd poza ścieżkami z `fail` nie może wyjść bez wiersza.
      process.stderr.write(`[headless] błąd wewnętrzny: ${err?.stack || err}\n`)
      exitWithRow(1, "ERROR", { sprawdz: String(err?.message || err) })
    })
  }
}
