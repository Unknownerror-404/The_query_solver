# Societal Innovation Collaboration Portal Tasks

## Completed

- [x] Citizen login and registration
- [x] Citizen issue reporting with map location
- [x] Issue categories and community browsing
- [x] Image proof upload with EXIF GPS verification
- [x] Add video and supporting-document uploads
- [x] Store issue records in MySQL
- [x] Store issue proof images in MySQL
- [x] Store accounts and issue supporters in MySQL
- [x] AI-assisted duplicate issue detection
- [x] Add automatic issue category prediction
- [x] Add AI-assisted priority/severity scoring and matching explanations
- [x] Fix industry dashboard assignment data-shape crash
- [x] Community issue upvotes
- [x] Basic solution proposal submission
- [x] Basic professional review portal

## Phase 1: Jharkhand Foundation

- [x] Add Jharkhand districts and blocks
- [x] Add required domains: education, healthcare, agriculture, water, sanitation, environment, energy, accessibility, urban infrastructure, public administration, and rural livelihoods
- [x] Add district and block fields to issue reports
- [x] Replace Bengaluru sample locations with Jharkhand locations
- [x] Add issue moderation status: pending, approved, rejected, and archived
- [x] Add administrator role and protected admin routes

## Phase 2: Persistent Collaboration Data

- [x] Create MySQL tables for universities and departments
- [x] Create MySQL tables for faculty, students, teams, and industry partners
- [x] Persist solution proposals in MySQL
- [x] Persist proposal visuals in MySQL or object storage
- [x] Persist proposal votes and professional reviews
- [x] Persist issue assignments and project ownership
- [x] Persist project teams and student memberships
- [x] Persist notifications and communication records

## Phase 3: University Collaboration

- [x] Build university registration and profile management
- [x] Add university expertise, departments, laboratories, and incubation facilities
- [x] Match issues to universities by domain and expertise
- [x] Allow universities to accept or reject assigned issues
- [x] Allow faculty to create multidisciplinary student teams
- [x] Allow teams to submit solution proposals
- [x] Add faculty mentor assignment

## Phase 4: Industry Partnership

- [x] Build industry, startup, MSME, and CSR partner profiles
- [x] Add a separate polished industry registration and login flow
- [x] Allow partners to browse approved challenges
- [x] Add offers for mentorship, funding, prototyping, testing, and deployment
- [x] Allow universities to request industry support
- [x] Track partner commitments and participation

## Phase 5: Project Lifecycle

- [x] Add workflow statuses: submitted, validated, assigned, team formed, prototype, pilot, deployed, and impact measured
- [x] Add project milestones and due dates
- [x] Add deliverable uploads and review records
- [x] Add testing and pilot results
- [x] Add intellectual property and startup outcome fields
- [x] Add project status history and audit log

## Phase 6: Dashboards and Communication

- [x] Build citizen issue tracking page
- [x] Build university project dashboard
- [x] Build industry partnership dashboard
- [x] Build government administrator dashboard
- [x] Show district-wise and domain-wise issue analytics
- [x] Show university participation and industry engagement
- [x] Show project completion and measurable community impact
- [x] Add visual charts for district/domain distribution and project progress
- [ ] Add visual charts for university participation, industry support, completed projects, and impact outcomes
- [x] Add email or in-app notifications
- [x] Add role-based project communication

## Phase 7: Production Hardening

- [x] Move sessions to persistent secure session storage
- [ ] Add CSRF protection and HTTPS deployment
- [x] Validate and re-encode uploaded images
- [ ] Add malware scanning and complete EXIF privacy handling
- [ ] Move rate limits to Redis or MySQL for persistent enforcement
- [ ] Add secure database-backed role permissions
- [ ] Add password reset and account recovery
- [ ] Add persistent CAPTCHA/rate-limit protection
- [x] Replace the basic HTTP server with FastAPI or Django
- [x] Add database backups and deployment configuration

## Phase 8: SIH Final Improvements

- [ ] Add responsive PWA or a dedicated mobile client
- [x] Add admin approval workflow for university registrations
- [ ] Add admin approval workflow for professionals and industry partners
- [x] Add proposal moderation to the admin interface
- [ ] Add tests for university registration and approval
- [ ] Add tests for expertise matching and nearest-location fallback
- [ ] Add tests for proposal submission and industry offer flow
- [ ] Add tests for admin moderation and assignment workflows

## Project Status

The project is a functional demo with citizen reporting, moderation, university collaboration,
industry support, project tracking, MySQL persistence, and FastAPI integration implemented.
The remaining work is focused on multimedia support, stronger AI assistance, verified onboarding,
dashboard visualization, production security, broader testing, mobile delivery, and fixing the
industry dashboard data-shape bug listed above.
