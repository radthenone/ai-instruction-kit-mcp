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
 * Kody wyjścia: kod wykonawcy, 124 = timeout, 2 = błędne wywołanie.
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
const DEFAULT_TIMEOUT_MIN = 30
const DEFAULT_HEARTBEAT_MIN = 10
const TAIL_LINES = 20

// Numer ticketu z brancha `typ/<N>-slug`; inny branch (dev, detached, brak gita) — linia pominięta.
const ticketNumber = () => /^[a-z]+\/(\d+)-/.exec(git("branch", "--show-current") || "")?.[1]

const footer = (runDir, ticket) => `

---
Zasady tej sesji (headless, bez użytkownika):${ticket ? `
- Ticket #${ticket}: przeczytaj \`gh issue view ${ticket} --comments\` — to specyfikacja zadania.` : ""}
- Katalog runu: ${runDir} — logi testów, skrypty i pliki robocze tylko tam, nie w repo.
- Nie używaj \`git stash\`, \`git checkout\` ani \`git reset\`. Porównanie z bazą: \`git worktree add --detach ${join(runDir, "base")} <ref>\`, na końcu \`git worktree remove ${join(runDir, "base")}\`.
- Ticket z więcej niż 3 kryteriami akceptacji albo więcej niż jedną aplikacją/pakietem: najpierw plan 5–10 kroków.
- Praca test-first: test czerwony → kod → test zielony → lokalny commit po każdym zielonym kroku.
- Lokalnie tylko testy dotknięte zmianą i szybkie bramki; pełny zestaw zrobi CI.
- Na VPS \`uv run\` zawsze z \`--no-sync\`.
- Maks. 2 próby naprawy tego samego błędu, potem stop i opis w sekcji Problemy raportu.
- Nie pushuj i nie otwieraj PR — zrobi to host po review.
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
    // Treść od `-` (np. lista markdown) parser opencode wziąłby za flagę — nowa linia na
    // początku tego nie zmienia dla modelu.
    args: (model, prompt) => [
      "run", "--standalone", "--auto", ...(model ? ["--model", model] : []),
      prompt.startsWith("-") ? `\n${prompt}` : prompt,
    ],
    stdin: false,
  },
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
  const executor = EXECUTORS[opts.executor]
  const found = executor.bins.map(which).find(Boolean)
  const bin = (process.platform === "win32" && /\.(cmd|bat)$/i.test(found || "") && resolveShim(found)) || found
  // `.cmd`/`.bat` (shim npm na Windows) idzie przez cmd.exe, który rozbija wieloliniowy
  // argument i interpretuje `& | >` — treść w argumencie byłaby niebezpieczna.
  const needsShell = process.platform === "win32" && /\.(cmd|bat)$/i.test(bin || "")
  if (needsShell && !executor.stdin) {
    fail(`${bin} to skrypt cmd — treść w argumencie nie przejdzie bezpiecznie. Dodaj do PATH binarkę .exe ${opts.executor}`)
  }
  if (!bin) fail(`nie znaleziono ${executor.bins.join(" ani ")} w PATH. Dozwoleni wykonawcy z ${opts.host}: ${allowed.join(", ")}`)

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
  const args = executor.args(opts.model, prompt)
  log(`[headless] ${opts.host} → ${opts.executor}: ${bin} ${args.slice(0, -1).join(" ")} (timeout ${opts.timeoutMin} min)\n`)

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
  })
  const closed = new Promise((done) => child.on("close", done))
  // Ostatnie linie wykonawcy do heartbeatu i raportu; `partial` = linia bez `\n` jeszcze,
  // osobno per strumień. `setEncoding` nie tnie znaków UTF-8 na granicy chunków.
  const tail = []
  const partial = new Map()
  let lastOutput = Date.now()
  let stallReported = false
  const capture = (source, stream) => {
    source.setEncoding("utf8")
    partial.set(source, "")
    source.on("data", (text) => {
      log(text, stream)
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

  // Host, który zabija wrapper (koniec sesji, własny timeout), nie może zostawić wykonawcy
  // z uprawnieniami na edycje i bash.
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => {
      killTree(child)
      log(finalReport({ startHead, startStash, tail: fullTail() }))
      process.exit(128 + constants.signals[signal])
    })
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
  if (timedOut) {
    log(`[headless] timeout po ${opts.timeoutMin} min — drzewo procesów ${opts.executor} zabite\n`)
    code = 124
  }
  log(finalReport({ startHead, startStash, tail: fullTail() }))
  log(`[headless] kod wyjścia: ${code}\n`)
  // Pusty zapis z callbackiem — stdout do potoku bywa asynchroniczny (macOS, Windows).
  process.stdout.write("", () => process.exit(code))
}

// Raport końcowy — zawsze, także po timeoucie: co wykonawca zostawił w drzewie, w historii
// i w stashu. Stasha nie zdejmujemy (`pop` może dać konflikt) — tylko ostrzeżenie.
function finalReport({ startHead, startStash, tail }) {
  const out = ["[headless] raport końcowy"]
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
