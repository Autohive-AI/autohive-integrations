# Kajabi

Kajabi is an all-in-one platform for creating and selling online courses, memberships, and digital products. This integration provides 21 actions covering contacts, contact tags, contact notes, offers, courses, and blog posts.

## Auth Setup

1. Log in to your Kajabi account and go to **Settings > Integrations > API**.
2. Generate or copy your API key.
3. Add the API key to your Autohive connection under **API Key**.

> The Kajabi Public API requires a Pro plan or the API add-on ($25/mo).

## Actions

| Action | Description |
|--------|-------------|
| `list_contacts` | List contacts with optional search and pagination |
| `get_contact` | Retrieve a contact by ID |
| `create_contact` | Create a new contact |
| `update_contact` | Update an existing contact's details |
| `delete_contact` | Permanently delete a contact |
| `list_contact_tags` | List all contact tags |
| `get_contact_tag` | Retrieve a tag by ID |
| `add_tag_to_contact` | Add one or more tags to a contact |
| `remove_tag_from_contact` | Remove one or more tags from a contact |
| `list_contact_notes` | List notes for a contact |
| `get_contact_note` | Retrieve a contact note by ID |
| `create_contact_note` | Create a note on a contact |
| `update_contact_note` | Update the content of a contact note |
| `delete_contact_note` | Delete a contact note |
| `list_contact_offers` | List offers granted to a contact |
| `grant_offer_to_contact` | Grant a product offer to a contact |
| `revoke_offer_from_contact` | Revoke a product offer from a contact |
| `list_courses` | List all courses |
| `get_course` | Retrieve a course by ID |
| `list_blog_posts` | List all blog posts |
| `get_blog_post` | Retrieve a blog post by ID |

## API Info

- **Base URL:** `https://api.kajabi.com/v1`
- **Docs:** [developers.kajabi.com](https://developers.kajabi.com)
- **Auth:** Bearer token (API key)
- **Response format:** JSON:API (`application/vnd.api+json`)

## Troubleshooting

- **401 Unauthorized** - Check your API key is correct and has not been revoked.
- **403 Forbidden** - Your Kajabi plan may not include API access (requires Pro or add-on).
- **404 Not Found** - The resource ID does not exist or belongs to a different site.
