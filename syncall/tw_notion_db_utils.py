"""NotionDb-related utils for TaskWarrior synchronization."""
import datetime
from typing import Any

from bubop import format_datetime_tz, parse_datetime

from syncall.sync_side import ItemType
from syncall.types import TwItem


def convert_tw_to_notion_db(tw_item: TwItem) -> ItemType:
    """Convert a TaskWarrior item to a Notion Database item.

    :param tw_item: TaskWarrior item dictionary
    :return: Notion database item dictionary
    """
    modified = tw_item["modified"]
    dt = modified if isinstance(modified, datetime.datetime) else parse_datetime(modified)

    item: dict[str, Any] = {
        "description": tw_item["description"],
        "status": tw_item["status"],
        "last_edited_time": dt,
    }

    # Add due date if present
    if "due" in tw_item:
        due = tw_item["due"]
        if isinstance(due, str):
            item["due"] = parse_datetime(due)
        elif isinstance(due, datetime.datetime):
            item["due"] = due

    return item


def convert_notion_db_to_tw(notion_item: ItemType) -> TwItem:
    """Convert a Notion Database item to a TaskWarrior item.

    :param notion_item: Notion database item dictionary
    :return: TaskWarrior item dictionary
    """
    tw_item: TwItem = {
        "description": notion_item["description"],
        "status": notion_item["status"],
    }

    # Add modified time if present
    if "last_edited_time" in notion_item:
        last_edited = notion_item["last_edited_time"]
        if isinstance(last_edited, datetime.datetime):
            tw_item["modified"] = format_datetime_tz(last_edited)
        else:
            tw_item["modified"] = last_edited

    # Add due date if present
    if "due" in notion_item:
        due = notion_item["due"]
        if isinstance(due, datetime.datetime):
            tw_item["due"] = format_datetime_tz(due)
        else:
            tw_item["due"] = due

    return tw_item
