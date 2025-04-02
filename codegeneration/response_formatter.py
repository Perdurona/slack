"""
Response Formatter for formatting PR creation results.

This module provides the ResponseFormatter class that formats PR creation results
into user-friendly messages for Slack.
"""

import logging
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class ResponseFormatter:
    """
    Formatter for PR creation results.
    
    This class formats PR creation results into user-friendly messages for Slack.
    """
    
    def __init__(self):
        """
        Initialize the Response Formatter.
        """
        pass
    
    def format_pr_creation_result(self, pr_result: Dict[str, Any]) -> str:
        """
        Format a PR creation result into a user-friendly message.
        
        Args:
            pr_result: The PR creation result
            
        Returns:
            A formatted message
        """
        if "error" in pr_result:
            return self.format_error_message(pr_result)
        
        # Extract PR details
        pr_number = pr_result.get("pr_number")
        pr_url = pr_result.get("pr_url")
        pr_title = pr_result.get("pr_title")
        files_modified = pr_result.get("files_modified", [])
        
        # Format the message
        message = f":tada: <{pr_url}|View PR #{pr_number} on GitHub> :tada:\n\n"
        
        # Add PR title and description
        message += f"*Title*: {pr_title}\n\n"
        
        # Add files modified
        if files_modified:
            message += "*Summary of Changes*:\n"
            for file in files_modified[:5]:  # Limit to 5 files to avoid long messages
                path = file.get("path", "")
                action = file.get("action", "modified")
                
                if action == "create":
                    message += f"• Created `{path}`\n"
                elif action == "modify":
                    message += f"• Modified `{path}`\n"
                elif action == "delete":
                    message += f"• Deleted `{path}`\n"
                else:
                    message += f"• Changed `{path}`\n"
            
            if len(files_modified) > 5:
                message += f"• ... and {len(files_modified) - 5} more files\n"
        
        return message
    
    def format_error_message(self, error_result: Dict[str, Any]) -> str:
        """
        Format an error message.
        
        Args:
            error_result: The error result
            
        Returns:
            A formatted error message
        """
        error_message = error_result.get("error", "Unknown error")
        
        message = f":warning: *Error creating PR*: {error_message}\n\n"
        
        # Add additional details if available
        if "files_modified" in error_result and error_result["files_modified"]:
            message += "*Files that were modified before the error*:\n"
            for file in error_result["files_modified"]:
                path = file.get("path", "")
                status = file.get("status", "unknown")
                
                if status == "success":
                    message += f"• Successfully modified `{path}`\n"
                else:
                    file_error = file.get("error", "unknown error")
                    message += f"• Failed to modify `{path}`: {file_error}\n"
        
        return message
    
    def format_repository_analysis(self, analysis_result: Dict[str, Any]) -> str:
        """
        Format a repository analysis result into a user-friendly message.
        
        Args:
            analysis_result: The repository analysis result
            
        Returns:
            A formatted message
        """
        if "error" in analysis_result:
            return f":warning: *Error analyzing repository*: {analysis_result['error']}"
        
        repository = analysis_result.get("repository", "")
        analysis = analysis_result.get("analysis", {})
        
        # Extract repository structure
        repo_structure = analysis.get("repository_structure", {})
        key_files = repo_structure.get("key_files", [])
        key_directories = repo_structure.get("key_directories", [])
        
        # Extract analysis details
        analysis_details = analysis.get("analysis", {})
        summary = analysis_details.get("summary", "")
        key_findings = analysis_details.get("key_findings", [])
        
        # Format the message
        message = f":mag: *Repository Analysis for {repository}*\n\n"
        
        if summary:
            message += f"*Summary*: {summary}\n\n"
        
        if key_files:
            message += "*Key Files*:\n"
            for file in key_files[:5]:  # Limit to 5 files
                message += f"• `{file}`\n"
            if len(key_files) > 5:
                message += f"• ... and {len(key_files) - 5} more files\n"
            message += "\n"
        
        if key_directories:
            message += "*Key Directories*:\n"
            for directory in key_directories[:5]:  # Limit to 5 directories
                message += f"• `{directory}`\n"
            if len(key_directories) > 5:
                message += f"• ... and {len(key_directories) - 5} more directories\n"
            message += "\n"
        
        if key_findings:
            message += "*Key Findings*:\n"
            for finding in key_findings[:5]:  # Limit to 5 findings
                message += f"• {finding}\n"
            if len(key_findings) > 5:
                message += f"• ... and {len(key_findings) - 5} more findings\n"
        
        return message