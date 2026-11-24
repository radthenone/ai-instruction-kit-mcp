#!/usr/bin/env python3
"""
Modele agentów kita: `model-tier:` w template, `targets:` i `agents:` w Profilu (ADR-0018).

Użycie:
    model_tiers.py sync PROFILE AGENTS_DIR
    model_tiers.py apply CLIENT PROFILE DEST_DIR

`sync` waliduje Profil i dopasowuje blok `agents:` do agentów kita (przepisuje tylko
ten blok, raport na stdout). `apply` dopisuje do frontmattera plików `DEST_DIR/<agent>.md`
`model:` (Claude także `effort:`) z `targets.<klient>.<tier>`; OpenCode dostaje wariant jako
sufiks nazwy modelu (`provider/model#variant`). Codex i Antigravity nie mają plików.

Bez PyYAML — bootstrap leci na systemowym Pythonie, a bloki mają wcięcia i proste wartości.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

TIERS = ("light", "standard", "heavy")
_ALLOWED = ", ".join(TIERS)
# Blok `targets:` (ADR-0018): klienci i tiery; `takeover` jest opcjonalny u każdego klienta (brak = kopia `standard`).
TARGET_CLIENTS = ("claude", "codex", "antigravity", "opencode")
TARGET_TIERS = TIERS + ("takeover",)
TARGET_FIELDS = ("providerInstanceId", "model", "options")
# Aliasy Claude Code dla przejęcia poza T3 (narzędzie Agent przyjmuje tylko alias).
TAKEOVER_ALIASES = ("haiku", "sonnet", "opus", "fable")
# Stare klucze modeli: nie są czytane, a ich obecność to błąd z instrukcją migracji.
RETIRED_KEYS = ("models", "t3")

# Pole opcji bez przecinka i nawiasów, bez spacji na brzegach: dopasowanie jednoznaczne, czas liniowy.
_FIELD = r"[^,{}\s](?:[^,{}]*[^,{}\s])?"
_OPTION = re.compile(rf"\{{\s*id:\s*({_FIELD})\s*,\s*value:\s*({_FIELD})\s*\}}")
_OPTION_NC = rf"\{{\s*id:\s*{_FIELD}\s*,\s*value:\s*{_FIELD}\s*\}}"
# Lista opcji: wpisy oddzielone przecinkiem, dopuszczony końcowy przecinek (składnia YAML).
_OPTIONS_BODY = re.compile(rf"(?:{_OPTION_NC}(?:\s*,\s*{_OPTION_NC})*\s*,?)?")


class ProfileError(ValueError):
    """Profil ma niepoprawne `targets:`, `agents:` albo stare klucze modeli."""


def template_tiers(agents_dir: Path) -> dict[str, str]:
    """Agent → `model-tier:` z frontmattera template."""
    tiers: dict[str, str] = {}
    for src in sorted(agents_dir.glob("*.md")):
        lines = src.read_text(encoding="utf-8").splitlines()
        end = lines.index("---", 1)
        for line in lines[1:end]:
            if line.startswith("model-tier:"):
                tiers[src.stem] = line.partition(":")[2].strip()
    return tiers


def _block_range(lines: list[str], key: str) -> tuple[int, int] | None:
    """Zakres linii bloku `key:` najwyższego poziomu, bez pustych linii i komentarzy na końcu."""
    start = next((i for i, line in enumerate(lines) if re.match(rf"{key}:\s*(#.*)?$", line)), None)
    if start is None:
        return None
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t#"):
        end += 1
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].startswith("#")):
        end -= 1
    return start, end


def _entries(lines: list[str]) -> list[tuple[int, str, str]]:
    """(wcięcie, klucz, wartość) z linii bloku; komentarze wycięte."""
    found = []
    for line in lines:
        line = _strip_comment(line.rstrip("\r\n"))
        if not line.strip():
            continue
        key, _, value = line.strip().partition(":")
        found.append((len(line) - len(line.lstrip()), key.strip(), value.strip()))
    return found


def _strip_comment(line: str) -> str:
    """
    Wycina komentarz zaczynający się od `#` na początku linii lub po białym znaku, poza cudzysłowem.

    W cudzysłowie podwójnym zapis escape nie zamyka cudzysłowu.

    Args:
        line: Linia Profilu bez końca linii.

    Returns:
        str: Linia bez komentarza.
    """
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote == '"' and ch == "\\":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
        i += 1
    return line


def _unquote(raw: str, where: str) -> str:
    """
    Zdejmuje cudzysłowy z wartości pola zgodnie z YAML.

    Obsługiwane są tylko: podwojony apostrof w cudzysłowie pojedynczym oraz backslash i cudzysłów
    jako escape w cudzysłowie podwójnym. Pozostałe escape'y są błędem, a nie cichym przepisaniem.

    Args:
        raw: Surowa wartość z Profilu, po wycięciu komentarzy.
        where: Ścieżka pola do komunikatu błędu.

    Returns:
        str: Wartość bez cudzysłowów, bez białych znaków na brzegach.

    Raises:
        ProfileError: Cudzysłów bez domknięcia, nieescapowany cudzysłów w środku albo nieobsługiwany escape.
    """
    quotes = ("'", '"')
    if raw[:1] not in quotes and raw[-1:] not in quotes:
        return raw.strip()
    if len(raw) < 2 or raw[0] not in quotes or raw[-1] != raw[0]:
        raise ProfileError(f"Profil: `{where}` ma błędne cytowanie: `{raw}`.")
    quote, inner = raw[0], raw[1:-1]
    if quote == "'":
        if "'" in inner.replace("''", ""):
            raise ProfileError(f"Profil: `{where}` ma błędne cytowanie: `{raw}`.")
        return inner.replace("''", "'").strip()
    out: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\":
            nxt = inner[i + 1 : i + 2]
            if nxt not in ('"', "\\"):
                raise ProfileError(f"Profil: `{where}` ma nieobsługiwany escape: `{raw}`.")
            out.append(nxt)
            i += 2
            continue
        if ch == '"':
            raise ProfileError(f"Profil: `{where}` ma błędne cytowanie: `{raw}`.")
        out.append(ch)
        i += 1
    return "".join(out).strip()


def _targets_tree(lines: list[str]) -> dict:
    """Zagnieżdżone słowniki z wcięć; pusta wartość = podsłownik, pozostałe = tekst."""
    root: dict = {}
    # ramka: [wcięcie węzła, słownik, ścieżka, wcięcie dzieci (ustala się przy pierwszym dziecku)]
    stack: list[list] = [[-1, root, "targets", None]]
    scalar: tuple[int, str] | None = None  # wcięcie i ścieżka ostatniego pola skalarnego
    for line in lines:
        line = _strip_comment(line.rstrip("\r\n"))
        if not line.strip():
            continue
        leading = line[: len(line) - len(line.lstrip())]
        if "\t" in leading:
            raise ProfileError("Profil: `targets:` nie przyjmuje tabulatorów we wcięciach — użyj spacji.")
        indent = len(leading)
        key, sep, value = line.strip().partition(":")
        key = key.strip()
        if not sep or not key:
            raise ProfileError(f"Profil: `targets:` ma linię bez klucza: `{line.strip()}`.")
        if scalar and indent > scalar[0]:
            raise ProfileError(f"Profil: `{scalar[1]}` ma wartość skalarną i nie może mieć zagnieżdżenia.")
        scalar = None
        while stack[-1][0] >= indent:
            stack.pop()
        frame = stack[-1]
        _, node, path, child_indent = frame
        if child_indent is None:
            frame[3] = indent
        elif indent != child_indent:
            raise ProfileError(
                f"Profil: klucz `{key}` w `{path}` ma inne wcięcie niż rodzeństwo — wyrównaj wcięcia."
            )
        if key in node:
            raise ProfileError(f"Profil: klucz `{path}.{key}` jest zdublowany — zostaw jeden wpis.")
        if value.strip():
            if key == "options" and value.strip().startswith("[") and not value.strip().endswith("]"):
                raise ProfileError(
                    f"Profil: `{path}.{key}` zapisz inline, np. `options: [{{ id: effort, value: low }}]`."
                )
            node[key] = _unquote(value.strip(), f"{path}.{key}")
            scalar = (indent, f"{path}.{key}")
        else:
            if key == "options":
                raise ProfileError(
                    f"Profil: `{path}.options` zapisz inline, np. `options: [{{ id: effort, value: low }}]` "
                    "albo `options: []`."
                )
            child: dict = {}
            node[key] = child
            stack.append([indent, child, f"{path}.{key}", None])
    return root


def _parse_options(where: str, raw: object) -> list[dict[str, str]]:
    """`options: [{ id: effort, value: low }]` → lista `{id, value}`; inne formy odrzucane."""
    form = f"Profil: `{where}.options` zapisz inline, np. `options: [{{ id: effort, value: low }}]`."
    if not isinstance(raw, str) or not (raw.startswith("[") and raw.endswith("]")):
        raise ProfileError(form)
    body = raw[1:-1]
    if not _OPTIONS_BODY.fullmatch(body.strip()):
        raise ProfileError(
            f"Profil: `{where}.options` ma wpis poza formatem `{{ id: …, value: … }}` (wpisy rozdziel przecinkiem)."
        )
    options = [
        {"id": _unquote(m.group(1), f"{where}.options"), "value": _unquote(m.group(2), f"{where}.options")}
        for m in _OPTION.finditer(body)
    ]
    if any(not opt["id"] or not opt["value"] for opt in options):
        raise ProfileError(f"Profil: pusta wartość w `{where}.options`.")
    seen: set[str] = set()
    for opt in options:
        if opt["id"] in seen:
            raise ProfileError(f"Profil: opcja `{opt['id']}` w `{where}.options` jest zdublowana — zostaw jedną.")
        seen.add(opt["id"])
    return options


def _target_entry(client: str, tier: str, fields: dict) -> dict:
    """Jeden wpis `targets.<klient>.<tier>` → `{providerInstanceId, model, options}`."""
    where = f"targets.{client}.{tier}"
    for field in fields:
        if field not in TARGET_FIELDS:
            raise ProfileError(f"Profil: nieznane pole `{where}.{field}`. Dozwolone: {', '.join(TARGET_FIELDS)}.")
    provider = fields.get("providerInstanceId")
    if provider is None:
        raise ProfileError(f"Profil: `{where}` bez `providerInstanceId`.")
    if not isinstance(provider, str) or not provider:
        raise ProfileError(f"Profil: `{where}.providerInstanceId` bez wartości — wpisz nazwę instancji providera.")
    model = fields.get("model")
    if "model" in fields and (not isinstance(model, str) or not model):
        raise ProfileError(f"Profil: `{where}.model` bez modelu — wpisz nazwę albo usuń linię.")
    return {
        "providerInstanceId": provider,
        "model": model,
        "options": _parse_options(where, fields.get("options", "[]")),
    }


def _parse_targets(lines: list[str]) -> dict[str, dict[str, dict]]:
    """Blok `targets:` → `targets[klient][tier]`; brak `takeover` = kopia `standard` tego klienta."""
    tree = _targets_tree(lines)
    targets: dict[str, dict[str, dict]] = {}
    for client, tiers in tree.items():
        if client not in TARGET_CLIENTS:
            raise ProfileError(f"Profil: nieznany klient `targets.{client}`. Dozwolone: {', '.join(TARGET_CLIENTS)}.")
        if not isinstance(tiers, dict):
            raise ProfileError(f"Profil: `targets.{client}` ma wartość zamiast tierów ({', '.join(TARGET_TIERS)}).")
        if not tiers:
            raise ProfileError(
                f"Profil: `targets.{client}` bez tierów — dopisz co najmniej jeden tier ({', '.join(TARGET_TIERS)}) albo usuń klienta."
            )
        found: dict[str, dict] = {}
        for tier, fields in tiers.items():
            if tier not in TARGET_TIERS:
                raise ProfileError(f"Profil: nieznany tier `targets.{client}.{tier}`. Dozwolone: {', '.join(TARGET_TIERS)}.")
            if not isinstance(fields, dict):
                raise ProfileError(
                    f"Profil: `targets.{client}.{tier}` ma wartość zamiast pól (`providerInstanceId`, `model`, `options`)."
                )
            found[tier] = _target_entry(client, tier, fields)
        if "takeover" not in found and "standard" in found:
            found["takeover"] = copy.deepcopy(found["standard"])
        targets[client] = found
    return targets


def parse_profile(text: str) -> tuple[dict[str, dict[str, dict]], dict[str, list[str]] | None]:
    """
    `targets:` i `agents:` z Profilu, zwalidowane.

    Returns:
        tuple: ``(targets[klient][tier] = {providerInstanceId, model, options}, agents[tier] = [nazwy] albo None bez bloku)``.

    Raises:
        ProfileError: Stare klucze `models:` / `t3:`, zapis inline, nieznany klient, tier, pole
            albo agent w dwóch tierach.
    """
    retired = re.search(rf"^({'|'.join(RETIRED_KEYS)}):", text, re.MULTILINE)
    if retired:
        raise ProfileError(
            f"Profil: `{retired.group(1)}:` nie jest już czytany — przenieś wpisy do bloku `targets:` "
            "(README „Model tiers”), np. przez komendę kit-project-edit."
        )
    for key in ("targets", "agents"):
        if re.search(rf"^{key}:[ \t]*[^\s#]", text, re.MULTILINE):
            raise ProfileError(f"Profil: `{key}:` zapisz blokiem z wcięciami (jak w README), nie w jednej linii.")
        if len(re.findall(rf"^{key}:", text, re.MULTILINE)) > 1:
            raise ProfileError(f"Profil: blok `{key}:` jest zdublowany na najwyższym poziomie — zostaw jeden.")
    lines = text.splitlines(keepends=True)
    span = _block_range(lines, "targets")
    targets = _parse_targets(lines[span[0] + 1 : span[1]]) if span else {}
    span = _block_range(lines, "agents")
    if span is None:
        return targets, None
    agents: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    entries = _entries(lines[span[0] + 1 : span[1]])
    if any(tier.startswith("-") for _, tier, _ in entries):
        raise ProfileError(
            "Profil: `agents.<tier>` to lista nazw po przecinku w jednej linii, "
            "np. `light: git-start,cleanup`."
        )
    for _, tier, value in entries:
        if tier not in TIERS:
            raise ProfileError(
                f"Profil: nieznany tier `agents.{tier}`. Dozwolone: {_ALLOWED} — "
                "przenieś jego agentów do jednego z nich."
            )
        if value[:1] in ("'", '"') and value[-1:] == value[:1]:
            # Cały zapis w cudzysłowie: zdejmij go raz i dziel po przecinkach; pozycji nie cytujemy ponownie.
            names = [n.strip() for n in _unquote(value, f"agents.{tier}").split(",") if n.strip()]
        else:
            body = value[1:-1] if value.startswith("[") and value.endswith("]") else value
            if "[" in body or "]" in body:
                raise ProfileError(f"Profil: `agents.{tier}` ma niedopasowane nawiasy `[]`.")
            names = [_unquote(n.strip(), f"agents.{tier}") for n in body.split(",") if n.strip()]
        if not names and value.strip() != "[]":
            raise ProfileError(f"Profil: `agents.{tier}` jest pusty — wpisz nazwy agentów albo `[]`.")
        if "" in names:
            raise ProfileError(f"Profil: pusta nazwa agenta w `agents.{tier}`.")
        for name in names:
            if name in seen:
                raise ProfileError(
                    f"Profil: agent `{name}` jest w dwóch tierach (`agents.{seen[name]}` "
                    f"i `agents.{tier}`). Zostaw go w jednym."
                )
            seen[name] = tier
        if tier in agents:
            raise ProfileError(f"Profil: tier `agents.{tier}` jest zdublowany — zostaw jeden wpis.")
        agents[tier] = names
    return targets, agents


def sync_agents(text: str, template: dict[str, str]) -> tuple[str, list[str]]:
    """
    Dopasuj blok `agents:` do agentów kita. Profil wygrywa nad template.

    Returns:
        tuple: ``(nowy tekst Profilu, raport zmian)``; bez zmian — tekst bez dotykania.
    """
    _, agents = parse_profile(text)
    report: list[str] = []
    synced: dict[str, list[str]] = {tier: [] for tier in TIERS}
    for tier, names in (agents or {}).items():
        for name in names:
            if name in template:
                synced[tier].append(name)
            else:
                report.append(f"- agents.{tier}: {name} (nie ma takiego agenta w kicie)")
    assigned = {name for names in synced.values() for name in names}
    for name in sorted(template):
        if name not in assigned:
            synced[template[name]].append(name)
            report.append(f"+ agents.{template[name]}: {name}")
    if agents is not None and not report:
        return text, []

    eol = "\r\n" if "\r\n" in text else "\n"
    block = [f"agents:{eol}"] + [f"  {tier}: {','.join(names)}{eol}" for tier, names in synced.items() if names]
    lines = text.splitlines(keepends=True)
    span = _block_range(lines, "agents")
    if span:
        lines[span[0] : span[1]] = block
        return "".join(lines), report
    if text and not text.endswith("\n"):
        text += eol
    return text + (eol if text.strip() else "") + "".join(block), report


def resolve_target(entry: dict, targets: dict[str, dict[str, dict]]) -> dict:
    """
    Wpis `target` (Clean Slate, council) → obiekt `{providerInstanceId, model, options}`.

    Bez wywołań w kodzie produkcyjnym do czasu #546 (Clean Slate) i #545 (council).

    Args:
        entry: Ref ``{"target": "<klient>.<tier>"}`` z opcjonalnym ``model`` / ``options``
            albo pełny wpis z ``providerInstanceId``.
        targets: Wynik `parse_profile` (klucz `targets`).

    Returns:
        dict: Kopia obiektu target z nadpisaniem ``model`` / ``options`` z wpisu.

    Raises:
        ProfileError: Nieznany ref albo wpis bez ``target`` i bez ``providerInstanceId``.
    """
    if "target" in entry:
        ref = entry["target"]
        client, _, tier = ref.partition(".")
        base = targets.get(client, {}).get(tier)
        if base is None:
            raise ProfileError(f"Profil: nieznany ref `target: {ref}` — brak `targets.{client}.{tier}`.")
        resolved = copy.deepcopy(base)
        if "model" in entry:
            resolved["model"] = entry["model"]
        if "options" in entry:
            resolved["options"] = copy.deepcopy(entry["options"])
        return resolved
    if "providerInstanceId" in entry:
        return {
            "providerInstanceId": entry["providerInstanceId"],
            "model": entry.get("model"),
            "options": copy.deepcopy(entry.get("options", [])),
        }
    raise ProfileError("Profil: wpis bez `target` i bez `providerInstanceId`.")


def takeover_alias(model: str | None) -> str | None:
    """
    Alias Claude Code dla przejęcia poza T3 (ADR-0018).

    Args:
        model: Id modelu z ``targets.claude.takeover.model`` albo sam alias; None = brak modelu.

    Returns:
        str | None: ``haiku`` / ``sonnet`` / ``opus`` / ``fable``; None = brak albo nieznane id, czyli model sesji.
    """
    if not model:
        return None
    if model in TAKEOVER_ALIASES:
        return model
    match = re.fullmatch(r"claude-(haiku|sonnet|opus|fable)-.+", model)
    return match.group(1) if match else None


def apply_models(client: str, profile_text: str, dest_dir: Path) -> None:
    """Dopisz `model:` (Claude też `effort:`) agentom, których tier ma wpis w `targets:` (ADR-0018)."""
    if client not in ("claude", "opencode"):
        return  # Codex i Antigravity nie mają plików agentów.
    targets, agents = parse_profile(profile_text)
    mapping = targets.get(client, {})
    for tier, names in (agents or {}).items():
        entry = mapping.get(tier)
        if not entry:
            continue
        option = {opt["id"]: opt["value"] for opt in entry["options"]}
        extra = []
        if entry["model"]:
            suffix = f"#{option['variant']}" if client == "opencode" and "variant" in option else ""
            extra.append(f"model: {entry['model']}{suffix}\n")
        if client == "claude" and "effort" in option:
            extra.append(f"effort: {option['effort']}\n")
        if not extra:
            continue
        for name in names:
            path = dest_dir / f"{name}.md"
            if not path.is_file():
                continue
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
            lines[end:end] = extra
            path.write_text("".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 4 and argv[1] == "sync":
            profile, agents_dir = Path(argv[2]), Path(argv[3])
            text = profile.read_text(encoding="utf-8") if profile.is_file() else ""
            synced, report = sync_agents(text, template_tiers(agents_dir))
            if synced != text:
                profile.write_text(synced, encoding="utf-8", newline="\n")
            for line in report:
                print(f"  {line}")
            return 0
        if len(argv) == 5 and argv[1] == "apply":
            profile = Path(argv[3])
            text = profile.read_text(encoding="utf-8") if profile.is_file() else ""
            apply_models(argv[2], text, Path(argv[4]))
            return 0
    except ProfileError as exc:
        print(f"{exc} (plik: .ai/project.profile.yaml)", file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
