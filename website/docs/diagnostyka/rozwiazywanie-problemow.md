# Rozwiązywanie problemów

Najczęstsze problemy i ich przyczyny. Zacznij od `kit-ai doctor` i narzędzia `check_kit_status`.

## Serwer MCP się nie łączy (`CONNECTION_CLOSED`)

Przyczyna: konfiguracja MCP została zacommitowana z innej maszyny. Ścieżki z Windowsa (`M:/projects/…`) na Linuksie nie działają, a błąd nie mówi dlaczego.

Rozwiązanie: pliki MCP są per maszyna. Każda maszyna uruchamia `kit-ai reload` u siebie. Jeśli pliki są w indeksie gita, usuń je z indeksu, ale najpierw przenieś z nich ustawienia wspólne dla zespołu (np. modele i providerów z `opencode.json`). Zob. [Pliki w projekcie](../konfiguracja/pliki-w-projekcie.md).

## Komendy `/kit-ai:*` nie działają albo nie widać ich w menu

Przyczyna: klient nie wystartował po bootstrapie. MCP i komendy ładują się przy starcie.

Rozwiązanie: zrestartuj IDE albo CLI. W side chacie T3 Code wpisz pełną nazwę komendy ręcznie.

## Zmiany w `modules/` nie są widoczne

Przyczyna: serwer działa ze zdalnego źródła i używa kopii w cache `uv`, zaktualizowanej dopiero po zmianie wersji.

Rozwiązanie: użyj lokalnego klona (`uv run --project`) albo zainstaluj nową wersję. Zob. [Aktualizacja](../start/aktualizacja.md).

## Guard blokuje komendę, którą uważasz za bezpieczną

Przeczytaj powód w komunikacie guarda, np. `server-guard: …` albo `git-guard: …`. Powód zawsze wskazuje dozwoloną alternatywę.

- Wyjątek dla projektu dodajesz w `server.allow` w Profilu.
- Gdy heurystyka hosta jest błędna, wymuś profil zmienną `KIT_HOST_PROFILE` na tej maszynie. Nie wyłączaj guarda w repo.

## Hooki nie działają na Windows

Przyczyna: brak `node` w PATH powłoki nieinteraktywnej. Częste przy nvm.

Rozwiązanie: dodaj `node` do PATH globalnie. Zob. [Windows](../hosty/windows.md).

## `npx` nie uruchamia lokalnego serwera MCP na Windows

Przyczyna: stdio przez `npx` wymaga `cmd /c` na Windows.

Rozwiązanie: `"command": "cmd", "args": ["/c", "npx", …]`. Serwery zdalne tego nie potrzebują.

## `reload` ostrzega o PyYAML

Przyczyna: bootstrap uruchomiono na systemowym Pythonie bez PyYAML. Reload nie sprawdza wtedy składni Profilu, więc karta T3 zostaje bez zmian.

Rozwiązanie: uruchom `kit-ai reload`. Używa własnego interpretera kita, który ma PyYAML.

## `kit-ai install` odmawia

Przyczyna: repo ma już zainstalowany kit.

Rozwiązanie: użyj `kit-ai reload`.

## Doctor pokazuje `stale-path`

Przyczyna: reguła albo overlay wskazuje ścieżkę, której nie ma, np. po przeniesieniu katalogu.

Rozwiązanie: popraw ścieżkę ręcznie albo przez `/kit-ai:kit-project-edit "napraw zgłoszenia doctora"`. Zob. [Doctor](doctor.md).

## Reload pokazuje `uncertain-migration`

Przyczyna: `AGENTS.md` albo `BUGBOT.md` był zmieniany ręcznie, więc kit nie wie, gdzie przenieść twoje linie. Plik zostaje bez zmian.

Rozwiązanie: przenieś własne reguły do bloku `project:rules` (w `BUGBOT.md`) albo `project:agents` (w `AGENTS.md`). Propozycja jest w polu `value`. Tekstowy raport go nie pokazuje: uruchom `kit-ai doctor --json` i znajdź w `findings` wpis z `kind: uncertain-migration`.

Gdy kit działa z pakietu (bez historii gita szablonu), migracji nie da się dopasować i doctor nie tworzy tego wpisu. Plik zostaje bez zmian. Porównaj go wtedy ręcznie z szablonem kita (`templates/cursor/BUGBOT.md`, `templates/AGENTS.md`) i przenieś własne linie do bloku projektu, a potem uruchom `kit-ai reload`.

## Nie wiem, co kit zmieni

Użyj dry run:

```text
reload_workspace()     # lista plików nowych, nadpisanych i usuniętych, bez zapisu
```

Przed `reload` bez dry run sprawdź `git diff` plików klientów. Konfiguracje MCP (`.mcp.json` i podobne) są w `.gitignore`, więc `git diff` ich nie pokaże. Jeśli ręcznie zmieniałeś w nich wpis `kit-ai-mcp`, zrób kopię, bo reload go podmieni.
