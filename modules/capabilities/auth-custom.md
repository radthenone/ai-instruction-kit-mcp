# Auth — custom

Wariant `decisions.auth: custom` (**default**). Kit nie narzuca pakietu/wzorca —
projekt ma własny mechanizm albo jeszcze go nie wybrał.

## Co zrobić

1. Opisz realny kontrakt auth w `.ai/project.md`: endpointy, format tokena/sesji,
   gdzie żyje weryfikacja, MFA/social jeśli jest.
2. Jeśli docelowo to ma być allauth albo JWT — przełącz `decisions.auth` na `allauth` / `jwt`
   zamiast utrzymywać opis ręcznie w overlay.
3. Orval: standardowy, jeden klient z DRF schema — dopisz w overlay tylko co odbiega
   (np. header auth inny niż `Authorization: Bearer`).

## Dlaczego default custom, nie allauth

Kit nie zakłada konkretnego pakietu auth dla nowego projektu bez decyzji — allauth i JWT
to gotowe wzorce do świadomego wyboru (`decisions.auth`), nie ukryty default.

## Powiązane

- `capability:auth` — część wspólna (frontend, testy)
- `capability:auth:allauth`, `capability:auth:jwt` — gotowe wzorce, jeśli pasują
