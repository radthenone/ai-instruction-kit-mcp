#!/usr/bin/env node
/**
 * Wrapper `/headless` — uruchamia innego klienta kitu w trybie headless i sprząta po nim.
 *
 *   node .ai/headless.mjs --host <klient> <wykonawca> [--model <id>] [--timeout <min>] [--heartbeat <min>] [treść…]
 *
 * Treść: argumenty po fladze albo (bez nich) stdin — słowo w słowo, plus stała stopka.
 * `--host` wstawia bootstrap w pliku agenta każdego klienta; wykonawca musi być w tabeli
 * EXECUTORS, w `clients:` Profilu i różny od hosta. Model: `--model` > projektowy config
 * wykonawcy (np. `model` w opencode.json) > domyślny model wykonawcy.
 *
 * Po zakończeniu, błędzie albo timeoucie wrapper zabija całe drzewo procesów wykonawcy
 * (Unix: grupa procesów, Windows: `taskkill /T /F`) — razem z jego LSP i serwerami MCP.
 * Kody wyjścia: kod wykonawcy, 124 = timeout, 2 = błędne wywołanie, 75 = pauza limitu
 * dostawcy wykonawcy (nie błąd; linia `PAUSE=rate-limit reset=<ISO|brak>` w raporcie).
 * Pierwszeństwo: limit w ogonie wyjścia wygrywa też z timeoutem (75, nie 124).
 *
 * Wyjście wykonawcy idzie dalej i do logu w katalogu runu `.ai/headless-runs/<start>/`
 * (ścieżka w pierwszej linii). Co `--heartbeat` minut linia `[headless] ♥` ze stanem repo,
 * po 2 interwałach ciszy ostrzeżenie o zacięciu. Na końcu (także 124) raport: status, commity
 * od startu, nowe wpisy stasha, ostatnie linie wykonawcy. Liczy to Node — zero tokenów.
 */
import { execFile, spawn, spawnSync } from "node:child_process"
import { appendFileSync, existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs"
import { constants } from "node:os"
import { basename, delimiter, dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const KNOWN_CLIENTS = ["cursor", "claude", "codex", "vscode", "kiro", "kilo", "antigravity", "opencode"]
const FLAGS = ["--model", "--timeout", "--heartbeat"]
const DEFAULT_TIMEOUT_MIN = 60
const DEFAULT_HEARTBEAT_MIN = 10
const TAIL_LINES = 20
// Pauza limitu dostawcy wykonawcy (nie błąd): kod wyjścia 75 (EX_TEMPFAIL).
const PAUSE_CODE = 75
// Komunikaty limitu opencode/Codex/agy i innych (watchdog.sh czyta limit Claude z pól JSON
// transkryptu, nie z tekstu — tam wzorca nie ma). agy sprawdza też `/quota` (`quota` w EXECUTORS).
const LIMIT_PATTERN = /usage limit|\brate[ _-]limit|session limit|quota exceeded|quota exhausted|resource_exhausted|too many requests|api error: 429/i
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

const footer = (runDir, ticket) => `

---
Zasady tej sesji (headless, bez użytkownika):${ticket ? `
- Ticket #${ticket}: przeczytaj \`gh issue view ${ticket} --comments\` — to specyfikacja zadania.` : ""}
- Katalog runu: ${runDir} — logi testów, skrypty i pliki robocze tylko tam, nie w repo.
- Nie używaj \`git stash\`, \`git checkout\` ani \`git reset\`. Porównanie z bazą: \`node .ai/worktree.mjs add ${join(runDir, 'base')} --detach <ref> --plain\` (nie gołym \`git worktree add --detach\`), na końcu \`node .ai/worktree.mjs remove ${join(runDir, 'base')}\` (nie \`git worktree remove\`).
- Ticket z więcej niż 3 kryteriami akceptacji albo więcej niż jedną aplikacją/pakietem: najpierw plan 5–10 kroków.
- Praca test-first: test czerwony → kod → test zielony → lokalny commit po każdym zielonym kroku.
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

function fail(message) {
  process.stderr.write(`[headless] ${message}\n`)
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

function parse(argv) {
  const opts = { host: "", executor: "", model: "", timeoutMin: DEFAULT_TIMEOUT_MIN, heartbeatMin: DEFAULT_HEARTBEAT_MIN, words: [] }
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

function killTree(child) {
  if (!child.pid) return
  if (process.platform === "win32") {
    for (const pid of [child.pid, ...descendants]) {
      spawnSync("taskkill", ["/T", "/F", "/PID", String(pid)], { stdio: "ignore", windowsHide: true })
    }
  } else {
    try {
      process.kill(-child.pid, "SIGKILL")
    } catch {
      // Grupa już pusta — nie ma czego sprzątać.
    }
  }
}

// Git w katalogu roboczym; poza repo (albo bez gita) — null, raport pomija pola.
// `--no-optional-locks`: `status` z heartbeatu nie bierze index.lock, więc nie wywraca
// commita wykonawcy. Limit 15 s — zawieszony git nie blokuje event loop ani `--timeout`.
function git(...args) {
  const r = spawnSync("git", ["--no-optional-locks", ...args], { encoding: "utf8", windowsHide: true, timeout: 15_000, killSignal: "SIGKILL" })
  return r.status === 0 ? r.stdout.trimEnd() : null
}

const lines = (text) => (text ? text.split("\n") : [])

async function main() {
  const opts = parse(process.argv.slice(2))
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
    fail(`${why}. Dozwoleni wykonawcy z ${opts.host}: ${allowed.join(", ") || "brak"}`)
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
  const logPath = join(runDir, "headless.log")
  const ticket = ticketNumber()
  prompt += footer(runDir, ticket)

  // Wszystko, co wrapper i wykonawca piszą, trafia też do logu.
  const log = (text, stream = process.stdout) => {
    stream.write(text)
    appendFileSync(logPath, text)
  }
  process.stdout.write(`[headless] log: ${logPath}\n`)
  // Prompt nie trafia do logu — numer ticketu tak, żeby run dało się przypisać do issue.
  if (ticket) log(`[headless] ticket #${ticket}\n`)

  // Host, który zabija wrapper (koniec sesji, własny timeout), nie może zostawić wykonawcy
  // z uprawnieniami na edycje i bash.
  const current = { child: null, report: () => "" }
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => {
      if (current.child) killTree(current.child)
      log(current.report())
      process.exit(128 + constants.signals[signal])
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
    code = await runOnce({ opts, name, executor, bin, needsShell, model: i === 0 ? opts.model : "", prompt, log, current, last: !next })
    if (code !== PAUSE_CODE || !next) {
      if (code === PAUSE_CODE) for (const c of chain.slice(i + 1)) log(`[headless] brak zastępcy ${c.name}: ${c.why}\n`)
      break
    }
    log(`[headless] limit ${name} — przekazuję zadanie 1:1: ${name} → ${next}\n`)
  }
  log(`[headless] kod wyjścia: ${code}\n`)
  // Pusty zapis z callbackiem — stdout do potoku bywa asynchroniczny (macOS, Windows).
  process.stdout.write("", () => process.exit(code))
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
  const startStash = new Set(lines(git("stash", "list", "--format=%H")))
  const started = Date.now()

  // Unix: własna grupa procesów (setsid), żeby zabić ją w całości. Windows: powłoka tylko dla
  // shima `.cmd` bez exe (wykonawca ze stdin); drzewo i tak sprząta taskkill /T.
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
  const capture = (source, stream) => {
    source.setEncoding("utf8")
    partial.set(source, "")
    source.on("data", (text) => {
      log(text, stream)
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
  current.report = () => finalReport({ startHead, startStash, tail: fullTail(), config: config?.line })

  const heartbeatMs = opts.heartbeatMin * 60_000
  const heartbeat = setInterval(() => {
    const status = git("status", "--short")
    const commits = startHead ? git("rev-list", "--count", `${startHead}..HEAD`) : null
    log(`[headless] ♥ ${minutes(Date.now() - started)} min | pliki: ${status === null ? "?" : lines(status).length}`
      + ` | commity: ${commits ?? "?"} | ostatnio: ${lastLine() || "—"}\n`)
    const silent = Date.now() - lastOutput
    // Tylko ostrzeżenie — zabija `--timeout`. Raz na okres ciszy, żeby host budził się raz.
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
    killTree(child)
  }
  // Po ubiciu drzewa potoki się zamykają — dociągamy resztę wyjścia (maks. 3 s).
  // `closed` złapany od startu — `close` mógł już przyjść przed `exit`.
  await Promise.race([closed, new Promise((done) => setTimeout(done, 3000))])
  current.child = null
  if (timedOut) log(`[headless] timeout po ${opts.timeoutMin} min — drzewo procesów ${name} zabite\n`)
  // Limit dostawcy to pauza do resetu, nie błąd — host ponawia po godzinie z linii PAUSE.
  // Limit wygrywa z timeoutem: wykonawca mógł wisieć na limicie do końca czasu.
  let pause = null
  const failed = timedOut || code !== 0
  const textLimit = failed && LIMIT_PATTERN.test(tailLines(outputTail))
  const quota = failed && !textLimit && executor.quota ? executor.quota(bin) : null
  if (quota) log(`[headless] /quota ${name}: limit wyczerpany\n`)
  if (textLimit || quota) {
    pause = `PAUSE=rate-limit reset=${(quota ? quota.reset : resetIso(tailLines(outputTail))) ?? "brak"}`
    code = PAUSE_CODE
  } else if (timedOut) {
    code = 124
  }
  // PAUSE tylko u ostatniego — host czyta ją jako „przejmij”, a zastępca jeszcze nie ruszył.
  log(finalReport({ startHead, startStash, tail: fullTail(), pause: last ? pause : null, config: config?.line }))
  return code
}

// Raport końcowy — zawsze, także po timeoucie: co wykonawca zostawił w drzewie, w historii
// i w stashu. Stasha nie zdejmujemy (`pop` może dać konflikt) — tylko ostrzeżenie.
function finalReport({ startHead, startStash, tail, pause, config }) {
  const out = ["[headless] raport końcowy"]
  if (pause) out.push(`## ${pause}`)
  // Skąd wzięty config wykonawcy (worktree): główny checkout albo brak — nigdy cicho.
  if (config) out.push(`## ${config}`)
  const status = git("status", "--short")
  if (status !== null) out.push("## git status --short", status || "(czysto)")
  if (startHead) out.push(`## git log ${startHead.slice(0, 7)}..HEAD --oneline`, git("log", `${startHead}..HEAD`, "--oneline") || "(brak commitów)")
  // Po hashach, nie po liczbie — `drop` + nowy wpis nie zmienia liczby.
  const added = lines(git("stash", "list", "--format=%H%x09%gd: %gs"))
    .map((l) => l.split("\t"))
    .filter(([hash]) => !startStash.has(hash))
    .map(([, entry]) => entry)
  if (added.length) {
    out.push("## UWAGA: nowe wpisy stasha — praca wykonawcy może tam być; nie zdjęte automatycznie (`git stash pop` ręcznie)", ...added)
  }
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
if (isMain) await main()
