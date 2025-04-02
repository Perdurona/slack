"""
PR Agent for creating GitHub PRs from Slack messages.

This module provides the main PR Agent class that coordinates the workflow
between Slack, Codegen, and GitHub.
"""

import logging
import os
import re
import json
import uuid
import time
from typing import Dict, Any, Optional, Tuple, List, Literal, Callable, Union

from fastapi import Request
from slack_bolt import App

from codegen import CodeAgent, Codebase
from codegen.sdk.core.codebase import Codebase
from codegen.shared.enums.programming_language import ProgrammingLanguage
from codegen.extensions.langchain.agent import (
    create_codebase_inspector_agent,
    create_chat_agent,
    create_codebase_agent,
    create_agent_with_tool
)
from codegen.extensions.langchain.tools import (
    GithubCreatePRTool,
    GithubViewPRTool,
    GithubCreatePRCommentTool,
    GithubCreatePRReviewCommentTool,
    CreateFileTool,
    DeleteFileTool,
    EditFileTool,
    ListDirectoryTool,
    MoveSymbolTool,
    RenameFileTool,
    ReplacementEditTool,
    RevealSymbolTool,
    SearchTool,
    SemanticEditTool,
    ViewFileTool,
)
from codegen.extensions.tools.github.create_pr import create_pr
from codegen.git.repo_operator.repo_operator import RepoOperator
from codegen.sdk.code_generation.prompts.api_docs import (
    get_docstrings_for_classes,
    get_codebase_docstring,
    get_behavior_docstring,
    get_core_symbol_docstring,
    get_language_specific_docstring,
    get_codegen_sdk_docs
)
from codegen.extensions.events.codegen_app import CodegenApp
from codegen.extensions.github.types.pull_request import PullRequestLabeledEvent
from codegen.extensions.slack.types import SlackEvent

from .codebase_analyzer import CodebaseAnalyzer
from .github_handler import GitHubHandler
from .response_formatter import ResponseFormatter

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class PRAgent:
    """
    Agent for creating GitHub PRs from Slack messages.
    
    This agent coordinates the workflow between Slack, Codegen, and GitHub.
    It detects PR creation requests, extracts repository and change details,
    and creates PRs with appropriate titles and descriptions.
    """
    
    def __init__(
        self,
        github_token: str,
        model_provider: str = "anthropic",
        model_name: str = "claude-3-5-sonnet-latest",
        default_repo: str = None,
        default_org: str = None,
        slack_app: Optional[App] = None,
        tmp_dir: str = "/tmp/codegen"
    ):
        """
        Initialize the PR Agent.
        
        Args:
            github_token: GitHub API token
            model_provider: Model provider (anthropic or openai)
            model_name: Model name to use
            default_repo: Default repository name
            default_org: Default organization name
            slack_app: Slack app instance (optional)
            tmp_dir: Temporary directory for cloning repositories
        """
        self.github_token = github_token
        self.model_provider = model_provider
        self.model_name = model_name
        self.default_repo = default_repo
        self.default_org = default_org
        self.slack_app = slack_app
        self.tmp_dir = tmp_dir
        
        # Initialize components
        self.codebase_analyzer = CodebaseAnalyzer(
            model_provider=model_provider,
            model_name=model_name,
            github_token=github_token,
            tmp_dir=tmp_dir
        )
        self.github_handler = GitHubHandler(github_token=github_token)
        self.response_formatter = ResponseFormatter()
        
        # Compile regex patterns for PR creation requests
        self.pr_patterns = [
            r"create\s+(?:a\s+)?pr",
            r"create\s+(?:a\s+)?pull\s+request",
            r"make\s+(?:a\s+)?pr",
            r"make\s+(?:a\s+)?pull\s+request",
            r"submit\s+(?:a\s+)?pr",
            r"submit\s+(?:a\s+)?pull\s+request",
            r"open\s+(?:a\s+)?pr",
            r"open\s+(?:a\s+)?pull\s+request"
        ]
        self.pr_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.pr_patterns]
        
        # Initialize codegen app if slack_app is provided
        self.codegen_app = None
        if slack_app:
            self.setup_codegen_app()
        
    def setup_codegen_app(self):
        """
        Set up the Codegen app with event handlers.
        
        This method initializes a CodegenApp instance and sets up event handlers
        for Slack, GitHub, and Linear events.
        """
        if not self.slack_app:
            logger.warning("Cannot set up Codegen app: Slack app not provided")
            return
        
        try:
            # Initialize the Codegen app
            self.codegen_app = CodegenApp(
                name="pr-agent",
                repo=f"{self.default_org}/{self.default_repo}" if self.default_org and self.default_repo else None,
                tmp_dir=self.tmp_dir
            )
            
            # Set up event handlers
            self.setup_event_handlers(self.codegen_app)
            
            logger.info("Codegen app set up successfully")
        except Exception as e:
            logger.error(f"Error setting up Codegen app: {str(e)}")
    
    def setup_event_handlers(self, cg: CodegenApp):
        """
        Set up event handlers for the Codegen app.
        
        Args:
            cg: The Codegen app instance
        """
        @cg.slack.event("app_mention")
        async def handle_mention(event: SlackEvent):
            logger.info("[APP_MENTION] Received app_mention event")
            
            # Extract event data
            text = event.text
            user = event.user
            channel = event.channel
            thread_ts = event.thread_ts or event.ts
            
            # Check if this is a PR creation request
            if self.is_pr_creation_request(text):
                # Acknowledge receipt
                cg.slack.client.chat_postMessage(
                    channel=channel,
                    text=f"I'll work on creating a PR based on your request, <@{user}>!",
                    thread_ts=thread_ts
                )
                
                # Process the PR creation request
                result = await self.process_pr_creation_request_async(
                    text, user, channel, thread_ts, 
                    lambda text, thread_ts: cg.slack.client.chat_postMessage(
                        channel=channel, text=text, thread_ts=thread_ts
                    )
                )
                
                return result
            else:
                # Try to get the codebase
                try:
                    # Extract repository name from the text
                    repo_name = self._extract_repo_name_from_text(text)
                    if repo_name == "default_repo" and self.default_org and self.default_repo:
                        repo_name = f"{self.default_org}/{self.default_repo}"
                    
                    # Initialize the codebase
                    codebase = self.codebase_analyzer.get_codebase(repo_name)
                    
                    # Create a code agent
                    agent = CodeAgent(codebase=codebase)
                    
                    # Run the agent
                    response = agent.run(text)
                    
                    # Send the response
                    cg.slack.client.chat_postMessage(
                        channel=channel,
                        text=response,
                        thread_ts=thread_ts
                    )
                    
                    return {"message": "Mentioned", "received_text": text, "response": response}
                except Exception as e:
                    logger.error(f"Error processing mention: {str(e)}")
                    
                    # Fallback to a simple response
                    cg.slack.client.chat_postMessage(
                        channel=channel,
                        text=f"Hi <@{user}>! I'm a PR creation bot. To create a PR, mention me with 'create PR' or 'create pull request' followed by your request.",
                        thread_ts=thread_ts
                    )
                    
                    return {"message": "Not a PR creation request", "error": str(e)}
        
        @cg.github.event("pull_request:labeled")
        def handle_pr(event: PullRequestLabeledEvent):
            logger.info("PR labeled")
            logger.info(f"PR head sha: {event.pull_request.head.sha}")
            
            try:
                # Get the repository name
                repo_name = f"{event.repository.owner.login}/{event.repository.name}"
                
                # Initialize the codebase
                codebase = self.codebase_analyzer.get_codebase(repo_name)
                logger.info(f"Codebase: {codebase.name} codebase.repo: {codebase.repo_path}")
                
                # Check out commit
                logger.info("> Checking out commit")
                codebase.checkout(commit=event.pull_request.head.sha)
                
                # Analyze the PR
                logger.info("> Analyzing PR")
                self.analyze_pr(codebase, event)
                
                return {
                    "message": "PR event handled", 
                    "num_files": len(codebase.files), 
                    "num_functions": len(codebase.functions)
                }
            except Exception as e:
                logger.error(f"Error handling PR event: {str(e)}")
                return {"error": str(e)}
    
    def analyze_pr(self, codebase: Codebase, event: PullRequestLabeledEvent):
        """
        Analyze a PR and provide feedback.
        
        Args:
            codebase: The codebase instance
            event: The PR labeled event
        """
        # Define tools for the agent
        pr_tools = [
            GithubViewPRTool(codebase),
            GithubCreatePRCommentTool(codebase),
            GithubCreatePRReviewCommentTool(codebase),
        ]
        
        # Create agent with the defined tools
        agent = CodeAgent(codebase=codebase, tools=pr_tools)
        
        # Create a prompt for the agent
        prompt = f"""
        Analyze this pull request:
        {event.pull_request.url}
        
        Provide a summary of the changes and any potential issues or improvements.
        Be specific about the changes, produce a short summary, and point out possible improvements.
        Use the tools at your disposal to create proper PR reviews.
        """
        
        # Run the agent
        response = agent.run(prompt)
        
        # Add a comment to the PR
        codebase._op.create_pr_comment(event.number, response)
    
    def is_pr_creation_request(self, text: str) -> bool:
        """
        Check if the text is a PR creation request.
        
        Args:
            text: The message text
            
        Returns:
            True if the text is a PR creation request, False otherwise
        """
        # Check if any of the patterns match
        for pattern in self.pr_patterns:
            if pattern.search(text):
                return True
                
        return False
    
    def _extract_repo_name_from_text(self, text: str) -> str:
        """
        Extract repository name from text.
        
        Args:
            text: The message text
            
        Returns:
            The repository name
        """
        # Try to extract repository information using regex
        repo_pattern = r"(?:in|for|to|on|at)\s+(?:the\s+)?(?:repo(?:sitory)?|project)?\s*[\"']?([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)[\"']?"
        repo_match = re.search(repo_pattern, text, re.IGNORECASE)
        
        if repo_match:
            return repo_match.group(1)
        
        # If no match, use the default repository
        if self.default_org and self.default_repo:
            return f"{self.default_org}/{self.default_repo}"
        
        # If no default repository, return a placeholder
        return "default_repo"
    
    async def process_pr_creation_request_async(
        self, 
        text: str, 
        user_id: str, 
        channel_id: str, 
        thread_ts: str,
        say_callback: Callable[[str, str], Any]
    ) -> Dict[str, Any]:
        """
        Process a PR creation request asynchronously.
        
        Args:
            text: The message text
            user_id: The user ID
            channel_id: The channel ID
            thread_ts: The thread timestamp
            say_callback: Callback function for sending messages
            
        Returns:
            A dictionary containing the result of the PR creation
        """
        try:
            # Extract repository and change details
            repo_name, change_details = self.codebase_analyzer.extract_repo_and_changes(text)
            
            # If the repository is "default_repo", use the default repository
            if repo_name == "default_repo" and self.default_org and self.default_repo:
                repo_name = f"{self.default_org}/{self.default_repo}"
            
            # Send an update
            say_callback(
                text=self.response_formatter.format_loading_message(f"Analyzing the repository '{repo_name}'"),
                thread_ts=thread_ts
            )
            
            # Analyze the codebase
            analysis = self.codebase_analyzer.analyze_codebase(repo_name)
            
            # Send an update
            say_callback(
                text=self.response_formatter.format_loading_message(f"Generating changes based on your request"),
                thread_ts=thread_ts
            )
            
            # Generate changes
            changes = self.codebase_analyzer.generate_changes(repo_name, change_details)
            
            # Check if there was an error
            if "error" in changes:
                error_message = changes.get("error", "Unknown error")
                say_callback(
                    text=self.response_formatter.format_error_response(f"Error generating changes: {error_message}"),
                    thread_ts=thread_ts
                )
                return {"error": error_message}
            
            # Send an update
            say_callback(
                text=self.response_formatter.format_loading_message(f"Creating a PR with the generated changes"),
                thread_ts=thread_ts
            )
            
            # Create the PR
            pr_result = self.github_handler.create_pr(repo_name, changes, user_id)
            
            # Check if there was an error
            if "error" in pr_result:
                error_message = pr_result.get("error", "Unknown error")
                say_callback(
                    text=self.response_formatter.format_error_response(f"Error creating PR: {error_message}"),
                    thread_ts=thread_ts
                )
                return {"error": error_message}
            
            # Format and send the response
            response = self.response_formatter.format_pr_creation_response(pr_result)
            say_callback(text=response, thread_ts=thread_ts)
            
            return pr_result
        except Exception as e:
            logger.error(f"Error processing PR creation request: {str(e)}")
            say_callback(
                text=self.response_formatter.format_error_response(f"Error processing PR creation request: {str(e)}"),
                thread_ts=thread_ts
            )
            return {"error": str(e)}
    
    def process_pr_creation_request(
        self, 
        text: str, 
        user_id: str, 
        channel_id: str, 
        thread_ts: str,
        say_callback: Callable[[Dict[str, Any]], Any]
    ) -> Dict[str, Any]:
        """
        Process a PR creation request.
        
        Args:
            text: The message text
            user_id: The user ID
            channel_id: The channel ID
            thread_ts: The thread timestamp
            say_callback: Callback function for sending messages
            
        Returns:
            A dictionary containing the result of the PR creation
        """
        try:
            # Extract repository and change details
            repo_name, change_details = self.codebase_analyzer.extract_repo_and_changes(text)
            
            # If the repository is "default_repo", use the default repository
            if repo_name == "default_repo" and self.default_org and self.default_repo:
                repo_name = f"{self.default_org}/{self.default_repo}"
            
            # Send an update
            say_callback(
                text=self.response_formatter.format_loading_message(f"Analyzing the repository '{repo_name}'"),
                thread_ts=thread_ts
            )
            
            # Analyze the codebase
            analysis = self.codebase_analyzer.analyze_codebase(repo_name)
            
            # Send an update
            say_callback(
                text=self.response_formatter.format_loading_message(f"Generating changes based on your request"),
                thread_ts=thread_ts
            )
            
            # Generate changes
            changes = self.codebase_analyzer.generate_changes(repo_name, change_details)
            
            # Check if there was an error
            if "error" in changes:
                error_message = changes.get("error", "Unknown error")
                say_callback(
                    text=self.response_formatter.format_error_response(f"Error generating changes: {error_message}"),
                    thread_ts=thread_ts
                )
                return {"error": error_message}
            
            # Send an update
            say_callback(
                text=self.response_formatter.format_loading_message(f"Creating a PR with the generated changes"),
                thread_ts=thread_ts
            )
            
            # Create the PR
            pr_result = self.github_handler.create_pr(repo_name, changes, user_id)
            
            # Check if there was an error
            if "error" in pr_result:
                error_message = pr_result.get("error", "Unknown error")
                say_callback(
                    text=self.response_formatter.format_error_response(f"Error creating PR: {error_message}"),
                    thread_ts=thread_ts
                )
                return {"error": error_message}
            
            # Format and send the response
            response = self.response_formatter.format_pr_creation_response(pr_result)
            say_callback(text=response, thread_ts=thread_ts)
            
            return pr_result
        except Exception as e:
            logger.error(f"Error processing PR creation request: {str(e)}")
            say_callback(
                text=self.response_formatter.format_error_response(f"Error processing PR creation request: {str(e)}"),
                thread_ts=thread_ts
            )
            return {"error": str(e)}
    
    def handle_app_mention(self, event: Dict[str, Any], say_callback) -> Dict[str, Any]:
        """
        Handle an app mention event.
        
        Args:
            event: The event data
            say_callback: Callback function for sending messages
            
        Returns:
            A dictionary containing the result of the event handling
        """
        try:
            # Extract event data
            text = event.get("text", "")
            user_id = event.get("user", "")
            channel_id = event.get("channel", "")
            thread_ts = event.get("thread_ts", event.get("ts", ""))
            
            # Check if this is a PR creation request
            if self.is_pr_creation_request(text):
                # Acknowledge receipt
                say_callback(text=f"I'll work on creating a PR based on your request, <@{user_id}>!", thread_ts=thread_ts)
                
                # Process the PR creation request
                return self.process_pr_creation_request(text, user_id, channel_id, thread_ts, say_callback)
            else:
                # Handle other types of requests
                say_callback(
                    text=f"Hi <@{user_id}>! I'm a PR creation bot. To create a PR, mention me with 'create PR' or 'create pull request' followed by your request.",
                    thread_ts=thread_ts
                )
                return {"message": "Not a PR creation request"}
                
        except Exception as e:
            logger.error(f"Error handling app mention: {str(e)}")
            return {"error": str(e)}

class PRAgentEventsMixin:
    """
    Mixin for handling events in the PR Agent.
    
    This mixin provides methods for handling events from different sources,
    such as Slack, GitHub, and Linear.
    """
    
    async def handle_event(
        self, 
        org: str, 
        repo: str, 
        provider: Literal["slack", "github", "linear"], 
        request: Request
    ):
        """
        Handle an event from a provider.
        
        Args:
            org: The organization name
            repo: The repository name
            provider: The provider name
            request: The request object
            
        Returns:
            The result of handling the event
        """
        logger.info(f"Handling {provider} event for {org}/{repo}")
        
        # Get the request payload
        payload = await request.json()
        
        # Handle the event based on the provider
        if provider == "slack":
            return await self.handle_slack_event(org, repo, payload, request)
        elif provider == "github":
            return await self.handle_github_event(org, repo, payload, request)
        elif provider == "linear":
            return await self.handle_linear_event(org, repo, payload, request)
        else:
            return {"error": f"Unsupported provider: {provider}"}
    
    async def handle_slack_event(self, org: str, repo: str, payload: Dict[str, Any], request: Request):
        """
        Handle a Slack event.
        
        Args:
            org: The organization name
            repo: The repository name
            payload: The event payload
            request: The request object
            
        Returns:
            The result of handling the event
        """
        # Extract the event type
        event_type = payload.get("type")
        
        # Handle different event types
        if event_type == "app_mention":
            return await self.handle_app_mention_event(org, repo, payload, request)
        else:
            return {"error": f"Unsupported Slack event type: {event_type}"}
    
    async def handle_github_event(self, org: str, repo: str, payload: Dict[str, Any], request: Request):
        """
        Handle a GitHub event.
        
        Args:
            org: The organization name
            repo: The repository name
            payload: The event payload
            request: The request object
            
        Returns:
            The result of handling the event
        """
        # Extract the event type
        event_type = request.headers.get("X-GitHub-Event")
        
        # Handle different event types
        if event_type == "pull_request":
            return await self.handle_pull_request_event(org, repo, payload, request)
        else:
            return {"error": f"Unsupported GitHub event type: {event_type}"}
    
    async def handle_linear_event(self, org: str, repo: str, payload: Dict[str, Any], request: Request):
        """
        Handle a Linear event.
        
        Args:
            org: The organization name
            repo: The repository name
            payload: The event payload
            request: The request object
            
        Returns:
            The result of handling the event
        """
        # Extract the event type
        event_type = payload.get("type")
        
        # Handle different event types
        if event_type == "Issue":
            return await self.handle_issue_event(org, repo, payload, request)
        else:
            return {"error": f"Unsupported Linear event type: {event_type}"}
    
    async def handle_app_mention_event(self, org: str, repo: str, payload: Dict[str, Any], request: Request):
        """
        Handle an app mention event.
        
        Args:
            org: The organization name
            repo: The repository name
            payload: The event payload
            request: The request object
            
        Returns:
            The result of handling the event
        """
        # Extract event data
        event = payload.get("event", {})
        text = event.get("text", "")
        user_id = event.get("user", "")
        channel_id = event.get("channel", "")
        thread_ts = event.get("thread_ts", event.get("ts", ""))
        
        # Check if this is a PR creation request
        if self.is_pr_creation_request(text):
            # Acknowledge receipt
            self.slack_app.client.chat_postMessage(
                channel=channel_id,
                text=f"I'll work on creating a PR based on your request, <@{user_id}>!",
                thread_ts=thread_ts
            )
            
            # Process the PR creation request
            return await self.process_pr_creation_request_async(
                text, user_id, channel_id, thread_ts, 
                lambda text, thread_ts: self.slack_app.client.chat_postMessage(
                    channel=channel_id, text=text, thread_ts=thread_ts
                )
            )
        else:
            # Handle other types of requests
            self.slack_app.client.chat_postMessage(
                channel=channel_id,
                text=f"Hi <@{user_id}>! I'm a PR creation bot. To create a PR, mention me with 'create PR' or 'create pull request' followed by your request.",
                thread_ts=thread_ts
            )
            return {"message": "Not a PR creation request"}
    
    async def handle_pull_request_event(self, org: str, repo: str, payload: Dict[str, Any], request: Request):
        """
        Handle a pull request event.
        
        Args:
            org: The organization name
            repo: The repository name
            payload: The event payload
            request: The request object
            
        Returns:
            The result of handling the event
        """
        # Extract event data
        action = payload.get("action")
        pr = payload.get("pull_request", {})
        pr_number = pr.get("number")
        
        # Handle different actions
        if action == "labeled":
            # Extract label
            label = payload.get("label", {})
            label_name = label.get("name")
            
            # Check if this is a Codegen label
            if label_name == "Codegen":
                # Initialize the codebase
                codebase = self.codebase_analyzer.get_codebase(f"{org}/{repo}")
                
                # Check out the PR head
                head_sha = pr.get("head", {}).get("sha")
                codebase.checkout(commit=head_sha)
                
                # Analyze the PR
                self.analyze_pr(codebase, PullRequestLabeledEvent(
                    action=action,
                    number=pr_number,
                    pull_request=pr,
                    label=label,
                    organization={"login": org},
                    repository={"name": repo}
                ))
                
                return {
                    "message": "PR event handled", 
                    "num_files": len(codebase.files), 
                    "num_functions": len(codebase.functions)
                }
            else:
                return {"message": f"Ignored label: {label_name}"}
        else:
            return {"message": f"Ignored action: {action}"}
    
    async def handle_issue_event(self, org: str, repo: str, payload: Dict[str, Any], request: Request):
        """
        Handle an issue event.
        
        Args:
            org: The organization name
            repo: The repository name
            payload: The event payload
            request: The request object
            
        Returns:
            The result of handling the event
        """
        # Extract event data
        action = payload.get("action")
        issue = payload.get("issue", {})
        issue_number = issue.get("number")
        
        # Handle different actions
        if action == "created":
            # Initialize the codebase
            codebase = self.codebase_analyzer.get_codebase(f"{org}/{repo}")
            
            return {
                "message": "Issue event handled", 
                "num_files": len(codebase.files), 
                "num_functions": len(codebase.functions)
            }
        else:
            return {"message": f"Ignored action: {action}"}