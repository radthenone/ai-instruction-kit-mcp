"""Blok `council:` z Profilu — tryb dyskusji rundowej i delegaci (ADR-0018, #545)."""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Importy z scripts/model_tiers.py bez PyYAML (wspólny parser i resolver z #515)
try:
    from model_tiers import (
        ProfileError,
        _block_range,
        _parse_options,
        _targets_tree,
        _unquote,
        parse_profile,
        resolve_target,
    )
except ImportError:
    for base in (
        Path(__file__).resolve().parents[2] / "scripts",
        Path(__file__).resolve().parent / "_data" / "scripts",
    ):
        if (base / "model_tiers.py").is_file():
            sys.path.insert(0, str(base))
            break
    from model_tiers import (
        ProfileError,
        _block_range,
        _parse_options,
        _targets_tree,
        _unquote,
        parse_profile,
        resolve_target,
    )

COUNCIL_SEATS = 3
DEFAULT_ROUNDS = 2


@dataclass(frozen=True)
class CouncilMember:
    """Jeden delegat rady — nazwa, rozwiązany target oraz opcjonalny supp-target."""

    name: str
    target: dict[str, Any]
    supp_target: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Kształt obiektu dla narzędzia get_council i delegacji."""
        res: dict[str, Any] = {
            "name": self.name,
            "target": copy.deepcopy(self.target),
        }
        if self.supp_target is not None:
            res["supp-target"] = copy.deepcopy(self.supp_target)
        return res


@dataclass(frozen=True)
class CouncilConfig:
    """Wynik odczytu `council:`. Liczba rund, poprawni członkowie i uwagi z walidacji."""

    rounds: int
    members: list[CouncilMember]
    notices: list[str]


def _split_inline_pairs(body: str) -> list[str]:
    """Podziel zawartość mapy inline `{ k: v, ... }` na pary po przecinku poza nawiasami i cudzysłowami."""
    pairs: list[str] = []
    depth = 0
    quote: str | None = None
    start = 0
    i = 0
    while i < len(body):
        ch = body[i]
        if quote == '"' and ch == "\\":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch in ("{", "["):
            depth += 1
        elif ch in ("}", "]"):
            depth -= 1
        elif ch == "," and depth == 0:
            pairs.append(body[start:i].strip())
            start = i + 1
        i += 1
    if body[start:].strip():
        pairs.append(body[start:].strip())
    return pairs


def _parse_inline_dict(raw: str, where: str) -> dict[str, Any]:
    """Przetwórz mapę inline `{ k: v, ... }` na słownik Pythona."""
    raw = raw.strip()
    if not (raw.startswith("{") and raw.endswith("}")):
        raise ProfileError(f"Profil: `{where}` oczekiwano mapy inline `{{ ... }}`.")
    body = raw[1:-1].strip()
    result: dict[str, Any] = {}
    for pair in _split_inline_pairs(body):
        if not pair:
            continue
        k, sep, v = pair.partition(":")
        if not sep:
            raise ProfileError(f"Profil: `{where}` ma niepoprawną parę `{pair}`.")
        key = k.strip()
        val = v.strip()
        if key == "options":
            result[key] = _parse_options(where, val)
        else:
            result[key] = _unquote(val, f"{where}.{key}")
    return result


def _normalize_entry(raw: Any, where: str) -> dict[str, Any]:
    """Sprowadź wpis target / supp-target (string, inline dict lub dict) do postaci dla resolve_target."""
    if isinstance(raw, str):
        trimmed = raw.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            return _parse_inline_dict(trimmed, where)
        return {"target": _unquote(trimmed, where)}
    if isinstance(raw, dict):
        result: dict[str, Any] = {}
        for k, v in raw.items():
            if k == "options" and isinstance(v, str):
                result[k] = _parse_options(where, v)
            elif isinstance(v, str):
                result[k] = _unquote(v.strip(), f"{where}.{k}")
            else:
                result[k] = v
        return result
    raise ProfileError(f"Profil: `{where}` nie jest tekstem ani mapą.")


def _resolve_member(
    name: str,
    raw_member: Any,
    targets: dict[str, dict[str, dict]],
) -> tuple[CouncilMember | None, list[str]]:
    """Rozwiąż pojedynczego członka rady (`target` i opcjonalny `supp-target`)."""
    notices: list[str] = []
    if isinstance(raw_member, str):
        trimmed = raw_member.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                raw_member = _parse_inline_dict(trimmed, f"council.members.{name}")
            except ProfileError as e:
                return None, [f"council: członek `{name}` — błąd składni: {e}"]
        else:
            raw_member = {"target": trimmed}

    if not isinstance(raw_member, dict):
        return None, [f"council: członek `{name}` nie jest mapą — pominięty"]

    raw_target = raw_member.get("target")
    if raw_target is None:
        return None, [f"council: członek `{name}` bez `target` — pominięty"]

    resolved_target: dict[str, Any] | None = None
    try:
        norm_target = _normalize_entry(raw_target, f"council.members.{name}.target")
        resolved_target = resolve_target(norm_target, targets)
    except ProfileError as e:
        notices.append(f"council: członek `{name}` — nierozwiązywalny `target`: {e}")

    raw_supp = raw_member.get("supp-target")
    if raw_supp is None:
        raw_supp = raw_member.get("supp_target")

    resolved_supp: dict[str, Any] | None = None
    if raw_supp is not None:
        try:
            norm_supp = _normalize_entry(raw_supp, f"council.members.{name}.supp-target")
            resolved_supp = resolve_target(norm_supp, targets)
        except ProfileError as e:
            notices.append(f"council: członek `{name}` — nierozwiązywalny `supp-target`: {e}")

    if resolved_target is None and resolved_supp is None:
        return None, notices

    if resolved_target is None and resolved_supp is not None:
        # Główny target nierozwiązywalny, ale supp-target dostępny
        member = CouncilMember(name=name, target=resolved_supp, supp_target=None)
        return member, notices

    assert resolved_target is not None
    member = CouncilMember(name=name, target=resolved_target, supp_target=resolved_supp)
    return member, notices


def parse_council(section: Any, targets: dict[str, dict[str, dict]] | None = None) -> CouncilConfig:
    """
    Odczytaj sekcję `council:`. Błędy nie zatrzymują działania — trafiają do uwag (ADR-0004).

    Args:
        section: Wartość `council:` z Profilu: brak (None) albo mapa z `rounds` i `members`.
        targets: Wynik `parse_profile` (klucz `targets`).

    Returns:
        CouncilConfig: Liczba rund, poprawni członkowie i lista uwag.
    """
    if targets is None:
        targets = {}

    if section is None:
        return CouncilConfig(
            rounds=DEFAULT_ROUNDS,
            members=[],
            notices=["council: brak bloku `council:` w Profilu — skonfiguruj skład rady"],
        )

    if not isinstance(section, dict):
        return CouncilConfig(
            rounds=DEFAULT_ROUNDS,
            members=[],
            notices=["council: oczekiwano mapy — blok pominięty"],
        )

    notices: list[str] = []
    raw_rounds = section.get("rounds", DEFAULT_ROUNDS)
    try:
        rounds = int(raw_rounds)
        if rounds <= 0:
            notices.append(f"council: `rounds` musi być > 0, użyto domyślnego {DEFAULT_ROUNDS}")
            rounds = DEFAULT_ROUNDS
    except (ValueError, TypeError):
        notices.append(f"council: błędna wartość `rounds: {raw_rounds}`, użyto domyślnego {DEFAULT_ROUNDS}")
        rounds = DEFAULT_ROUNDS

    raw_members = section.get("members")
    if raw_members is None:
        notices.append("council: brak sekcji `members` w `council:`")
        raw_members = {}
    elif not isinstance(raw_members, dict):
        notices.append("council: `members` musi być mapą członków (klucz = nazwa)")
        raw_members = {}

    members: list[CouncilMember] = []
    for name, entry in raw_members.items():
        member, member_notices = _resolve_member(str(name), entry, targets)
        notices.extend(member_notices)
        if member is not None:
            members.append(member)

    if members and len(members) != COUNCIL_SEATS:
        notices.append(f"council: {len(members)} członków, rada wymaga {COUNCIL_SEATS}")
    elif not members and not any("brak bloku" in n for n in notices):
        notices.append("council: brak poprawnych członków rady")

    return CouncilConfig(rounds=rounds, members=members, notices=notices)


def load_council(profile_path: Path) -> CouncilConfig:
    """
    Wczytaj `council:` z pliku Profilu bez PyYAML; brak pliku oznacza brak bloku.

    Args:
        profile_path: Ścieżka do `.ai/project.profile.yaml`.

    Returns:
        CouncilConfig: Wynik `parse_council` dla sekcji `council`.
    """
    if not profile_path.is_file():
        return parse_council(None)

    text = profile_path.read_text(encoding="utf-8")
    notices: list[str] = []
    try:
        targets, _ = parse_profile(text)
    except ProfileError as e:
        targets = {}
        notices.append(f"targets: błąd Profilu — {e}")

    lines = text.splitlines()
    span = _block_range(lines, "council")
    if span is None:
        cfg = parse_council(None, targets=targets)
        return CouncilConfig(rounds=cfg.rounds, members=cfg.members, notices=[*notices, *cfg.notices])

    block_lines = lines[span[0] + 1 : span[1]]
    try:
        tree = _targets_tree(block_lines)
    except ProfileError as e:
        return CouncilConfig(
            rounds=DEFAULT_ROUNDS,
            members=[],
            notices=[*notices, f"council: błąd składni — {e}"],
        )

    cfg = parse_council(tree, targets=targets)
    return CouncilConfig(rounds=cfg.rounds, members=cfg.members, notices=[*notices, *cfg.notices])
