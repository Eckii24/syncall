"""NotionDbSide - Notion Database synchronization side."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Sequence, cast

from bubop import logger, parse_datetime

if TYPE_CHECKING:
    from notion_client import Client

from syncall.sync_side import ItemType, SyncSide
from syncall.types import NotionID


class StatusMappingKind(str, Enum):
    """Enum for status mapping types."""

    STATUS_PROP = "status_prop"
    SELECT = "select"
    CHECKBOX = "checkbox"


class ProjectMappingKind(str, Enum):
    """Enum for project mapping types."""

    SELECT = "select"
    MULTI_SELECT = "multi_select"
    RELATION = "relation"


@dataclass
class NotionSideConfig:
    """Configuration for NotionDbSide schema mapping.

    This structure holds the dynamic parameters for mapping Notion database
    properties to internal item representation.
    """

    map_field_title: str = "Name"
    """The name of the Title property in Notion."""

    map_field_status: str = "Status"
    """The name of the property tracking completion."""

    map_field_due: str = "Due Date"
    """The name of the property tracking the deadline."""

    map_field_project: str | None = None
    """(Optional) The name of the property tracking the project."""

    map_field_priority: str | None = None
    """(Optional) The name of the property tracking the priority."""

    map_field_url: str | None = None
    """(Optional) Property to store the URL/Link if needed."""

    status_mapping_kind: StatusMappingKind = StatusMappingKind.STATUS_PROP
    """Defines how status is stored: checkbox, select, or status_prop."""

    project_mapping_kind: ProjectMappingKind = ProjectMappingKind.SELECT
    """Defines how project is stored: select, multi_select, or relation."""

    status_map: dict[str, str] = field(default_factory=dict)
    """Mapping from TaskWarrior status (pending/completed) to Notion select values."""

    priority_map: dict[str, str] = field(default_factory=dict)
    """Mapping from TaskWarrior priority (H/M/L) to Notion select values."""

    def __post_init__(self):
        """Initialize default values after dataclass initialization."""
        if not self.status_map:
            self.status_map = {"pending": "Not started", "completed": "Done"}
        if not self.priority_map:
            self.priority_map = {"H": "High", "M": "Medium", "L": "Low"}


# Default configuration instance
DEFAULT_CONFIG = NotionSideConfig()


class NotionDbSide(SyncSide):
    """Wrapper class for Notion Database synchronization.

    This class implements bidirectional synchronization between a Notion Database
    and the syncall internal Item representation. It's designed to be schema-agnostic,
    allowing all column names and mappings to be configurable.
    """

    def __init__(
        self,
        client: Client,
        database_id: str,
        config: NotionSideConfig | None = None,
    ):
        """Initialize NotionDbSide.

        :param client: Authenticated Notion client
        :param database_id: ID of the Notion database to sync
        :param config: Configuration for schema mapping (uses defaults if not provided)
        """
        super().__init__(name="NotionDb", fullname="Notion Database")
        self._client = client
        self._database_id = database_id
        self._config = config or DEFAULT_CONFIG
        self._items_cache: dict[NotionID, ItemType] = {}
        self._is_cached = False

    @classmethod
    def id_key(cls) -> str:
        """Return the key for item ID."""
        return "id"

    @classmethod
    def summary_key(cls) -> str:
        """Return the key for item summary/description."""
        return "description"

    @classmethod
    def last_modification_key(cls) -> str:
        """Return the key for last modification timestamp."""
        return "last_edited_time"

    def _parse_title_property(self, properties: dict) -> str:
        """Parse the title property from Notion page properties.

        :param properties: Page properties dictionary
        :return: Concatenated plain text from title rich text array
        """
        title_prop = properties.get(self._config.map_field_title, {})
        if not title_prop or "title" not in title_prop:
            logger.warning(
                f"Title property '{self._config.map_field_title}' not found or empty",
            )
            return "(No Title)"

        rich_text_array = title_prop["title"]
        if not rich_text_array:
            return "(No Title)"

        return "".join(rt.get("plain_text", "") for rt in rich_text_array)

    def _parse_status_property(self, properties: dict) -> bool:
        """Parse the status property to determine if item is completed.

        :param properties: Page properties dictionary
        :return: True if completed, False otherwise
        """
        status_prop = properties.get(self._config.map_field_status, {})
        if not status_prop:
            return False

        # Determine the property type and parse accordingly
        prop_type = status_prop.get("type")

        if (
            prop_type == "status"
            or self._config.status_mapping_kind == StatusMappingKind.STATUS_PROP
        ):
            # Native Status Property
            status_value = status_prop.get("status", {}).get("name", "")
            completed_value = self._config.status_map.get("completed", "")
            return bool(status_value == completed_value)

        elif (
            prop_type == "select"
            or self._config.status_mapping_kind == StatusMappingKind.SELECT
        ):
            # Select/Dropdown
            select_value = status_prop.get("select")
            if select_value:
                status_name = select_value.get("name", "")
                completed_value = self._config.status_map.get("completed", "")
                return bool(status_name == completed_value)
            return False

        elif (
            prop_type == "checkbox"
            or self._config.status_mapping_kind == StatusMappingKind.CHECKBOX
        ):
            # Checkbox
            checkbox_value = status_prop.get("checkbox", False)
            return bool(checkbox_value)

        logger.warning(f"Unknown status property type: {prop_type}")
        return False

    def _parse_due_property(self, properties: dict) -> datetime.datetime | None:
        """Parse the due date property.

        :param properties: Page properties dictionary
        :return: datetime object or None
        """
        due_prop = properties.get(self._config.map_field_due, {})
        if not due_prop or "date" not in due_prop:
            return None

        date_value = due_prop["date"]
        if not date_value:
            return None

        start_date = date_value.get("start")
        if not start_date:
            return None

        return parse_datetime(start_date)

    def _parse_project_property(self, properties: dict) -> str | None:
        """Parse the project property.

        :param properties: Page properties dictionary
        :return: Project name or None
        """
        if not self._config.map_field_project:
            return None

        project_prop = properties.get(self._config.map_field_project, {})
        if not project_prop:
            return None

        prop_type = project_prop.get("type")

        if (
            prop_type == "select"
            or self._config.project_mapping_kind == ProjectMappingKind.SELECT
        ):
            # Select dropdown
            select_value = project_prop.get("select")
            if select_value:
                name = select_value.get("name")
                return str(name) if name else None
            return None

        elif (
            prop_type == "multi_select"
            or self._config.project_mapping_kind == ProjectMappingKind.MULTI_SELECT
        ):
            # Multi-select - take first value
            multi_select_values = project_prop.get("multi_select", [])
            if multi_select_values:
                name = multi_select_values[0].get("name")
                return str(name) if name else None
            return None

        elif (
            prop_type == "relation"
            or self._config.project_mapping_kind == ProjectMappingKind.RELATION
        ):
            # Relation - we need to fetch the related page to get its title
            # For now, we'll store the relation ID and handle it in a future update
            # This requires additional API calls which we'll implement
            relation_values = project_prop.get("relation", [])
            if relation_values:
                # Return the ID for now - ideally we'd fetch the title
                rel_id = relation_values[0].get("id")
                return str(rel_id) if rel_id else None
            return None

        logger.warning(f"Unknown project property type: {prop_type}")
        return None

    def _parse_priority_property(self, properties: dict) -> str | None:
        """Parse the priority property.

        :param properties: Page properties dictionary
        :return: TaskWarrior priority (H/M/L) or None
        """
        if not self._config.map_field_priority:
            return None

        priority_prop = properties.get(self._config.map_field_priority, {})
        if not priority_prop:
            return None

        # Priority is expected to be a Select property
        select_value = priority_prop.get("select")
        if not select_value:
            return None

        notion_priority = select_value.get("name", "")

        # Reverse lookup in priority map to convert Notion value to TW value
        for tw_priority, notion_value in self._config.priority_map.items():
            if notion_value == notion_priority:
                return tw_priority

        logger.warning(
            f"Unknown priority value: {notion_priority}, not in mapping"
            f" {self._config.priority_map}"
        )
        return None

    def _create_title_property(self, title: str) -> dict:
        """Create a title property for Notion API.

        :param title: Text content for the title
        :return: Property dictionary
        """
        return {"title": [{"text": {"content": title}}]}

    def _create_status_property(self, is_completed: bool) -> dict:
        """Create a status property for Notion API.

        :param is_completed: Whether the item is completed
        :return: Property dictionary
        """
        status_value = (
            self._config.status_map.get("completed")
            if is_completed
            else self._config.status_map.get("pending")
        )

        if self._config.status_mapping_kind == StatusMappingKind.STATUS_PROP:
            # Native Status Property
            return {"status": {"name": status_value}}

        elif self._config.status_mapping_kind == StatusMappingKind.SELECT:
            # Select/Dropdown
            return {"select": {"name": status_value}}

        elif self._config.status_mapping_kind == StatusMappingKind.CHECKBOX:
            # Checkbox
            return {"checkbox": is_completed}

        # Default to status property
        return {"status": {"name": status_value}}

    def _create_due_property(self, due: datetime.datetime | None) -> dict:
        """Create a due date property for Notion API.

        :param due: Due date or None to clear
        :return: Property dictionary
        """
        if due is None:
            return {"date": None}
        return {"date": {"start": due.isoformat()}}

    def _create_project_property(self, project: str | None) -> dict | None:
        """Create a project property for Notion API.

        :param project: Project name or None
        :return: Property dictionary or None if no project
        """
        if not project or not self._config.map_field_project:
            return None

        if self._config.project_mapping_kind == ProjectMappingKind.SELECT:
            return {"select": {"name": project}}

        elif self._config.project_mapping_kind == ProjectMappingKind.MULTI_SELECT:
            return {"multi_select": [{"name": project}]}

        elif self._config.project_mapping_kind == ProjectMappingKind.RELATION:
            # For relation, we would need to search for the page by title
            # This requires additional API calls and database ID of the related database
            # For now, we'll log a warning
            logger.warning(
                "Relation project mapping not yet fully implemented - requires page lookup"
            )
            return None

        return None

    def _create_priority_property(self, priority: str | None) -> dict | None:
        """Create a priority property for Notion API.

        :param priority: TaskWarrior priority (H/M/L) or None
        :return: Property dictionary or None if no priority
        """
        if not priority or not self._config.map_field_priority:
            return None

        # Map TW priority to Notion select value
        notion_priority = self._config.priority_map.get(priority)
        if not notion_priority:
            logger.warning(
                f"Unknown TaskWarrior priority: {priority}, not in mapping"
                f" {self._config.priority_map}"
            )
            return None

        return {"select": {"name": notion_priority}}

    def _page_to_item(self, page: dict) -> ItemType:
        """Convert a Notion page to an internal item representation.

        :param page: Notion page object from API
        :return: Item dictionary
        """
        properties = page.get("properties", {})

        # Parse last_edited_time
        last_edited_str = page.get("last_edited_time", "")
        last_edited = (
            parse_datetime(last_edited_str)
            if last_edited_str
            else datetime.datetime.now(datetime.timezone.utc)
        )

        item: dict[str, Any] = {
            "id": page["id"],
            "description": self._parse_title_property(properties),
            "status": "completed" if self._parse_status_property(properties) else "pending",
            "last_edited_time": last_edited,
        }

        # Add due date if present
        due_date = self._parse_due_property(properties)
        if due_date:
            item["due"] = due_date

        # Add project if present
        project = self._parse_project_property(properties)
        if project:
            item["project"] = project

        # Add priority if present
        priority = self._parse_priority_property(properties)
        if priority:
            item["priority"] = priority

        return item

    def get_all_items(self, **kargs) -> Sequence[ItemType]:
        """Query the Notion database and return all items.

        Implements pagination to handle databases with >100 items.

        :param kargs: Extra options for the call
        :return: List of items
        """
        del kargs

        all_items: list[ItemType] = []
        has_more = True
        start_cursor = None

        try:
            while has_more:
                query_params: dict[str, Any] = {
                    "database_id": self._database_id,
                }
                if start_cursor:
                    query_params["start_cursor"] = start_cursor

                response: dict[str, Any] = self._client.databases.query(**query_params)  # type: ignore

                # Process results
                for page in response.get("results", []):
                    # Skip archived pages
                    if page.get("archived", False):
                        continue

                    try:
                        item = self._page_to_item(page)
                        all_items.append(item)
                    except Exception as e:
                        logger.warning(f"Failed to parse page {page.get('id')}: {e}")
                        continue

                # Check for more pages
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

        except Exception as e:
            logger.error(f"Error querying Notion database: {e}")
            raise

        # Update cache
        self._items_cache = {cast(NotionID, item["id"]): item for item in all_items}
        self._is_cached = True

        return all_items

    def get_item(self, item_id: NotionID, use_cached: bool = False) -> ItemType | None:
        """Get a single item based on the given UUID.

        :param item_id: Notion page ID
        :param use_cached: False if you want to fetch the latest version
        :return: None if not found, the item in dict representation otherwise
        """
        if use_cached and item_id in self._items_cache:
            return self._items_cache[item_id]

        try:
            page: dict[str, Any] = self._client.pages.retrieve(page_id=item_id)  # type: ignore
            if page.get("archived", False):
                raise KeyError(f"Page {item_id} is archived")

            item = self._page_to_item(page)
            self._items_cache[item_id] = item
            return item

        except Exception as e:
            logger.debug(f"Failed to retrieve page {item_id}: {e}")
            raise KeyError(f"Page {item_id} not found") from e

    def delete_single_item(self, item_id: NotionID):
        """Delete an item by archiving it.

        Notion doesn't support true deletion via API, so we archive instead.

        :param item_id: Notion page ID to archive
        """
        try:
            self._client.pages.update(page_id=item_id, archived=True)
            # Remove from cache
            self._items_cache.pop(item_id, None)
        except Exception as e:
            logger.error(f"Failed to archive page {item_id}: {e}")
            raise KeyError(f"Failed to delete item {item_id}") from e

    def update_item(self, item_id: NotionID, **changes):
        """Update an item with the given changes.

        :param item_id: ID of item to update
        :param changes: Keyword parameters that are to change in the item
        """
        properties: dict[str, Any] = {}

        # Map changes to Notion properties
        if "description" in changes:
            properties[self._config.map_field_title] = self._create_title_property(
                changes["description"],
            )

        if "status" in changes:
            is_completed = changes["status"] == "completed"
            properties[self._config.map_field_status] = self._create_status_property(
                is_completed,
            )

        if "due" in changes:
            properties[self._config.map_field_due] = self._create_due_property(
                changes.get("due"),
            )

        if "project" in changes and self._config.map_field_project:
            project_prop = self._create_project_property(changes.get("project"))
            if project_prop:
                properties[self._config.map_field_project] = project_prop

        if "priority" in changes and self._config.map_field_priority:
            priority_prop = self._create_priority_property(changes.get("priority"))
            if priority_prop:
                properties[self._config.map_field_priority] = priority_prop

        if not properties:
            logger.warning(f"No valid properties to update for item {item_id}")
            return

        try:
            self._client.pages.update(page_id=item_id, properties=properties)
            # Invalidate cache for this item
            self._items_cache.pop(item_id, None)
        except Exception as e:
            logger.error(f"Failed to update page {item_id}: {e}")
            raise

    def add_item(self, item: ItemType) -> ItemType:
        """Add a new item to the database.

        :param item: Item to add
        :return: The newly added item with Notion-assigned ID
        """
        properties: dict[str, Any] = {}

        # Title (required for most databases)
        properties[self._config.map_field_title] = self._create_title_property(
            item.get("description", "(No Title)"),
        )

        # Status
        if "status" in item:
            is_completed = item["status"] == "completed"
            properties[self._config.map_field_status] = self._create_status_property(
                is_completed,
            )

        # Due date
        if "due" in item:
            properties[self._config.map_field_due] = self._create_due_property(item["due"])

        # Project
        if "project" in item and self._config.map_field_project:
            project_prop = self._create_project_property(item.get("project"))
            if project_prop:
                properties[self._config.map_field_project] = project_prop

        # Priority
        if "priority" in item and self._config.map_field_priority:
            priority_prop = self._create_priority_property(item.get("priority"))
            if priority_prop:
                properties[self._config.map_field_priority] = priority_prop

        try:
            response: dict[str, Any] = self._client.pages.create(  # type: ignore
                parent={"database_id": self._database_id},
                properties=properties,
            )

            # Return fresh item parsed from response
            new_item = self._page_to_item(response)
            self._items_cache[cast(NotionID, new_item["id"])] = new_item
            return new_item

        except Exception as e:
            logger.error(f"Failed to create page: {e}")
            raise

    @classmethod
    def items_are_identical(
        cls,
        item1: ItemType,
        item2: ItemType,
        ignore_keys: Sequence[str] | None = None,
    ) -> bool:
        """Determine whether two items are identical.

        :param item1: First item
        :param item2: Second item
        :param ignore_keys: Keys to ignore in comparison
        :return: True if items are identical, False otherwise
        """
        if ignore_keys is None:
            ignore_keys = []

        # Compare relevant keys
        keys_to_compare = ["description", "status", "due"]
        keys_to_compare = [k for k in keys_to_compare if k not in ignore_keys]

        return cls._items_are_identical(item1, item2, keys_to_compare)
