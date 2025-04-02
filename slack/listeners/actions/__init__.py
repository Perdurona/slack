from slack_bolt import App
from .set_user_selection import set_user_selection
from .interactive_components import handle_button_click


def register(app: App):
    app.action("pick_a_provider")(set_user_selection)
    
    # Register button click handlers
    app.action({"action_id": "regenerate_.*"})(handle_button_click)
    app.action({"action_id": "feedback_helpful_.*"})(handle_button_click)
    app.action({"action_id": "feedback_not_helpful_.*"})(handle_button_click)
