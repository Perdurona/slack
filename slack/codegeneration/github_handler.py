"""
GitHub Handler for creating and managing PRs.

This module provides the GitHubHandler class that creates and manages PRs
using Codegen's GitHub tools.
"""

import logging
import os
import time
import uuid
from typing import Dict, Any, List, Optional

from codegen.extensions.tools.github.create_pr import create_pr
from codegen.git.repo_operator.repo_operator import RepoOperator

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class GitHubHandler:
    """
    Handler for GitHub operations, including PR creation and management.
    
    This class uses Codegen's GitHub tools to create and manage PRs.
    """
    
    def __init__(self, github_token: Optional[str] = None, default_base_branch: str = "main"):
        """
        Initialize the GitHub handler.
        
        Args:
            github_token: GitHub API token
            default_base_branch: Default base branch for PRs
        """
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.default_base_branch = default_base_branch
        
    def create_pr(
        self,
        repo_name: str,
        changes: Dict[str, Any],
        user_id: str,
        base_branch: Optional[str] = None,
        head_branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a GitHub PR based on the generated changes.
        
        Args:
            repo_name: The name of the repository
            changes: The changes to apply
            user_id: The user ID
            base_branch: The base branch for the PR
            head_branch: The head branch for the PR
            
        Returns:
            A dictionary containing the PR details
        """
        logger.info(f"Creating PR for repo: {repo_name}")
        
        try:
            # Initialize the repo operator
            repo_operator = RepoOperator(repo_name, token=self.github_token)
            
            # Set the base branch
            base = base_branch or self.default_base_branch
            
            # Generate a unique branch name if not provided
            if not head_branch:
                unique_id = str(uuid.uuid4())[:8]
                timestamp = int(time.time())
                head_branch = f"codegen-pr-{user_id}-{timestamp}-{unique_id}"
            
            # Create a new branch for the changes
            try:
                repo_operator.create_branch(head_branch, base_ref=base)
                logger.info(f"Created branch: {head_branch}")
            except Exception as e:
                logger.error(f"Error creating branch: {str(e)}")
                return {"error": f"Failed to create branch: {str(e)}", "user": user_id}
            
            # Apply the changes to the branch
            files_modified = []
            for file_change in changes.get("files_modified", []):
                file_path = file_change.get("path")
                content = file_change.get("content")
                action = file_change.get("action", "modify")
                
                try:
                    if action == "create":
                        repo_operator.create_file(file_path, content, branch=head_branch)
                    elif action == "modify":
                        repo_operator.update_file(file_path, content, branch=head_branch)
                    elif action == "delete":
                        repo_operator.delete_file(file_path, branch=head_branch)
                    
                    files_modified.append({
                        "path": file_path,
                        "action": action,
                        "status": "success"
                    })
                except Exception as e:
                    logger.error(f"Error modifying file {file_path}: {str(e)}")
                    files_modified.append({
                        "path": file_path,
                        "action": action,
                        "status": "error",
                        "error": str(e)
                    })
            
            # Create the PR
            try:
                pr_title = changes.get("pr_title", f"Automated PR: {head_branch}")
                pr_body = changes.get("pr_description", "This PR was automatically created based on a Slack request.")
                commit_message = changes.get("commit_message", f"Changes for {pr_title}")
                
                # Commit any remaining changes
                repo_operator.commit(commit_message, branch=head_branch)
                
                # Create the PR
                pr_result = create_pr(
                    repo_operator,
                    title=pr_title,
                    body=pr_body,
                    head=head_branch,
                    base=base
                )
                
                logger.info(f"Created PR: {pr_result.number}")
                
                return {
                    "pr_number": pr_result.number,
                    "pr_url": pr_result.url,
                    "pr_title": pr_result.title,
                    "pr_body": pr_body,
                    "files_modified": files_modified,
                    "user": user_id,
                    "head_branch": head_branch,
                    "base_branch": base
                }
            except Exception as e:
                logger.error(f"Error creating PR: {str(e)}")
                return {
                    "error": f"Failed to create PR: {str(e)}",
                    "files_modified": files_modified,
                    "user": user_id
                }
                
        except Exception as e:
            logger.error(f"Error in create_pr: {str(e)}")
            return {"error": str(e), "user": user_id}
    
    def add_pr_comment(self, repo_name: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """
        Add a comment to a GitHub PR.
        
        Args:
            repo_name: The name of the repository
            pr_number: The PR number
            comment: The comment text
            
        Returns:
            A dictionary containing the comment details
        """
        try:
            repo_operator = RepoOperator(repo_name, token=self.github_token)
            comment_result = repo_operator.create_pr_comment(pr_number, comment)
            return {
                "comment_id": comment_result.get("id"),
                "comment_url": comment_result.get("html_url"),
                "pr_number": pr_number
            }
        except Exception as e:
            return {"error": str(e), "pr_number": pr_number}
    
    def update_pr(
        self,
        repo_name: str,
        pr_number: int,
        changes: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Update an existing PR with new changes.
        
        Args:
            repo_name: The name of the repository
            pr_number: The PR number
            changes: The changes to apply
            user_id: The user ID
            
        Returns:
            A dictionary containing the PR details
        """
        logger.info(f"Updating PR #{pr_number} for repo: {repo_name}")
        
        try:
            # Initialize the repo operator
            repo_operator = RepoOperator(repo_name, token=self.github_token)
            
            # Get the PR details
            pr = repo_operator.get_pr(pr_number)
            head_branch = pr.head.ref
            
            # Apply the changes to the branch
            files_modified = []
            for file_change in changes.get("files_modified", []):
                file_path = file_change.get("path")
                content = file_change.get("content")
                action = file_change.get("action", "modify")
                
                try:
                    if action == "create":
                        repo_operator.create_file(file_path, content, branch=head_branch)
                    elif action == "modify":
                        repo_operator.update_file(file_path, content, branch=head_branch)
                    elif action == "delete":
                        repo_operator.delete_file(file_path, branch=head_branch)
                    
                    files_modified.append({
                        "path": file_path,
                        "action": action,
                        "status": "success"
                    })
                except Exception as e:
                    logger.error(f"Error modifying file {file_path}: {str(e)}")
                    files_modified.append({
                        "path": file_path,
                        "action": action,
                        "status": "error",
                        "error": str(e)
                    })
            
            # Commit the changes
            commit_message = changes.get("commit_message", f"Update PR #{pr_number}")
            repo_operator.commit(commit_message, branch=head_branch)
            
            # Add a comment to the PR
            comment = changes.get("pr_comment", f"Updated PR with new changes.")
            self.add_pr_comment(repo_name, pr_number, comment)
            
            return {
                "pr_number": pr_number,
                "pr_url": pr.html_url,
                "pr_title": pr.title,
                "files_modified": files_modified,
                "user": user_id,
                "head_branch": head_branch,
                "base_branch": pr.base.ref
            }
                
        except Exception as e:
            logger.error(f"Error updating PR: {str(e)}")
            return {"error": str(e), "user": user_id, "pr_number": pr_number}