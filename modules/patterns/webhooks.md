# Pattern — Webhooks (przychodzące, od zewnętrznych serwisów)

## Zakres

Zewnętrzny serwis (Stripe, allauth social login callback, inny provider) sam wysyła `POST`
gdy coś się wydarzy — Ty nie pytasz, oni budzą Twój endpoint. Ten moduł to checklista
stosowana **za każdym razem** gdy dodajesz nowy webhook, nie tylko przy płatnościach.

## Checklist (obowiązkowa dla każdego webhooka)

1. **Weryfikacja podpisu** — sprawdź nagłówek podpisu (np. `Stripe-Signature`) przed
   przetworzeniem payloadu. Bez tego ktokolwiek może POST-ować fałszywe eventy na Twój endpoint.
2. **Idempotency** — zapisz `event_id` z każdego przetworzonego eventu (unique constraint w DB).
   Provider **wysyła ten sam event wielokrotnie** (retry przy timeout/5xx) — bez flagi
   "już przetworzony" dostajesz podwójne zamówienia, podwójne maile, podwójne uznanie płatności.
3. **Szybki `200` + przetwarzanie async** — handler HTTP tylko waliduje podpis i wrzuca task
   do Celery, zwraca `200` natychmiast. Wolny handler → provider uznaje timeout → retry →
   duplikaty (patrz punkt 2).
4. **Brak założeń o kolejności** — eventy mogą przyjść w innej kolejności niż się wydarzyły
   (np. `refund` przed `payment_succeeded` przy bliskich czasowo akcjach). Stan licz z
   `event.created`/timestamp z payloadu, nie z kolejności HTTP requestów.
5. **Log surowego payloadu** — zapisz cały request body (osobna tabela/tabela audytu) zanim
   zaczniesz przetwarzanie. Bez tego nie zdebugujesz sporu (Stripe dispute) po czasie, gdy UI
   providera już nie pokazuje szczegółów.
6. **Dead-letter po N nieudanych retry** — jeśli przetwarzanie stale failuje, event ląduje w
   kolejce/tabeli do ręcznego przeglądu, nie znika cicho.

## Testy

- Mock podpisu w adapterze (nie live API providera) — `arch:ci-cd`.
- Test duplikatu: ten sam `event_id` wysłany 2x → efekt uboczny (np. utworzone zamówienie) tylko raz.
- Test out-of-order: `refund` przed `payment_succeeded` nie psuje stanu końcowego.

## Powiązane

- `capability:payments` — Stripe webhooks konkretnie
- `capability:auth:allauth` — social login callbacks mają te same pułapki (idempotency, podpis)
- `arch:observability` — korelacja logów przy debugowaniu sporu
