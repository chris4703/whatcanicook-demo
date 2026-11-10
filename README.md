# What Can I Cook?

A shared pantry application that connects groceries to meal ideas: scan product barcodes, track quantities, maintain a shopping list, and review recipe deductions before updating stock.

Designed for a mobile browser, with Python, SQLite, a locally served barcode scanner, and Docker Compose. The core service is not tied to a particular computer, household, or operating system.

> **A local-first demo, not an authenticated public service.** There are no individual accounts or access roles. Everyone who can reach the application shares pantry access and can make changes. This repository shares source code, not access to a household instance. Keep a running instance on localhost or behind an appropriate private access boundary. Do not populate a publicly reachable demo with real household data or enable paid recipe requests for anonymous visitors.

## What it does

- Continuous camera scanning with confirmation feedback and duplicate-scan handling.
- Queued scan events with idempotent retries; keep the page open until saved.
- Quantity tracking in grams, milliliters, or item counts, including fractional amounts.
- Product identification through Open Food Facts, optionally backed by a local catalog index.
- Manual correction for unknown items, package sizes, and quantities.
- Automatic low-stock shopping entries plus manually added items.
- Optional recipe suggestions with source links and editable ingredient deductions.
- Transactional deduction and undo, with conflict checks for shared inventory edits.

The application starts with an empty pantry. No real inventory, shopping history, user accounts, photographs, certificates, database, or API credentials are distributed.

## Start a separate Docker demo

Requires Docker with Compose v2. The default project is `pantry-demo` and uses its own named data volume; it does not attach to an existing household pantry.

```sh
cp .env.example .env
# Adjust the example port if it is already in use.
docker compose up -d --build --wait
```

Open http://127.0.0.1:18088 on the Docker host. This starts only the application. The HTTPS proxy and large barcode catalog importer are opt-in profiles.

Leave `OPENAI_API_KEY` blank to try pantry management without recipe search. Do not put real credentials in a tracked file. No script installs keys or connects to your private deployment automatically.

Hardware, ports, storage capacity, filesystem permissions, and networking vary. The default port and hostname are examples, not the original author's home-network settings. Do not start a second writable instance against an existing pantry database or reuse its volume without a migration plan.

## Barcode scanning and product lookup

The browser scanner is served locally from the vendored ZXing library; it does not fetch scanner code from a CDN. Camera access requires a browser-supported secure context. Localhost can be used for local development; a phone connecting to a server over the LAN needs a trusted HTTPS setup. Browser and device behavior must be checked on the actual device.

Before enabling provider lookups, review the [Open Food Facts usage documentation](https://openfoodfacts.github.io/openfoodfacts-server/api/) and configure `OFF_USER_AGENT` with an appropriate application/contact identity in your private runtime settings.

Catalog misses use read-only product API requests. Unknown or failed lookups can be corrected manually. Barcodes identify products, not how much remains in a package; ambiguous sizes and multipacks require review. Compressed UPC-E codes are not expanded to UPC-A by this implementation.

### Optional local catalog

```sh
docker compose --profile catalog up -d --build
```

The `off-index` service downloads the official compressed product CSV export and builds a local SQLite lookup database. This is a large download that can take substantial time, disk space, and memory; it is intentionally not part of the default startup. Check your machine’s capacity before enabling it.

```sh
docker compose logs -f off-index
```

The importer stages a replacement index and refreshes according to `OFF_INDEX_INTERVAL_HOURS`. These application settings do not replace the provider’s current usage or data-license requirements. Review the [Open Food Facts data terms](https://world.openfoodfacts.org/data) before redistributing an index or derived dataset.

## Optional recipe suggestions

Recipe search is disabled without a server-side `OPENAI_API_KEY`. `OPENAI_MODEL` is configurable; the checked-in example retains the application's existing default. A model and account must support the features used by this code. This guide does not promise model availability, pricing, or service access.

The app sends pantry item names, IDs, quantities, units, and meal/cuisine/serving preferences to the recipe provider. Its request disables response storage with `store: false`; that setting is not a blanket guarantee about a provider’s other data-handling policies. No live requests are made by the automated tests.

Recipe output must link to a URL present in the response’s web-search sources. Matching, scaling, substitutions, and unit conversions are estimates, not dietary or food-safety verification. Review the original recipe and deductions before confirming. The UI lets you choose servings; the default is an example preference, not a statement about the author's household.

The current matching policy assumes a broad list of staples, including herbs, aromatics, rice, meats, dairy, pasta, eggs, oatmeal, sugar, flour, butter, and honey, and allows up to two other missing ingredients. Those assumptions are application behavior rather than proof of pantry availability. Adapt them for your needs and review all ingredients, especially for allergies or dietary restrictions.

## Optional HTTPS for a trusted local network

```sh
docker compose --profile https up -d --build --wait
```

Caddy uses an internal certificate authority. The default example is loopback-only at `https://localhost:18443`; clients will need to trust the appropriate certificate before treating it as a secure endpoint.

For another device, deliberately set `PANTRY_HOST` to the server hostname or IP used in the browser and `LAN_IP` to the specific interface address on which to listen. The hostname must already resolve on that device. This does not register a new `.local` name, configure DNS, or add an access-control layer.

For devices you control, export **only the public root certificate** if needed:

```sh
mkdir -p certs
docker compose cp https:/data/caddy/pki/authorities/local/root.crt certs/pantry-root.crt
```

Transfer and trust only the certificate from your own instance. The Caddy data volume also contains private CA key material; do not export it or publish it. Device certificate-installation steps vary by OS and version. Trusting a local root is a manual decision on each device; never install someone else's sample CA as part of running this repository.

`scripts/make_iphone_profile.py` can package an existing public certificate into a local installation profile. Generated profiles and certificates are excluded from Git. It does not install a profile, grant trust, or include an API key.

### Optional macOS forwarding helper

`scripts/install_macos_forwarder.py` is an optional host-side workaround for a specific Docker Desktop LAN-forwarding problem. It is not run by Docker and is not needed for ordinary localhost use. The core app also runs outside macOS.

The helper requires explicit private-interface and port arguments. It creates the demo-specific LaunchAgent `local.pantry-demo.lan-forwarder`, so it does not replace an older deployment’s differently named agent. Review the script and choose a unique port before running it; do not create competing forwards. It does not bypass HTTPS certificate requirements.

## Storage, exports, and recovery

The app and optional catalog use the demo project's `pantry_data` volume. The optional HTTPS service has separate Caddy state/config volumes. `docker compose down` preserves volumes; `docker compose down -v` deletes them.

The Settings export is a readable inventory/shopping snapshot, not a complete restorable backup. For a consistent full database backup, use SQLite’s backup API or stop the service before copying its database. Keep backups, exports, logs, and library files out of Git. Test restoration into separate storage before relying on it, and never overwrite a running household instance for a demo.

Source-code updates do not migrate data between different Compose projects. Back up before updating code or changing volume mappings.

## Local development and checks

Python 3.9+; no Python package installation or JavaScript build step is required.

```sh
python3 app.py
# Default local application URL: http://127.0.0.1:8080
```

Direct Python execution uses process environment variables, not automatic `.env` loading. `HOST` (default `127.0.0.1`), `PORT`, `PANTRY_DB`, and `OFF_DB` can select a separate listener and fresh data paths. The optional catalog importer and HTTPS proxy do not start with this command.

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example --profile https --profile catalog config --quiet
```

Tests use temporary databases and mocked providers, covering scan retries, inventory units, conflicts, deduction/undo, recipe-source checks, shopping policy, and catalog import behavior. They do not spend API credits. Live camera behavior, provider coverage, certificate trust, and external requests need separate testing with your own configuration.

## Project layout

| Path | Purpose |
| --- | --- |
| `app.py` | HTTP API, SQLite state, lookup queue, and recipe/deduction logic |
| `static/` | Mobile interface and locally served scanner |
| `scripts/import_openfoodfacts.py` | Optional catalog importer |
| `scripts/` | Optional macOS forwarding and iPhone certificate-profile helpers |
| `tests/` | Mocked integration and behavior checks |
| `PUBLICATION.md` | Clean-history export and privacy boundaries |

Open Food Facts attribution and license links remain in the interface. ZXing notices are preserved in `static/vendor/ZXING-LICENSE` and `static/vendor/ZXING-LIBRARY-LICENSE`; generalizing the app does not remove upstream licensing obligations. No license for the original application code has been selected in this preparation step.
