# StackBridge — BookStack Document Importer

**Open-source, self-hosted document importer for BookStack. Import DOCX / Word, PDF, Markdown, HTML and TXT into BookStack with OCR, document preview, folder-to-chapter structure and optional AI enhancement.**

> **BookStack Document Importer · DOCX to BookStack · Word to BookStack · PDF to BookStack · BookStack OCR · Docker · Self-hosted**

StackBridge is a **Document Import Studio for BookStack**, version `1.0.0`. It is designed for users and administrators who need an easy way to migrate or bulk-import existing documentation into BookStack while preserving useful document structure.

StackBridge permet l’**import massif de documents vers BookStack** : DOCX/Word, PDF, Markdown, HTML et TXT, avec structure dossiers → chapitres, OCR Tesseract, prévisualisation et amélioration IA optionnelle.

## ✨ Features / Fonctionnalités

- 📄 **DOCX / Microsoft Word to BookStack** import
- 📕 **PDF to BookStack** import
- 🔎 **OCR for scanned PDFs** using Tesseract
- 📝 Markdown, HTML and TXT import
- 📂 Bulk import of multiple documents
- 🗂️ Folder / ZIP structure converted into **BookStack chapters**
- 👁️ Document preview before import
- 🖼️ Image extraction and integration into BookStack pages
- 🤖 Optional AI-assisted document enhancement
- 🔌 OpenAI-compatible AI endpoints and Ollama preset
- 🐳 Docker / Docker Compose deployment
- 🔐 Encrypted BookStack and AI API credentials
- 🛡️ HTML sanitization, CSRF protection and secure admin sessions
- 🏠 Fully **self-hosted**

## 🎯 Why StackBridge?

BookStack is excellent for building structured documentation, but migrating an existing collection of Word documents, PDFs and folders can require significant manual work. StackBridge provides a web interface between your existing documents and the **BookStack API** so that documentation can be converted, previewed and imported more efficiently.

Typical use cases include:

- migrating **Word/DOCX documentation to BookStack**;
- importing **PDF documentation into BookStack**;
- processing scanned PDF files with **OCR**;
- migrating a shared documentation folder into books and chapters;
- bulk importing technical or internal documentation;
- improving imported pages with an optional local or remote AI model.

## 🚀 Quick start with Docker

### Requirements

- Docker Engine or Docker Desktop with Compose v2;
- Git;
- TCP port `5050` available;
- a BookStack instance with API access.

### Installation

```bash
git clone https://github.com/odi2050/stackbridge.git
cd stackbridge
docker build --build-arg APP_VERSION=1.0.0 -t stackbridge:1.0.0 .
```

Generate the `.env` file interactively. The setup command asks for the administrator password and automatically creates its scrypt hash as well as session and encryption keys.

Linux / macOS:

```bash
docker run --rm -it -v "$PWD:/config" stackbridge:1.0.0 \
  python /app/scripts/setup_env.py --output /config/.env
```

PowerShell:

```powershell
docker run --rm -it -v "${PWD}:/config" stackbridge:1.0.0 `
  python /app/scripts/setup_env.py --output /config/.env
```

Start StackBridge:

```bash
docker compose up -d --build
docker compose ps
```

Open `http://SERVER_ADDRESS:5050`. Administration is available at `/admin`.

The container uses Waitress with eight threads. Encrypted settings are persisted in `data/`, logs in `logs/`, and the healthcheck queries `/api/health` every 30 seconds.

## 📂 Importing folders

StackBridge does not use the browser's native folder picker. To preserve a complete directory tree without repeated browser confirmation, compress the directory into a ZIP file and select the archive.

The internal ZIP paths are used to create the corresponding **BookStack chapter structure**.

## 🔄 Docker update

```bash
git pull
python scripts/check_release.py
docker compose build --pull
docker compose up -d
```

Before a major update, back up `.env`, `data/` and `logs/`. Never delete `data/.settings.key` if `SETTINGS_ENCRYPTION_KEY` is not defined in `.env`.

### Stop and restart

```bash
docker compose stop
docker compose start
docker compose restart
```

Remove only the container while keeping persistent data:

```bash
docker compose down
```

## 🏷️ Versioning and Docker releases

StackBridge follows [Semantic Versioning](https://semver.org/) using `MAJOR.MINOR.PATCH`.

- `MAJOR`: incompatible configuration, API or data change;
- `MINOR`: backward-compatible feature;
- `PATCH`: backward-compatible fix.

The `VERSION` file is the repository source of truth. The same value must be set in `APP_VERSION` in `.env` when creating a release. It is then:

- embedded in the image as `STACKBRIDGE_VERSION`;
- used for the `stackbridge:<version>` tag;
- written to OCI image labels;
- displayed in the interface;
- exposed through `/api/version` and `/api/health`;
- used for CSS and JavaScript cache invalidation.

### Create a release

1. Choose the new SemVer version, for example `1.1.0`.
2. Update `VERSION` and `APP_VERSION` in `.env` with the same value.
3. Add changes to `CHANGELOG.md` under a dated section.
4. Validate consistency: `python scripts/check_release.py`.
5. Build: `docker compose build --pull`.
6. Verify: `docker compose run --rm stackbridge python -c "from version import APP_VERSION; print(APP_VERSION)"`.
7. Start: `docker compose up -d`.
8. Check: `docker compose ps`, then open `/api/health`.
9. Optionally create a Git tag: `git tag -a v1.1.0 -m "StackBridge 1.1.0"`.

Never reuse the same tag for different images. For intermediate testing, use SemVer prereleases such as `1.1.0-rc.1`.

## 🐍 Installation without Docker

### Requirements

- Python 3.12 or compatible;
- Git;
- Tesseract OCR, optional but required for scanned PDFs;
- network access to BookStack and, if enabled, the AI API.

Debian / Ubuntu:

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng
```

On Windows, install Tesseract and add its directory to `PATH`.

### Linux / macOS

```bash
git clone https://github.com/odi2050/stackbridge.git
cd stackbridge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/setup_env.py
python app.py
```

### Windows PowerShell

```powershell
git clone https://github.com/odi2050/stackbridge.git
Set-Location stackbridge
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts\setup_env.py
python app.py
```

StackBridge listens on `0.0.0.0:5050` with Waitress. `.env` is loaded automatically at startup.

### Direct installation update

```bash
git pull
python -m pip install -r requirements.txt
python scripts/check_release.py
```

Restart the StackBridge process or its system service afterwards.

## ⚙️ Administration

Open `/admin` to configure BookStack, AI, TLS certificate verification and detailed logging. Model discovery queries the OpenAI-compatible `/v1/models` endpoint.

- `Vérifier les certificats SSL/TLS` applies to BookStack and AI calls.
- `http://` URLs are supported but should only be used on trusted networks.
- Global detailed logging traces routes, conversion, OCR, HTTP calls, AI and imports.
- Rotating logs are written to `logs/app.log`.

Before an AI call, Base64 images are replaced with small markers and restored after the response. This prevents image data from consuming large amounts of the model context. `AI_MAX_INPUT_TOKENS` sets the preventive input text limit (6000 by default).

The administration option `Envoyer les images à l’IA` can disable this masking. It is disabled by default because Base64 image payloads can rapidly exceed provider token limits.

### Custom AI API

Custom mode allows configuration of the POST endpoint, JSON request body and response text path. Available variables are `{{model}}`, `{{system_prompt}}`, `{{prompt}}`, `{{html}}` and `{{level}}`.

Response paths use dot notation, for example `message.content` or `choices.0.message.content`. An Ollama preset is included.

Tokens and API keys are never displayed in the user interface. They are stored encrypted in `data/settings.json`, excluded from Git.

Sensitive `settings.json` fields (`token_id`, `token_secret`, `ai_api_key`) are encrypted with Fernet. A local key is created in `data/.settings.key`; for production, prefer `SETTINGS_ENCRYPTION_KEY` supplied through a Docker secret or environment variable.

## 🔐 Security

### Secret protection

- BookStack Token ID, Token Secret and AI API key are encrypted at rest with Fernet.
- Legacy plaintext values are automatically migrated when loaded.
- The local key is stored in `data/.settings.key` with restrictive permissions where supported.
- In production, `SETTINGS_ENCRYPTION_KEY` should come from a secret manager, Docker secret or secured environment variable.
- Secrets are never returned by the public API or displayed in the UI.
- `.env`, `data/settings.json`, `data/admin_auth.json`, `data/.settings.key` and logs are excluded from Git or the Docker build context.

### Administrator authentication

- Administrator password can be changed from `/admin`.
- New passwords must contain at least 12 characters.
- Only a salted scrypt hash is stored in `data/admin_auth.json`.
- Current password is required before modification.
- Existing administrator sessions are invalidated after a password change.
- After five failed logins from one address, new attempts are blocked for 15 minutes.
- Production Docker deployments should define `ADMIN_PASSWORD_HASH` and `SECRET_KEY` in `.env`.

### Sessions and administrative requests

- Administrative data-changing requests are protected with a random session-bound CSRF token.
- Login and logout are also protected against cross-site requests.
- Session cookies use `HttpOnly` and `SameSite=Strict`.
- With HTTPS, set `SESSION_COOKIE_SECURE=true`.

### Imported content and preview

- HTML from documents and AI responses is sanitized before preview and BookStack import.
- Dangerous active tags including `script`, `iframe`, `object`, `embed` and forms are removed.
- Event attributes such as `onclick` and `onerror`, plus `javascript:` and `vbscript:` URLs, are removed.
- ZIP archives are read without direct filesystem extraction, reducing path traversal risk.
- Encrypted or unreadable ZIPs, archives containing more than 2,000 documents, or archives exceeding the decompressed size limit are rejected.

### HTTP and network security

- BookStack and AI calls are performed server-side through a centralized HTTP client; tokens do not transit through the browser.
- TLS verification is global and enabled by default.
- HTTP URLs are accepted but send data without encryption; HTTPS is recommended outside trusted networks.
- Responses include security headers such as `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` and CSP.
- HSTS is automatically sent when the application itself is served through HTTPS.
- Waitress replaces Flask's development server for production execution.

### Logging

- Detailed logs do not record tokens, API keys or authorization headers.
- Log files rotate, are size-limited and excluded from Git and the Docker image.
- Detailed mode can contain filenames, models, endpoints and technical information; restrict access to `logs/`.

### Deployment recommendations

1. Use an HTTPS reverse proxy in front of Waitress.
2. Define unique strong values for `SECRET_KEY`, `ADMIN_PASSWORD_HASH` and `SETTINGS_ENCRYPTION_KEY`.
3. Enable `SESSION_COOKIE_SECURE=true` when HTTPS is operational.
4. Back up `data/settings.json`, `data/admin_auth.json` and the encryption key separately.
5. Restrict `data/` and `logs/` permissions to the application account.
6. Keep TLS verification enabled and rotate BookStack tokens and AI keys regularly.
7. Never publish `.env`, `data/`, `logs/` or a Docker image built without the appropriate `.dockerignore` protections.

## 🔍 Search keywords

StackBridge may also be useful if you are searching for:

`BookStack importer` · `BookStack document importer` · `BookStack DOCX import` · `Word to BookStack` · `DOCX to BookStack` · `PDF to BookStack` · `BookStack PDF importer` · `BookStack OCR` · `BookStack migration tool` · `self-hosted document importer` · `Docker BookStack importer`

## 🤝 Contributing

Issues, bug reports, documentation improvements and contributions are welcome. If you find StackBridge useful, starring the repository helps other BookStack users discover the project.

## 📜 License

StackBridge is released under the **MIT License**. See `LICENSE` for details.

## Notes

The preview cache is stored in memory and disappears after restart. PDF vector drawings are detected but are not separately rasterized, avoiding conversion of borders and tables into images.
