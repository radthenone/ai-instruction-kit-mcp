// Pętla /goal i /loop dla opencode V2 — odpowiednik tych komend z Claude Code.
// Sam markdown komendy kończy się z końcem tury; ten plugin budzi sesję na
// `session.execution.succeeded` i wysyła kolejną turę, dopóki cel nie jest osiągnięty.
// V2 nie emituje `session.idle` przez `ctx.event.subscribe` (sprawdzone na 2.0.18).
//
// Przerwania: Esc (`session.execution.interrupted`), błąd tury (`.failed`), `/goal clear`,
// `/loop stop`, `<promise>DONE</promise>` jako ostatnia linia, limit tur (`max=N`).
// Stan tylko w pamięci — restart opencode kasuje aktywne pętle.

// Bez importu @opencode/plugin — Plugin.define() to tylko identyczność,
// a goły `export default { id, setup }` omija błąd resolvowania pakietu
// ("Cannot find package '@opencode/plugin'") w lokalnych pluginach .js.

const DONE = "<promise>DONE</promise>"
const LIMIT = { goal: 25, loop: 10 }
const UNIT = { s: 1e3, m: 6e4, h: 36e5 }

const loops = new Map() // sessionID -> { kind, task, turn, max, everyMs, timer }

// `/loop [5m] [max=N] <zadanie>`, `/goal [max=N] <cel>` — kolejność flag dowolna.
function parseArgs(kind, raw) {
  let max = LIMIT[kind]
  let everyMs = 0
  const words = raw.trim().split(/\s+/).filter(Boolean)
  while (words.length) {
    const m = /^max=(\d+)$/.exec(words[0])
    const every = kind === "loop" && /^(\d+)([smh])$/.exec(words[0])
    if (m) max = Number(m[1])
    else if (every) everyMs = Number(every[1]) * UNIT[every[2]]
    else break
    words.shift()
  }
  return { kind, task: words.join(" "), turn: 0, max, everyMs, timer: undefined }
}

const nextPrompt = (s) =>
  `[/${s.kind} tura ${s.turn}/${s.max}] Kontynuuj: ${s.task}\n` +
  `Zrób kolejny krok i zweryfikuj go dowodem (kod wyjścia, testy, zawartość pliku). ` +
  `Gdy warunek końca jest spełniony dowodem, zakończ odpowiedź dokładnie linią ${DONE}.`

// Wykryj wywołanie /goal lub /loop w tekście promptu.
// Działa dla surowej formy (`/goal <args>`) i dla rozwiniętego markdowna
// (`# /goal ...` + linia `Argumenty użytkownika ...: <args>`).
function detectCommand(text) {
  const trimmed = text.trim()
  // `(?:\s|$)` zamiast `\b` — `/goal-setting` to nie `/goal`.
  let m = /^\/(goal|loop)(?:\s|$)([\s\S]*)$/.exec(trimmed)
  if (m) return { command: m[1], raw: m[2].trim() }
  // Rozwinięty markdown komendy — pierwsza linia nagłówka + linia z argumentami.
  m = /^#\s*\/(goal|loop)\b/m.exec(text)
  if (m) {
    const argsLine = /^Argumenty użytkownika.*?:[ \t]*(.*)$/m.exec(text)
    return { command: m[1], raw: (argsLine?.[1] ?? "").replace(/\$ARGUMENTS/g, "").trim() }
  }
  return null
}

function handleCommand(sessionID, command, raw) {
  const verb = (raw.trim().split(/\s+/)[0] ?? "").toLowerCase()
  if (verb === "" || verb === "status") return
  if (["clear", "stop", "pause"].includes(verb)) return stopLoop(sessionID, `/${command} ${verb}`)
  stopLoop(sessionID, "nowy cel")
  loops.set(sessionID, parseArgs(command, raw))
}

function stopLoop(id, why) {
  const s = loops.get(id)
  if (!s) return
  clearTimeout(s.timer)
  loops.delete(id)
  console.log(`[kit-loop] /${s.kind} zatrzymany: ${why} (tura: ${s.turn})`)
}

export default {
  id: "kit-loop",
  async setup(ctx) {
    // Przed turą komendy — tu zapamiętujemy stan, zanim sesja stanie się idle.
    // V1 `command.execute.before` nie istnieje w V2, więc nasłuchujemy promptów.
    await ctx.session.hook("prompt", (event) => {
      const text = event.prompt?.text ?? ""
      const hit = detectCommand(text)
      if (!hit) return
      handleCommand(event.sessionID, hit.command, hit.raw)
    })

    const controller = new AbortController()

    const onIdle = async (id) => {
      const s = loops.get(id)
      if (!s || s.timer) return

      let messages
      try {
        const res = await ctx.session.context({ sessionID: id })
        // Wrapper pluginu koduje wynik schematem endpointu HTTP (`{ data: [...] }`) — przyjmij oba kształty.
        messages = Array.isArray(res) ? res : res?.data ?? []
      } catch (err) {
        return stopLoop(id, `context: ${err?.message ?? err}`)
      }
      const last = [...messages].reverse().find((msg) => msg.type === "assistant")
      if (!last || last.type !== "assistant") return stopLoop(id, "brak odpowiedzi modelu")
      // Esc w TUI przerywa turę — wiadomość dostaje błąd / finish=error.
      if (last.error) return stopLoop(id, last.error?.message ?? last.error?.name ?? "błąd tury")
      if (last.finish === "error") return stopLoop(id, "błąd tury")
      const text = (last.content ?? [])
        .filter((p) => p.type === "text")
        .map((p) => p.text)
        .join("")
      // Tylko ostatnia linia — wzmianka o znaczniku w treści nie kończy pętli.
      if (text.trim().split("\n").at(-1)?.trim() === DONE) return stopLoop(id, "cel osiągnięty")
      if (s.turn >= s.max) return stopLoop(id, `limit ${s.max} tur`)

      s.turn += 1
      const send = () => {
        s.timer = undefined
        if (loops.get(id) !== s) return // zatrzymany w trakcie czekania
        ctx.session
          .prompt({ sessionID: id, text: nextPrompt(s) })
          .catch((err) => stopLoop(id, `prompt: ${err?.message ?? err}`))
      }
      if (s.everyMs) s.timer = setTimeout(send, s.everyMs)
      else send()
    }

    void (async () => {
      for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
        const id = event.data?.sessionID
        if (!id) continue
        if (event.type === "session.execution.interrupted" || event.type === "session.execution.failed") {
          stopLoop(id, event.type)
          continue
        }
        if (event.type !== "session.execution.succeeded") continue
        // Wyjątek nie może zostawić pętli w `loops` bez kolejnej tury — zatrzymaj ją jawnie.
        await onIdle(id).catch((err) => stopLoop(id, `idle: ${err?.message ?? err}`))
      }
    })().catch((err) => {
      if (!controller.signal.aborted) console.error(`[kit-loop] strumień zdarzeń: ${err?.message ?? err}`)
    })

    return () => {
      controller.abort()
      for (const [, s] of loops) clearTimeout(s.timer)
      loops.clear()
    }
  },
}
