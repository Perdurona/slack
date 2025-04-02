from slack_bolt import App
from .ask_command import ask_callback
from .localai_settings import localai_settings_callback, handle_localai_settings_submission
from .preferences import preferences_callback, handle_preferences_submission
from .thread_chat import thread_chat_callback
from .summarize_command import summarize_callback
from .image_command import image_callback


def register(app: App):
    # Register commands
    app.command("/ask-bolty")(ask_callback)
    app.command("/localai-settings")(localai_settings_callback)
    app.command("/ai-preferences")(preferences_callback)
    app.command("/chat")(thread_chat_callback)
    app.command("/summarize")(summarize_callback)
    app.command("/image")(image_callback)
    
    # Register view submissions
    app.view("localai_settings_modal")(handle_localai_settings_submission)
    app.view("ai_preferences_modal")(handle_preferences_submission)
