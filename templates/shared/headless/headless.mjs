#!/usr/bin/env node
/**
 * Wrapper `/headless` — uruchamia innego klienta kitu w trybie headless i sprząta po nim.
 *
 *   node .ai/headless.mjs --host <klient> <wykonawca> [--model <id>] [--timeout <min>] [treść…]
 *
 * Treść: argumenty po fladze albo (bez nich) stdin — słowo w słowo, plus stała stopka.
 * `--host` wstawia bootstrap w pliku agenta każdego klienta; wykonawca musi być w tabeli
 * EXECUTORS, w `clients:` Profilu i różny od hosta. Model: `--model` > projektowy config
 * wykonawcy (np. `model` w opencode.json) > domyślny model wykonawcy.
 *
 * Po zakończeniu, błędzie albo timeoucie wrapper zabija całe drzewo procesów wykonawcy
 * (Unix: grupa procesów, Windows: `taskkill /T /F`) — razem z jego LSP i serwerami MCP.
 * Kody wyjścia: kod wykonawcy, 124 = timeout, 2 = błędne wywołanie.
 */
import { execFile, spawn, spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { constants } from "node:os"
import { delimiter, join } from "node:path"

const KNOWN_CLIENTS = ["cursor", "claude", "codex", "vscode", "kiro", "kilo", "antigravity", "opencode"]
const FLAGS = ["--model", "--timeout"]
const DEFAULT_TIMEOUT_MIN = 30

const FOOTER = `

---
Zasady tej sesji (headless, bez użytkownika):
- Nie commituj i nie pushuj — commit zrobi host.
- Po zmianach odpal testy projektu.
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
  const opts = { host: "", executor: "", model: "", timeoutMin: DEFAULT_TIMEOUT_MIN, words: [] }
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

const opts = parse(process.argv.slice(2))
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
prompt += FOOTER

const executor = EXECUTORS[opts.executor]
const bin = executor.bins.map(which).find(Boolean)
// `.cmd`/`.bat` (shim npm na Windows) idzie przez cmd.exe, który rozbija wieloliniowy
// argument i interpretuje `& | >` — treść w argumencie byłaby niebezpieczna.
const needsShell = process.platform === "win32" && /\.(cmd|bat)$/i.test(bin || "")
if (needsShell && !executor.stdin) {
  fail(`${bin} to skrypt cmd — treść w argumencie nie przejdzie bezpiecznie. Dodaj do PATH binarkę .exe ${opts.executor}`)
}
if (!bin) fail(`nie znaleziono ${executor.bins.join(" ani ")} w PATH. Dozwoleni wykonawcy z ${opts.host}: ${allowed.join(", ")}`)

const args = executor.args(opts.model, prompt)
process.stdout.write(`[headless] ${opts.host} → ${opts.executor}: ${bin} ${args.slice(0, -1).join(" ")} (timeout ${opts.timeoutMin} min)\n`)

// Unix: własna grupa procesów (setsid), żeby zabić ją w całości. Windows: `.cmd` z npm
// wymaga powłoki; drzewo i tak sprząta taskkill /T.
const child = spawn(bin, args, {
  detached: process.platform !== "win32",
  shell: needsShell,
  stdio: [executor.stdin ? "pipe" : "ignore", "inherit", "inherit"],
  windowsHide: true,
})
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
  killTree(child)
}
if (timedOut) {
  process.stdout.write(`[headless] timeout po ${opts.timeoutMin} min — drzewo procesów ${opts.executor} zabite\n`)
  code = 124
}
process.stdout.write(`[headless] kod wyjścia: ${code}\n`)
process.exit(code)
