"""Tests for NotionDbSide implementation."""
import datetime
from unittest.mock import Mock, MagicMock

import pytest
from dateutil.tz import tzutc

from syncall.notion.notion_db_side import (
    NotionDbSide,
    NotionSideConfig,
    ProjectMappingKind,
    StatusMappingKind,
)


@pytest.fixture
def mock_client():
    """Create a mock Notion client."""
    return Mock()


@pytest.fixture
def notion_db_page_status_prop():
    """Sample Notion database page with status property."""
    return {
        "id": "test-page-id-1",
        "archived": False,
        "last_edited_time": "2021-12-04T10:01:00.000Z",
        "properties": {
            "Name": {
                "id": "title",
                "type": "title",
                "title": [
                    {
                        "type": "text",
                        "text": {"content": "Test Task"},
                        "plain_text": "Test Task",
                    }
                ],
            },
            "Status": {
                "id": "status",
                "type": "status",
                "status": {"name": "Not started"},
            },
            "Due Date": {
                "id": "due",
                "type": "date",
                "date": {"start": "2021-12-10T00:00:00.000Z"},
            },
        },
    }


@pytest.fixture
def notion_db_page_completed():
    """Sample Notion database page with completed status."""
    return {
        "id": "test-page-id-2",
        "archived": False,
        "last_edited_time": "2021-12-05T15:30:00.000Z",
        "properties": {
            "Name": {
                "id": "title",
                "type": "title",
                "title": [
                    {
                        "type": "text",
                        "text": {"content": "Completed Task"},
                        "plain_text": "Completed Task",
                    }
                ],
            },
            "Status": {
                "id": "status",
                "type": "status",
                "status": {"name": "Done"},
            },
            "Due Date": {"id": "due", "type": "date", "date": None},
        },
    }


def test_notion_db_side_init(mock_client):
    """Test NotionDbSide initialization."""
    side = NotionDbSide(mock_client, "test-db-id")
    assert side.name == "NotionDb"
    assert side.fullname == "Notion Database"
    assert side._database_id == "test-db-id"
    # Test that default config is applied
    assert side._config.map_field_title == "Name"
    assert side._config.status_map == {"pending": ["Not started"], "completed": ["Done"]}


def test_notion_side_config_defaults():
    """Test NotionSideConfig default initialization."""
    config = NotionSideConfig()
    assert config.status_map == {"pending": ["Not started"], "completed": ["Done"]}
    assert config.map_field_title == "Name"
    assert config.status_mapping_kind == StatusMappingKind.STATUS_PROP


def test_notion_db_side_with_custom_config(mock_client):
    """Test NotionDbSide with custom configuration."""
    config = NotionSideConfig(
        map_field_title="Task Name",
        map_field_status="State",
        map_field_due="Deadline",
        status_map={"pending": ["To Do", "In Progress"], "completed": ["Complete", "Done"]},
        status_mapping_kind=StatusMappingKind.SELECT,
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)
    assert side._config.map_field_title == "Task Name"
    assert side._config.map_field_status == "State"
    assert side._config.status_mapping_kind == StatusMappingKind.SELECT


def test_parse_title_property(mock_client, notion_db_page_status_prop):
    """Test parsing title property."""
    side = NotionDbSide(mock_client, "test-db-id")
    title = side._parse_title_property(notion_db_page_status_prop["properties"])
    assert title == "Test Task"


def test_parse_title_property_empty(mock_client):
    """Test parsing empty title property."""
    side = NotionDbSide(mock_client, "test-db-id")
    props = {"Name": {"title": []}}
    title = side._parse_title_property(props)
    assert title == "(No Title)"


def test_parse_status_property_not_started(mock_client, notion_db_page_status_prop):
    """Test parsing status property with 'Not started' value."""
    side = NotionDbSide(mock_client, "test-db-id")
    is_completed = side._parse_status_property(notion_db_page_status_prop["properties"])
    assert is_completed is False


def test_parse_status_property_done(mock_client, notion_db_page_completed):
    """Test parsing status property with 'Done' value."""
    side = NotionDbSide(mock_client, "test-db-id")
    is_completed = side._parse_status_property(notion_db_page_completed["properties"])
    assert is_completed is True


def test_parse_due_property(mock_client, notion_db_page_status_prop):
    """Test parsing due date property."""
    side = NotionDbSide(mock_client, "test-db-id")
    due = side._parse_due_property(notion_db_page_status_prop["properties"])
    assert due is not None
    assert isinstance(due, datetime.datetime)


def test_parse_due_property_none(mock_client, notion_db_page_completed):
    """Test parsing None due date property."""
    side = NotionDbSide(mock_client, "test-db-id")
    due = side._parse_due_property(notion_db_page_completed["properties"])
    assert due is None


def test_page_to_item(mock_client, notion_db_page_status_prop):
    """Test converting Notion page to item."""
    side = NotionDbSide(mock_client, "test-db-id")
    item = side._page_to_item(notion_db_page_status_prop)

    assert item["id"] == "test-page-id-1"
    assert item["description"] == "Test Task"
    assert item["status"] == "pending"
    assert "due" in item
    assert isinstance(item["last_edited_time"], datetime.datetime)


def test_page_to_item_completed(mock_client, notion_db_page_completed):
    """Test converting completed Notion page to item."""
    side = NotionDbSide(mock_client, "test-db-id")
    item = side._page_to_item(notion_db_page_completed)

    assert item["id"] == "test-page-id-2"
    assert item["description"] == "Completed Task"
    assert item["status"] == "completed"
    assert "due" not in item  # No due date set


def test_get_all_items(mock_client, notion_db_page_status_prop, notion_db_page_completed):
    """Test get_all_items method."""
    side = NotionDbSide(mock_client, "test-db-id")

    # Mock the database query response
    mock_client.databases.query.return_value = {
        "results": [notion_db_page_status_prop, notion_db_page_completed],
        "has_more": False,
        "next_cursor": None,
    }

    items = side.get_all_items()

    assert len(items) == 2
    assert items[0]["id"] == "test-page-id-1"
    assert items[1]["id"] == "test-page-id-2"
    mock_client.databases.query.assert_called_once()


def test_get_all_items_with_pagination(mock_client, notion_db_page_status_prop):
    """Test get_all_items with pagination."""
    side = NotionDbSide(mock_client, "test-db-id")

    # Mock paginated responses
    mock_client.databases.query.side_effect = [
        {
            "results": [notion_db_page_status_prop],
            "has_more": True,
            "next_cursor": "cursor-1",
        },
        {
            "results": [notion_db_page_status_prop],
            "has_more": False,
            "next_cursor": None,
        },
    ]

    items = side.get_all_items()

    assert len(items) == 2
    assert mock_client.databases.query.call_count == 2


def test_add_item(mock_client, notion_db_page_status_prop):
    """Test adding an item."""
    side = NotionDbSide(mock_client, "test-db-id")

    # Mock the create response
    mock_client.pages.create.return_value = notion_db_page_status_prop

    new_item = {"description": "New Task", "status": "pending"}
    result = side.add_item(new_item)

    assert result["id"] == "test-page-id-1"
    assert result["description"] == "Test Task"
    mock_client.pages.create.assert_called_once()


def test_update_item(mock_client):
    """Test updating an item."""
    side = NotionDbSide(mock_client, "test-db-id")

    side.update_item("test-page-id-1", description="Updated Task", status="completed")

    mock_client.pages.update.assert_called_once()
    call_args = mock_client.pages.update.call_args
    assert call_args[1]["page_id"] == "test-page-id-1"
    assert "properties" in call_args[1]


def test_delete_single_item(mock_client):
    """Test deleting (archiving) an item."""
    side = NotionDbSide(mock_client, "test-db-id")

    side.delete_single_item("test-page-id-1")

    mock_client.pages.update.assert_called_once_with(page_id="test-page-id-1", archived=True)


def test_items_are_identical():
    """Test items_are_identical class method."""
    item1 = {"id": "1", "description": "Task", "status": "pending"}
    item2 = {"id": "1", "description": "Task", "status": "pending"}
    item3 = {"id": "1", "description": "Different", "status": "pending"}

    assert NotionDbSide.items_are_identical(item1, item2)
    assert not NotionDbSide.items_are_identical(item1, item3)


def test_create_status_property_checkbox(mock_client):
    """Test creating status property with checkbox type."""
    config = NotionSideConfig(status_mapping_kind=StatusMappingKind.CHECKBOX)
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    prop = side._create_status_property(True)
    assert prop == {"checkbox": True}

    prop = side._create_status_property(False)
    assert prop == {"checkbox": False}


def test_create_status_property_select(mock_client):
    """Test creating status property with select type."""
    config = NotionSideConfig(
        status_mapping_kind=StatusMappingKind.SELECT,
        status_map={"pending": ["To Do", "In Progress"], "completed": ["Complete", "Done"]},
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    prop = side._create_status_property(True)
    assert prop == {"select": {"name": "Complete"}}

    prop = side._create_status_property(False)
    assert prop == {"select": {"name": "To Do"}}


# Tests for Project functionality
def test_parse_project_property_select(mock_client):
    """Test parsing project property with select type."""
    side = NotionDbSide(mock_client, "test-db-id")
    side._config.map_field_project = "Project"

    props = {
        "Project": {
            "type": "select",
            "select": {"name": "Work"},
        }
    }

    project = side._parse_project_property(props)
    assert project == "Work"


def test_parse_project_property_multi_select(mock_client):
    """Test parsing project property with multi-select type."""
    config = NotionSideConfig(
        map_field_project="Project",
        project_mapping_kind=ProjectMappingKind.MULTI_SELECT,
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    props = {
        "Project": {
            "type": "multi_select",
            "multi_select": [{"name": "Personal"}, {"name": "Work"}],
        }
    }

    project = side._parse_project_property(props)
    assert project == "Personal"  # Takes first value


def test_parse_project_property_relation(mock_client):
    """Test parsing project property with relation type."""
    config = NotionSideConfig(
        map_field_project="Project",
        project_mapping_kind=ProjectMappingKind.RELATION,
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    props = {
        "Project": {
            "type": "relation",
            "relation": [{"id": "related-page-id"}],
        }
    }

    project = side._parse_project_property(props)
    assert project == "related-page-id"


def test_create_project_property_select(mock_client):
    """Test creating project property with select type."""
    config = NotionSideConfig(
        map_field_project="Project",
        project_mapping_kind=ProjectMappingKind.SELECT,
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    prop = side._create_project_property("Work")
    assert prop == {"select": {"name": "Work"}}


def test_create_project_property_multi_select(mock_client):
    """Test creating project property with multi-select type."""
    config = NotionSideConfig(
        map_field_project="Project",
        project_mapping_kind=ProjectMappingKind.MULTI_SELECT,
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    prop = side._create_project_property("Personal")
    assert prop == {"multi_select": [{"name": "Personal"}]}


# Tests for Priority functionality
def test_parse_priority_property(mock_client):
    """Test parsing priority property."""
    config = NotionSideConfig(
        map_field_priority="Priority",
        priority_map={"H": "High", "M": "Medium", "L": "Low"},
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    props = {
        "Priority": {
            "type": "select",
            "select": {"name": "High"},
        }
    }

    priority = side._parse_priority_property(props)
    assert priority == "H"


def test_parse_priority_property_medium(mock_client):
    """Test parsing medium priority."""
    config = NotionSideConfig(
        map_field_priority="Priority",
        priority_map={"H": "High", "M": "Medium", "L": "Low"},
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    props = {
        "Priority": {
            "type": "select",
            "select": {"name": "Medium"},
        }
    }

    priority = side._parse_priority_property(props)
    assert priority == "M"


def test_create_priority_property(mock_client):
    """Test creating priority property."""
    config = NotionSideConfig(
        map_field_priority="Priority",
        priority_map={"H": "High", "M": "Medium", "L": "Low"},
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    prop = side._create_priority_property("H")
    assert prop == {"select": {"name": "High"}}

    prop = side._create_priority_property("M")
    assert prop == {"select": {"name": "Medium"}}

    prop = side._create_priority_property("L")
    assert prop == {"select": {"name": "Low"}}


def test_page_to_item_with_project_and_priority(mock_client):
    """Test converting page to item with project and priority."""
    config = NotionSideConfig(
        map_field_project="Project",
        map_field_priority="Priority",
        priority_map={"H": "High", "M": "Medium", "L": "Low"},
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    page = {
        "id": "test-page-id-3",
        "archived": False,
        "last_edited_time": "2021-12-04T10:01:00.000Z",
        "properties": {
            "Name": {
                "id": "title",
                "type": "title",
                "title": [
                    {
                        "type": "text",
                        "text": {"content": "Task with Project and Priority"},
                        "plain_text": "Task with Project and Priority",
                    }
                ],
            },
            "Status": {
                "id": "status",
                "type": "status",
                "status": {"name": "Not started"},
            },
            "Due Date": {"id": "due", "type": "date", "date": None},
            "Project": {
                "type": "select",
                "select": {"name": "Work"},
            },
            "Priority": {
                "type": "select",
                "select": {"name": "High"},
            },
        },
    }

    item = side._page_to_item(page)
    assert item["id"] == "test-page-id-3"
    assert item["description"] == "Task with Project and Priority"
    assert item["status"] == "pending"
    assert item["project"] == "Work"
    assert item["priority"] == "H"


def test_add_item_with_project_and_priority(mock_client):
    """Test adding item with project and priority."""
    config = NotionSideConfig(
        map_field_project="Project",
        map_field_priority="Priority",
        priority_map={"H": "High", "M": "Medium", "L": "Low"},
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    # Mock response
    mock_response = {
        "id": "new-page-id",
        "archived": False,
        "last_edited_time": "2021-12-06T10:00:00.000Z",
        "properties": {
            "Name": {
                "title": [{"plain_text": "New Task"}],
            },
            "Status": {
                "status": {"name": "Not started"},
            },
            "Due Date": {"date": None},
            "Project": {
                "select": {"name": "Personal"},
            },
            "Priority": {
                "select": {"name": "Medium"},
            },
        },
    }

    mock_client.pages.create.return_value = mock_response

    new_item = {
        "description": "New Task",
        "status": "pending",
        "project": "Personal",
        "priority": "M",
    }

    result = side.add_item(new_item)
    mock_client.pages.create.assert_called_once()

    # Verify properties were created correctly
    call_args = mock_client.pages.create.call_args
    properties = call_args[1]["properties"]
    assert "Project" in properties
    assert properties["Project"] == {"select": {"name": "Personal"}}
    assert "Priority" in properties
    assert properties["Priority"] == {"select": {"name": "Medium"}}


def test_update_item_with_project_and_priority(mock_client):
    """Test updating item with project and priority."""
    config = NotionSideConfig(
        map_field_project="Project",
        map_field_priority="Priority",
        priority_map={"H": "High", "M": "Medium", "L": "Low"},
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    side.update_item(
        "test-page-id-1",
        description="Updated Task",
        status="completed",
        project="Work",
        priority="H",
    )

    mock_client.pages.update.assert_called_once()
    call_args = mock_client.pages.update.call_args
    properties = call_args[1]["properties"]

    assert "Project" in properties
    assert properties["Project"] == {"select": {"name": "Work"}}
    assert "Priority" in properties
    assert properties["Priority"] == {"select": {"name": "High"}}


def test_converter_with_project_and_priority():
    """Test converters handle project and priority."""
    from syncall.tw_notion_db_utils import (
        convert_notion_db_to_tw,
        convert_tw_to_notion_db,
    )
    import datetime

    # Test TW to Notion conversion
    tw_item = {
        "description": "Test task",
        "status": "pending",
        "modified": "20211204T100100Z",
        "project": "Work",
        "priority": "H",
    }

    notion_item = convert_tw_to_notion_db(tw_item)
    assert notion_item["project"] == "Work"
    assert notion_item["priority"] == "H"

    # Test Notion to TW conversion
    notion_item_test = {
        "description": "Notion task",
        "status": "completed",
        "last_edited_time": datetime.datetime(
            2021, 12, 4, 10, 1, tzinfo=datetime.timezone.utc
        ),
        "project": "Personal",
        "priority": "M",
    }

    tw_item_back = convert_notion_db_to_tw(notion_item_test)
    assert tw_item_back["project"] == "Personal"
    assert tw_item_back["priority"] == "M"


def test_status_map_one_to_many(mock_client):
    """Test 1:n status mapping - multiple Notion values map to same TW status."""
    config = NotionSideConfig(
        status_map={
            "pending": ["Not started", "To Do", "In Progress"],
            "completed": ["Done", "Complete", "Finished"],
        }
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    # Test parsing - all "completed" values should be recognized
    test_cases = [
        ("Done", True),
        ("Complete", True),
        ("Finished", True),
        ("Not started", False),
        ("To Do", False),
        ("In Progress", False),
    ]

    for status_name, expected_completed in test_cases:
        props = {
            "Status": {
                "type": "status",
                "status": {"name": status_name},
            }
        }
        result = side._parse_status_property(props)
        assert result == expected_completed, f"Failed for status: {status_name}"

    # Test creating - should use first value in the list
    completed_prop = side._create_status_property(True)
    assert completed_prop == {"status": {"name": "Done"}}

    pending_prop = side._create_status_property(False)
    assert pending_prop == {"status": {"name": "Not started"}}


def test_parse_project_property_relation_with_title_lookup(mock_client):
    """Test parsing project property with relation type and title lookup."""
    config = NotionSideConfig(
        map_field_project="Project",
        project_mapping_kind=ProjectMappingKind.RELATION,
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    # Mock the related page response
    mock_related_page = {
        "id": "related-page-id",
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": "Work Project"}],
            }
        },
    }
    mock_client.pages.retrieve.return_value = mock_related_page

    props = {
        "Project": {
            "type": "relation",
            "relation": [{"id": "related-page-id"}],
        }
    }

    project = side._parse_project_property(props)
    assert project == "Work Project"
    mock_client.pages.retrieve.assert_called_once_with(page_id="related-page-id")


def test_parse_project_property_relation_fallback_to_id(mock_client):
    """Test relation parsing falls back to ID when title lookup fails."""
    config = NotionSideConfig(
        map_field_project="Project",
        project_mapping_kind=ProjectMappingKind.RELATION,
    )
    side = NotionDbSide(mock_client, "test-db-id", config=config)

    # Mock API error
    mock_client.pages.retrieve.side_effect = Exception("API Error")

    props = {
        "Project": {
            "type": "relation",
            "relation": [{"id": "related-page-id"}],
        }
    }

    project = side._parse_project_property(props)
    # Should fallback to ID when API call fails
    assert project == "related-page-id"
