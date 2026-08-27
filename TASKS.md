# Societal Innovation Collaboration Portal Tasks

## Completed

- [x] Citizen login and registration
- [x] Citizen issue reporting with map location
- [x] Issue categories and community browsing
- [x] Image proof upload with EXIF GPS verification
- [x] Store issue records in MySQL
- [x] Store issue proof images in MySQL
- [x] Store accounts and issue supporters in MySQL
- [x] AI-assisted duplicate issue detection
- [x] Community issue upvotes
- [x] Basic solution proposal submission
- [x] Basic professional review portal

## Phase 1: Jharkhand Foundation

- [x] Add Jharkhand districts and blocks
- [x] Add required domains: education, healthcare, agriculture, water, sanitation, environment, energy, accessibility, urban infrastructure, public administration, and rural livelihoods
- [x] Add district and block fields to issue reports
- [ ] Replace Bengaluru sample locations with Jharkhand locations
- [x] Add issue moderation status: pending, approved, rejected, and archived
- [x] Add administrator role and protected admin routes

## Phase 2: Persistent Collaboration Data

- [x] Create MySQL tables for universities and departments
- [ ] Create MySQL tables for faculty, students, teams, and industry partners
- [x] Persist solution proposals in MySQL
- [x] Persist proposal visuals in MySQL or object storage
- [x] Persist proposal votes and professional reviews
- [x] Persist issue assignments and project ownership
- [ ] Persist notifications and communication records

## Phase 3: University Collaboration

- [ ] Build university registration and profile management
- [ ] Add university expertise, departments, laboratories, and incubation facilities
- [ ] Match issues to universities by domain and expertise
- [ ] Allow universities to accept or reject assigned issues
- [ ] Allow faculty to create multidisciplinary student teams
- [ ] Allow teams to submit solution proposals
- [ ] Add faculty mentor assignment

## Phase 4: Industry Partnership

- [ ] Build industry, startup, MSME, and CSR partner profiles
- [ ] Allow partners to browse approved challenges
- [ ] Add offers for mentorship, funding, prototyping, testing, and deployment
- [ ] Allow universities to request industry support
- [ ] Track partner commitments and participation

## Phase 5: Project Lifecycle

- [ ] Add workflow statuses: submitted, validated, assigned, team formed, prototype, pilot, deployed, and impact measured
- [ ] Add project milestones and due dates
- [ ] Add deliverable uploads and review records
- [ ] Add testing and pilot results
- [ ] Add intellectual property and startup outcome fields
- [ ] Add project status history and audit log

## Phase 6: Dashboards and Communication

- [ ] Build citizen issue tracking page
- [ ] Build university project dashboard
- [ ] Build industry partnership dashboard
- [ ] Build government administrator dashboard
- [ ] Show district-wise and domain-wise issue analytics
- [ ] Show university participation and industry engagement
- [ ] Show project completion and measurable community impact
- [ ] Add email or in-app notifications
- [ ] Add role-based project communication

## Phase 7: Production Hardening

- [ ] Move sessions to persistent secure session storage
- [ ] Add CSRF protection and HTTPS deployment
- [ ] Validate and re-encode uploaded images
- [ ] Add malware scanning and EXIF privacy handling
- [ ] Move rate limits to Redis or MySQL
- [ ] Add automated tests for storage, proof uploads, deduplication, and APIs
- [ ] Replace the basic HTTP server with FastAPI or Django
- [ ] Add database backups and deployment configuration

## Recommended Next Task

Start with Phase 1: add Jharkhand districts, domains, moderation status, and administrator access. Then implement persistent proposals and university records before building the dashboards.
