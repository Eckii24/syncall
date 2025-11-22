from __future__ import annotations

import os
import sys

import click
from bubop import (
    check_optional_mutually_exclusive,
    check_required_mutually_exclusive,
    format_dict,
    logger,
    loguru_tqdm_sink,
    verbosity_int_to_std_logging_lvl,
)

from syncall.app_utils import (
    confirm_before_proceeding,
    fetch_from_pass_manager,
    inform_about_app_extras,
)

try:
    from syncall.notion.notion_db_side import (
        NotionDbSide,
        NotionSideConfig,
        ProjectMappingKind,
        StatusMappingKind,
    )
    from syncall.taskwarrior.taskwarrior_side import TaskWarriorSide
except ImportError:
    inform_about_app_extras(["notion", "tw"])

from notion_client import Client  # type: ignore

from syncall.aggregator import Aggregator
from syncall.app_utils import (
    app_log_to_syslog,
    cache_or_reuse_cached_combination,
    error_and_exit,
    fetch_app_configuration,
    get_resolution_strategy,
    register_teardown_handler,
)
from syncall.cli import (
    opt_notion_database_id,
    opt_notion_map_due,
    opt_notion_map_priority,
    opt_notion_map_project,
    opt_notion_map_status,
    opt_notion_map_title,
    opt_notion_priority_map,
    opt_notion_project_kind,
    opt_notion_status_done,
    opt_notion_status_kind,
    opt_notion_status_todo,
    opt_notion_token_pass_path,
    opts_miscellaneous,
    opts_tw_filtering,
)
from syncall.tw_notion_db_utils import convert_notion_db_to_tw, convert_tw_to_notion_db


# CLI parsing ---------------------------------------------------------------------------------
@click.command()
@opt_notion_database_id()
@opt_notion_token_pass_path()
@opt_notion_map_title()
@opt_notion_map_status()
@opt_notion_map_due()
@opt_notion_map_project()
@opt_notion_map_priority()
@opt_notion_status_done()
@opt_notion_status_todo()
@opt_notion_status_kind()
@opt_notion_project_kind()
@opt_notion_priority_map()
@opts_tw_filtering()
@opts_miscellaneous("TW", "Notion Database")
def main(
    database_id: str,
    token_pass_path: str,
    map_title: str,
    map_status: str,
    map_due: str,
    map_project: str,
    map_priority: str,
    status_done: tuple[str],
    status_todo: tuple[str],
    status_kind: str,
    project_kind: str,
    priority_map: tuple[str],
    tw_filter: str,
    tw_tags: list[str],
    tw_project: str,
    tw_only_modified_last_X_days: str,
    tw_sync_all_tasks: bool,
    prefer_scheduled_date: bool,
    resolution_strategy: str,
    verbose: int,
    combination_name: str,
    custom_combination_savename: str,
    pdb_on_error: bool,
    confirm: bool,
):
    """Synchronise filters of TW tasks with the items of Notion databases.

    The list of TW tasks can be based on a TW project, tag, on the modification date or on an
    arbitrary filter while the notion database should be provided by its ID.
    """
    # setup logger ----------------------------------------------------------------------------
    loguru_tqdm_sink(verbosity=verbose)
    app_log_to_syslog()
    logger.debug("Initialising...")
    inform_about_config = False

    # cli validation --------------------------------------------------------------------------
    check_optional_mutually_exclusive(combination_name, custom_combination_savename)

    tw_filter_li = [
        t
        for t in [
            tw_filter,
            tw_only_modified_last_X_days,
        ]
        if t
    ]

    combination_of_tw_filters_and_notion_db = any(
        [
            tw_filter_li,
            tw_tags,
            tw_project,
            tw_sync_all_tasks,
            database_id,
        ],
    )
    check_optional_mutually_exclusive(
        combination_name,
        combination_of_tw_filters_and_notion_db,
    )

    # existing combination name is provided ---------------------------------------------------
    if combination_name is not None:
        app_config = fetch_app_configuration(
            side_A_name="Taskwarrior",
            side_B_name="NotionDatabase",
            combination=combination_name,
        )
        tw_filter_li = app_config["tw_filter_li"]
        tw_tags = app_config["tw_tags"]
        tw_project = app_config["tw_project"]
        tw_sync_all_tasks = app_config["tw_sync_all_tasks"]
        database_id = app_config["database_id"]
        # Load Notion config if saved
        map_title = app_config.get("map_title", map_title)
        map_status = app_config.get("map_status", map_status)
        map_due = app_config.get("map_due", map_due)
        map_project = app_config.get("map_project", map_project)
        map_priority = app_config.get("map_priority", map_priority)
        status_done = app_config.get("status_done", status_done)
        status_todo = app_config.get("status_todo", status_todo)
        status_kind = app_config.get("status_kind", status_kind)
        project_kind = app_config.get("project_kind", project_kind)
        priority_map = app_config.get("priority_map", priority_map)

    # combination manually specified ----------------------------------------------------------
    else:
        inform_about_config = True
        combination_name = cache_or_reuse_cached_combination(
            config_args={
                "database_id": database_id,
                "tw_filter_li": tw_filter_li,
                "tw_project": tw_project,
                "tw_tags": tw_tags,
                "map_title": map_title,
                "map_status": map_status,
                "map_due": map_due,
                "map_project": map_project,
                "map_priority": map_priority,
                "status_done": list(status_done),
                "status_todo": list(status_todo),
                "status_kind": status_kind,
                "project_kind": project_kind,
                "priority_map": list(priority_map),
            },
            config_fname="tw_notion_db_configs",
            custom_combination_savename=custom_combination_savename,
        )

    # more checks -----------------------------------------------------------------------------
    combination_of_tw_related_options = any([tw_filter_li, tw_tags, tw_project])
    check_required_mutually_exclusive(
        tw_sync_all_tasks,
        combination_of_tw_related_options,
        "sync_all_tw_tasks",
        "combination of specific TW-related options",
    )

    if database_id is None:
        error_and_exit(
            "You have to provide the database ID of the Notion database for synchronization."
            " You can do so either via CLI arguments or by specifying an existing saved"
            " combination",
        )

    # announce configuration ------------------------------------------------------------------
    logger.info(
        format_dict(
            header="Configuration",
            items={
                "TW Filter": " ".join(tw_filter_li),
                "TW Tags": tw_tags,
                "TW Project": tw_project,
                "TW Sync All Tasks": tw_sync_all_tasks,
                "Notion Database ID": database_id,
                "Notion Title Field": map_title,
                "Notion Status Field": map_status,
                "Notion Due Field": map_due,
                "Notion Project Field": map_project or "(Not configured)",
                "Notion Priority Field": map_priority or "(Not configured)",
                "Status Done Values": list(status_done),
                "Status Todo Values": list(status_todo),
                "Status Kind": status_kind,
                "Project Kind": project_kind,
                "Priority Map": list(priority_map) if priority_map else "(Using defaults)",
                "Prefer scheduled dates": prefer_scheduled_date,
            },
            prefix="\n\n",
            suffix="\n",
        ),
    )
    if confirm:
        confirm_before_proceeding()

    # find token to connect to notion ---------------------------------------------------------
    api_key_env_var = "NOTION_API_KEY"
    token_v2 = os.environ.get(api_key_env_var)
    if token_v2 is not None:
        logger.debug("Reading the Notion API key from environment variable...")
    else:
        if token_pass_path is None:
            logger.error(
                "You have to provide the Notion API key, either via the"
                f" {api_key_env_var} environment variable or via the UNIX Password Manager"
                ' and the "--token-pass-path" CLI parameter',
            )
            sys.exit(1)
        token_v2 = fetch_from_pass_manager(token_pass_path)

    if not token_v2:
        logger.error("Failed to retrieve Notion API token")
        sys.exit(1)

    # teardown function and exception handling ------------------------------------------------
    register_teardown_handler(
        pdb_on_error=pdb_on_error,
        inform_about_config=inform_about_config,
        combination_name=combination_name,
        verbose=verbose,
    )

    # initialize sides ------------------------------------------------------------------------
    # tw
    tw_side = TaskWarriorSide(
        tw_filter=" ".join(tw_filter_li),
        tags=tw_tags,
        project=tw_project,
    )

    # notion database
    # client is a bit too verbose by default.
    client_verbosity = max(verbose - 1, 0)
    client = Client(
        auth=token_v2,
        log_level=verbosity_int_to_std_logging_lvl(client_verbosity),
    )

    # Create config
    # Parse priority map
    parsed_priority_map: dict[str, str] = {}
    if priority_map:
        for mapping in priority_map:
            if ":" in mapping:
                tw_priority, notion_value = mapping.split(":", 1)
                parsed_priority_map[tw_priority.strip()] = notion_value.strip()
            else:
                logger.warning(f"Invalid priority mapping format: {mapping}, skipping")

    notion_config = NotionSideConfig(
        map_field_title=map_title,
        map_field_status=map_status,
        map_field_due=map_due,
        map_field_project=map_project if map_project else None,
        map_field_priority=map_priority if map_priority else None,
        val_status_todo=list(status_todo),
        val_status_done=list(status_done),
        status_mapping_kind=StatusMappingKind(status_kind),
        project_mapping_kind=ProjectMappingKind(project_kind),
        priority_map=parsed_priority_map if parsed_priority_map else {},
    )

    notion_side = NotionDbSide(client=client, database_id=database_id, config=notion_config)

    # sync ------------------------------------------------------------------------------------
    with Aggregator(
        side_A=notion_side,
        side_B=tw_side,
        converter_B_to_A=convert_tw_to_notion_db,
        converter_A_to_B=convert_notion_db_to_tw,
        resolution_strategy=get_resolution_strategy(
            resolution_strategy,
            side_A_type=type(notion_side),
            side_B_type=type(tw_side),
        ),
        config_fname=combination_name,
        ignore_keys=(
            ("last_edited_time",),
            ("due", "end", "entry", "modified", "urgency"),
        ),
    ) as aggregator:
        aggregator.sync()

    return 0


if __name__ == "__main__":
    sys.exit(main())
