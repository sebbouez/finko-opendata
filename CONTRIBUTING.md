# Contributing to finko-opendata

Thanks for helping build this catalog. It powers the online data features of
[Finko](https://github.com/sebbouez/CohoApps), where the entries you add are shown
directly to users — so accuracy matters more than volume here.

Everything in this repository is public, open data. Please do not add anything that
is not already published on an official, publicly accessible website.

## How to contribute

1. Fork the repository.
2. Create a branch from `main`.
3. Make your change.
4. Run the validator locally (see below).
5. Open a pull request against `main`.

Direct pushes to `main` are not possible: every change goes through a pull request
and must pass the automated validation.

## The golden rule: every entry needs a verifiable source

This is the one thing reviewers check hardest.

Finko displays the bank names and links from this catalog inside the application.
A wrong or hostile link reaches real users as something that looks trustworthy.
So for **every bank you add or modify**, your pull request description must state
where the information comes from — normally the bank's own official website.

Pull requests that add entries without a source will be asked for one before review
continues. When in doubt about whether an institution qualifies, open an issue first.

## Repository layout

```
index.json          list of covered countries
<country>/          one folder per country, named after its ISO 3166-1 alpha-2 code
  banks.json        banks for that country
  services.json     subscription services for that country
  thirdparties.json common payees for that country
```

### `index.json`

```json
{
  "countries": [
    {
      "code": "fr",
      "displayName": "France",
      "items": [
        { "banks": "fr/banks.json" },
        { "services": "fr/services.json" },
        { "thirdparties": "fr/thirdparties.json" }
      ]
    }
  ]
}
```

- `code` — lowercase two-letter ISO 3166-1 alpha-2 country code. It must match the
  folder name.
- `displayName` — the country name as it should be shown.
- `items` — the data files published for this country. Each entry maps an item name
  to a path inside the country folder. Supported item names: `banks`, `services`,
  `thirdparties`, `providers`.

### `<country>/banks.json`

```json
{
  "banks": [
    {
      "displayName": "BNP Paribas",
      "url": "https://mabanque.bnpparibas/"
    }
  ]
}
```

- `displayName` — the bank's commercial name, as customers know it. No leading or
  trailing whitespace, 120 characters maximum, and unique within the country.
- `url` — optional, but when present it must be the bank's official public website,
  over HTTPS.

No other fields are accepted. The validator rejects unknown keys on purpose, so that
a typo never ships silently.

### `<country>/services.json`

Subscription services, used by Finko to pre-fill a recurring operation.

```json
{
  "services": [
    {
      "key": "fr-amazon-prime-monthly",
      "displayName": "Amazon Prime (mensuel)",
      "thirdParty": "Amazon",
      "label": "Amazon Prime",
      "frequency": "eachMonth",
      "url": "https://www.amazon.fr/amazonprime"
    }
  ]
}
```

- `key` — stable identifier, lowercase words separated by hyphens, unique within the
  country. Finko stores it in the user's file, so **never change or reuse a key**: rename
  the `displayName` instead.
- `displayName` — how the entry appears in the catalog. When a service is offered with
  several billing periods, add the period so entries stay distinguishable, in the language
  of the country.
- `thirdParty` — who gets paid, for example `Amazon`. Finko selects or creates a matching
  third party.
- `label` — the suggested label for the operation itself, for example `Amazon Prime`.
- `frequency` — one of `eachWeek`, `eachMonth`, `eachTrimester` (3 months),
  `eachQuarter` (4 months), `eachHalfYear`, `eachYear`.
- `url` — optional, the official public page of the service.

**This file carries no price, and the validator rejects any attempt to add one.** Tariffs
change several times a year, vary by plan and country, and many users are on grandfathered
or promotional rates — a published price would be wrong for a large share of them. Finko
detects the real amount from the user's own bank operations instead, and the `url` lets
them check the current tariff themselves.

### `<country>/thirdparties.json`

Common payees, offered in bulk when a user sets up a new file.

```json
{
  "thirdParties": [
    {
      "displayName": "Carrefour",
      "category": "Grande distribution"
    }
  ]
}
```

- `displayName` — the payee name as it will be created in the user's file. Unique within
  the country.
- `category` — optional, a grouping hint shown under the name and included in the search.
  Write it in the language of the country.

No URL here: a payee is a label in the user's account book, not a link. Keep the list to
names a user would actually recognise on a bank statement.

## Rules enforced automatically

The `Validate catalog` check runs on every pull request and must pass before a merge.
It fails when:

- a JSON file is malformed, empty, or not valid UTF-8;
- `index.json` references a file that does not exist, or one that lives outside its
  country folder;
- a country code is not a lowercase two-letter code, or is declared twice;
- a `displayName` is missing, empty, padded with whitespace, too long, contains
  control characters, or duplicates another entry in the same country;
- a `url` is not HTTPS, carries credentials in the host part (the
  `https://real-bank.example@attacker.example/` trick), points at a raw IP address,
  or contains whitespace;
- a service `key` is malformed, or duplicated within the country;
- a third party is missing its `displayName`, or duplicates another one in the country;
- a service `frequency` is not one of the supported values;
- an object contains a field that is not part of the format.

It warns, without failing, when a data file is not referenced by `index.json`, or
when two banks in the same country share a URL.

### Running the validator locally

No dependencies beyond Python 3:

```bash
python3 .github/scripts/validate_catalog.py
```

## Adding a new country

1. Create a folder named after the ISO 3166-1 alpha-2 code, in lowercase (`de`, `es`, `it`).
2. Add `banks.json`, `services.json` and/or `thirdparties.json` inside it, following the
   formats above.
3. Register the country in `index.json`, keeping the list sorted by `displayName`.
4. Run the validator, then open your pull request.

## Style

- UTF-8, no BOM.
- Two-space indentation in JSON files.
- Keep bank and service lists sorted alphabetically by `displayName` — it keeps diffs
  readable and makes duplicates obvious during review. Third parties are sorted by
  `category`, then by `displayName`.

## Reporting a problem

For a wrong or outdated entry, open an issue. If you believe an entry is actively
harmful — a link that leads somewhere it should not — please report it privately
through the repository's security advisory page rather than in a public issue.
