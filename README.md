# Jharkhand Societal Innovation Collaboration Portal

A local Python portal that connects community challenges with government moderation, universities, student teams, and industry support. It currently provides:

- Citizen issue reporting on a Leaflet/OpenStreetMap map
- Jharkhand districts, blocks, and societal domains
- MySQL persistence for issues, users, proof images, proposals, assignments, teams, universities, and industry offers
- AI-assisted duplicate detection and image GPS verification
- Administrator moderation and university assignment
- University dashboards for decisions, teams, and proposals
- Industry dashboards for support offers

This is currently a local Python demo using Python's standard-library HTTP server. Login sessions are kept in memory and are lost when the server stops. Existing records in `accounts.csv` are imported into MySQL on startup.

## Quick Start

From the repository root, create a MySQL database and application user:

```powershell
mysql -u root -p
CREATE DATABASE civic_map;
CREATE USER 'civic_app'@'localhost' IDENTIFIED BY 'change-this-password';
GRANT ALL PRIVILEGES ON civic_map.* TO 'civic_app'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Set the connection variables in PowerShell:

```powershell
$env:CIVIC_MAP_DB_USER = "civic_app"
$env:CIVIC_MAP_DB_PASSWORD = "change-this-password"
$env:CIVIC_MAP_DB_NAME = "civic_map"
python -m pip install -r requirements.txt
python map.py
```

The default local configuration connects to database `sih26` as MySQL user `root`. The environment variables above are recommended for a separate application user. `storage.py` creates the selected database tables and applies compatible schema migrations automatically.

Open:

```text
http://127.0.0.1:8000
```

The application opens the browser automatically after starting. If it does not, open the URL manually.

### Demo accounts

```text
Email: citizen@example.com
Password: map123
```

Verified professional:

```text
Email: engineer@example.gov
Password: gov12345
```

Administrator access is allowlisted for `admin@jharkhand.gov.in`. Register that email with a password of at least 8 characters before using `/admin`.

University and industry profiles use their MySQL contact email as the account identity. Register one of these emails before logging in:

```text
innovation@bitmesra.ac.in
innovation@cuj.ac.in
innovation@nitjsr.ac.in
partner@jin.example
connect@alf.example
innovation@etm.example
```

For real use, create a new account instead of using the demo credentials.

## How to Operate the Application

1. Start the server with `python map.py`.
2. Sign in or create an account.
3. Click the map to place a report pin. The pin can be dragged to adjust its position.
4. Select a Jharkhand district, enter a block or city, and enter a title, domain, and description.
5. Optionally select a JPEG, PNG, or WebP image as proof.
6. Submit the report.
7. Open the Community page to browse nearby issues and support existing reports.
8. Use the `Propose` link on the Community page to choose one of the top-voted problems and submit a solution title, description, and optional visual.
9. Stop the server with `Ctrl+C`.

Verified professionals can open `/professionals` after signing in. The local demo account is marked as a verified government professional.

The administrator can open `/admin` to review pending issues. Register or import the account `admin@jharkhand.gov.in` to use the local administrator allowlist, then approve, reject, or archive reports with a reason.

University accounts linked to a university profile's contact email can open `/university-dashboard` to view assigned challenges, accept or reject them with a reason, create a faculty-led student team, and submit a solution proposal.

Administrators can register and edit university profiles at `/universities`, including institution name, district, domains, departments, laboratories, incubation facilities, and contact email.

Industry accounts linked to an industry partner profile's contact email can open `/industry-dashboard` to browse approved challenges and offer mentorship, funding, prototyping, testing, or deployment support.

University teams can update their project stage through `Team Formed`, `Prototype`, `Pilot`, `Deployed`, and `Impact Measured`, and add milestones with due dates and deliverables from `/university-dashboard`.

## Solution Proposals

The Community page links to `/proposals`. This page ranks the existing `ISSUES` collection by supporter count and presents the highest-supported problems as proposal targets. Signed-in users can submit a proposal with:

- A selected civic issue
- A title
- A description
- An optional JPEG, PNG, or WebP visual up to 8 MB

Proposal records, optional visuals, votes, and professional reviews are persisted in the MySQL `proposals` table. Visuals are stored as `LONGBLOB` values and served through stable proposal-visual URLs after restart.

Issue support is tracked per authenticated user in the MySQL `issue_supporters` table, so each user can support an issue only once. Existing demonstration supporter totals are displayed, but only recorded user supports can establish voting eligibility.

Solution voting is now enabled on `/community` and `/proposals`. A user must have supported the related issue before voting. Each eligible user has one active solution choice per issue; proposal vote totals are persisted in MySQL, while the per-user eligibility map remains in memory for this prototype.

Public status labels make the workflow transparent: ranked problems show `Awaiting Consideration`, the leading problem shows `Awaiting Solution`, new user proposals show `Awaiting Approval`, approved proposals show `Solution Approved`, non-feasible proposals show `Marked Non-Feasible`, and proposals needing changes show `Revision Requested`.

## Professional Portal

`/professionals` is restricted by the explicit `VERIFIED_PROFESSIONALS` registry in `login_users.py`; ordinary users receive a forbidden response. Verified users see proposals ranked by solution votes in batches of ten and can submit one of these decisions with an explanation:

- Under review
- Approved
- Non-feasible
- Needs revision

Reviews are persisted with proposals and display the reviewer name, decision, and explanation. The professional registry is still a local allowlist and should be replaced with administrator-approved role records in production.

## Image Proof

The report form accepts images up to 8 MB.

When Pillow is installed, `AI_model.py` reads EXIF GPS metadata from the image and compares it with the selected map pin. Accepted proof images are stored as MySQL `LONGBLOB` values and remain available after a server restart:

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

## Anti-Spam Protection

`spam.py` provides prototype protections at the API boundary:

- Per-user and per-IP rate limits for issue reports, solution proposals, issue support, solution votes, and professional reviews
- Rejection of repeated submissions within a short period
- Minimum title and description lengths
- Control-character and excessive-link checks
- Repeated-filler-text detection
- Existing one-vote-per-user rules for issue support and solution voting

For production, move the guard state to Redis or the database, add CAPTCHA or device-risk checks for suspicious traffic, moderate comments and uploaded media, scan images for malware, and keep an audit log for moderation actions. Rate limiting is also needed on login, registration, password reset, comments, notifications, and professional verification requests.

## Project Files

```text
SIH26043/
  AI_model.py       Duplicate detection and EXIF GPS verification
  community.py      Shared issues, matching integration, community page, upvotes
  login_users.py    CSV-backed accounts and password hashing
  map.py            HTTP server, map page, API routes, image proof serving
  storage.py        MySQL connection, schema initialization, and persistence operations
  accounts.csv      Legacy account source, imported into MySQL if present
  .env.example      MySQL configuration template
  README.md         This guide
```

`accounts.csv` contains password hashes and salts, not plain-text passwords. Do not commit it to a public repository.

## Available Routes

| Route | Access | Purpose |
|---|---|---|
| `/` | Signed-in users | Jharkhand issue map and report form |
| `/community` | Signed-in users | Browse, filter, and support issues |
| `/my-issues` | Signed-in users | Track reports submitted by the current citizen |
| `/proposals` | Signed-in users | Submit and vote on solution proposals |
| `/professionals` | Verified professionals | Review proposals |
| `/admin` | Administrator | Moderate pending issues |
| `/universities` | Administrator | Edit university profiles and assign issues |
| `/university-dashboard` | Linked university account | Review assignments, create teams, and submit proposals |
| `/industry-dashboard` | Linked industry account | Browse approved challenges and submit support offers |
| `/government-dashboard` | Administrator | View issue, institution, partner, and project analytics |
| `/notifications` | Signed-in users | View persistent in-app notifications |
| `/messages` | Signed-in users | Send and receive project messages |

## MySQL Tables

`storage.py` initializes and migrates these tables in the configured database:

- `issues`: challenges, locations, moderation, and proof image blobs
- `issue_supporters`: authenticated issue support records
- `accounts`: password hashes, salts, and email identities
- `proposals`: solutions, visuals, votes, and professional reviews
- `universities`: institutions and their expertise/capabilities
- `issue_assignments`: issue-to-university routing and university responses
- `project_teams`: faculty-led teams linked to assigned issues
- `team_members`: student membership records
- `industry_partners`: startup, MSME, and CSR partner profiles
- `support_offers`: partner support for approved challenges
- `support_offers` also records commitment status and notes for admin follow-up.
- `milestones`: project milestones, due dates, and deliverable notes
- `project_status_history`: timestamped project stage audit entries
- `notifications`: persistent workflow notifications
- `messages`: persistent role-based project communication

## Useful Checks

Run the Python syntax check from the repository root:

```powershell
python -m py_compile AI_model.py community.py login_users.py map.py storage.py
```

Check that the required packages are available:

```powershell
python -c "import PIL, sentence_transformers, mysql.connector; print('Dependencies available')"
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

## Remaining Work for a Real Deployment

The current demo still needs persistent workflow, communication, and production security features. Recommended additions are:

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

Current product roadmap:

- Add project lifecycle statuses, milestones, deliverables, testing, pilots, and impact measurement.
- Add persistent notifications and role-based communication.
- Add university registration, faculty/student role records, and partner approval workflows.
- Add government analytics dashboards for district, domain, institution, partner, progress, and impact data.
- Move sessions and rate limits to persistent secure infrastructure.

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
