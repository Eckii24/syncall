# [Taskwarrior](https://taskwarrior.org/) ⬄ [Notion](https://notion.so) Databases

## Description

Synchronize tasks between a Notion Database and Taskwarrior with configurable schema mapping. Unlike `tw_notion_sync` which syncs to_do blocks within a page, `tw_notion_db_sync` synchronizes with database pages, providing more flexibility and structure.

Upon execution, `tw_notion_db_sync` will synchronize, and on subsequent runs keep synchronized, the following attributes:

- Notion database page Title property <-> TW task description
- Notion Status/Select/Checkbox property <-> TW task completion status
- Notion Date property <-> TW task due date
- Notion Project property (Select/Multi-select/Relation) <-> TW task project
- Notion Priority property (Select) <-> TW task priority (H/M/L)
- Page is archived <-> TW task deletion

## Key Features

- **Schema Agnostic**: All column names are configurable via CLI options
- **Type Flexible**: Supports Status, Select, or Checkbox properties for completion tracking
- **Project Support**: Syncs with Select, Multi-select, or Relation properties for projects
- **Priority Mapping**: Configurable priority mapping between TaskWarrior (H/M/L) and Notion select values
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
  --status-map "completed:Complete" \
  --status-map "pending:In Progress"
```

For databases using a Checkbox:

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --status-kind checkbox
```

Note: Default status mapping is `pending:Not started`, `completed:Done` if not specified.

### Project Synchronization

Sync with a Project column using Select property:

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --map-project "Project" \
  --project-kind select
```

For Multi-select project column:

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --map-project "Projects" \
  --project-kind multi_select
```

For Relation project column (stores relation ID):

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --map-project "Project" \
  --project-kind relation
```

### Priority Synchronization

Sync with custom priority mappings:

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --map-priority "Priority" \
  --priority-map "H:High" \
  --priority-map "M:Medium" \
  --priority-map "L:Low"
```

Note: Default priority mapping is `H:High`, `M:Medium`, `L:Low` if not specified.

### Complete Example with All Fields

```sh
tw_notion_db_sync \
  --database-id <database-uuid> \
  -t mytasks \
  --map-title "Task" \
  --map-status "Status" \
  --map-due "Due Date" \
  --map-project "Project" \
  --map-priority "Priority" \
  --status-kind status_prop \
  --status-map "completed:Done" \
  --status-map "pending:Not started" \
  --project-kind select \
  --priority-map "H:🔴 High" \
  --priority-map "M:🟡 Medium" \
  --priority-map "L:🟢 Low"
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
- `--map-project`: Notion column name for the Project property (optional)
- `--map-priority`: Notion column name for the Priority property (optional)
- `--status-kind`: Type of status property - `status_prop`, `select`, or `checkbox` (default: "status_prop")
- `--project-kind`: Type of project property - `select`, `multi_select`, or `relation` (default: "select")
- `--status-map`: Status mapping in format "TW_STATUS:NOTION_VALUE" (e.g., "completed:Done", "pending:Not started"). Can be specified multiple times. Default: pending:Not started, completed:Done
- `--priority-map`: Priority mapping in format "TW_PRIORITY:NOTION_VALUE" (e.g., "H:High"). Can be specified multiple times. Default: H:High, M:Medium, L:Low

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

Optionally, you can add:

- A **Date** property for due dates
- A **Select/Multi-select/Relation** property for projects
- A **Select** property for priority

Example database structure:

| Name (Title) | Status (Status) | Due Date (Date) | Project (Select) | Priority (Select) |
|--------------|-----------------|-----------------|------------------|-------------------|
| Task 1       | Not started     | 2024-01-15      | Work             | High              |
| Task 2       | Done            | 2024-01-20      | Personal         | Medium            |

### Priority Values

The priority property should be a Select field in Notion with values corresponding to TaskWarrior priorities:

- **H** (High) - Default maps to "High"
- **M** (Medium) - Default maps to "Medium"  
- **L** (Low) - Default maps to "Low"

You can customize these mappings using the `--priority-map` option.

### Project Property Types

The project property can be one of three types:

1. **Select**: Single project selection (recommended)
2. **Multi-select**: Multiple projects (only first project is synced to TW)
3. **Relation**: Related to another database (stores relation ID)

## Notes on this Synchronization

- The Title property in Notion must be of type "Title"
- The Status property can be:
  - Native Status property (recommended)
  - Select/Multi-select dropdown
  - Checkbox
- Date properties should be of type "Date" in Notion
- Project property can be:
  - Select (recommended)
  - Multi-select (only first value is synced)
  - Relation (stores relation ID, not title)
- Priority property should be a Select field with customizable value mappings
- Archived pages in Notion are treated as deleted tasks in Taskwarrior
- When a Taskwarrior task is deleted, the corresponding Notion page is archived (not permanently deleted)
- TaskWarrior priority values (H/M/L) are mapped to Notion select values via `--priority-map` option

## See also

- <a href="https://github.com/bergercookie/syncall/blob/master/docs/taskwarrior-filtering.md">Taskwarrior Filtering.md</a>
- <a href="https://github.com/bergercookie/syncall/blob/master/docs/readme-tw-notion.md">TW-Notion (Page Blocks) Sync</a>
