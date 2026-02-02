# Grammarly Integration for Autohive

Connects Autohive to the Grammarly API to enable writing quality assessment, AI detection, plagiarism checking, and analytics automation.

## Description

This integration provides a comprehensive connection to Grammarly's suite of writing analysis APIs. It allows users to automate document analysis for writing quality, detect AI-generated content, check for plagiarism, and retrieve user analytics directly from Autohive.

The integration uses Grammarly's OAuth 2.0 client credentials flow for authentication and implements 7 comprehensive actions covering writing scores, AI detection, plagiarism detection, and analytics.

## Setup & Authentication

This integration uses **OAuth 2.0 Client Credentials** authentication for secure access to your Grammarly API.

### Authentication Method

The integration uses OAuth 2.0 client credentials flow with the following scopes:
- `scores-api:read` and `scores-api:write` - Writing Score API access
- `analytics-api:read` - Analytics API access
- `ai-detection-api:read` and `ai-detection-api:write` - AI Detection API access
- `plagiarism-api:read` and `plagiarism-api:write` - Plagiarism Detection API access

### Setup Steps in Autohive

1. Create a Grammarly developer account at https://developer.grammarly.com/
2. Create a new OAuth 2.0 application in the Grammarly Developer Portal
3. Copy your Client ID and Client Secret
4. Add Grammarly integration in Autohive
5. Enter your Client ID and Client Secret when prompted
6. The integration will automatically handle token management and refresh

The OAuth integration automatically handles token management and refresh, so you don't need to manually manage access tokens.

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields (e.g., `score_request_id`, `status`, `data`)

Example successful response:
```json
{
  "result": true,
  "score_request_id": "abc123"
}
```

Example error response:
```json
{
  "result": false,
  "error": "Invalid file format"
}
```

## Actions

### Writing Score API (2 actions)

#### `analyze_writing_score`
Submits a document for comprehensive writing quality analysis.

**Inputs:**
- `filename` (required): Name of the file to be analyzed (e.g., 'document.txt', 'article.docx')
- `file_content` (required): The text content of the file to analyze

**Outputs:**
- `score_request_id`: Unique identifier to retrieve the analysis results
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Notes:**
- Supports .doc, .docx, .odt, .txt, .rtf formats
- Maximum file size: 4MB
- Minimum text length: 30 words

---

#### `get_writing_score_results`
Retrieves the writing quality score results for a previously submitted document.

**Inputs:**
- `score_request_id` (required): The score request ID from analyze_writing_score

**Outputs:**
- `status`: Status of the scoring request (PENDING, COMPLETED, or FAILED)
- `general_score`: Overall writing quality score (null if status is PENDING or FAILED)
- `engagement`: Engagement score (null if status is PENDING or FAILED)
- `correctness`: Correctness score (null if status is PENDING or FAILED)
- `delivery`: Delivery score (null if status is PENDING or FAILED)
- `clarity`: Clarity score (null if status is PENDING or FAILED)
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Notes:**
- Results available for 30 days after submission
- Scores are provided on a 0-100 scale

---

### Analytics API (1 action)

#### `get_user_analytics`
Retrieves paginated list of users with Grammarly usage statistics for a date range.

**Inputs:**
- `date_from` (required): Start date in YYYY-MM-DD format (must be within 365 days prior)
- `date_to` (required): End date in YYYY-MM-DD format (latest allowed is two days before current date)
- `cursor` (optional): Pagination cursor for fetching next page of results
- `limit` (optional): Number of results per page (min: 1, max: 400)

**Outputs:**
- `data`: Array of user objects with analytics data
  - `id`: Unique user identifier
  - `name`: User's name
  - `email`: User's email address
  - `days_active`: Number of days the user actively used Grammarly
  - `sessions_count`: Number of writing sessions
  - `sessions_improved_percent`: Percentage of sessions with improvements
  - `prompt_count`: Number of generative AI prompts used
- `paging`: Pagination information
  - `next_cursor`: Cursor for next page of results
  - `has_more`: Whether more results are available
  - `page_size`: Number of items in current page
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Notes:**
- Data available for past 365 days with 2-day lag
- Use cursor for pagination through large result sets

---

### AI Detection API (2 actions)

#### `analyze_ai_detection`
Submits a document for AI content detection analysis.

**Inputs:**
- `filename` (required): Name of the file to be analyzed (e.g., 'document.txt', 'article.docx')
- `file_content` (required): The text content of the file to analyze

**Outputs:**
- `score_request_id`: Unique identifier to retrieve the analysis results
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Notes:**
- Evaluates likelihood text was generated by AI
- Maximum file size: 4MB
- API is in Beta

---

#### `get_ai_detection_results`
Retrieves AI detection results for a previously submitted document.

**Inputs:**
- `score_request_id` (required): The score request ID from analyze_ai_detection

**Outputs:**
- `status`: Status of the detection request (PENDING, COMPLETED, or FAILED)
- `average_confidence`: Confidence level of the AI detection (0-1 scale, null if status is PENDING or FAILED)
- `ai_generated_percentage`: Percentage of text that appears to be AI-generated (0-100, null if status is PENDING or FAILED)
- `updated_at`: Timestamp when the result was last updated
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Notes:**
- Results available for 30 days after submission
- Higher confidence indicates more certainty in the detection

---

### Plagiarism Detection API (2 actions)

#### `analyze_plagiarism_detection`
Submits a document for plagiarism detection analysis.

**Inputs:**
- `filename` (required): Name of the file to be checked (e.g., 'document.txt', 'paper.docx')
- `file_content` (required): The text content of the file to analyze

**Outputs:**
- `score_request_id`: Unique identifier to retrieve the analysis results
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Notes:**
- Compares text against billions of web pages and academic papers
- Maximum file size: 4MB
- API is in Beta

---

#### `get_plagiarism_detection_results`
Retrieves plagiarism detection results for a previously submitted document.

**Inputs:**
- `score_request_id` (required): The score request ID from analyze_plagiarism_detection

**Outputs:**
- `status`: Status of the detection request (PENDING, COMPLETED, or FAILED)
- `originality_score`: Originality score (higher means more original, null if status is PENDING or FAILED)
- `plagiarism_percentage`: Percentage of text that appears to be plagiarized (0-100, null if status is PENDING or FAILED)
- `updated_at`: Timestamp when the result was last updated
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Notes:**
- Results available for 30 days after submission
- Higher originality score indicates more unique content

---

## Requirements

- `autohive_integrations_sdk` - The Autohive integrations SDK

## API Information

- **Authentication**: OAuth 2.0 Client Credentials
- **Token URL**: `https://auth.grammarly.com/v4/api/oauth2/token`
- **Base URLs**:
  - Writing Score API: `https://api.grammarly.com/ecosystem/api/v2/scores`
  - Analytics API: `https://api.grammarly.com/ecosystem/api/v2/analytics/users`
  - AI Detection API: `https://api.grammarly.com/ecosystem/api/v1/ai-detection`
  - Plagiarism API: `https://api.grammarly.com/ecosystem/api/v1/plagiarism`
- **Documentation**: https://developer.grammarly.com/
- **Rate Limits**:
  - POST requests: 10 requests per second
  - GET requests: 50 requests per second

## Important Notes

- OAuth tokens are automatically managed by the integration
- Tokens are automatically refreshed when expired
- Results from scoring and detection requests are retained for 30 days
- Uploaded documents are retained for maximum 24 hours
- File size limit: 4MB for all document uploads
- Maximum text length: 100,000 characters
- Minimum text length: 30 words (for scoring)
- Supported formats: .doc, .docx, .odt, .txt, .rtf
- AI Detection and Plagiarism Detection APIs are currently in Beta

## Testing

To test the integration:

1. Navigate to the integration directory: `cd grammarly`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure OAuth credentials in the test file
4. Update the credentials in `tests/test_grammarly.py`:
   - Replace placeholder values for `CLIENT_ID` and `CLIENT_SECRET`
5. Run tests: `python tests/test_grammarly.py`

## Common Use Cases

**Writing Quality Analysis:**
1. Submit documents for comprehensive quality analysis
2. Retrieve scores for engagement, correctness, delivery, and clarity
3. Use scores to track writing improvement over time
4. Automate quality checks for content before publication
5. Generate reports on writing quality metrics

**User Analytics & Reporting:**
1. Track team usage of Grammarly across date ranges
2. Monitor active days and session counts
3. Measure improvement rates across users
4. Track AI prompt usage for generative AI features
5. Generate usage reports for management

**AI Content Detection:**
1. Verify originality of submitted content
2. Detect AI-generated text in documents
3. Get confidence scores for AI detection
4. Track percentage of AI-generated content
5. Ensure human-written content compliance

**Plagiarism Detection:**
1. Check documents for plagiarism before publication
2. Compare content against billions of sources
3. Get originality scores for submitted work
4. Identify matching content from external sources
5. Ensure academic integrity compliance

**Workflow Automation:**
1. Automated document quality checks in publishing workflows
2. Batch processing of documents for analysis
3. Scheduled analytics reports for team usage
4. Integration with content management systems
5. Compliance checking for submitted content

## Version History

- **1.0.0** - Initial release with 7 comprehensive actions
  - Writing Score API: analyze_writing_score, get_writing_score_results (2 actions)
  - Analytics API: get_user_analytics (1 action)
  - AI Detection API: analyze_ai_detection, get_ai_detection_results (2 actions)
  - Plagiarism Detection API: analyze_plagiarism_detection, get_plagiarism_detection_results (2 actions)
