# Civic Project End-to-End Workflow

## From Citizen Report to Final Contractor Implementation

### 1. Citizen Registration and Login

The citizen creates an account with an email address and password. The password is securely hashed before storage. After login, the system creates a session so the citizen can submit reports and track progress.

**Entity:** Citizen  
**Database tables:** `accounts`, `sessions`

### 2. Reporting a Civic Problem

The citizen submits:

- Issue title
- Category
- Description
- District and block
- Map location
- Photo, video, or document evidence

The report is saved in the `issues` table with a pending moderation status.

**Entity:** Citizen  
**Database table:** `issues`

### 3. Evidence and GPS Verification

For an uploaded image, the system reads EXIF GPS metadata and compares it with the map location selected by the citizen.

- Within 100 meters: the image is marked `verified`.
- More than 100 meters away: the report is rejected as a GPS mismatch and the image is not stored.
- No GPS metadata: the image is stored as `unverified`.
- Invalid or unreadable metadata: the image is marked `unverified`.

Image bytes and metadata are stored with the issue in the database.

**Entities:** Citizen and AI verification system  
**Database table:** `issues`

### 4. AI Classification and Duplicate Detection

The AI analyzes the title, description, selected category, location, and available image or video evidence. It can:

- Predict the problem category
- Generate issue tags
- Estimate classification confidence
- Detect duplicate reports
- Identify possible duplicates for review
- Add support to an existing confirmed duplicate

**Entity:** AI system  
**Database fields:** AI category, tags, confidence, video classification, and matching information

### 5. Government or Admin Moderation

The government administrator reviews the report and evidence. The administrator can:

- Approve the issue
- Reject the issue
- Archive the issue
- Add a reason
- Notify the citizen of the decision

The decision is recorded with the moderation status, reason, and moderator identity.

**Entity:** Government administrator  
**Database table:** `issues`

### 6. AI University Matching

For a new issue, the AI compares the problem with every active university profile. The score considers:

- Problem category
- Issue title and description
- University domains
- Registered expertise
- Departments
- Laboratories
- Incubation facilities
- District and location

The university with the strongest valid match is selected. The assignment is stored in `issue_assignments`, and the university receives a notification.

**Entities:** AI system and university  
**Database tables:** `universities`, `issue_assignments`, `notifications`

### 7. University Reviews the Assignment

The university logs in and reviews the assigned challenge, including its description, location, category, evidence, and GPS verification status.

The university can respond with:

- `Accepted`
- `Rejected`
- `Needs clarification`

The response and explanation are saved with the assignment.

**Entity:** University  
**Database table:** `issue_assignments`

### 8. University Defines the Project

After accepting the assignment, the university converts the challenge into a structured project. It defines:

- Project title
- Problem statement
- Objectives
- Proposed approach
- Required resources
- Faculty mentor
- Student team
- Timeline
- Success measurements

The project is stored as a project team record.

**Entity:** University  
**Database table:** `project_teams`

### 9. University Creates a Project Team

The university assigns a faculty mentor and student members. Team members can be given responsibilities such as:

- Field survey
- Data collection
- Hardware design
- Software development
- GIS mapping
- Testing
- Documentation
- Community coordination

**Database table:** `team_members`

### 10. University Creates Milestones

The university divides the project into measurable stages:

1. Problem validation
2. Field survey
3. Requirement analysis
4. Concept design
5. Prototype development
6. Laboratory testing
7. Field pilot
8. Performance evaluation
9. Final documentation
10. Deployment handover

Each milestone can contain a due date, status, deliverable, testing result, and completion date.

**Database table:** `milestones`

### 11. University Research and Field Validation

The university validates the real-world problem by visiting the location, interviewing affected citizens, measuring the problem, checking available records, and identifying technical constraints.

This ensures that the solution addresses the real civic need rather than only the original report description.

**Entity:** University

### 12. Industry Partner Participation

An industry partner can support an approved issue by providing:

- Funding
- Hardware
- Software tools
- Technical mentoring
- Manufacturing support
- Cloud infrastructure
- Testing equipment
- Prototyping facilities
- Deployment expertise
- Maintenance support

The industry partner submits a support offer containing the support type, details, funding, resources, and timeline.

**Entities:** Industry partner and university  
**Database tables:** `industry_partners`, `support_offers`

### 13. University and Industry Coordination

The university leads the research and technical direction. The industry partner contributes practical engineering and implementation capability.

#### University responsibilities

- Define technical requirements
- Lead research
- Design the solution
- Supervise students
- Test the prototype
- Validate performance
- Prepare reports
- Confirm deployment readiness

#### Industry responsibilities

- Provide promised resources
- Supply equipment or funding
- Improve scalability and reliability
- Give engineering advice
- Help estimate deployment cost
- Support manufacturing or integration
- Assist with implementation planning

The industry partner supports the university but does not replace its academic responsibility.

### 14. Prototype Development

The university team develops the first working solution. Depending on the issue, this may include IoT sensors, mobile applications, web dashboards, GIS systems, water monitoring devices, road-condition detection systems, waste tracking tools, or energy monitoring equipment.

The industry partner may provide components, technical specifications, engineering support, test equipment, software licenses, and manufacturing guidance.

### 15. Testing and Pilot Deployment

The university first tests the prototype in controlled conditions. Testing may measure:

- Accuracy
- Reliability
- Response time
- Cost
- Durability
- Security
- Usability
- Environmental performance
- Maintenance requirements

After laboratory testing, the solution is piloted at the issue location.

### 16. University Progress Reports

The university submits reports containing:

- Work completed
- Current milestone
- Testing results
- Problems encountered
- Resources used
- Industry contribution
- Evidence and photographs
- Next steps
- Deployment recommendation

Reports are stored in `university_reports`, and the government administrator receives a notification.

### 17. Government Project Review

The government monitors:

- Whether the university accepted the issue
- Whether milestones are progressing
- Whether industry support was delivered
- Whether the prototype works
- Whether the project is delayed
- Whether the solution is suitable for public deployment

The government can request clarification and review project reports.

### 18. Final Solution Evaluation

Before implementation, the university provides a final recommendation covering:

- Technical feasibility
- Expected public benefit
- Total cost
- Required materials
- Deployment timeline
- Maintenance plan
- Risks
- Expected performance
- Scalability

The government uses this recommendation to decide whether to proceed.

### 19. Final Contractor Allocation

When the solution is ready for field implementation, the government administrator assigns a contractor. The contractor is selected using:

- Required specialization
- District coverage
- Approval status
- Performance score
- Completed projects
- Complaint history
- Implementation capacity

The assignment is saved in `contractor_assignments`, and the contractor receives a notification.

The university provides the contractor with:

- Technical design
- Specifications
- Prototype results
- Installation instructions
- Testing criteria
- Quality requirements
- Training or technical supervision

**Entities:** Government, university, and contractor  
**Database tables:** `contractors`, `contractor_assignments`, `notifications`

### 20. Contractor Executes the Work

The contractor:

1. Reviews the assigned issue.
2. Studies the university design.
3. Procures or receives materials.
4. Performs field work.
5. Marks the assignment `In Progress`.
6. Uploads progress images.
7. Adds completion notes.
8. Marks the assignment `Completed`.

Progress information is stored in `contractor_assignments`.

### 21. University Supports Implementation

During contractor execution, the university may:

- Clarify technical requirements
- Inspect installation quality
- Test the deployed system
- Compare field performance with the prototype
- Train government or local staff
- Recommend corrections
- Confirm acceptance criteria

The university is the technical knowledge partner. The contractor is the field implementation partner.

### 22. Government Closes the Project

The government reviews contractor evidence, university validation, citizen feedback, final reports, cost, timeline, and performance results.

If the work is acceptable, the government closes the project. If the work is incomplete or defective, the government can request corrections or review contractor performance.

## Responsibilities by Entity

| Entity | Responsibility |
|---|---|
| Citizen | Registers, reports problems, uploads evidence, and supports reports |
| AI system | Verifies GPS, classifies problems, detects duplicates, and matches universities |
| Government/admin | Moderates reports, oversees projects, approves partners, and assigns contractors |
| University | Researches the problem, develops solutions, manages teams, and submits reports |
| Industry partner | Provides funding, equipment, expertise, and implementation support |
| Contractor | Executes field work and submits completion evidence |

## Final Responsibility Distinction

The AI recommends and assigns the best university for research and solution development based on the university's registered expertise.

The government administrator retains oversight and assigns the final contractor for implementation.

The university develops and validates the solution. The industry partner helps make the solution practical and scalable. The contractor performs the physical implementation. The government accepts and closes the project.
  