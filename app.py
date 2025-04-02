import os
import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from listeners import register_listeners
from env_loader import load_environment_variables
from codegeneration.pr_agent import PRAgent
from codegeneration.codebase_analyzer import create_codebase
from codegen.shared.enums.programming_language import ProgrammingLanguage
from codegen.extensions.events.codegen_app import CodegenApp

# Load and normalize environment variables
load_environment_variables()

# Initialization
slack_app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
logging.basicConfig(level=logging.DEBUG)

# Initialize CodegenApp
codegen_app = CodegenApp(
    name="slack-pr-agent",
    repo=os.environ.get("DEFAULT_REPO"),
    tmp_dir=os.environ.get("CODEGEN_TMP_DIR", "/tmp/codegen")
)

# Initialize PR Agent
pr_agent = PRAgent(
    github_token=os.environ.get("GITHUB_TOKEN"),
    model_provider=os.environ.get("CODEGEN_MODEL_PROVIDER", "anthropic"),
    model_name=os.environ.get("CODEGEN_MODEL_NAME", "claude-3-5-sonnet-latest"),
    default_repo=os.environ.get("DEFAULT_REPO"),
    default_org=os.environ.get("DEFAULT_ORG"),
    slack_app=slack_app,  # Pass the Slack app instance to the PR Agent
    codegen_app=codegen_app  # Pass the CodegenApp instance to the PR Agent
)

# Initialize default codebase if specified
default_sdk_repo = os.environ.get("DEFAULT_SDK_REPO", "codegen-sh/codegen-sdk")
if default_sdk_repo:
    try:
        logging.info(f"Initializing SDK codebase: {default_sdk_repo}")
        pr_agent.codebase_analyzer.run_this_on_startup()
        logging.info(f"Successfully initialized SDK codebase")
    except Exception as e:
        logging.error(f"Failed to initialize SDK codebase: {e}")

# Parse the repository if specified
if codegen_app.repo:
    try:
        logging.info(f"Parsing repository: {codegen_app.repo}")
        codegen_app.parse_repo()
        logging.info(f"Successfully parsed repository: {codegen_app.repo}")
    except Exception as e:
        logging.error(f"Failed to parse repository: {e}")

# Register listeners (excluding app_mention which is handled by PR Agent)
register_listeners(slack_app)

# Start Bolt app
if __name__ == "__main__":
    SocketModeHandler(slack_app, os.environ.get("SLACK_APP_TOKEN")).start()
