# Reddit Integration

Connect your workflows to Reddit with this official Autohive integration. Search subreddit posts and engage with the Reddit community through automated comments.

## What You Can Do

- **Search Posts**: Find relevant posts across any subreddit with filtering options
- **Post Comments**: Automatically reply to posts or engage in comment threads
- **Gather Insights**: Extract post data including scores, comment counts, and timestamps

## Quick Setup

1. **Install the Integration**: Add the Reddit integration to your Autohive workspace
2. **Connect Your Account**: Authenticate with Reddit using OAuth (requires `read` and `submit` permissions)
3. **Start Automating**: Use the actions in your workflows immediately

## Available Actions

### Search Subreddit Posts

Find posts in any subreddit with customizable filters.

**Parameters:**
- `subreddit` (required): Subreddit name (without r/)
- `query` (optional): Search terms
- `sort`: `relevance`, `hot`, `top`, `new`, or `comments`
- `time_filter`: `all`, `day`, `week`, `month`, or `year`
- `limit`: Number of posts to return (1-100)

**Example Use Cases:**
- Monitor mentions of your brand across relevant subreddits
- Find trending posts in your industry
- Gather customer feedback from product-related discussions

### Post Comments

Reply to posts or join conversations automatically.

**Parameters:**
- `parent_id` (required): Post ID (`t3_abc123`) or comment ID (`t1_def456`)
- `text` (required): Your comment content

**Example Use Cases:**
- Provide customer support on product-related posts
- Share helpful resources on relevant discussions
- Engage with community feedback automatically

## Example Workflows

### Brand Monitoring
```
1. Search r/technology for mentions of "YourProduct"
2. Filter for posts with high engagement (>100 upvotes)
3. Post helpful response with product information
4. Send summary to your team via Slack
```

### Community Engagement
```
1. Search r/AskReddit for questions about your expertise
2. Filter for recent posts (<24 hours)
3. Post helpful answers automatically
4. Track engagement metrics in your dashboard
```

### Content Discovery
```
1. Search multiple subreddits for trending topics
2. Compile top posts into daily digest
3. Send curated content to your content team
4. Schedule follow-up posts based on trends
```

## Authentication Setup

This integration uses Reddit's OAuth system:

1. The integration will redirect you to Reddit for authorization
2. Grant permissions for `read` (view content) and `submit` (post comments)
3. You'll be redirected back to Autohive with access granted

**Note**: You need a verified Reddit account (confirmed email) to use this integration.

## Best Practices

### Respectful Automation
- Follow each subreddit's rules and guidelines
- Avoid spammy or repetitive comments
- Engage meaningfully with the community
- Respect rate limits (approximately 60 requests per minute)

### Content Guidelines
- Keep comments relevant and helpful
- Disclose when appropriate that responses are automated
- Monitor and moderate your automated interactions
- Have human oversight for sensitive discussions

### Performance Tips
- Use specific search terms to get more relevant results
- Set appropriate limits to avoid overwhelming your workflows

## Getting Parent IDs

To reply to posts or comments, you need the correct ID format:

- **Post IDs**: Start with `t3_` (e.g., `t3_abc123`)
- **Comment IDs**: Start with `t1_` (e.g., `t1_def456`)

These IDs are returned in the search results, or you can extract them from Reddit URLs.

## Troubleshooting

**Can't authenticate?**
- Ensure your Reddit account email is verified
- Check that you're granting the required permissions
- Try clearing browser cache and reconnecting

**Search returning no results?**
- Verify subreddit name spelling (case matters)
- Check if the subreddit is public and accessible
- Try broader search terms

**Comments not posting?**
- Confirm you have permission to post in that subreddit
- Check the parent ID format is correct
- Some subreddits have karma or account age requirements

## Support

Need help? Check out the [Autohive Documentation](https://docs.autohive.com) or contact support through your Autohive dashboard.
