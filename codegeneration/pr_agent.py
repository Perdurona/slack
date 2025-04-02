"""
PR Agent for creating GitHub PRs from Slack messages.

This module provides the main PR Agent class that coordinates the workflow
between Slack, Codegen, and GitHub.
"""

import logging
import os
import re
import json
from typing import Dict, Any, Optional, Tuple, List, Literal, Callable

from fastapi import Request
from slack_bolt import App

from codegen import CodeAgent, Codebase
from codegen.sdk.core.codebase import Codebase
from codegen.shared.enums.programming_language import ProgrammingLanguage
from codegen.extensions.langchain.agent import (
    create_codebase_inspector_agent,
    create_chat_agent,
    create_codebase_agent,
    create_agent_with_tools
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
    RipGrepTool,
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

from .codebase_analyzer import CodebaseAnalyzer
from .github_handler import GitHubHandler
from .response_formatter import ResponseFormatter
from ai.providers import get_provider_response
from listeners.listener_utils.parse_conversation import parse_conversation
from listeners.listener_utils.listener_constants import DEFAULT_LOADING_TEXT

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
        slack_app: Optional[App] = None
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
        """
        self.github_token = github_token
        self.model_provider = model_provider
        self.model_name = model_name
        self.default_repo = default_repo
        self.default_org = default_org
        self.slack_app = slack_app
        
        # Initialize components
        self.codebase_analyzer = CodebaseAnalyzer(
            model_provider=model_provider,
            model_name=model_name,
            github_token=github_token
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
        
        # Register app_mention handler if slack_app is provided
        if slack_app:
            self.register_slack_handlers()
    
    def register_slack_handlers(self):
        """
        Register Slack event handlers.
        """
        if not self.slack_app:
            logger.warning("Cannot register handlers: Slack app not provided")
            return
        
        @self.slack_app.event("app_mention")
        def handle_app_mention(event, say, client):
            try:
                channel_id = event.get("channel")
                thread_ts = event.get("thread_ts", event.get("ts"))
                user_id = event.get("user")
                text = event.get("text", "")
                
                # Check if this is a PR creation request
                if self.is_pr_creation_request(text):
                    # Acknowledge receipt
                    say(
                        text=f"I'll work on creating a PR based on your request, <@{user_id}>!",
                        thread_ts=thread_ts
                    )
                    
                    # Process the PR creation request
                    self.process_pr_creation_request(
                        text, user_id, channel_id, thread_ts,
                        lambda msg, ts: say(text=msg, thread_ts=ts)
                    )
                else:
                    # Get conversation context for AI response
                    if thread_ts:
                        conversation = client.conversations_replies(
                            channel=channel_id, ts=thread_ts, limit=10
                        )["messages"]
                    else:
                        conversation = client.conversations_history(
                            channel=channel_id, limit=10
                        )["messages"]
                    
                    conversation_context = parse_conversation(conversation[:-1])
                    
                    # Send loading message
                    waiting_message = say(text=DEFAULT_LOADING_TEXT, thread_ts=thread_ts)
                    
                    # Get AI response
                    response = get_provider_response(user_id, text, conversation_context)
                    
                    # Update message with response
                    client.chat_update(
                        channel=channel_id,
                        ts=waiting_message["ts"],
                        text=response
                    )
            except Exception as e:
                logger.error(f"Error handling app mention: {str(e)}")
                say(
                    text=f"Sorry, I encountered an error: {str(e)}",
                    thread_ts=thread_ts
                )
    
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
    
    def extract_repo_info(self, text: str) -> Tuple[str, str, str]:
        """
        Extract repository information from the text.
        
        Args:
            text: The message text
            
        Returns:
            A tuple containing (org_name, repo_name, full_repo_name)
        """
        # Try to extract repository information using regex
        repo_pattern = r"(?:in|for|to|on|at)\s+(?:the\s+)?(?:repo(?:sitory)?|project)?\s*[\"']?([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)[\"']?"
        repo_match = re.search(repo_pattern, text)
        
        if repo_match:
            full_repo_name = repo_match.group(1)
            org_name, repo_name = full_repo_name.split("/")
            return org_name, repo_name, full_repo_name
        
        # If no repository is specified, use the default
        if self.default_org and self.default_repo:
            return self.default_org, self.default_repo, f"{self.default_org}/{self.default_repo}"
        
        # If no repository is specified and no default is set, return empty strings
        return "", "", ""
    
    def process_pr_creation_request(
        self,
        text: str,
        user_id: str,
        channel_id: str,
        thread_ts: str,
        say_callback: Callable[[str, str], Any]
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
            # Extract repository information
            org_name, repo_name, full_repo_name = self.extract_repo_info(text)
            
            if not full_repo_name:
                say_callback(
                    f"I couldn't determine which repository to create a PR for. Please specify a repository in the format 'org/repo'.",
                    thread_ts
                )
                return {"error": "Repository not specified"}
            
            # Update the user
            say_callback(
                f"Analyzing repository {full_repo_name}...",
                thread_ts
            )
            
            # Analyze the repository
            analysis_result = self.codebase_analyzer.analyze_repository(full_repo_name, text)
            
            if "error" in analysis_result:
                say_callback(
                    f"Error analyzing repository: {analysis_result['error']}",
                    thread_ts
                )
                return analysis_result
            
            # Update the user
            say_callback(
                f"Generating changes for {full_repo_name}...",
                thread_ts
            )
            
            # Generate changes
            changes = self.codebase_analyzer.generate_changes(full_repo_name, text, analysis_result)
            
            if "error" in changes:
                say_callback(
                    f"Error generating changes: {changes['error']}",
                    thread_ts
                )
                return changes
            
            # Update the user
            say_callback(
                f"Creating PR for {full_repo_name}...",
                thread_ts
            )
            
            # Create the PR
            pr_result = self.github_handler.create_pr(
                repo_name=full_repo_name,
                changes=changes,
                user_id=user_id
            )
            
            if "error" in pr_result:
                say_callback(
                    f"Error creating PR: {pr_result['error']}",
                    thread_ts
                )
                return pr_result
            
            # Format the response
            response = self.response_formatter.format_pr_creation_result(pr_result)
            
            # Send the response
            say_callback(response, thread_ts)
            
            return pr_result
            
        except Exception as e:
            logger.error(f"Error processing PR creation request: {str(e)}")
            say_callback(
                f"Sorry, I encountered an error while processing your PR creation request: {str(e)}",
                thread_ts
            )
            return {"error": str(e)}
    
    def handle_app_mention(self, event: Dict[str, Any], say) -> Dict[str, Any]:
        """
        Handle an app mention event.
        
        Args:
            event: The event data
            say: Function for sending messages
            
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
                say(text=f"I'll work on creating a PR based on your request, <@{user_id}>!", thread_ts=thread_ts)
                
                # Process the PR creation request
                return self.process_pr_creation_request(text, user_id, channel_id, thread_ts, 
                                                      lambda msg, ts: say(text=msg, thread_ts=ts))
            else:
                # This will be handled by the default app_mentioned_callback
                return {"message": "Not a PR creation request"}
                
        except Exception as e:
            logger.error(f"Error handling app mention: {str(e)}")
            say(text=f"Sorry, I encountered an error: {str(e)}", thread_ts=thread_ts)
            return {"error": str(e)}