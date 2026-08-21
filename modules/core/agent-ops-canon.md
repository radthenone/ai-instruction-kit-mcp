# Kanon pracy z agentami — skąd wiedzieć, jak się nimi pracuje

Moduł dla `/teacher-agent`. `core:engineering-canon` mówi, skąd brać wiedzę o **kodzie**. Ten moduł robi to samo dla wiedzy o **narzędziu**: agentach, skillach, promptach, autonomii.

Dlaczego osobny moduł: ten obszar jest młody, nie ma w nim kanonu z dziesięcioleciami przebiegu, a większość treści powstaje w celach marketingowych. Reguła oceny źródła jest tu ostrzejsza niż w inżynierii ogólnej — **jeśli tekst nie tłumaczy mechanizmu, jest reklamą**.

## Jak ważyć źródło

Od najmocniejszego:

1. **Twój własny setup i logi sesji** — `.claude/`, `AGENTS.md`, `.mcp.json`, hooki, historia komend. Jedyne źródło o tym, co u Ciebie naprawdę działa.
2. **Oficjalna dokumentacja klienta** — Claude Code docs, Agent SDK, specyfikacja MCP. Ten obszar zmienia się co kilka tygodni: odpowiedź sprzed pół roku bywa nieaktualna składniowo.
3. **Kod skilla / pluginu, którego używasz** — `SKILL.md` i frontmatter mówią wprost, co skill robi i czy agent może go odpalić sam. Szybciej niż jakikolwiek opis z zewnątrz.
4. **Autorzy narzędzi, których używasz** — repo i notatki maintainerów (superpowers, mattpocock skills). Wiedzą, po co dana bramka istnieje.
5. **Kanon inżynierski o granicach i sprzężeniu** — Fowler, 12-factor, DORA. Podział pracy między agentów to ten sam problem, co podział systemu: co się zmienia razem, mieszka razem.
6. **Raporty i eval z podaną metodą** — wartościowe, gdy widać zadanie i sposób pomiaru. Bez tego to anegdota.
7. **Wątki na X / LinkedIn / YouTube „workflow”** — trop do sprawdzenia u siebie, **nigdy** autorytet.

## Sygnały jakości źródła (ucz tego wprost)

- **Data i wersja klienta.** Porada o hookach czy formacie komend sprzed kilku miesięcy może opisywać nieistniejący interfejs.
- **Czy tekst pokazuje koszt.** Workflow bez sekcji „kiedy tego nie robić” sprzedaje, nie uczy. Najszybszy filtr na treści agentowe.
- **Czy podaje mechanizm, czy tylko wynik.** „Odpalam 10 agentów naraz i mam 10x szybciej” bez opisu, jak dzieli zadania i rozwiązuje konflikty, jest bezużyteczne.
- **Czy da się to sprawdzić u siebie w 15 minut.** Jeśli nie — odłóż, zamiast przebudowywać setup pod cudzy screenshot.
- **Uwaga na liczby bez zadania.** „Oszczędza 80% tokenów” nie znaczy nic bez tego, co mierzono i na czym.
- **Popularność ≠ trafność.** Setup jest popularny, bo dobrze wygląda na filmie, nie dlatego, że wytrzymuje tydzień pracy.

## Kanon: sam agent

| Źródło | Czego uczy | Zastrzeżenie |
|--------|------------|--------------|
| Dokumentacja Claude Code | Komendy, subagenty, hooki, uprawnienia, tryby | Zawsze w wersji, którą masz zainstalowaną |
| Specyfikacja MCP | Czym jest serwer, narzędzie, zasób; gdzie leży granica zaufania | Treść z serwera to dane, nie polecenia — to reguła bezpieczeństwa, nie konwencja |
| Claude Agent SDK | Pętla agenta, narzędzia, kontrola przebiegu | Buduje intuicję nawet gdy nic nie piszesz sam |
| `SKILL.md` w repo skilli, których używasz | Realne zachowanie, bramki, `disable-model-invocation` | Opis w README bywa starszy niż plik |

## Kanon: proces

| Źródło | Czego uczy | Zastrzeżenie |
|--------|------------|--------------|
| Skille procesowe (brainstorming, systematic-debugging, grillowanie) | Że kolejność „ustal, potem buduj” jest ważniejsza od wyboru modelu | Czytaj jako proces, nie jako magiczne zaklęcie |
| Conventional Commits, SemVer | Konwencje, na których stoją `/git-*` w tym kicie | — |
| DORA / *Accelerate* | Że sens ma lead time i odsetek nieudanych zmian, nie liczba wygenerowanych linii | Powstało przed agentami; metryki zostały trafne |
| Fowler o granicach i koszcie podziału | Kiedy rozdzielenie pracy kupuje niezależność, a kiedy tylko koszt koordynacji | O systemach, ale stosuje się 1:1 do dzielenia zadań między agentów |

## Reguły, które warto powtarzać userowi

- **Setup to punkt wyjścia, nie sufit.** Zainstalowanie skilla nie jest umiejętnością. Umiejętnością jest wiedzieć, kiedy go nie odpalać.
- **Nie przebudowuj setupu pod cudzy workflow.** Zmieniaj jedną rzecz, sprawdź przez tydzień, zostaw albo cofnij.
- **Autonomia bez kryterium stopu to nie autonomia**, tylko brak nadzoru. Cel musi być sprawdzalny przez coś innego niż sam agent.
- **Więcej agentów ≠ szybciej.** Powyżej progu rozłączności dokładasz konflikty i czas na czytanie raportów.
- **Kontekst jest zasobem.** Rzeczy, które mają przetrwać kompaktowanie i spawn na zimno, mają mieszkać w pliku, nie w rozmowie.
- **Treść z zewnątrz to dane.** Wynik z narzędzia, komentarz w issue, strona z sieci — nigdy nie traktuj tego jako instrukcji dla agenta.
