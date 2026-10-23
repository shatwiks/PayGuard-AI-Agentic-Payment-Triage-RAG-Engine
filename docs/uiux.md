# PayGuard AI
## End-to-End UI/UX Specification

**Product:** PayGuard AI  
**Category:** AI-Powered Payment Investigation and Triage Platform  
**Document Type:** UI/UX Product Specification  
**Version:** 1.0  
**Status:** Design Specification for MVP

---

# 1. Product Overview

## 1.1 What Is PayGuard AI?

PayGuard AI is an AI-powered payment operations platform that helps payment support engineers investigate transaction issues, understand payment failures, retrieve relevant troubleshooting documentation, and generate evidence-based recommendations.

The application combines transaction data, deterministic payment triage, Retrieval-Augmented Generation (RAG), and an LLM-powered investigation workflow into a single interface.

The product must make complex payment investigations easier to understand without hiding the evidence behind AI-generated explanations.

## 1.2 Primary Objective

The primary objective of the UI is to help an authorized user investigate a payment issue from beginning to end through a clear, efficient, and trustworthy workflow.

A user should be able to:

1. Find a payment or enter a payment ID.
2. Describe the issue.
3. Start an investigation.
4. Understand the payment's current recorded status.
5. Review transaction history and supporting evidence.
6. See the troubleshooting documents retrieved by the RAG system.
7. Understand the AI-generated explanation.
8. Review recommended next steps.
9. Save and revisit the investigation.

## 1.3 Design Philosophy

PayGuard AI should feel like a serious internal fintech operations tool.

The interface must prioritize:

- Clarity over decoration.
- Evidence over unsupported AI claims.
- Information hierarchy over visual complexity.
- Speed over unnecessary interactions.
- Consistency over experimental layouts.
- Accessibility over purely aesthetic choices.
- Trust and transparency over exaggerated AI branding.

Avoid generic AI dashboard aesthetics, excessive gradients, unnecessary glassmorphism, decorative animations, fake statistics, fake customer testimonials, and visual elements that do not improve usability.

---

# 2. Target Users

## 2.1 Primary User: Payment Operations Engineer

Responsible for investigating delayed, failed, pending, reversed, or otherwise problematic transactions.

Needs:
- Quick access to payment records.
- Clear transaction timelines.
- Relevant troubleshooting instructions.
- Reliable investigation summaries.
- Evidence supporting every important conclusion.

## 2.2 Secondary User: Customer Support Engineer

Responsible for understanding customer-reported payment issues.

Needs:
- Simple payment search.
- Plain-English explanations.
- Clear recommended next steps.
- Easy access to previous investigations.

## 2.3 Administrative User

Responsible for managing application access and reviewing system activity.

Needs:
- User and role management.
- Audit history.
- System health information.
- Visibility into investigation failures and operational issues.

For the initial MVP, administrative functionality can remain limited to essential access controls and audit visibility.

---

# 3. Information Architecture

The application should use a persistent sidebar for navigation and a top header for global controls.

## 3.1 Primary Navigation

The sidebar should contain:

1. Overview
2. Investigations
3. Payments
4. Knowledge Base
5. Activity Logs
6. Settings

### Overview

Displays operational summaries, recent investigations, and quick actions.

### Investigations

Displays investigation history, search, filters, and investigation details.

### Payments

Allows users to search and inspect payment records.

### Knowledge Base

Allows users to browse available troubleshooting documents and inspect document metadata.

Document ingestion and management should be available only to authorized users.

### Activity Logs

Displays relevant audit events and investigation activity according to the user's permissions.

### Settings

Contains user profile, account preferences, and any administrative configuration available to the current user.

## 3.2 Global Header

The header should contain:

- Current page title or breadcrumb.
- Global search entry point.
- System status indicator.
- Notification area, if notifications are implemented.
- User avatar or initials.
- Account menu.

Do not display controls that are not functional.

## 3.3 Navigation Behavior

- The active navigation item must be visually distinguishable.
- The sidebar should support a compact mode if practical.
- On smaller screens, navigation should collapse into a drawer.
- Page navigation must preserve investigation context where appropriate.
- Direct navigation to a saved investigation should work through its URL.
- Unauthorized users must not see or access restricted functionality.

---

# 4. Visual Design System

## 4.1 Overall Style

Use a clean, restrained fintech operations aesthetic.

The interface should feel closer to a professional payment operations console than a consumer banking application.

Use:
- A light neutral application background.
- White or near-white content surfaces.
- Dark, high-contrast text.
- A restrained blue accent for primary actions.
- Green for confirmed successful states.
- Amber for pending or caution states.
- Red for failures and critical errors.
- Gray for neutral and unavailable states.

Colors must never be the only way to communicate status.

## 4.2 Color Tokens

Use the following initial color palette. These values are design defaults and may be adjusted after implementation and accessibility testing.

| Token | Color | Usage |
|---|---|---|
| Primary | `#2563EB` | Primary buttons, links, active controls |
| Primary Hover | `#1D4ED8` | Hover state for primary actions |
| App Background | `#F8FAFC` | Main application background |
| Surface | `#FFFFFF` | Cards, dialogs, tables |
| Main Text | `#0F172A` | Headings and primary content |
| Secondary Text | `#475569` | Supporting descriptions |
| Muted Text | `#64748B` | Metadata and timestamps |
| Border | `#E2E8F0` | Dividers and card borders |
| Success | `#15803D` | Successful states |
| Success Background | `#F0FDF4` | Success indicators |
| Warning | `#B45309` | Pending and caution states |
| Warning Background | `#FFFBEB` | Warning indicators |
| Danger | `#B91C1C` | Failure and destructive actions |
| Danger Background | `#FEF2F2` | Error indicators |
| Neutral Background | `#F1F5F9` | Neutral badges and controls |

Verify text and control contrast against applicable accessibility requirements before finalizing the implementation.

## 4.3 Typography

Use Inter or another highly readable sans-serif font.

Recommended hierarchy:

- Page title: 28–32 px, semibold.
- Section heading: 18–22 px, semibold.
- Card title: 14–16 px, semibold.
- Body text: 14–16 px.
- Supporting text: 12–14 px.
- Table content: 13–14 px.
- Metadata: 12 px, provided it remains readable.

Use consistent line heights and avoid excessively small text.

## 4.4 Spacing

Use a consistent spacing scale:

- 4 px: Tight icon spacing.
- 8 px: Compact component spacing.
- 12 px: Small internal spacing.
- 16 px: Standard component spacing.
- 24 px: Card and section spacing.
- 32 px: Major section separation.
- 40–48 px: Page-level separation where needed.

## 4.5 Component Styling

### Cards
- White background.
- Thin neutral border.
- Subtle shadow only when it improves separation.
- Consistent padding.
- Small to moderate corner radius.

### Buttons
- Primary buttons use the primary blue.
- Secondary buttons use neutral backgrounds or outlined styling.
- Destructive buttons use red only when an actual destructive operation exists.
- Disabled buttons must look disabled and expose the disabled state to assistive technology.

### Tables
- Clear column headings.
- Consistent row heights.
- Subtle row separators.
- Readable status badges.
- Proper alignment for dates, amounts, and identifiers.

### Status Badges
Every status badge should include text, not just a colored dot.

Examples:
- `SUCCESS`
- `PENDING`
- `FAILED`
- `REVERSED`
- `UNKNOWN`

The exact status vocabulary must match the backend's validated status model.

## 4.6 Iconography

Use one consistent icon library, such as Lucide.

Icons should be familiar and functional.

Avoid emoji as interface icons.

Decorative icons should not compete with the information they accompany.

---

# 5. Authentication

## 5.1 Login Page

Route: `/login`

### Purpose

Provide a secure entry point for authorized users.

### Layout

Use a centered login panel with:

- PayGuard AI logo or wordmark.
- Product name.
- Short description.
- Email field.
- Password field.
- Show/hide password control.
- Sign-in button.
- Error message area.

Optional supporting copy:

"Investigate payment issues with evidence-backed insights."

Do not add social login buttons unless those authentication providers are implemented.

### Input Fields

**Email**
- Required.
- Must follow valid email syntax.
- Trim leading and trailing whitespace.
- Display a clear validation message when invalid.

**Password**
- Required.
- Use password input masking by default.
- Allow users to reveal the password temporarily.
- Do not expose password values in logs or error messages.

### Interactions

When the user submits the form:

1. Validate required fields.
2. Disable repeated submission while the request is in progress.
3. Display a loading state.
4. Send credentials to the backend.
5. On success, navigate to the overview page.
6. On failure, display a generic authentication error that does not reveal whether a particular account exists.

### States

- Initial.
- Field validation error.
- Submitting.
- Invalid credentials.
- Network error.
- Session expired.

### Security Requirements

- Authentication must be verified by the backend.
- Protected pages must not rely solely on frontend route checks.
- Session handling must follow the selected authentication architecture.
- Never store passwords in browser storage.
- Do not hardcode credentials in the frontend.

---

# 6. Overview Dashboard

Route: `/dashboard`

## 6.1 Purpose

Give users a quick view of recent investigation activity and provide immediate access to the main workflow.

## 6.2 Page Header

Title: `Overview`

Supporting text:

"Monitor payment investigations and review recent activity."

Primary action:

`+ New Investigation`

Secondary action:

`View All Investigations`

## 6.3 Summary Cards

Display a row of summary cards.

### Card 1: Total Investigations

Displays the number of investigations recorded in the selected period or scope.

### Card 2: Open Investigations

Displays the number of investigations that remain unresolved according to the application's defined workflow.

### Card 3: Completed Investigations

Displays the number of investigations successfully completed.

### Card 4: Failed Investigations

Displays the number of investigations that could not be completed because of an application, data, or processing failure.

These values must come from real backend data.

Do not invent numbers for an empty database.

If the MVP does not implement investigation lifecycle statuses, show only metrics that can be calculated accurately.

## 6.4 Recent Investigations

Display a table containing:

- Investigation ID.
- Payment ID.
- Issue category.
- Payment status.
- Investigation status.
- Created time.
- Action.

The action should open the corresponding investigation detail page.

Example structure:

| Investigation ID | Payment ID | Issue | Payment Status | Created | Action |
|---|---|---|---|---|---|
| INV-1001 | PAY-1001 | Delayed Payment | PENDING | Timestamp from backend | View |

The example is illustrative only. Do not seed production-facing statistics with invented activity.

## 6.5 Common Issue Categories

If sufficient real data exists, display a compact chart showing investigation counts by issue category.

Potential categories include:
- Delayed payment.
- Failed payment.
- Refund issue.
- Reversal issue.
- Unknown or other.

Do not render misleading charts when there is insufficient data.

## 6.6 Quick Actions

Include:
- Start an investigation.
- Search payments.
- View investigation history.

Only show actions supported by the current user's permissions.

## 6.7 Dashboard States

### Loading

Show skeleton cards and table rows.

### Empty

Display:

"No investigations yet."

Supporting text:

"Start your first investigation to review payment evidence and troubleshooting recommendations."

Action:

`New Investigation`

### Error

Display:

"Unable to load dashboard data."

Offer a retry action.

### Partial Data

Show the available data and clearly indicate which sections failed to load. Do not silently substitute fake values.

---

# 7. New Investigation Workflow

Route: `/investigations/new`

This is the primary user journey and should receive the greatest design attention.

## 7.1 Purpose

Allow a user to initiate a payment investigation with minimal effort while collecting enough information to produce a useful result.

## 7.2 Page Layout

Page title:

`New Investigation`

Supporting text:

"Provide the payment details and describe the issue you need to investigate."

Use a two-column layout on wide screens.

### Left Column: Investigation Form

Contains the input fields and submission controls.

### Right Column: Guidance Panel

Explains how the investigation works and what information will be analyzed.

The right column should remain visually secondary to the form.

On small screens, stack both columns vertically.

## 7.3 Payment ID

Label: `Payment ID`

Placeholder:

`Enter a payment ID`

Requirements:
- Required if the selected investigation mode is payment-specific.
- Trim whitespace.
- Validate length and allowed characters according to backend rules.
- Do not assume every payment identifier follows a particular prefix format.
- Provide a clear validation error for malformed input.

Optional interaction:

`Search Payment`

If this action is implemented, it should retrieve the payment through the backend and display a small confirmation panel.

The panel should show only fields the user is authorized to access.

## 7.4 Issue Description

Label: `Describe the issue`

Placeholder:

"Example: The customer reports that the payment was deducted, but the merchant has not confirmed receipt."

Requirements:
- Required for natural-language investigation.
- Support multiline input.
- Trim leading and trailing whitespace.
- Enforce a backend-defined maximum length.
- Display remaining characters if useful.
- Do not send the request until validation succeeds.

## 7.5 Optional Investigation Context

Provide an expandable section titled:

`Additional Context`

Possible fields:
- Customer-reported issue category.
- Approximate incident time.
- Additional reference information.

Do not collect unnecessary customer information.

Sensitive data such as full card numbers, CVVs, passwords, or banking credentials must not be requested.

## 7.6 Investigation Guidance Panel

Title:

`What happens next?`

Display these steps:

1. Retrieve authorized payment information.
2. Analyze the recorded transaction status and history.
3. Search relevant troubleshooting documentation.
4. Generate an evidence-based explanation.
5. Present recommended next steps.

Add a short note:

"Recommendations are based on the available transaction data and retrieved documentation. The system may report insufficient evidence when the available information is incomplete."

## 7.7 Form Actions

Primary button:

`Start Investigation`

Secondary button:

`Clear Form`

The clear action should reset the current form and should not create or delete backend records.

## 7.8 Submission Behavior

When the user selects `Start Investigation`:

1. Validate the form.
2. Check the user's authentication state.
3. Disable duplicate submission.
4. Display a loading state.
5. Send the request to the investigation API.
6. If the backend returns an investigation ID, navigate to its detail page.
7. If the request fails, preserve the user's input and show an actionable error.

Do not create a fake investigation result on the client.

## 7.9 Error Handling

Examples:

- "Enter a valid payment ID."
- "Describe the payment issue."
- "This payment could not be found."
- "You do not have permission to access this payment."
- "The investigation could not be started. Please try again."
- "The service is temporarily unavailable."

The frontend should display the appropriate message returned or mapped from a validated backend error response.

Do not expose stack traces, SQL errors, internal credentials, or sensitive implementation details.

---

# 8. Investigation Processing Experience

Route: `/investigations/{investigation_id}`

## 8.1 Purpose

Show the investigation's progress and final result without making the user wonder whether the application is still working.

## 8.2 Processing Layout

At the top, display:
- Investigation ID.
- Payment ID, if available.
- Start time.
- Current processing state.

Below it, display the investigation steps.

Suggested stages:

1. Validating request.
2. Retrieving payment information.
3. Classifying the issue.
4. Retrieving troubleshooting documents.
5. Analyzing available evidence.
6. Generating the investigation result.
7. Saving the result.

Only display stages that correspond to actual backend processing.

Do not claim that a step has completed unless the backend confirms it.

## 8.3 Processing States

### Queued

"The investigation is waiting to start."

### Running

"The investigation is in progress."

### Completed

"The investigation result is ready."

### Failed

"The investigation could not be completed."

### Requires More Information

"The available information is insufficient to complete this investigation."

If the implementation is synchronous, show a simple loading state rather than introducing a complex job-processing interface prematurely.

## 8.4 Loading Behavior

- Use a clear progress indicator.
- Explain that the investigation may take several seconds.
- Avoid fake percentage-completion indicators unless actual progress can be measured.
- Prevent accidental duplicate submissions.
- Allow navigation away from the page without losing a persisted investigation.

## 8.5 Failure Behavior

If processing fails:
- Preserve the investigation ID if a record was created.
- Display a human-readable error.
- Provide a retry action only if retrying is supported and safe.
- Avoid automatically duplicating an investigation on repeated submissions.
- Provide a link to the investigation history or dashboard.

---

# 9. Investigation Results Page

Route: `/investigations/{investigation_id}`

## 9.1 Purpose

Present the final investigation in a format that is easy to scan, verify, and act upon.

This is the most important page in the product.

The page must clearly separate recorded payment facts, deterministic classifications, retrieved documentation, and AI-generated interpretations.

## 9.2 Page Header

Display:
- Investigation ID.
- Payment ID.
- Investigation status.
- Creation time.
- Completion time, if available.

Actions:
- `Back to Investigations`
- `Copy Investigation ID`

Optional:
- `Export Result`, only if export functionality is implemented.

Do not display an action as active when it is not supported.

## 9.3 Investigation Summary

Place a prominent summary card near the top of the page.

Fields:

**Issue Category**

Example: `Delayed Payment`

**Recorded Payment Status**

Example: `PENDING`

**Investigation Outcome**

Example: `Evidence indicates that the payment remains pending in the available records.`

**Confidence**

Display only if the backend defines and validates a meaningful confidence score.

Do not treat an LLM's self-reported confidence as a calibrated probability.

If no reliable confidence measurement exists, omit the confidence indicator.

## 9.4 Payment Details Card

Display available, authorized payment fields:

- Payment ID.
- Amount and currency.
- Recorded status.
- Creation time.
- Last updated time.
- Payment method category, if available and safe to disclose.
- Relevant provider reference, if permitted.

Do not display sensitive payment credentials.

If a field is missing, display `Not available` rather than inventing a value.

If the database contains a payment record but the provider's current status has not been verified, label the status as the status recorded in the database.

## 9.5 Transaction Timeline

Display chronological payment events in a vertical timeline.

Each event should contain:
- Event type.
- Timestamp.
- Recorded status, if available.
- Relevant non-sensitive details.
- Source of the event.

Use the actual transaction history returned by the backend.

If there are no historical events, display:

"No transaction history is available for this payment."

Do not fabricate a timeline from the current payment status.

## 9.6 Evidence and Findings

Title:

`Evidence and Findings`

Organize the evidence into understandable groups.

### Payment Evidence

Show the relevant payment fields and recorded transaction events that support the investigation.

### Knowledge Base Evidence

Show retrieved troubleshooting passages and document references.

### Interpretation

Explain how the available evidence relates to the reported issue.

Each important conclusion should be traceable to a payment record, event, or retrieved document whenever possible.

If the evidence is contradictory, show the conflict rather than selecting one version without explanation.

## 9.7 AI-Generated Explanation

Title:

`Investigation Explanation`

The response should follow this structure:

**What we found**

A concise explanation of the issue based on available evidence.

**Why it may be happening**

A distinction between verified facts and possible explanations.

**What is still unknown**

Any information required to reach a stronger conclusion.

**Recommended next steps**

Practical troubleshooting steps grounded in the available records and documentation.

### Explanation Requirements

- Use plain English.
- Avoid unsupported certainty.
- Do not invent transaction events.
- Do not invent provider responses.
- Do not claim that funds were transferred, settled, or refunded without supporting evidence.
- Identify missing information.
- Distinguish observed facts from inferred explanations.
- Reference relevant evidence.
- Keep the main summary concise and allow additional detail to be expanded.

## 9.8 Recommended Next Steps

Display recommendations in a separate card.

Each recommendation should include:
- Action title.
- Brief explanation.
- Supporting evidence or policy reference, where available.
- Priority only when the backend has a meaningful priority definition.

Example:

**Verify the latest payment status**

"The available record shows a pending status. Confirm the latest status through the authorized payment-provider workflow before concluding that the payment failed."

The application should not automatically initiate refunds, reverse transactions, or modify financial records as part of the initial MVP.

Recommendations are informational unless an explicitly authorized action workflow is added in a future release.

## 9.9 Sources Panel

Title:

`Sources Used`

Show the documents and records used to generate the explanation.

For each knowledge source, display:
- Document title.
- Relevant section or chunk.
- Source identifier.
- Relevant excerpt.
- Link to the document, if available and authorized.

For payment evidence, display:
- Payment ID.
- Event identifier, where available.
- Relevant field or event.
- Timestamp.

If the response has no supporting knowledge source, do not create a fake citation.

The system should indicate when an answer is based only on payment data or when the retrieved documentation was insufficient.

## 9.10 Investigation Metadata

Provide an expandable section containing:
- Investigation ID.
- Creation timestamp.
- Completion timestamp.
- Processing duration, if measured.
- Model identifier, if available.
- Retrieval metadata appropriate for the user.
- Investigation status.
- Error details suitable for the user's permissions.

Do not expose internal chain-of-thought, secrets, raw credentials, or sensitive debugging data.

The interface may display concise explanations of the steps taken, tool names, and supporting evidence without exposing private model reasoning.

## 9.11 Result Page Actions

Possible actions:
- Copy summary.
- Copy investigation ID.
- Open related payment.
- Return to investigation history.
- Retry investigation, if supported.
- Export investigation, if implemented.

Any copy or export action must avoid including sensitive information the user is not authorized to access.

---

# 10. Investigations History

Route: `/investigations`

## 10.1 Purpose

Allow users to find, review, and reopen previously saved investigations.

## 10.2 Page Header

Title:

`Investigations`

Supporting text:

"Review payment investigations and their outcomes."

Primary action:

`New Investigation`

## 10.3 Search

Provide a search field that supports relevant backend-defined searchable fields.

Potential search fields:
- Investigation ID.
- Payment ID.
- Issue category.

Do not promise full-text search across all content unless implemented.

## 10.4 Filters

Provide filters for:
- Investigation status.
- Issue category.
- Payment status.
- Date range.

Only expose filters supported by the backend.

## 10.5 Table Columns

Recommended columns:

| Column | Description |
|---|---|
| Investigation ID | Unique investigation identifier |
| Payment ID | Associated payment |
| Issue Category | Classified issue |
| Payment Status | Status recorded in the data source |
| Investigation Status | Current processing or completion status |
| Created At | Investigation creation timestamp |
| Action | Open investigation |

## 10.6 Sorting and Pagination

- Default to the most recent investigations.
- Use server-side pagination.
- Preserve filters when moving between pages.
- Clearly show the current page and total results when available.
- Provide empty states for searches with no matches.

## 10.7 Row Interaction

Clicking a row or its view action opens the corresponding investigation detail page.

Avoid making the entire row interactive if it creates accessibility or usability problems with embedded controls.

## 10.8 Empty State

Title:

"No investigations found."

Supporting text:

"Try changing your filters or start a new investigation."

Actions:
- `Clear Filters`
- `New Investigation`

## 10.9 Error State

If the request fails:

"Unable to retrieve investigations."

Offer a retry action without discarding the current filters.

---

# 11. Payments Page

Route: `/payments`

## 11.1 Purpose

Provide an authorized way to search and inspect payment records independently of an investigation.

## 11.2 Search and Filters

Support:
- Payment ID.
- Recorded payment status.
- Date range.
- Amount range, if useful and supported.

Do not implement arbitrary search fields that cannot be queried efficiently or safely.

## 11.3 Payment Table

Recommended columns:
- Payment ID.
- Amount.
- Currency.
- Recorded status.
- Created time.
- Last updated time.
- Action.

## 11.4 Payment Details

Route: `/payments/{payment_id}`

Display:
- Payment summary.
- Available payment metadata.
- Recorded status.
- Transaction history.
- Related investigations.

Include an action:

`Investigate Payment`

Selecting it should open the new investigation form with the payment ID prefilled.

The backend must still validate access to the payment.

## 11.5 Empty and Error States

If no payments exist:

"No payment records are available."

If the payment cannot be found:

"Payment not found."

If access is denied, display an appropriate permission message without revealing restricted information.

---

# 12. Knowledge Base

Route: `/knowledge-base`

## 12.1 Purpose

Allow users to inspect the troubleshooting knowledge available to the RAG system.

The knowledge base should help users understand what documentation the system can reference.

## 12.2 Knowledge Base Overview

Display:
- Total indexed documents.
- Number of successfully indexed documents.
- Number of documents requiring attention, if processing states exist.
- Most recently updated documents.

These values must come from actual backend records.

## 12.3 Document List

Recommended columns:
- Document title.
- Category.
- Document status.
- Last updated.
- Number of indexed chunks, if available.
- Action.

## 12.4 Document Details

Display:
- Document title.
- Description, if available.
- Source identifier.
- Category.
- Ingestion timestamp.
- Indexing status.
- Relevant content or extracted sections.
- Chunk count, if available.

## 12.5 Document Ingestion

For an MVP with document upload, provide:
- Upload control.
- Supported file types.
- Maximum file size.
- Validation feedback.
- Upload progress.
- Indexing status.
- Failure message.

Supported file formats and limits must match the actual backend implementation.

Do not accept a file type in the frontend that the backend cannot process.

Document ingestion should be restricted to authorized users.

Uploaded documents must be treated as untrusted content. They must not be allowed to override application security rules or instruct the model to bypass tool restrictions.

## 12.6 Search Testing

If implemented, allow authorized users to submit a query and inspect the documents retrieved by the RAG system.

Display:
- Query.
- Retrieved document title.
- Relevant excerpt.
- Retrieval score, if meaningful and correctly defined.
- Source metadata.

Do not present similarity scores as probabilities of correctness.

If this functionality is not required for the MVP, defer it rather than building an incomplete testing interface.

---

# 13. Activity Logs

Route: `/activity`

## 13.1 Purpose

Provide an auditable view of relevant application activity.

## 13.2 Table Columns

- Event ID.
- Timestamp.
- Event type.
- Actor.
- Related investigation or payment identifier, where authorized.
- Outcome.

## 13.3 Event Types

Potential event types include:
- User login.
- Investigation created.
- Payment record accessed.
- Investigation completed.
- Investigation failed.
- Knowledge document uploaded.
- Authorization denied.

Only display events that are actually recorded by the backend.

## 13.4 Filters

Where supported:
- Event type.
- Date range.
- Actor.
- Outcome.

## 13.5 Security Requirements

- Audit logs must not be editable through the ordinary UI.
- Access must be restricted by role.
- Sensitive data must not be exposed in event details.
- Avoid logging raw prompts or model responses when they contain unnecessary sensitive information.
- Preserve event integrity through backend controls.

---

# 14. Settings

Route: `/settings`

## 14.1 Profile Settings

Display:
- User name, if available.
- Email.
- Assigned role.
- Account status.

Allow profile edits only where the backend supports them.

## 14.2 Security Settings

Potential options:
- Change password.
- View session information.
- Sign out.

Do not provide password reset or session management controls unless the corresponding backend flows are implemented securely.

## 14.3 Administrative Settings

For authorized administrators only:
- User management.
- Role assignment.
- Knowledge base management.
- System configuration visibility.

Never expose API keys, database passwords, signing secrets, or other credentials through the frontend.

Provider configuration should be managed through secure server-side configuration rather than ordinary browser forms.

---

# 15. Global Application States

Every major page must handle the following states consistently.

## 15.1 Loading State

Use skeleton components or simple progress indicators.

Do not show empty-state messages while data is still loading.

## 15.2 Empty State

Explain why no data is displayed and provide a relevant next action.

Do not populate the dashboard with fabricated records to make it look active.

## 15.3 Error State

Display a concise explanation and an appropriate recovery action.

Do not expose internal stack traces or database errors.

## 15.4 Permission Denied

Explain that the user does not have permission to access the requested resource.

Do not disclose sensitive details about inaccessible records.

## 15.5 Session Expired

Prompt the user to authenticate again.

Preserve non-sensitive form input where appropriate and safe.

## 15.6 Network Failure

Explain that the application could not communicate with the backend.

Provide a retry action where appropriate.

## 15.7 Partial Failure

If one dashboard section fails while another succeeds, retain the successful section and show an error only for the affected component.

## 15.8 Stale Data

Where data freshness matters, show the last-updated timestamp.

Do not imply that a database status is a live payment-provider status unless the system has actually verified it.

---

# 16. Responsive Design

The application must work on desktop, tablet, and mobile screens.

## 16.1 Desktop

Prioritize desktop usability because payment investigations often involve comparing multiple pieces of evidence.

Use:
- Persistent sidebar.
- Two-column investigation form.
- Full-width data tables.
- Side-by-side evidence panels where practical.

## 16.2 Tablet

- Collapse the sidebar if necessary.
- Reduce grid columns.
- Stack summary cards when space is limited.
- Preserve readable transaction details.

## 16.3 Mobile

- Use a compact navigation drawer.
- Stack form fields vertically.
- Keep primary actions easy to reach.
- Make tables horizontally scrollable or convert rows into compact cards.
- Avoid requiring hover to access information.
- Ensure evidence and recommendations remain readable.

## 16.4 Responsive Breakpoints

Use the frontend framework's standard responsive breakpoints as a starting point.

Do not hardcode layouts that only work at one screen size.

---

# 17. Accessibility Requirements

Follow WCAG 2.2 AA as the accessibility target where applicable.

Requirements:
- All interactive controls must be keyboard accessible.
- Focus states must be visible.
- Form fields must have accessible labels.
- Validation messages must be associated with the relevant fields.
- Statuses must use readable text in addition to color.
- Tables must use appropriate semantic markup.
- Dialogs must manage focus correctly.
- Loading and error states should be announced appropriately to assistive technologies.
- Text and control contrast must be sufficient.
- Icon-only buttons must have accessible names.
- Reduced-motion preferences should be respected.
- Avoid unnecessary animation.

Accessibility must be tested rather than assumed from the use of a component library.

---

# 18. Interaction and Motion Guidelines

Use motion only when it improves feedback or understanding.

Appropriate examples:
- A subtle sidebar transition.
- Button loading indicators.
- A short expansion animation for evidence details.
- A progress indicator during investigation processing.
- A toast after successfully copying an investigation ID.

Avoid:
- Full-screen animation sequences.
- Animated backgrounds.
- Excessive parallax.
- Decorative cursor effects.
- Fake AI typing animations that imply processing has completed when it has not.
- Artificial percentage counters.

Animations should not interfere with reading evidence or operating the interface.

---

# 19. Notifications and Feedback

## 19.1 Toast Notifications

Use concise messages for short-lived feedback.

Examples:
- "Investigation created."
- "Investigation ID copied."
- "Changes saved."
- "Unable to complete the request."

Do not use a toast as the only place to display an important persistent error.

## 19.2 Inline Validation

Display validation messages next to the relevant fields.

Clear errors when the user corrects the relevant input, where appropriate.

## 19.3 Confirmation Dialogs

Use confirmation dialogs for destructive actions or actions with significant consequences.

The initial MVP should not expose destructive financial actions such as issuing refunds or reversing payments.

---

# 20. Frontend Technical Recommendations

## 20.1 Recommended Stack

Use:
- Next.js with TypeScript.
- React.
- Tailwind CSS.
- A consistent component library, such as shadcn/ui, where useful.
- Lucide icons.
- A typed API client.
- A charting library only if meaningful dashboard charts are required.

Choose dependencies based on actual requirements. Do not install multiple component libraries or duplicate state-management tools without justification.

## 20.2 Component Structure

A possible structure is:

```text
frontend/
├── app/
│   ├── login/
│   │   └── page.tsx
│   └── dashboard/
│       ├── layout.tsx
│       ├── page.tsx
│       ├── investigations/
│       │   ├── page.tsx
│       │   ├── new/
│       │   │   └── page.tsx
│       │   └── [id]/
│       │       └── page.tsx
│       ├── payments/
│       │   ├── page.tsx
│       │   └── [id]/
│       │       └── page.tsx
│       ├── knowledge-base/
│       │   └── page.tsx
│       ├── activity/
│       │   └── page.tsx
│       └── settings/
│           └── page.tsx
├── components/
│   ├── layout/
│   ├── dashboard/
│   ├── investigations/
│   ├── payments/
│   ├── knowledge-base/
│   └── ui/
├── lib/
│   ├── api.ts
│   ├── auth.ts
│   ├── validation.ts
│   └── utils.ts
├── types/
└── tests/
```

This is a suggested organization. Adapt it to the project's existing structure and routing conventions.

## 20.3 API Integration

- Keep backend requests in a shared API client or well-defined service modules.
- Define TypeScript types for API requests and responses.
- Use consistent error handling.
- Handle loading and empty states.
- Avoid duplicating business logic in the frontend.
- Do not hardcode payment records or investigation outcomes as substitutes for backend responses.
- If mock data is temporarily used during development, isolate it from production behavior and remove or disable it when real integration is complete.

## 20.4 Form Validation

Use schema-based validation where useful.

Frontend validation should improve usability, but the backend must independently validate every request.

## 20.5 Authentication

- Protect application routes.
- Use the backend's actual authentication mechanism.
- Do not treat a hidden button as an authorization control.
- Do not store credentials in source code.
- Avoid storing long-lived access tokens in browser-accessible storage when a safer session design is available.
- If cookie-based authentication is selected, configure appropriate cookie security attributes and CSRF protections where needed.

The final approach must match the backend authentication architecture.

---

# 21. UI/UX Integration Requirements

The frontend and backend must agree on:

- Authentication behavior.
- Payment identifiers.
- Payment status values.
- Investigation lifecycle statuses.
- API request formats.
- API response formats.
- Error response structures.
- Pagination conventions.
- Timestamps and time zones.
- Document source identifiers.
- Investigation result structure.

The frontend must not invent backend states that the API does not support.

When a backend capability is unavailable, either hide the feature, disable it with a clear explanation, or implement a genuine alternative.

---

# 22. MVP Feature Prioritization

## P0: Required for the First Working MVP

- Login and authentication.
- Protected dashboard.
- Payment search.
- New investigation form.
- Investigation processing state.
- Investigation results page.
- Evidence display.
- Retrieved document sources.
- Recommended next steps.
- Investigation history.
- Loading, error, and empty states.
- Responsive layouts.
- Real backend integration.

## P1: Important Improvements

- Dashboard summary cards.
- Investigation filtering and pagination.
- Transaction timeline.
- Payment details page.
- Knowledge base document browsing.
- Investigation metadata.
- Activity log viewer.
- Copy investigation summary.

## P2: Defer Until the Core MVP Works

- Advanced analytics dashboards.
- Complex role administration.
- Export to PDF or CSV.
- Real-time notifications.
- Advanced knowledge base search controls.
- Customizable dashboards.
- Multiple payment-provider integrations.
- Financial action execution.
- Multi-agent orchestration interfaces.

Do not delay the core payment investigation workflow to implement P1 or P2 features.

---

# 23. End-to-End User Journey

The primary user journey should be:

1. The user opens PayGuard AI.
2. The user signs in.
3. The overview dashboard loads real application data.
4. The user selects `New Investigation`.
5. The user enters a payment ID and describes the issue.
6. The frontend validates the input.
7. The backend authorizes the request and creates the investigation.
8. The payment service retrieves the available transaction records.
9. The triage engine classifies the issue using defined rules.
10. The RAG service retrieves relevant troubleshooting documentation.
11. The orchestration layer combines the available evidence.
12. The LLM generates a structured, evidence-grounded explanation.
13. The backend validates and persists the investigation result.
14. The frontend displays the investigation summary.
15. The user reviews payment details, transaction history, evidence, and recommendations.
16. The user opens the supporting documents to verify the recommendations.
17. The user returns to the investigation history.
18. The investigation remains available for future review according to the user's permissions.

If the system cannot retrieve enough information, it should explain the limitation rather than invent a successful investigation.

---

# 24. UI/UX Acceptance Criteria

The design is ready for implementation when:

- The application has a consistent navigation structure.
- Every primary page has a defined purpose.
- The new investigation workflow is clearly specified.
- The result page distinguishes facts, evidence, and interpretations.
- Every important action has defined loading, success, and failure behavior.
- Empty databases do not produce fake statistics.
- The design supports desktop, tablet, and mobile.
- Status indicators use readable labels.
- Forms are keyboard accessible and have clear validation.
- Protected screens rely on backend authorization.
- The UI reflects real backend states.
- The system never presents fabricated evidence as real data.
- Unsupported features are deferred rather than represented as functional.
- The core user journey can be completed without confusion.

---

# 25. Implementation Instructions

Use this specification as the source of truth for the PayGuard AI frontend.

Before implementation:

1. Inspect the existing repository.
2. Confirm the backend API contracts.
3. Identify which endpoints are already available.
4. Map the screens to actual backend capabilities.
5. Reuse existing components and conventions where practical.

Implement the UI incrementally.

Recommended implementation order:

1. Design tokens and shared UI components.
2. Application layout and navigation.
3. Login page.
4. Dashboard.
5. Payment search and details.
6. New investigation form.
7. Investigation processing and results.
8. Investigation history.
9. Knowledge base.
10. Activity logs and settings.
11. Responsive behavior and accessibility.
12. End-to-end integration testing.

Do not build every page before verifying the first complete user journey.

Start by implementing the application shell and the primary investigation flow. Connect each screen to real API responses as the corresponding backend endpoints become available.

The finished product should be professional, reliable, accessible, and visually consistent. It should prioritize evidence-backed payment investigations over decorative AI features.