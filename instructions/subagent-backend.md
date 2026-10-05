# `/subagent-backend` — cross-review w dwóch oknach (strona backend)

> Prywatne notatki z użycia. Źródło: `.claude/commands/subagent-backend.md`.
> Druga strona: [subagent-frontend](subagent-frontend.md).

**Do czego to jest:** mam dwa osobne okna edytora. W jednym backendowy
reviewer, w drugim frontendowy. **Nie widzą się nawzajem** — jedyny kanał
komunikacji to **raport, który przeklejam ja**.

## Jak to chodzi

```
okno BE                              okno FE
────────                             ────────
/subagent-backend                    /subagent-frontend
  → tabela findingów                   → tabela findingów
  → "Raport do przekazania              → "Raport do przekazania
     dla subagent-frontend"                dla subagent-backend"
            │                                      │
            └────────► przeklejam ja ◄─────────────┘
```

Zwraca **zawsze dwie sekcje**:

1. tabela `Severity | Location | Finding | Fix` — jak zwykły `/review-*`
2. `## Raport do przekazania dla subagent-frontend` — zwięzłe punkty dla drugiej
   strony

**Bez wklejonego raportu** robi zwykły review — dokładnie to samo co
[review-backend](review-backend.md).

## Co sprawdza, gdy dostanie raport od FE

Czy serializer, endpoint, kody błędów, format daty i ACL faktycznie dostarczają
to, czego FE oczekuje.

## Kiedy to ma sens, a kiedy nie

**Ma:** zmiana przechodzi przez kontrakt API. Endpoint po jednej stronie, ekran
po drugiej. To jedyna sytuacja, w której jeden reviewer nie widzi połowy obrazu.

**Nie ma:** zmiana tylko po jednej stronie. Wtedy to [review-backend](review-backend.md)
i koniec — dwa okna to narzut bez zysku.

## Pułapka

**Ja jestem kanałem.** Jeśli nie przekleję raportu, dostaję dwa niezależne
review i całą wartość tracę. Nie ma tu automatu — komendy są zaprojektowane pod
ręczne przekazywanie, bo okna faktycznie się nie widzą.

Alternatywa, o której warto pamiętać: `/code-review` Matta odpala **dwa
równoległe subagenty w jednej sesji** (Standards + Spec) i sam agreguje wynik.
Inny podział ról, ale bez przeklejania.

## Do przemyślenia

Para `subagent-*` powstała pod dwa okna Cursora. W Claude Code mogę odpalić
dwa worktree i dwie sesje — mechanika ta sama, ale nazwy komend sugerują
Cursora. Może warto to kiedyś przemianować.
