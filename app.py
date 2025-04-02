import os
import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from listeners import register_listeners
from env_loader import load_environment_variables
from codegeneration.pr_agent import PRAgent

# Load and normalize environment variables
load_environment_variables()

# Initialization
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
logging.basicConfig(level=logging.DEBUG)

# Initialize PR Agent
pr_agent = PRAgent(
    github_token=os.environ.get("GITHUB_TOKEN"),
    model_provider=os.environ.get("CODEGEN_MODEL_PROVIDER", "anthropic"),
    model_name=os.environ.get("CODEGEN_MODEL_NAME", "claude-3-5-sonnet-latest"),
    default_repo=os.environ.get("DEFAULT_REPO"),
    default_org=os.environ.get("DEFAULT_ORG"),
    slack_app=app  # Pass the Slack app instance to the PR Agent
)

# Register listeners (excluding app_mention which is handled by PR Agent)
register_listeners(app)

# Start Bolt app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
