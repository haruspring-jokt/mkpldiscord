from src.handlers.channel_create import handle_guild_channel_create
from src.handlers.commands import handle_message_commands
from src.handlers.schedule import (
    ScheduleModal,
    ScheduleTriggerView,
    process_schedule_submission,
)
from src.handlers.applications import (
    ApplyRequestModal,
    ApplyTypeSelectionView,
    handle_thread_create,
)


def test_handler_modules_are_importable() -> None:
    assert callable(handle_message_commands)
    assert callable(handle_guild_channel_create)
    assert callable(handle_thread_create)
    assert callable(process_schedule_submission)
    assert ScheduleModal is not None
    assert ScheduleTriggerView is not None
    assert ApplyRequestModal is not None
    assert ApplyTypeSelectionView is not None
