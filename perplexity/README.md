# Perplexity Search Integration for Autohive

Web search integration powered by Perplexity's AI search API. Get ranked, structured search results from billions of webpages with advanced filtering options.

## Description

This integration provides access to Perplexity's Search API, enabling AI agents and automation workflows to perform real-time web searches. It returns structured, ranked results optimized for AI consumption with comprehensive content extraction capabilities.

Key features include:
- Real-time web search across hundreds of billions of webpages
- Structured JSON results with titles, URLs, snippets, and dates
- Content depth control (quick, default, detailed extraction)
- Geographic filtering by country
- Multi-query support (up to 5 queries per request)
- Configurable result limits (1-20 results per query)

This integration uses the Perplexity Search API and provides robust error handling with clear user-facing error messages.

## Setup & Authentication

This integration requires a Perplexity API key set as an environment variable:

```bash
export PERPLEXITY_API_KEY="your-api-key-here"
```

Get your API key from [Perplexity API Settings](https://www.perplexity.ai/settings/api).

The integration automatically handles:
- API authentication via Bearer token
- Rate limiting (3 requests per second)
- Error handling for missing API key, insufficient credits, and invalid keys
- Content extraction optimization

## Actions

### search_web

Search the web using Perplexity's search API. Returns ranked, structured results with titles, URLs, snippets, and dates.

**Input Parameters:**
- `query` (required): Search query string or array of queries for multi-query search
- `max_results` (optional): Maximum number of results to return (1-20, default: 10)
- `content_depth` (optional): Content extraction depth
  - `"quick"` - Brief snippets (512 tokens per page)
  - `"default"` - Moderate content (2048 tokens per page)
  - `"detailed"` - Comprehensive content (8192 tokens per page)
- `country` (optional): Two-letter ISO country code for geographic filtering (e.g., "US", "GB", "DE")

**Output:**
- `results`: Array of search results with:
  - `title`: Page title
  - `url`: Full URL
  - `snippet`: Content excerpt
  - `date`: Publication date (may be null)
  - `last_updated`: Last update date (may be null)
- `id`: Unique request identifier
- `total_results`: Total number of results returned

**Example Usage:**

Basic search:
```
Search for "quantum computing breakthroughs 2025"
```

Multi-query search:
```
Search for "AI agents", "LLM developments", and "autonomous systems" using Perplexity
```

Detailed research:
```
Search for "comprehensive climate change solutions" with detailed content depth
```

Geographic filtering:
```
Search for "tech startups" in the US using Perplexity
```

## Rate Limits

- 3 requests per second
- 3 request burst capacity
- Tier-based limits (50-2000 requests per minute depending on API spending)

## Error Handling

The integration provides clear error messages for:
- Missing API key (PERPLEXITY_API_KEY not set)
- Rate limit exceeded (429 errors)
- Invalid API key (401 errors)
- Insufficient credits (403 errors)
- General API failures

## Use Cases

- Real-time web research for AI agents
- Competitive intelligence gathering
- Content research and curation
- Market research automation
- News monitoring and alerts
- Academic research compilation
- Product comparison research
- Customer support knowledge gathering

## Technical Details

- **API Endpoint**: `https://api.perplexity.ai/search`
- **Authentication**: Bearer token via `PERPLEXITY_API_KEY` environment variable
- **Response Format**: JSON
- **Pricing**: $5 per 1,000 requests
