# [Taskwarrior](https://taskwarrior.org/) ⬄ [Notion](https://notion.so) Databases

## Description

Synchronize tasks between a Notion Database and Taskwarrior with configurable schema mapping. Unlike `tw_notion_sync` which syncs to_do blocks within a page, `tw_notion_db_sync` synchronizes with database pages, providing more flexibility and structure.

Upon execution, `tw_notion_db_sync` will synchronize, and on subsequent runs keep synchronized, the following attributes:

- Notion database page Title property <-> TW task description
- Notion Status/Select/Checkbox property <-> TW task completion status
- Notion Date property <-> TW task due date
- Page is archived <-> TW task deletion

## Key Features

- **Schema Agnostic**: All column names are configurable via CLI options
- **Type Flexible**: Supports Status, Select, or Checkbox properties for completion tracking
- **Sensible Defaults**: Uses standard Notion template naming conventions ("Name", "Status", "Due Date")
- **Pagination Support**: Efficiently handles databases with >100 items

## Usage Examples

### Basic Synchronization

Synchronize a Notion database with a Taskwarrior tag using default field mappings:

```sh
tw_notion_db_sync --database-id <database-uuid> -t mytasks
```

### Custom Field Mapping

Customize which Notion columns map to task properties:

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --map-title "Task Name" \
  --map-status "State" \
  --map-due "Deadline"
```

### Different Status Property Types

For databases using a Select dropdown instead of Status property:

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --status-kind select \
  --status-done "Complete" \
  --status-done "Finished"
```

For databases using a Checkbox:

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --status-kind checkbox
```

### Sync with Project

Synchronize with a Taskwarrior project instead of tags:

```sh
tw_notion_db_sync --database-id <database-uuid> -p "My Project"
```

## Installation

### Package Installation

Install the `syncall` package from PyPI, enabling the `notion` and `tw` extras:

```sh
pip3 install syncall[notion,tw]
```

### Create a Notion Integration

After installing the python package, you have to create an integration at Notion. This is a mandatory step since this is not an official Notion integration.

1. Navigate to your [Integrations](https://www.notion.so/my-integrations)
2. Create a new integration and copy the API token
3. The name of the integration does not matter
4. Give the integration access to the database you want to sync:
   - Open the database in Notion
   - Click the three dots (...) menu at the top right
   - Go to "Connections" or "Add connections"
   - Select your integration

### Finding the Database ID

You can find the database ID from the database URL:

```
https://www.notion.so/<workspace>/<database-id>?v=...
```

The `<database-id>` is the 32-character hexadecimal string between the workspace name and the `?v=` parameter.

### Reading the Notion Integration Token

There are two ways `tw_notion_db_sync` can read the API token:

- Via the `NOTION_API_KEY` environment variable, or
- Via the [UNIX Password Manager](https://wiki.archlinux.org/title/Pass). You can specify the path in the Pass manager to read the encrypted token from using the `--token-pass-path` option.

  The latter will run `gpg` in the background and assumes that you are using a gpg-agent, otherwise it will ask you for your GPG password.

## Configuration

### CLI Options

- `--database-id`: (Required) The UUID of the Notion database
- `--map-title`: Notion column name for the Title property (default: "Name")
- `--map-status`: Notion column name for the Status property (default: "Status")
- `--map-due`: Notion column name for the Due Date property (default: "Due Date")
- `--status-kind`: Type of status property - `status_prop`, `select`, or `checkbox` (default: "status_prop")
- `--status-done`: Value(s) considered as completed (can be specified multiple times, default: "Done")
- `--status-todo`: Value(s) considered as pending (can be specified multiple times, default: "Not started")

### Saving Configurations

You can save your configuration for repeated syncs:

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --map-title "Task Name" \
  --custom-combination-savename my-notion-sync
```

Then reuse it:

```sh
tw_notion_db_sync --combination my-notion-sync
```

## Notion Database Setup

Your Notion database should have at minimum:

- A **Title** property (any name you choose)
- A **Status/Select/Checkbox** property for tracking completion
- Optionally, a **Date** property for due dates

Example database structure:

| Name (Title) | Status (Status) | Due Date (Date) |
|--------------|-----------------|-----------------|
| Task 1       | Not started     | 2024-01-15      |
| Task 2       | Done            | 2024-01-20      |

## Notes on this Synchronization

- The Title property in Notion must be of type "Title"
- The Status property can be:
  - Native Status property (recommended)
  - Select/Multi-select dropdown
  - Checkbox
- Date properties should be of type "Date" in Notion
- Archived pages in Notion are treated as deleted tasks in Taskwarrior
- When a Taskwarrior task is deleted, the corresponding Notion page is archived (not permanently deleted)

## See also

- <a href="https://github.com/bergercookie/syncall/blob/master/docs/taskwarrior-filtering.md">Taskwarrior Filtering.md</a>
- <a href="https://github.com/bergercookie/syncall/blob/master/docs/readme-tw-notion.md">TW-Notion (Page Blocks) Sync</a>
