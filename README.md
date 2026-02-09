# Integrations by Autohive
This repository hosts Autohive integrations made and maintained by the Autohive team.

## Integrations

### Uber Ride Requests

[uber](uber): Comprehensive Uber Ride Requests integration for booking rides, getting fare estimates, tracking ride status, and retrieving receipts through the Uber Riders API v1.2. Supports listing available products at a location (UberX, UberXL, Black, etc.), price estimates for trips between locations, time estimates for driver arrival, detailed ride fare estimates with upfront pricing, ride requests on behalf of users, real-time ride status tracking with driver and vehicle information, tracking map URLs for active rides, ride cancellation, receipt retrieval for completed rides, user profile access, ride history with pagination, and payment method listing. Features OAuth 2.0 authorization code flow with scopes for profile, history, places, request, and request_receipt. Includes centralized API handling with error type categorization (validation_error, auth_error, rate_limited, not_found, server_error, api_error), comprehensive input validation for coordinates, seat counts, and pagination parameters, and 47 unit tests covering validation helpers, success paths, error paths, and edge cases. Comprises 12 actions covering products, estimates, ride requests, tracking, receipts, user profile, history, and payment methods. Ideal for transportation automation, corporate travel management, ride booking workflows, and expense tracking integration.

### Notion

[notion](notion): Enhanced integration with Notion API featuring comprehensive workspace management capabilities. Supports searching pages and databases, querying database entries with advanced filtering, creating and managing pages, updating page properties, retrieving and modifying block content, and managing database schemas. Includes robust error handling and pagination support for large datasets.

### RSS Reader 

[rss-reader-feedparser](rss-reader-feedparser): Reads RSS feeds using the `feedparser` library.

[rss-reader-feedparser-ah-fetch](rss-reader-feedparser-ah-fetch): Reads RSS feeds using `feedparser` and the `autohive-integration-sdk`'s `fetch()` method for HTTP requests. 

Supports basic HTTP authentication and Bearer token authentication via the SDK.

### Google Ads

[google-ads](google-ads): Comprehensive Google Ads integration with full CRUD operations for campaigns, ad groups, ads, keywords, and Keyword Planner functionality. Supports account discovery (list accessible accounts with details), campaign management (create, update, remove campaigns with budget and bidding strategy configuration), ad group operations (create, update, remove ad groups with CPC bid control), responsive search ad creation with multiple headlines and descriptions, keyword management (add, update, remove keywords with match type support), and negative keyword management at both campaign and ad group levels. Includes extensive reporting capabilities: campaign metrics, ad group metrics, ad metrics, keyword metrics, search terms report, and active ad URLs retrieval. Features Keyword Planner integration for generating keyword ideas, retrieving historical metrics with monthly search volumes, and forecasting keyword performance with budget projections. Supports OAuth2 platform authentication with Google Ads API scopes, Manager Account (MCC) support via login_customer_id, flexible date range filtering (YYYY-MM-DD_YYYY-MM-DD, 'last 7 days', DD/MM/YYYY), and billing cost tracking with ActionResult. Includes 24 actions covering account access, campaign CRUD, ad group CRUD, ad CRUD, keyword CRUD, negative keywords, metrics retrieval, and keyword planning. Ideal for advertising automation, campaign management, performance monitoring, and keyword research workflows.

### Google Analytics

[google-analytics](google-analytics): Google Analytics 4 (GA4) integration for accessing analytics data, reports, and metrics through the Analytics Data API. Supports running customized reports with dimensions and metrics, real-time analytics for monitoring active users and current activity in the last 30 minutes, metadata discovery for exploring available dimensions and metrics, and batch processing for running multiple reports in a single API call. Features OAuth2 authentication with Analytics Data API scope, flexible date range filtering (absolute YYYY-MM-DD and relative formats like "7daysAgo"), pagination support with limit and offset, and access to all GA4 event data including common dimensions (country, city, deviceCategory, browser, pagePath, eventName) and metrics (activeUsers, sessions, screenPageViews, bounceRate, conversions, engagementRate). Includes 4 actions for standard reports, real-time data, metadata retrieval, and batch report execution. Ideal for analytics workflows, data analysis, reporting automation, and business intelligence.

### Bitly

[bitly](bitly): URL shortening and link management integration with Bitly API v4 for creating, managing, and tracking shortened links. Supports quick URL shortening, advanced bitlink creation with custom back-halves and tags, link retrieval and updates, expanding bitlinks to original URLs, and listing bitlinks by group. Features click analytics (detailed counts by time unit and summaries), group management, and organization access. Uses OAuth 2.0 platform authentication with automatic token handling. Includes 12 actions covering user info, link management (6 actions), click analytics (2 actions), and groups/organizations (3 actions). Ideal for marketing automation, link tracking, campaign analytics, and URL management workflows.
### Google BigQuery

[bigquery](bigquery): Google BigQuery integration for serverless data warehouse operations, SQL queries, and dataset management. Supports query execution with standard and legacy SQL dialects, dry run for cost estimation, dataset lifecycle management (create, list, get, delete), table operations with schema management, time partitioning, and clustering, streaming data inserts, and job monitoring. Features OAuth2 platform authentication, automatic row parsing from BigQuery's nested response format, pagination for large result sets, and support for all BigQuery data types including RECORD, JSON, and GEOGRAPHY. Includes 14 actions covering queries, datasets, tables, jobs, and project discovery. Ideal for data warehousing, analytics automation, ETL pipelines, and business intelligence workflows.

### Box

[box](box): Manages files and folders in Box cloud storage. Supports listing shared folders, searching files, downloading file contents, uploading files, and browsing folder contents with recursive support.

### Dropbox

[dropbox](dropbox): Cloud file storage integration with Dropbox API v2 for comprehensive file and folder management. Supports folder listing with recursive browsing and pagination (list_folder, list_folder_continue), file and folder metadata retrieval, temporary download link generation (valid for 4 hours), file uploads with conflict handling modes (add, overwrite, update), folder creation, and complete file operations (delete, move, copy with autorename support). Features OAuth 2.0 authentication with automatic token management, cursor-based pagination for large directories, and support for mounted folders. Includes 9 actions covering file browsing, metadata access, uploads, and file organization. Ideal for file synchronization, backup workflows, document management, and cloud storage automation.

### Canva

[canva](canva): Comprehensive Canva integration for managing assets, designs, folders, and brand templates through the Canva Connect API. Supports uploading and managing assets (images, videos, audio), creating and exporting designs in various formats (PNG, JPG, PDF, PPTX, etc.), organizing content with folders, and accessing brand templates for Enterprise users. Features OAuth 2.0 with PKCE authentication, asynchronous job tracking for uploads and exports, pagination support for large datasets, and complete CRUD operations across all resource types. Includes 18 actions covering asset management, design creation and export, folder organization, and brand template access. Ideal for content creation automation and asset management workflows.

### Calendly

[calendly](calendly): Scheduling and appointment management integration with Calendly API v2 for managing scheduled events, event types, invitees, availability, and webhooks. Supports user information retrieval, event type discovery (list and get event type details), scheduled event management (list, get, cancel events with filtering by date, status, and invitee email), invitee tracking (list and get invitee details with questions and answers), availability checking (get available times for event types, user busy times, and availability schedules), organization membership listing, webhook management (list, get, create, delete webhook subscriptions), and routing form operations (list forms, get details, list submissions). Features OAuth 2.0 platform authentication with access based on subscription level (Free, Standard+, Teams/Enterprise), URI-based resource references, and pagination support. Includes 20 actions covering users, event types, scheduled events, invitees, availability, organization, webhooks, and routing forms. Ideal for scheduling automation, calendar integration, appointment tracking, and meeting management workflows.

### Circle

[circle](circle): Comprehensive integration with Circle.so community platform for managing posts, members, spaces, and events. Features searching and creating posts with markdown-to-TipTap conversion, member management with email search and profile access, space discovery and filtering by type, event tracking for upcoming/past community events, and comment operations for engagement. Includes comprehensive error handling, pagination support, and access to community-wide information and statistics.

### ClickUp

[clickup](clickup): Comprehensive project management integration with ClickUp API v2 for task management, list organization, and team collaboration automation. Supports full CRUD operations for tasks (create, get, update, delete, list with filtering by status, assignees, and pagination), lists (create in folders or spaces, get, update, delete), and folders (create, get, update, delete, list). Includes space management (get space details, list spaces in workspace), team/workspace discovery, and comment operations (create, get, update, delete task comments with markdown support). Features OAuth 2.0 authentication with automatic token management, priority levels (Urgent, High, Normal, Low), assignee management, due dates with timestamps, tag support, and subtask handling. Includes 22 actions covering tasks, lists, folders, spaces, teams, and comments. Ideal for task automation, project organization, workflow management, and team collaboration workflows.

### Coda

[coda](coda): Comprehensive Coda integration for managing documents, pages, tables, and rows. Supports full CRUD operations for docs (list, get, create, update, delete) and pages (list, get, create with HTML/Markdown content, update metadata, delete). Includes table and column discovery (list tables/columns, get table/column details) and complete row management (list with filtering/sorting, get, upsert with keyColumns, update, delete single/multiple). Features Bearer token authentication, pagination support, async processing (HTTP 202 responses), multiple value formats (simple/rich), and comprehensive error handling. Ideal for document automation, content management, and data synchronization workflows.

### ElevenLabs

[elevenlabs](elevenlabs): AI-powered text-to-speech integration with ElevenLabs API for voice generation and audio management. Supports converting text to realistic speech with customizable voice settings, browsing and filtering available voices by category and use case, accessing voice metadata and settings, tracking generation history, downloading previously generated audio files, and monitoring subscription usage and credits. Features 7 actions (1 paid, 6 free), API key authentication, multiple output formats (MP3, PCM), voice customization controls (stability, similarity, style), and base64-encoded audio file outputs. Includes 20 premade professional voices with various accents. Ideal for content creation, audiobook narration, voiceovers, and automated audio generation workflows.

### Fathom

[fathom](fathom): Conversation intelligence integration with Fathom AI for accessing meeting recordings, transcripts, and team data. Supports listing and filtering meeting recordings with advanced search capabilities by date range, participants, domains, and meeting type, retrieving full transcripts with speaker attribution and timestamps, accessing team and team member information, and comprehensive pagination support for all endpoints. Features OAuth 2.0 authentication with public_api scope and integration with Fathom's video meeting recording and transcription platform. Includes 4 actions covering meeting data access, transcript retrieval, and team management. Ideal for meeting analytics, conversation intelligence workflows, and automated report generation from meeting data.
### Eventbrite

[eventbrite](eventbrite): Comprehensive event management integration with Eventbrite API v3 for managing events, venues, attendees, orders, and ticket classes. Supports full event lifecycle management (create, update, delete, publish, unpublish, cancel, copy events), venue operations (create, update, list venues with address management), ticket class management (create, update, delete ticket types with pricing and quantity controls), order tracking by event or organization with status filtering, attendee management with check-in status, and category browsing. Features OAuth2 platform authentication with scopes for events, orders, attendees, venues, organizations, and user data. Includes 28 actions covering user info, organizations, events, venues, orders, attendees, ticket classes, and categories. Ideal for event automation, ticketing workflows, attendee tracking, and venue management.

### Front

[front](front): Customer service integration for Front's communication platform. Supports comprehensive inbox and conversation management, including listing and accessing inboxes, managing conversations and messages, creating new messages and replies through channels, accessing message templates for consistent responses, and managing conversation assignments and tags. Features channel-based message creation, conversation filtering, teammate and tag management, and complete message lifecycle operations for customer support workflows.

### Gong

[gong](gong): Integrates with Gong's conversation analytics platform to access call recordings, transcripts, and user data. Supports listing and searching calls, retrieving detailed call information and transcripts with speaker mapping, and managing user accounts. Includes comprehensive error handling and date filtering capabilities.

### Grammarly

[grammarly](grammarly): Comprehensive writing analysis integration with Grammarly API for quality assessment, AI detection, plagiarism checking, and analytics automation. Supports analyzing documents for writing quality with detailed scores (engagement, correctness, delivery, clarity), detecting AI-generated content with confidence scores and percentage metrics, checking for plagiarism against billions of sources with originality scores, and retrieving user analytics for team usage tracking (active days, sessions, improvements, AI prompt usage). Features OAuth 2.0 client credentials authentication with automatic token management, asynchronous job processing with status polling, 30-day result retention, and pagination support for analytics. Includes 7 actions covering Writing Score API (2 actions), Analytics API (1 action), AI Detection API (2 actions, Beta), and Plagiarism Detection API (2 actions, Beta). Supports multiple file formats (.doc, .docx, .odt, .txt, .rtf) with 4MB maximum file size. Ideal for content quality automation, academic integrity compliance, AI content verification, and team productivity tracking workflows.

### Google Looker

[google-looker](google-looker): Business intelligence integration with Looker API for accessing dashboards, executing queries, and managing data models. Supports listing and retrieving dashboards with full metadata, executing LookML queries against explores with dimensions and measures, running raw SQL queries against database connections, and browsing available models and connections. Features custom authentication and comprehensive error handling for enterprise analytics workflows.

### Xero

[xero](xero): Comprehensive Xero accounting integration with OAuth 2.0 authentication. Features retrieving available tenant connections, creating and updating sales invoices and purchase bills, attaching files to invoices/bills, contact search, and comprehensive financial reporting (aged payables/receivables, balance sheet, P&L, trial balance). Includes chart of accounts access, payment records, bank transactions, robust error handling, and rate limiting.

### Zoho CRM

[Zoho](Zoho): Comprehensive Zoho CRM integration providing full customer lifecycle management capabilities. Supports complete CRUD operations across all major CRM modules including contacts, accounts, deals, leads, tasks, events, and calls, with notes management across all 7 modules. Features lead-to-deal conversion workflows, advanced relationship queries, hierarchical account structures, activity tracking, and custom COQL query execution. Includes OAuth 2.0 authentication, robust error handling, pagination support, and 54 distinct actions covering sales pipeline management, customer onboarding, and CRM automation workflows.

### Pipedrive

[pipedrive](pipedrive): Pipedrive CRM integration for managing deals, contacts, organizations, activities, and sales pipelines. Supports full CRUD operations for deals (sales opportunities) with values, currencies, and expected close dates. Features complete contact management (persons) with email and phone information, organization management with company details, activity tracking for tasks, calls, meetings, deadlines, emails, and lunch meetings with scheduling and duration tracking. Includes note management with HTML formatting support, pipeline and stage discovery for sales workflow configuration, and universal search across all items (deals, persons, organizations, products) with exact match and custom field search capabilities. Features API token authentication, pagination support for large datasets (up to 500 items per request), and comprehensive filtering options by user, status, and custom filters. Comprises 30 actions covering deals, persons, organizations, activities, notes, pipelines, stages, and search. Ideal for sales pipeline management, customer relationship tracking, activity scheduling, and CRM automation workflows.
### Facebook Pages

[facebook](facebook): Comprehensive Facebook Pages integration for managing social media presence through the Graph API v21.0. Supports page discovery, full post lifecycle (create, retrieve, schedule, delete) with text, photo, video, and link content types, comment management (read, reply, hide/unhide, like/unlike, delete), and page/post-level analytics. Features scheduled posting (10 min to 75 days ahead) with ISO 8601 and Unix timestamp support. Uses a multi-file structure pattern for maintainability with separate action modules. Includes OAuth2 authentication with comprehensive page permissions.

### Reddit

[reddit](reddit): Connect workflows to Reddit with automated engagement capabilities. Search posts across subreddits with customizable filtering options and automatically post comments to join conversations. Includes authentication via Reddit OAuth with read and submit permissions, comprehensive post data extraction, and support for brand monitoring and community engagement workflows.

### App and Business Reviews

[app-business-reviews](app-business-reviews): Unified review aggregation integration powered by SerpAPI. Access reviews from Apple App Store (iOS apps), Google Play Store (Android apps), and Google Maps (business locations) through a single integration. Supports searching for apps and places, fetching reviews with advanced sorting and filtering, pagination for large datasets, and automatic ID resolution from names. Features customizable sort orders (newest, most helpful, rating-based), platform filtering for Android apps, and flexible location-based searches. Includes comprehensive error handling with helpful Place ID guidance and single API key authentication for all three review sources.

### Supadata

[supadata](supadata): Video transcription integration that extracts text transcripts from social media videos using the Supadata API. Supports YouTube, TikTok, Instagram, and X (Twitter) platforms with timestamped SRT-format output. Ideal for content analysis, accessibility features, and creating searchable text archives from video content.

### Heartbeat

[heartbeat](heartbeat): Connects to Heartbeat.chat community platform for comprehensive access to channels, threads, comments, users, and events. Supports retrieving channel information, managing thread discussions, creating and viewing comments, accessing user profiles, and viewing community events. Includes full CRUD operations for community engagement and content management.

### Humanitix

[humanitix](humanitix): Event management integration with Humanitix Public API v1 for retrieving events, orders, tickets, and attendee check-ins. Supports event retrieval (single event by ID or paginated list with date filtering), order retrieval with buyer details and payment status, ticket access with attendee information and check-in status filtering, attendee check-in and check-out operations with scanning message support, and tag retrieval for event categorization. Features API key authentication, location override with ISO 3166-1 alpha-2 country codes, pagination support (up to 100 results per page), and date-time filtering with ISO 8601. Includes 6 actions covering events, orders, tickets, check-in/check-out, and tags. Ideal for event operations, attendee tracking, and ticketing workflows.

### HeyGen

[heygen](heygen): AI-powered video avatar integration for creating realistic talking avatar videos. Supports generating AI photo avatars, creating and training avatar groups, generating new looks, creating videos with avatars and voice synthesis, and checking generation/video status. Includes voice and avatar discovery, motion and sound effects, and avatar group management. Features 19 actions with API key authentication.

### Instagram

[instagram](instagram): Comprehensive Instagram Business/Creator integration for managing posts, comments, and insights via the Instagram Graph API v24.0. Supports account information retrieval, content publishing (images, videos, reels, carousels, stories), comment moderation (read, reply, hide/unhide, delete), and advanced analytics for both account and post performance. Features Business Login for Instagram authentication with granular permissions, media container polling for reliable publishing, and support for alt text on images. Includes 8 actions covering account management, content creation, comment engagement, and insights retrieval. Rate limits scale with account reach (4800 × impressions per 24hrs) with 100 posts per day publishing limit.

### Google Calendar

[google-calendar](google-calendar): Integrates with Google Calendar API for comprehensive calendar and event management within Autohive workflows. Supports listing accessible calendars, creating and managing calendar events (both timed and all-day), attendee management, and event lifecycle operations. Features secure OAuth2 authentication and pagination support for large event datasets.

### Harvest

[harvest](harvest): Time tracking and project management integration with Harvest API for logging work hours, managing projects, clients, and teams. Supports creating and managing time entries with running timers, listing and filtering time entries by project, client, user, and date range, managing projects and clients, tracking tasks and team members, and comprehensive resource management operations. Features OAuth2 authentication, flexible time logging (manual hours or running timers), pagination support for large datasets, and full CRUD operations for time entries. Includes 10 core actions covering time tracking workflows, project organization, and team collaboration.

### Google Sheets

[google-sheets](google-sheets): Connects to Google Sheets and Drive APIs to list accessible spreadsheets, read and write A1 ranges, append rows, apply formatting, freeze panes, run batch updates, and duplicate spreadsheets. Uses Google OAuth2 platform authentication with appropriate scopes for Sheets and Drive.

### Microsoft Excel

[microsoft-excel](microsoft-excel): Comprehensive integration with Microsoft Excel workbooks stored in OneDrive for Business or SharePoint via Microsoft Graph API. Supports listing and searching Excel workbooks, reading and writing cell ranges using A1 notation, worksheet management (create, delete, list), full table operations (create, read, add/update/delete rows), sorting and filtering data, and applying formatting (font, fill, alignment, number format). Features named range access, used range detection, and support for both workbook-level and worksheet-level table operations. Uses OAuth2 platform authentication with Microsoft 365 and Files.ReadWrite scope. Ideal for automating Excel-based workflows, data extraction, reporting automation, and spreadsheet manipulation.

### Google Tasks

[google-tasks](google-tasks): Integrates with Google Tasks API for comprehensive task management within Autohive workflows. Supports listing and accessing task lists, and full CRUD operations for tasks including creating tasks with due dates and notes, managing subtasks with parent-child relationships, updating task status and properties, repositioning tasks, and filtering by completion status and date ranges. Features secure OAuth2 authentication, pagination support for large task collections (up to 2,000 lists and 20,000 tasks per list), and comprehensive error handling for productivity and workflow automation.

### Google Business Profile

[google-business-profile](google-business-profile): Connects to Google My Business API for comprehensive business profile and review management. Supports listing business accounts and locations, reading customer reviews with ratings and comments, replying to customer reviews professionally, and managing review interactions. Features secure OAuth2 authentication with Google Maps Reviews provider and comprehensive error handling for reputation management workflows.

### Microsoft Copilot 365

[Microsoft Copilot 365](microsoft365): Comprehensive integration with Microsoft Copilot 365 services including Outlook, OneDrive, Calendar, and SharePoint through Microsoft Graph API. Supports email management (send, draft, reply, forward, search with attachments), calendar operations (create, update, list events with date filtering), OneDrive file operations (search, read with PDF conversion), SharePoint site and document library access (search sites, list libraries, search documents across all drives, read files), and contact management. Features multi-drive SharePoint support, automatic PDF conversion for Office documents, timezone-aware calendar queries, null-safe field handling, and OAuth2 authentication with enterprise-grade permissions including Sites.Read.All for organizational knowledge base access.

### Microsoft Planner

[microsoft-planner](microsoft-planner): Comprehensive task and project management integration with Microsoft Planner via Microsoft Graph API v1.0 for organizing team work within Microsoft 365 groups. Supports complete plan lifecycle management (create, update, delete, list plans within groups), bucket organization for task categorization, full CRUD operations for tasks with assignments, due dates, priorities, categories, and progress tracking, and checklist operations within tasks. Features user lookup and search by email, group membership listing, task filtering by plan/bucket/user, task details management including descriptions and references, and board format customization for different views (assigned-to, bucket, progress). Includes automatic ETag management for optimistic concurrency control, proper assignment formatting with user GUIDs, data cleaning for read-only fields, and OAuth2 authentication with Tasks.ReadWrite and Group.ReadWrite.All scopes. Comprises 36 actions covering groups, users, plans, buckets, tasks, checklists, and board formatting. Ideal for team collaboration, project planning, task tracking, and workflow automation across Microsoft 365 workspaces.

### Microsoft Word

[microsoft-word](microsoft-word): Comprehensive Word document management integration via Microsoft Graph API for reading, creating, and manipulating .docx files stored in OneDrive for Business, SharePoint, or Group drives. Supports document listing with name filtering, document metadata retrieval, content extraction in text/HTML/markdown formats, document creation with optional templates, content updates with formatting preservation, text insertion at specific locations, paragraph management, find-and-replace operations with case sensitivity and whole-word matching, PDF export with save-to-drive option, and table extraction as structured data. Features secure XML parsing with defusedxml for XXE attack prevention, URL-encoded path handling for injection protection, parallel API calls for performance, streaming zip processing for memory efficiency, exponential backoff for polling operations, and OAuth2 authentication with Files.Read and Files.ReadWrite scopes. Includes 10 actions covering document lifecycle, content manipulation, and format conversion. Ideal for document automation, template-based generation, content processing, and workflow integration with Microsoft 365.

### Microsoft PowerPoint

[microsoft-powerpoint](microsoft-powerpoint): Comprehensive PowerPoint integration for reading, creating, and manipulating presentations in OneDrive/SharePoint via Microsoft Graph API. Supports listing and searching .pptx files with filtering, retrieving presentation metadata including author and timestamps, accessing slide thumbnails in multiple sizes, creating new presentations from scratch or templates, full slide CRUD operations (add, update, delete slides with layout and content control), exporting presentations to PDF format, and generating slide images. Features the python-pptx library for slide content manipulation (title, body text, speaker notes), automatic file download/upload for modifications, thumbnail API integration, and OAuth2 authentication with Files.Read, Files.ReadWrite, and User.Read scopes. Includes 10 actions covering presentation discovery, metadata access, slide management, content editing, and export operations. Ideal for marketing automation, sales deck generation, training content management, and programmatic presentation workflows.


### Spreadsheet Tools

[spreadsheet-tools](spreadsheet-tools): Tools for working with spreadsheet files including conversion to JSON format with automatic header sanitization and type inference. Supports Excel (.xlsx/.xls) and CSV file formats. Features automatic data type detection, header sanitization for valid JSON property names, duplicate header handling, and UTF-8/BOM encoding support. Ideal for data transformation, spreadsheet parsing, and converting tabular data into structured JSON for workflow automation.

### Asana

[asana](asana): Comprehensive project management integration with Asana API v1.0 for task and team collaboration automation. Supports complete task lifecycle management (create, get, update, list, delete tasks with assignees, due dates, and completion tracking), full project CRUD operations (list, get, create, update, delete projects with team associations and archiving), section organization (list, create, update sections, move tasks between sections for board/column workflows), team communication (create and list comments/stories on tasks), and subtask creation for breaking down complex work. Features Personal Access Token authentication with Bearer token headers, Asana data object wrapper handling, GID-based resource identification, and flexible task filtering. Includes 17 comprehensive actions covering tasks, projects, sections, comments, and subtasks. Ideal for workflow automation, task capture from external sources, project template creation, team collaboration, and productivity tracking across workspaces.

### Mailchimp

[mailchimp](mailchimp): Email marketing integration with Mailchimp Marketing API v3.0 for managing mailing lists, audience members, and email campaigns. Supports complete list management (create, get, list audiences), member operations (add, update, get members with merge fields and tags), and campaign management (create, get, list campaigns with status filtering). Features OAuth2 authentication with dynamic data center resolution, automatic rate limiting with retry logic (max 10 simultaneous connections), MD5 subscriber hash generation, and pagination support for large datasets. Includes 10 actions covering audience management, subscriber lifecycle, and email campaign workflows.

### Monday.com

[monday-com](monday-com): Comprehensive project and workflow management integration with Monday.com GraphQL API for managing boards, items, updates, and team collaboration. Supports board discovery with columns and groups (list with filtering by board kind: public, private, share), complete item management (retrieve items with column values and cursor-based pagination, create items with optional group assignment, update item column values), update operations (create comments and updates on items), and user management (list workspace users with team associations and admin status). Features platform OAuth authentication, GraphQL API with flexible querying, pagination support (page-based for boards/users, cursor-based for items), column value management for custom fields, comprehensive error handling, and workspace-wide access. Includes 6 actions covering board management, item lifecycle operations, commenting workflows, and user discovery. Ideal for task automation, project tracking, team collaboration, and workflow management.

### Google Chat

[google-chat](google-chat): User-authenticated Google Chat integration for messaging and space management. Supports sending and managing messages with threading and @mentions, creating and managing Chat spaces, listing and reacting to messages with emojis, managing space memberships, and finding direct message conversations. Features 13 actions including full CRUD operations for messages, space management, reaction support, and OAuth2 authentication with user context. Ideal for team communication automation, notification workflows, and Chat bot alternatives using user credentials.

### Google Search Console

[google-search-console](google-search-console): Comprehensive Google Search Console integration for accessing search analytics, URL inspection, sitemap management, and site verification data. Supports querying search performance data with dimensions (query, page, country, device, date) and metrics (clicks, impressions, CTR, position), advanced filtering and grouping, listing verified sites with permission levels, inspecting individual URLs for index status and mobile usability, and managing sitemaps with submission status tracking. Features OAuth2 authentication, pagination support for large datasets (up to 25,000 rows per request), support for both URL-prefix and Domain properties, and comprehensive error handling. Includes 5 actions covering search analytics queries, site listing, URL inspection, and sitemap management. Ideal for SEO automation, search performance monitoring, and website health tracking workflows.

### Hacker News

[hackernews](hackernews): Read-only integration with the official Hacker News API for fetching tech news, discussions, and community content. Supports retrieving top, best, and new stories, Ask HN discussions, Show HN project showcases, and YC job postings. Features story detail fetching with threaded comment trees (configurable depth), user profile lookup with karma scores, and LLM-optimized output with ISO timestamps and pre-computed HN URLs. Includes 8 actions with concurrent batch fetching for performance. No authentication required (public API, no rate limits). Ideal for daily tech news digests, community monitoring, and curated report generation.

### Google Docs

[google-docs](google-docs): Comprehensive integration with Google Docs API v1 for document creation, content formatting, and document analysis. Supports creating new documents, retrieving full document content and structure, inserting plain text paragraphs, inserting markdown-formatted content with automatic styling (headings H1-H6, bold, italic), applying text formatting (bold, italic, font size, colors), parsing document structure to identify headings and paragraphs, and executing complex batch update operations. Features OAuth2 authentication, markdown-to-Google Docs style conversion, and 6 core actions for document automation workflows.

### Freshdesk

[freshdesk](freshdesk): Comprehensive help desk integration with Freshdesk API v2 for complete customer support operations. Supports ticket management (create, list, get, update, delete tickets with priority and status control), contact management (full CRUD operations for customer contacts with company associations), company management (create and manage organizations with domain associations), and conversation tracking (list ticket conversations, add private notes for agents, create public replies to customers). Features custom API key authentication with automatic Basic Auth encoding, pagination support for all list operations, and robust error handling. Ideal for automating support workflows, ticket routing, customer communication, and help desk operations.

### Doc Maker

[doc-maker](doc-maker): Word document automation integration with markdown-first content creation and intelligent template filling. Supports creating professional documents from markdown syntax, safely filling templates with context-aware placeholder detection, find-and-replace operations with safety checks, and adding images, tables, and formatted content. Features LLM-optimized responses, stateless file streaming for AWS Lambda deployment, and comprehensive safety mechanisms to prevent unintended content corruption. No authentication required.

### Slide Maker

[slider](slider): PowerPoint automation integration with markdown-first content creation and intelligent template filling. Supports creating professional presentations from markdown syntax with two powerful modes: auto-layout for automatic vertical content flow and granular mode for precise positioning control. Features safe template filling with placeholder metadata support (font size, color, formatting), find-and-replace with automatic font sizing and safety checks, chart creation (column, line, pie, bar, area, scatter), image insertion, and intelligent overlap detection. Includes markdown support for headings (H1-H6), bullets, tables, blockquotes, and code blocks. Features stateless file streaming for AWS Lambda deployment, comprehensive positioning validation, and graceful error handling. No authentication required.

### Float

[float](float): Comprehensive resource management and project scheduling integration with Float API for team capacity planning, time tracking, and project coordination. Supports full CRUD operations for team members (people) with roles, departments, rates, and availability management. Includes complete project lifecycle management with client associations, budgets, timelines, and team assignments. Features task/allocation scheduling across team members, time off management with leave types, logged time tracking with billable hours, and client relationship management. Provides access to organizational structure (departments, roles), account settings, project stages, phases, milestones, and expenses. Includes comprehensive reporting capabilities (people utilization, project analytics) with date range filtering. Features 60 actions covering all Float API v3 endpoints, custom API key authentication with required User-Agent header, connected account information display, pagination support (up to 200 items per page), rate limiting awareness (200 GET/min, 100 non-GET/min), field filtering, sorting, modified-since sync capabilities, and ActionResult return type for cost tracking. Ideal for resource planning, capacity management, project scheduling, time tracking workflows, and team utilization analysis.

### Shopify Admin

[shopify-admin](shopify-admin): Integrates with the Shopify Admin API for backend store management. Currently enables comprehensive customer lifecycle management including searching, creating, updating, and deleting customer records via the GraphQL API.

### Shopify Storefront

[shopify-storefront](shopify-storefront): Connects to the Shopify Storefront API to manage customer-facing e-commerce operations. Supports searching and retrieving products and collections, full cart management (create, update, discounts), and customer authentication.

### Stripe

[stripe](stripe): Comprehensive payment and billing integration with Stripe API for managing customers, invoices, invoice items, subscriptions, products, prices, and payment methods. Supports full customer lifecycle management (create, list, get, update, delete) with address and metadata support. Features complete invoice workflow including draft creation, finalization, sending via email, payment processing, and voiding. Includes invoice item management for adding line items with quantities, unit amounts, and descriptions. Provides subscription management (create, update, cancel with trial periods and proration), product catalog operations (create, update, list products), price management (one-time and recurring pricing), and payment method handling (list, attach, detach). Supports OAuth authentication via Stripe Apps Marketplace and API key authentication (test and production keys). Features pagination with cursor-based navigation, filtering by customer/status/date, and multi-currency support. Includes actions covering customers, invoices, invoice items, subscriptions, products, prices, and payment methods. Ideal for billing automation, subscription management, and payment processing workflows.

### LinkedIn

[linkedin](linkedin): LinkedIn integration for sharing content and accessing user profile information. Supports posting text content to LinkedIn feed with PUBLIC or CONNECTIONS visibility, and retrieving authenticated user profile via OpenID Connect (sub, name, email, picture, locale). Features OAuth2 authentication with openid, profile, email, and w_member_social scopes, LinkedIn Posts API with versioned headers (202501), and comprehensive test suite. Includes 2 actions covering profile retrieval and content sharing. Ideal for social media automation, content publishing, and user identity workflows.

### LinkedIn Ads

[linkedin-ads](linkedin-ads): Comprehensive LinkedIn Marketing API integration for managing advertising campaigns, ad accounts, creatives, and performance analytics. Supports ad account discovery (list accessible accounts, get account users and roles), full campaign lifecycle management (create, get, update, pause, activate campaigns with objectives, budgets, and targeting), campaign group organization, and creative retrieval. Features performance analytics with customizable date ranges and time granularity (daily, monthly, all), including impressions, clicks, CTR, spend, and conversions. Supports LinkedIn URN format handling for accounts, campaigns, and creatives. Uses OAuth2 platform authentication with r_ads, r_ads_reporting, and rw_ads scopes. Includes 11 actions covering ad account management, campaign CRUD operations, campaign groups, creatives, analytics, and user access. Ideal for advertising automation, campaign management, performance monitoring, and marketing workflow integration.

### Trello

[trello](trello): Comprehensive project management integration with Trello REST API v1 for managing boards, lists, cards, and team collaboration automation. Supports full board lifecycle management (create, get, update, list boards with permission controls and filtering), list organization (create, get, update, list with positioning and archiving), complete card CRUD operations (create, get, update, delete, list cards with descriptions, due dates, member assignments, and label support), checklist management (create checklists, add checklist items with completion tracking), and team communication (add comments with Markdown support). Features custom API Key and Token authentication, position management (top/bottom/numeric), Markdown support in descriptions and comments, member and label assignment, and comprehensive filtering options. Includes 17 actions covering members, boards, lists, cards, checklists, and comments. Ideal for workflow automation, task tracking, project organization, team collaboration, and kanban-style board management.

### Webcal

[webcal](webcal): WebCalendar integration for fetching and processing events from webcal/iCal calendar feeds. Supports retrieving upcoming events within a configurable time range, searching events by keywords across summary, description, and location fields, timezone conversion for displaying events in any timezone, and detection of recurring and all-day events. Works with any iCal-compatible calendar source including Google Calendar, Apple iCloud, Microsoft Outlook, and Airbnb. Features no authentication required (public feeds), case-insensitive search with match field identification, and comprehensive event metadata extraction (organizer, attendees, URLs). Includes 2 actions for event fetching and searching. Ideal for calendar aggregation, scheduling automation, availability monitoring, and event-based workflow triggers.

### Productboard

[productboard](productboard): Comprehensive product management integration with Productboard API v2 for managing product hierarchy entities, notes, and analytics. Supports full entity lifecycle management for features, products, components, initiatives, objectives, releases, and subfeatures with custom field support. Includes complete note/feedback operations (create, list, get, update) for simple notes and conversations with tagging, owner assignment, and customer linking. Features analytics report access, entity configuration metadata, and user information retrieval. Supports OAuth2 authentication with comprehensive scopes (product_hierarchy_data, notes, custom_fields, users, companies), cursor-based pagination, and robust error handling. Includes 12 actions covering entities, notes, analytics, and user operations. Ideal for product roadmap automation, customer feedback management, and product analytics workflows.

### Netlify

[netlify](netlify): Web hosting and deployment integration with Netlify API v1 for managing sites and deployments. Supports complete site lifecycle management (create, list, get, update, delete sites with custom domain configuration), deployment operations (list deploys, create deploys with file uploads using SHA1 deduplication, get deploy details), and hosting automation. Features OAuth 2.0 platform authentication, automatic file hashing for efficient deployments, and comprehensive error handling. Includes 8 actions covering site management and deployment workflows. Ideal for static site hosting, continuous deployment automation, and web hosting management.

### Typeform

[typeform](typeform): Form building and data collection integration with Typeform API for managing forms, responses, workspaces, themes, images, and webhooks. Supports complete form lifecycle management (list, get, create, update, delete forms with fields, settings, and logic), response retrieval with filtering by date and completion status, workspace organization (list, get, create, update, delete), theme customization (list, get, create, delete with colors and fonts), image management, and webhook configuration for real-time notifications. Features OAuth 2.0 platform authentication with comprehensive scopes (accounts, forms, responses, workspaces, themes, images, webhooks read/write, offline for refresh tokens), pagination support, and 24+ field types including text, multiple choice, rating, file upload, and payment. Includes 24 actions covering user info, forms, responses, workspaces, themes, images, and webhooks. Ideal for survey automation, lead generation, customer feedback collection, and form workflow integration.
### GitLab

[gitlab](gitlab): Read-only GitLab integration for DevOps monitoring via GitLab REST API v4. Supports project browsing (list, get projects with statistics), issue tracking (list with filtering by state/labels/milestone/assignee, get issue details), merge request review (list, get, view changes/diffs, list commits in MRs), branch inspection (list, get branch details with protection status), commit history (list commits with date/path/author filtering, get commit details with stats, view commit diffs), CI/CD pipeline monitoring (list pipelines with status filtering, get pipeline details, list pipeline jobs), repository access (list directory tree recursively, get file contents as base64 or raw text, compare branches), and container registry access (list repositories, get repository details, list and get image tags). Features OAuth 2.0 platform authentication with read_api, read_user, read_repository, read_registry, and related scopes, automatic project ID encoding for path-based identifiers, pagination support (up to 100 per page), and comprehensive error handling. Includes 25 read-only actions covering user info, projects, issues, merge requests, branches, commits, pipelines, repository, and container registry. Ideal for DevOps monitoring, code review workflows, CI/CD status tracking, and GitLab data access.

### X (formerly Twitter)

[X](X): X (formerly Twitter) integration for social media automation via X API v2. Supports post lifecycle management (create, get, delete, search posts with advanced query operators), combined post-with-media action for streamlined content publishing with images, GIFs, and videos, repost operations, follow/unfollow users, and user profile retrieval. Features connected account support for automatic user info retrieval and pagination support for large datasets. Uses OAuth 2.0 with PKCE authentication. Includes 13 actions covering posts, reposts, and user operations. Ideal for social media automation, content scheduling, brand monitoring, and community management workflows.
### NZBN (New Zealand Business Number)

[nzbn](nzbn): Integration with the New Zealand Business Number (NZBN) API for searching and retrieving business entity information from the NZBN Register. Supports searching entities by name, trading name, or NZBN with filters for entity type and status, retrieving detailed entity information, accessing addresses, roles/officers, trading names, GST numbers, and industry classifications (ANZSIC codes), and tracking entity changes over time. Features 2-legged OAuth (Client Credentials) authentication with automatic token caching and refresh, zero-config experience for end users with server-side credential injection, and comprehensive error handling. Includes 9 actions covering entity search, details retrieval, and change tracking. Ideal for business verification, due diligence, compliance workflows, and NZ company data integration.

### Code Analysis

[code-analysis](code-analysis): Python code execution integration for data analysis, file processing, and automation tasks. Supports executing arbitrary Python code in a sandboxed environment, processing input files (CSV, Excel, JSON, images, PDFs), and automatically detecting and returning generated output files with base64 encoding. Pre-installed libraries include numpy, Pillow, PyPDF2, python-docx, reportlab, openpyxl, XlsxWriter, matplotlib, and python-pptx. Features ActionResult return type for cost tracking. No authentication required. Ideal for data transformation, document generation, chart creation, and custom automation workflows.

### Shopify Customer

[shopify-customer](shopify-customer): Facilitates customer self-service through the Shopify Customer Account API. Supports authenticated customer operations, including viewing and updating profiles, managing address books (list, create, update, delete, set default), and accessing order history. Features OAuth 2.0 with PKCE authentication helpers.

## Template

[template-structure](template-structure) contains a structural template for new integrations, including a sample template for an appropriate README file and a basic testbed.
