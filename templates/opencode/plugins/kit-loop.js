// Pętla /goal i /loop dla opencode — odpowiednik tych komend z Claude Code.
// Sam markdown komendy kończy się z końcem tury; ten plugin budzi sesję na
// `session.idle` i wysyła kolejną turę, dopóki cel nie jest osiągnięty.
//
// Przerwania: Esc (abort tury → błąd na ostatniej wiadomości), `/goal clear`,
// `/loop stop`, `<promise>DONE</promise>` jako ostatnia linia, limit tur (`max=N`).
// Stan tylko w pamięci — restart opencode kasuje aktywne pętle.

const DONE = "<promise>DONE</promise>"
const LIMIT = { goal: 25, loop: 10 }
const UNIT = { s: 1e3, m: 6e4, h: 36e5 }

const loops = new Map() // sessionID -> { kind, task, turn, max, everyMs, timer }

// `/loop [5m] [max=N] <zadanie>`, `/goal [max=N] <cel>` — kolejność flag dowolna.
// Bez `export`: opencode wywołuje każdy eksport pliku jako plugin.
function parseArgs(kind, raw) {
  let max = LIMIT[kind]
  let everyMs = 0
  const words = raw.trim().split(/\s+/)
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

export const KitLoop = async ({ client }) => {
  const toast = (message, variant = "info") =>
    client.tui.showToast({ body: { message, variant } }).catch(() => {})

  const stop = (id, why) => {
    const s = loops.get(id)
    if (!s) return
    clearTimeout(s.timer)
    loops.delete(id)
    toast(`/${s.kind} zatrzymany: ${why} (tur: ${s.turn})`, why === "cel osiągnięty" ? "success" : "warning")
  }

  const lastAssistant = async (id) => {
    const res = await client.session.messages({ path: { id } })
    return (res.data ?? []).findLast((m) => m.info.role === "assistant")
  }

  return {
    // Przed turą komendy — tu zapamiętujemy stan, zanim sesja stanie się idle.
    "command.execute.before": async ({ command, sessionID, arguments: raw = "" }) => {
      if (command !== "goal" && command !== "loop") return
      const verb = raw.trim().split(/\s+/)[0]
      if (verb === "" || verb === "status") return
      if (["clear", "stop", "pause"].includes(verb)) return stop(sessionID, `/${command} ${verb}`)
      stop(sessionID, "nowy cel")
      loops.set(sessionID, parseArgs(command, raw))
    },

    event: async ({ event }) => {
      if (event.type !== "session.idle") return
      const id = event.properties.sessionID
      const s = loops.get(id)
      if (!s || s.timer) return

      const last = await lastAssistant(id).catch(() => undefined)
      if (!last) return stop(id, "brak odpowiedzi modelu")
      // Esc w TUI przerywa turę — wiadomość dostaje MessageAbortedError.
      if (last.info.error) return stop(id, last.info.error.name ?? "błąd tury")
      const text = last.parts.filter((p) => p.type === "text").map((p) => p.text).join("")
      // Tylko ostatnia linia — wzmianka o znaczniku w treści nie kończy pętli.
      if (text.trim().split("\n").at(-1).trim() === DONE) return stop(id, "cel osiągnięty")
      if (s.turn >= s.max) return stop(id, `limit ${s.max} tur`)

      s.turn += 1
      const send = () => {
        s.timer = undefined
        if (loops.get(id) !== s) return // zatrzymany w trakcie czekania
        client.session
          .prompt({ path: { id }, body: { parts: [{ type: "text", text: nextPrompt(s) }] } })
          .catch((err) => stop(id, `prompt: ${err?.message ?? err}`))
      }
      if (s.everyMs) s.timer = setTimeout(send, s.everyMs)
      else send()
    },
  }
}
