# Supabase Integration for Autohive

Connects Autohive to Supabase for database operations, storage management, and user authentication administration.

## Description

This integration provides access to your Supabase project's database via PostgREST, storage buckets, and auth user management. It allows you to query and manipulate data in your PostgreSQL database, manage files in storage buckets, and administer authenticated users.

The integration uses the Supabase REST API with service role authentication and implements 15 actions covering database CRUD operations, storage management, and auth administration.

## Setup & Authentication

This integration uses **API Key** authentication with your Supabase project credentials.

### Required Credentials

- **Project URL (Host)**: Your Supabase project URL (e.g., `https://xxxx.supabase.co`)
- **Service Role Secret**: The `service_role` API key from your project settings

### Setup Steps

1. Log in to your [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project (or create a new one)
3. Go to **Project Settings** > **API**
4. Copy the **Project URL** from the "Project URL" section
5. Copy the **service_role** key from the "Project API keys" section (click to reveal)
6. Enter these values in the Autohive integration settings

**Important**: The `service_role` key bypasses Row Level Security (RLS). Keep it secure and never expose it client-side.

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields

## Actions (15 Total)

### Database Operations (5 actions)

#### `select_records`
Query records from a table with optional filtering, ordering, and pagination.

**Inputs:**
- `table` (required): Name of the table to query
- `select` (optional): Columns to select (default: * for all)
- `filters` (optional): Filter conditions as key-value pairs (e.g., `{"status": "eq.active", "age": "gt.18"}`)
- `order` (optional): Order by column (e.g., `created_at.desc`)
- `limit` (optional): Maximum number of records to return
- `offset` (optional): Number of records to skip (for pagination)

**Outputs:**
- `records`: Array of matching records
- `count`: Number of records returned
- `result`: Success status

**Filter Operators:**
- `eq.` - equals
- `neq.` - not equals
- `gt.` - greater than
- `gte.` - greater than or equal
- `lt.` - less than
- `lte.` - less than or equal
- `like.` - LIKE pattern match
- `ilike.` - case-insensitive LIKE
- `is.` - IS (for null/true/false)
- `in.` - IN list (e.g., `in.(a,b,c)`)

---

#### `insert_records`
Insert one or more records into a table.

**Inputs:**
- `table` (required): Name of the table to insert into
- `records` (required): Array of record objects to insert
- `return_records` (optional): Whether to return the inserted records (default: true)
- `on_conflict` (optional): Column(s) for upsert conflict resolution

**Outputs:**
- `records`: Inserted records (if return_records is true)
- `count`: Number of records inserted
- `result`: Success status

---

#### `update_records`
Update records in a table matching filter conditions.

**Inputs:**
- `table` (required): Name of the table to update
- `data` (required): Object with column-value pairs to update
- `filters` (required): Filter conditions to match records
- `return_records` (optional): Whether to return the updated records (default: true)

**Outputs:**
- `records`: Updated records (if return_records is true)
- `count`: Number of records updated
- `result`: Success status

---

#### `delete_records`
Delete records from a table matching filter conditions.

**Inputs:**
- `table` (required): Name of the table to delete from
- `filters` (required): Filter conditions to match records
- `return_records` (optional): Whether to return the deleted records (default: false)

**Outputs:**
- `records`: Deleted records (if return_records is true)
- `count`: Number of records deleted
- `result`: Success status

---

#### `call_function`
Call a PostgreSQL function (RPC) with optional parameters.

**Inputs:**
- `function_name` (required): Name of the function to call
- `params` (optional): Parameters to pass to the function

**Outputs:**
- `data`: Function return value
- `result`: Success status

---

### Storage Operations (7 actions)

#### `list_buckets`
List all storage buckets in the project.

**Inputs:** None

**Outputs:**
- `buckets`: List of storage buckets
- `result`: Success status

---

#### `get_bucket`
Get details of a specific storage bucket.

**Inputs:**
- `bucket_id` (required): ID of the bucket

**Outputs:**
- `bucket`: Bucket details
- `result`: Success status

---

#### `create_bucket`
Create a new storage bucket.

**Inputs:**
- `name` (required): Name of the bucket (must be unique)
- `public` (optional): Whether the bucket is publicly accessible (default: false)
- `file_size_limit` (optional): Maximum file size in bytes
- `allowed_mime_types` (optional): Array of allowed MIME types

**Outputs:**
- `bucket`: Created bucket details
- `result`: Success status

---

#### `delete_bucket`
Delete a storage bucket (must be empty).

**Inputs:**
- `bucket_id` (required): ID of the bucket to delete

**Outputs:**
- `deleted`: Whether the bucket was deleted
- `result`: Success status

---

#### `list_files`
List files in a storage bucket.

**Inputs:**
- `bucket_id` (required): ID of the bucket
- `path` (optional): Folder path within the bucket
- `limit` (optional): Maximum number of files to return
- `offset` (optional): Number of files to skip
- `search` (optional): Search string to filter files

**Outputs:**
- `files`: List of files and folders
- `result`: Success status

---

#### `delete_files`
Delete one or more files from a storage bucket.

**Inputs:**
- `bucket_id` (required): ID of the bucket
- `paths` (required): Array of file paths to delete

**Outputs:**
- `deleted`: List of deleted file paths
- `result`: Success status

---

#### `get_public_url`
Get the public URL for a file in a public bucket.

**Inputs:**
- `bucket_id` (required): ID of the bucket
- `path` (required): Path to the file within the bucket

**Outputs:**
- `public_url`: Public URL of the file
- `result`: Success status

---

### Auth Administration (3 actions)

#### `list_users`
List all authenticated users (requires service_role).

**Inputs:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Users per page (default: 50, max: 1000)

**Outputs:**
- `users`: List of user objects
- `total`: Total number of users
- `result`: Success status

---

#### `get_user`
Get a user by their ID.

**Inputs:**
- `user_id` (required): The user's UUID

**Outputs:**
- `user`: User details
- `result`: Success status

---

#### `delete_user`
Delete a user by their ID.

**Inputs:**
- `user_id` (required): The user's UUID

**Outputs:**
- `deleted`: Whether the user was deleted
- `result`: Success status

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK

## API Information

- **Database API**: PostgREST (`/rest/v1/`)
- **Storage API**: Storage v1 (`/storage/v1/`)
- **Auth API**: GoTrue (`/auth/v1/admin/`)
- **Authentication**: API Key (service_role)
- **Documentation**: https://supabase.com/docs

## Important Notes

- **Service Role Key**: The `service_role` key bypasses Row Level Security (RLS). Use with caution.
- **Filter Syntax**: Filters use PostgREST operators (e.g., `eq.`, `gt.`, `like.`)
- **Upsert**: Use `on_conflict` parameter in `insert_records` to enable upsert behavior.
- **Storage Buckets**: Buckets must be empty before deletion.

## Common Use Cases

**Database Operations:**
- Query and filter records from any table
- Insert single or bulk records
- Update records with conditional filters
- Delete records safely with filters
- Call stored procedures and functions

**Storage Management:**
- Create and manage storage buckets
- List and search files in buckets
- Generate public URLs for public files
- Delete files and empty buckets

**User Administration:**
- List all authenticated users with pagination
- Look up specific users by ID
- Delete user accounts

## Version History

- **1.0.0** - Initial release with 15 actions
  - Database: select, insert, update, delete, call_function (5 actions)
  - Storage: list/get/create/delete buckets, list/delete files, get public URL (7 actions)
  - Auth: list/get/delete users (3 actions)

## Sources

- [Supabase Documentation](https://supabase.com/docs)
- [PostgREST Documentation](https://postgrest.org/en/stable/)
- [Supabase Storage API](https://supabase.com/docs/guides/storage)
- [Supabase Auth Admin API](https://supabase.com/docs/reference/javascript/auth-admin-listusers)
