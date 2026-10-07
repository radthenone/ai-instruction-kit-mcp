# Język i konwencje kodu (PL)

## Komunikacja

- ZAWSZE odpowiadaj po polsku, chyba że użytkownik wyraźnie poprosi o inny język.
- Dotyczy to też krótkich statusów/narracji w trakcie pracy (np. "Teraz sprawdzam X", "Dodaję Y") — nie tylko finalnej odpowiedzi. Nazwy plików, komend, kod i identyfikatory zostają w oryginale.
- Odpowiadaj konkretnie, technicznie i projektowo — bez lania wody.
- Jeśli czegoś nie da się potwierdzić, napisz to wprost.

## Kod

- Nazwy techniczne w kodzie po angielsku: zmienne, funkcje, klasy, typy, pliki, endpointy, migracje, testy.
- Docstringi publicznych funkcji, klas i endpointów — po polsku (Google style, PEP 257).
- Komentarze logiczne — po polsku, tylko gdy wyjaśniają nietrywialną logikę biznesową.
- Type hints — wymagane w nowym kodzie Python i TypeScript.

## Testy

- Nazwy funkcji i klas testów (`test_*`, `class Test*`) po angielsku — tak jak reszta identyfikatorów.
- Opis zachowania trafia do polskiego docstringa na każdym teście, nie do nazwy.

```python
# źle
def test_kupon_wygasa_po_terminie(): ...

# dobrze
def test_coupon_expires_after_deadline():
    """Kupon po dacie ważności nie obniża ceny koszyka."""
```

- Override dla `/tdd`: „test names match the project's domain language” oznacza angielskie nazwy terminów z nagłówków `CONTEXT.md`, nigdy polską prozę definicji.

## GitHub / git (proza)

- **Tytuły zawsze po angielsku**: tytuł issue, tytuł PR, slug brancha (`feat/42-add-cart-coupon`).
- Treść issue, treść PR, komentarze review, komunikaty commitów — po polsku (ten język ustawienia).

## Zasady zmian

- Preferuj lokalną, najmniejszą sensowną zmianę zamiast dużego refaktoru.
- Pilnuj separation of concerns i silnego typowania.
- Nie dodawaj abstrakcji bez realnej potrzeby.
- Zwracaj uwagę na testowalność, naming, performance, bezpieczeństwo i ryzyko regresji.
