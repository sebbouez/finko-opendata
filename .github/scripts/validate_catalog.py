#!/usr/bin/env python3
"""
Validation du catalogue de données ouvertes Finko.

Le script part de index.json, suit chaque fichier référencé et vérifie que
l'ensemble est exploitable par l'application : structure attendue, chemins
existants, absence de doublons et adresses web sûres.

Les messages sont en anglais : ils sont lus par les contributeurs dans les
journaux de l'intégration continue.

Utilisation : python .github/scripts/validate_catalog.py
Code de retour 1 si au moins une erreur est détectée.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

# Racine du dépôt, deux niveaux au-dessus de .github/scripts
ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "index.json"

# Rubriques qu'un pays peut publier dans index.json
ALLOWED_ITEMS = {"banks", "providers", "services"}

# Périodicités acceptées, alignées sur les modes de récurrence de Finko
ALLOWED_FREQUENCIES = {
    "eachWeek",
    "eachMonth",
    "eachTrimester",
    "eachQuarter",
    "eachHalfYear",
    "eachYear",
}

SERVICE_KEY_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

COUNTRY_CODE_PATTERN = re.compile(r"^[a-z]{2}$")
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
IP_LITERAL_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

MAX_DISPLAY_NAME_LENGTH = 120

_errors: list[str] = []
_warnings: list[str] = []


def error(message: str) -> None:
    _errors.append(message)


def warn(message: str) -> None:
    _warnings.append(message)


def rel(path: Path) -> str:
    """Chemin affiché relativement à la racine du dépôt."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, label: str):
    """Charge un fichier JSON en signalant les causes d'échec les plus courantes."""
    if not path.is_file():
        error(f"{label}: file not found ({rel(path)})")
        return None

    raw = path.read_bytes()
    if not raw.strip():
        error(f"{label}: file is empty ({rel(path)})")
        return None

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as ex:
        error(f"{label}: file is not valid UTF-8 ({rel(path)}): {ex}")
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError as ex:
        error(f"{label}: invalid JSON ({rel(path)}) at line {ex.lineno}, column {ex.colno}: {ex.msg}")
        return None


def check_display_name(value, label: str) -> bool:
    """Un nom affiché doit être une chaîne propre, directement utilisable dans l'interface."""
    if not isinstance(value, str):
        error(f"{label}: 'displayName' must be a string")
        return False

    if not value.strip():
        error(f"{label}: 'displayName' must not be empty")
        return False

    if value != value.strip():
        error(f"{label}: 'displayName' must not start or end with whitespace (got {value!r})")
        return False

    if CONTROL_CHARS_PATTERN.search(value):
        error(f"{label}: 'displayName' must not contain control characters (got {value!r})")
        return False

    if len(value) > MAX_DISPLAY_NAME_LENGTH:
        error(f"{label}: 'displayName' must be {MAX_DISPLAY_NAME_LENGTH} characters or fewer (got {len(value)})")
        return False

    return True


def check_url(value, label: str) -> None:
    """
    Une adresse est affichée aux utilisateurs de Finko : elle doit être en HTTPS
    et ne pas pouvoir se faire passer pour un autre domaine.
    """
    if not isinstance(value, str):
        error(f"{label}: 'url' must be a string")
        return

    if not value.strip():
        error(f"{label}: 'url' must not be empty (omit the field instead)")
        return

    if value != value.strip():
        error(f"{label}: 'url' must not start or end with whitespace (got {value!r})")
        return

    if CONTROL_CHARS_PATTERN.search(value) or any(c.isspace() for c in value):
        error(f"{label}: 'url' must not contain whitespace or control characters (got {value!r})")
        return

    parts = urlsplit(value)

    if parts.scheme != "https":
        error(f"{label}: 'url' must use the https scheme (got {value!r})")
        return

    if not parts.netloc:
        error(f"{label}: 'url' has no host (got {value!r})")
        return

    # https://banque-legitime.fr@domaine-malveillant.example/ affiche un domaine de confiance
    # tout en menant ailleurs : les identifiants dans l'URL sont refusés.
    if "@" in parts.netloc:
        error(f"{label}: 'url' must not contain credentials in the host part (got {value!r})")
        return

    host = parts.hostname or ""
    if IP_LITERAL_PATTERN.match(host) or host.startswith("["):
        error(f"{label}: 'url' must use a domain name, not an IP address (got {value!r})")
        return

    if "." not in host:
        error(f"{label}: 'url' host does not look like a public domain (got {value!r})")
        return

    if parts.username or parts.password:
        error(f"{label}: 'url' must not contain credentials (got {value!r})")


def check_relative_path(value, country_code: str, item_name: str, label: str) -> Path | None:
    """Un chemin de l'index doit rester dans le dossier du pays, sous la racine du dépôt."""
    if not isinstance(value, str) or not value.strip():
        error(f"{label}: path for '{item_name}' must be a non-empty string")
        return None

    if value != value.strip():
        error(f"{label}: path for '{item_name}' must not start or end with whitespace (got {value!r})")
        return None

    if "\\" in value:
        error(f"{label}: path for '{item_name}' must use forward slashes (got {value!r})")
        return None

    if value.startswith("/"):
        error(f"{label}: path for '{item_name}' must be relative (got {value!r})")
        return None

    if ".." in value.split("/"):
        error(f"{label}: path for '{item_name}' must not escape the repository (got {value!r})")
        return None

    if not value.startswith(f"{country_code}/"):
        error(f"{label}: path for '{item_name}' must live in the '{country_code}/' folder (got {value!r})")
        return None

    if not value.endswith(".json"):
        error(f"{label}: path for '{item_name}' must point to a .json file (got {value!r})")
        return None

    resolved = (ROOT / value).resolve()
    if not resolved.is_relative_to(ROOT):
        error(f"{label}: path for '{item_name}' resolves outside the repository (got {value!r})")
        return None

    if not resolved.is_file():
        error(f"{label}: path for '{item_name}' does not exist ({value})")
        return None

    return resolved


def validate_banks_file(path: Path, country_code: str) -> None:
    """Vérifie le contenu d'un fichier banks.json."""
    label = rel(path)
    data = load_json(path, label)
    if data is None:
        return

    if not isinstance(data, dict):
        error(f"{label}: root value must be an object")
        return

    banks = data.get("banks")
    if banks is None:
        error(f"{label}: missing 'banks' array")
        return

    if not isinstance(banks, list):
        error(f"{label}: 'banks' must be an array")
        return

    if not banks:
        error(f"{label}: 'banks' must not be empty (remove the file from index.json instead)")
        return

    unexpected_keys = set(data.keys()) - {"banks"}
    if unexpected_keys:
        warn(f"{label}: unexpected top-level keys: {', '.join(sorted(unexpected_keys))}")

    seen_names: dict[str, int] = {}
    seen_urls: dict[str, int] = {}

    for position, bank in enumerate(banks):
        entry_label = f"{label}: banks[{position}] ({country_code})"

        if not isinstance(bank, dict):
            error(f"{entry_label}: entry must be an object")
            continue

        unexpected = set(bank.keys()) - {"displayName", "url"}
        if unexpected:
            error(f"{entry_label}: unexpected keys: {', '.join(sorted(unexpected))}")

        if "displayName" not in bank:
            error(f"{entry_label}: missing 'displayName'")
            continue

        if not check_display_name(bank["displayName"], entry_label):
            continue

        name = bank["displayName"]
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            error(f"{entry_label}: duplicate bank name {name!r}, already declared at banks[{seen_names[normalized_name]}]")
        else:
            seen_names[normalized_name] = position

        if "url" in bank:
            check_url(bank["url"], entry_label)

            if isinstance(bank["url"], str):
                normalized_url = bank["url"].strip().casefold().rstrip("/")
                if normalized_url and normalized_url in seen_urls:
                    warn(f"{entry_label}: url already used by banks[{seen_urls[normalized_url]}] in the same file")
                else:
                    seen_urls[normalized_url] = position


def validate_services_file(path: Path, country_code: str) -> None:
    """Vérifie le contenu d'un fichier services.json."""
    label = rel(path)
    data = load_json(path, label)
    if data is None:
        return

    if not isinstance(data, dict):
        error(f"{label}: root value must be an object")
        return

    services = data.get("services")
    if services is None:
        error(f"{label}: missing 'services' array")
        return

    if not isinstance(services, list):
        error(f"{label}: 'services' must be an array")
        return

    if not services:
        error(f"{label}: 'services' must not be empty (remove the file from index.json instead)")
        return

    unexpected_keys = set(data.keys()) - {"services"}
    if unexpected_keys:
        warn(f"{label}: unexpected top-level keys: {', '.join(sorted(unexpected_keys))}")

    seen_keys: dict[str, int] = {}
    seen_names: dict[str, int] = {}

    for position, service in enumerate(services):
        entry_label = f"{label}: services[{position}] ({country_code})"

        if not isinstance(service, dict):
            error(f"{entry_label}: entry must be an object")
            continue

        unexpected = set(service.keys()) - {"key", "displayName", "thirdParty", "label", "frequency", "url"}
        if unexpected:
            error(f"{entry_label}: unexpected keys: {', '.join(sorted(unexpected))}")

        missing = [f for f in ("key", "displayName", "thirdParty", "label", "frequency") if f not in service]
        if missing:
            error(f"{entry_label}: missing required field(s): {', '.join(missing)}")
            continue

        # L'identifiant est conservé dans le fichier de l'utilisateur : il doit rester stable et unique
        key = service["key"]
        if not isinstance(key, str) or not SERVICE_KEY_PATTERN.match(key):
            error(f"{entry_label}: 'key' must be lowercase alphanumeric words separated by hyphens (got {key!r})")
        elif key in seen_keys:
            error(f"{entry_label}: duplicate key {key!r}, already declared at services[{seen_keys[key]}]")
        else:
            seen_keys[key] = position

        for field in ("displayName", "thirdParty", "label"):
            check_display_name(service[field], f"{entry_label}: '{field}'")

        frequency = service["frequency"]
        if frequency not in ALLOWED_FREQUENCIES:
            error(f"{entry_label}: 'frequency' must be one of {', '.join(sorted(ALLOWED_FREQUENCIES))} (got {frequency!r})")

        if isinstance(service["displayName"], str):
            normalized_name = service["displayName"].casefold()
            if normalized_name in seen_names:
                error(f"{entry_label}: duplicate service name, already declared at services[{seen_names[normalized_name]}]")
            else:
                seen_names[normalized_name] = position

        if "url" in service:
            check_url(service["url"], entry_label)


def validate_index() -> set[Path]:
    """Valide index.json et retourne l'ensemble des fichiers qu'il référence."""
    referenced: set[Path] = set()

    data = load_json(INDEX_PATH, "index.json")
    if data is None:
        return referenced

    if not isinstance(data, dict):
        error("index.json: root value must be an object")
        return referenced

    countries = data.get("countries")
    if countries is None:
        error("index.json: missing 'countries' array")
        return referenced

    if not isinstance(countries, list):
        error("index.json: 'countries' must be an array")
        return referenced

    if not countries:
        error("index.json: 'countries' must not be empty")
        return referenced

    unexpected_keys = set(data.keys()) - {"countries"}
    if unexpected_keys:
        warn(f"index.json: unexpected top-level keys: {', '.join(sorted(unexpected_keys))}")

    seen_codes: dict[str, int] = {}

    for position, country in enumerate(countries):
        label = f"index.json: countries[{position}]"

        if not isinstance(country, dict):
            error(f"{label}: entry must be an object")
            continue

        unexpected = set(country.keys()) - {"code", "displayName", "items"}
        if unexpected:
            error(f"{label}: unexpected keys: {', '.join(sorted(unexpected))}")

        code = country.get("code")
        if not isinstance(code, str) or not COUNTRY_CODE_PATTERN.match(code):
            error(f"{label}: 'code' must be a lowercase two-letter country code (got {code!r})")
            continue

        label = f"index.json: countries[{position}] ({code})"

        if code in seen_codes:
            error(f"{label}: duplicate country code, already declared at countries[{seen_codes[code]}]")
        else:
            seen_codes[code] = position

        if "displayName" not in country:
            error(f"{label}: missing 'displayName'")
        else:
            check_display_name(country["displayName"], label)

        items = country.get("items")
        if items is None:
            error(f"{label}: missing 'items' array")
            continue

        if not isinstance(items, list):
            error(f"{label}: 'items' must be an array")
            continue

        if not items:
            error(f"{label}: 'items' must not be empty")
            continue

        seen_item_names: set[str] = set()

        for item_position, item in enumerate(items):
            item_label = f"{label}: items[{item_position}]"

            if not isinstance(item, dict):
                error(f"{item_label}: entry must be an object mapping an item name to a file path")
                continue

            if not item:
                error(f"{item_label}: entry must not be empty")
                continue

            for item_name, item_path in item.items():
                if item_name not in ALLOWED_ITEMS:
                    error(f"{item_label}: unknown item {item_name!r} (allowed: {', '.join(sorted(ALLOWED_ITEMS))})")
                    continue

                if item_name in seen_item_names:
                    error(f"{item_label}: item {item_name!r} is declared more than once for '{code}'")
                    continue

                seen_item_names.add(item_name)

                resolved = check_relative_path(item_path, code, item_name, item_label)
                if resolved is None:
                    continue

                referenced.add(resolved)

                if item_name == "banks":
                    validate_banks_file(resolved, code)
                elif item_name == "services":
                    validate_services_file(resolved, code)

    return referenced


def report_orphan_files(referenced: set[Path]) -> None:
    """Signale les fichiers de données qu'aucun pays de l'index ne référence."""
    for path in sorted(ROOT.rglob("*.json")):
        if ".git" in path.parts or ".github" in path.parts:
            continue

        if path == INDEX_PATH or path in referenced:
            continue

        warn(f"{rel(path)}: file is not referenced by index.json and will never be read by the application")


def main() -> int:
    referenced = validate_index()
    report_orphan_files(referenced)

    for message in _warnings:
        print(f"warning: {message}")

    for message in _errors:
        print(f"error: {message}")

    print()
    print(f"{len(referenced)} data file(s) referenced, {len(_errors)} error(s), {len(_warnings)} warning(s).")

    if _errors:
        print("Catalog validation failed.")
        return 1

    print("Catalog validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
