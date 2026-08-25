# Civic Map and AI Issue Deduplication

A small civic-issue reporting application with:

- A Leaflet/OpenStreetMap map for selecting issue locations
- Local account creation and login
- Community browsing and issue support/upvotes
- Semantic duplicate detection for differently worded reports
- Category-aware geographic matching
- Optional image proof with EXIF GPS verification

This is currently a local Python demo. Issues, sessions, and uploaded proof images are kept in memory and are lost when the server stops. Accounts are stored in `accounts.csv`.

## Quick Start

From the repository root:

```powershell
cd SIH26043
python -m pip install Pillow sentence-transformers
python map.py
```

Open:

```text
http://127.0.0.1:8000
```

The application opens the browser automatically after starting. If it does not, open the URL manually.

### Demo account

```text
Email: citizen@example.com
Password: map123
```

For real use, create a new account instead of using the demo credentials.

## How to Operate the Application

1. Start the server with `python map.py`.
2. Sign in or create an account.
3. Click the map to place a report pin. The pin can be dragged to adjust its position.
4. Enter a title, category, and description.
5. Optionally select a JPEG, PNG, or WebP image as proof.
6. Submit the report.
7. Open the Community page to browse nearby issues and support existing reports.
8. Stop the server with `Ctrl+C`.

## Image Proof

The report form accepts images up to 8 MB.

When Pillow is installed, `AI_model.py` reads EXIF GPS metadata from the image and compares it with the selected map pin:

- GPS within 100 metres: proof is marked as location verified.
- GPS more than 100 metres away: the report is rejected.
- No GPS metadata: the image is accepted as photo proof, but marked location unverified.
- Invalid or unreadable image metadata: the proof is marked location unverified.

Many messaging and social-media applications remove EXIF metadata. Use the original camera file when location verification is required. GPS metadata is evidence, not an absolute guarantee that the image was taken at the reported location.

## Duplicate Detection

`AI_model.py` uses a two-stage design:

1. Candidate filtering by category and distance.
2. Text similarity using `intfloat/multilingual-e5-small` through `sentence-transformers`.

If the embedding library or model cannot be loaded, a token-overlap fallback keeps the application usable.

The matcher returns:

- `new`: create a new issue.
- `duplicate`: merge into the existing issue and increase its supporter count.
- `possible_duplicate`: do not create an issue automatically; ask the reporter to support the existing issue.

The distance radius varies by category. For example, roads use a tighter radius while water outages use a wider radius because one outage can affect a neighbourhood.

## Project Files

```text
SIH26043/
  AI_model.py       Duplicate detection and EXIF GPS verification
  community.py      Shared issues, matching integration, community page, upvotes
  login_users.py    CSV-backed accounts and password hashing
  map.py            HTTP server, map page, API routes, image proof serving
  accounts.csv      Local account data, created automatically if absent
  README.md         This guide
```

`accounts.csv` contains password hashes and salts, not plain-text passwords. Do not commit it to a public repository.

## Useful Checks

Run the Python syntax check from the repository root:

```powershell
python -m py_compile SIH26043\AI_model.py SIH26043\community.py SIH26043\map.py
```

Check that the required packages are available:

```powershell
python -c "import PIL, sentence_transformers; print('Dependencies available')"
```

If the embedding model has not been downloaded before, the first duplicate check downloads the model from Hugging Face and may take several minutes. Later runs use the local cache.

## Troubleshooting

### The map is blank

- Confirm the server is running.
- Refresh with `Ctrl+F5`.
- Check the browser developer console for JavaScript errors.
- Ensure the computer has internet access because Leaflet and OpenStreetMap tiles are loaded from external URLs.

### The server says the port is already in use

Stop the previous `python map.py` process, or change `PORT` in `map.py` to another unused port.

### Duplicate detection is slow on the first report

This is normally the one-time embedding model download and load. Install `sentence-transformers` before starting the server and allow the model to finish downloading.

### A geotagged image is shown as unverified

Check that the original image still contains EXIF GPS metadata. Screenshots, edited images, and images downloaded from many services commonly have their metadata removed.

## Recommended Next Files for a Real Deployment

The demo does not yet persist civic issues or proof files. The following files and services should be added before production:

```text
SIH26043/
  requirements.txt       Pinned Python dependencies
  .env.example            Configuration names, never real secrets
  .gitignore              accounts.csv, uploads, caches, and secrets
  storage.py              Database and image-storage access
  schema.sql              Users, issues, reports, proof, and support tables
  tests/
    test_deduplication.py Text and distance matching cases
    test_proof.py         EXIF, missing GPS, mismatch, and size cases
    test_api.py           Login, report, merge, and error responses
```

Recommended production components:

- PostgreSQL with PostGIS for persistent issues and radius queries
- Object storage such as S3-compatible storage for proof images
- A background worker for embedding generation and image processing
- A proper web framework such as FastAPI or Django
- HTTPS, secure persistent sessions, CSRF protection, and rate limiting
- Image MIME validation, re-encoding, malware scanning, and EXIF privacy rules
- Human review tools for borderline duplicate decisions

## Suggested `requirements.txt`

For the current demo, create `requirements.txt` with:

```text
Pillow>=10.0
sentence-transformers>=3.0
```

Install it with:

```powershell
python -m pip install -r requirements.txt
```

Pin exact versions after testing on the deployment machine. The embedding model itself is downloaded separately by `sentence-transformers`; it is not included in this repository.

## Data and Privacy Notes

- Uploaded proof images may contain faces, vehicle plates, or private location metadata.
- Obtain the required consent before publishing images.
- Decide whether to retain or strip EXIF metadata after verification.
- Do not treat automatic duplicate detection as a final moderation decision.
- Use a persistent database and authenticated user IDs before relying on supporter counts.
