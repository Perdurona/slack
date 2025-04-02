"""
Response Formatter for formatting Slack messages.

This module provides the ResponseFormatter class that formats responses
for Slack messages.
"""

import logging
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class ResponseFormatter:
    """
    Formatter for Slack messages.
    
    This class formats responses for Slack messages, including PR creation
    responses and error messages.
    """
    
    def __init__(self):
        """Initialize the response formatter."""
        pass
    
    def format_pr_creation_response(self, pr_result: Dict[str, Any]) -> str:
        """
        Format a PR creation response.
        
        Args:
            pr_result: The PR creation result
            
        Returns:
            A formatted response string
        """
        # Extract PR details
        pr_number = pr_result.get("pr_number")
        pr_url = pr_result.get("pr_url")
        pr_title = pr_result.get("pr_title")
        user = pr_result.get("user")
        files_modified = pr_result.get("files_modified", [])
        
        # Format the file modifications
        file_modifications = self._format_file_modifications(files_modified)
        
        # Format the message
        message = f""":tada: *PR Created Successfully!* :tada:

<@{user}>, I've created a new Pull Request for you:

*<{pr_url}|#{pr_number}: {pr_title}>*

*Changes:*
{file_modifications}

You can review and merge the PR using the link above."""
        
        return message
    
    def _format_file_modifications(self, files_modified: List[Dict[str, Any]]) -> str:
        """
        Format the file modifications for display in Slack.
        
        Args:
            files_modified: List of file modifications
            
        Returns:
            A formatted string
        """
        if not files_modified:
            return "No files were modified."
        
        formatted_files = []
        for file in files_modified:
            path = file.get("path", "unknown")
            action = file.get("action", "unknown")
            status = file.get("status", "unknown")
            
            if status == "success":
                icon = "✅"
            else:
                icon = "❌"
            
            if action == "create":
                action_text = "Created"
            elif action == "modify":
                action_text = "Modified"
            elif action == "delete":
                action_text = "Deleted"
            else:
                action_text = action.capitalize()
            
            formatted_files.append(f"{icon} {action_text} `{path}`")
        
        return "\n".join(formatted_files)
    
    def format_error_response(self, error_message: str) -> str:
        """
        Format an error response.
        
        Args:
            error_message: The error message
            
        Returns:
            A formatted error response string
        """
        message = f""":x: *Error*

I encountered an error while processing your request:

```
{error_message}
```

Please try again or contact an administrator if the problem persists."""
        
        return message
    
    def format_pr_update_response(self, pr_result: Dict[str, Any]) -> str:
        """
        Format a PR update response.
        
        Args:
            pr_result: The PR update result
            
        Returns:
            A formatted response string
        """
        # Extract PR details
        pr_number = pr_result.get("pr_number")
        pr_url = pr_result.get("pr_url")
        pr_title = pr_result.get("pr_title")
        user = pr_result.get("user")
        files_modified = pr_result.get("files_modified", [])
        
        # Format the file modifications
        file_modifications = self._format_file_modifications(files_modified)
        
        # Format the message
        message = f""":white_check_mark: *PR Updated Successfully!* :white_check_mark:

<@{user}>, I've updated the Pull Request for you:

*<{pr_url}|#{pr_number}: {pr_title}>*

*Changes:*
{file_modifications}

You can review the updated PR using the link above."""
        
        return message
    
    def format_loading_message(self, action: str) -> str:
        """
        Format a loading message.
        
        Args:
            action: The action being performed
            
        Returns:
            A formatted loading message string
        """
        return f":hourglass_flowing_sand: {action}... Please wait."
    
    def format_codebase_analysis_response(self, analysis: Dict[str, Any]) -> str:
        """
        Format a codebase analysis response.
        
        Args:
            analysis: The codebase analysis result
            
        Returns:
            A formatted response string
        """
        if "error" in analysis:
            return self.format_error_response(analysis["error"])
        
        if "raw_analysis" in analysis:
            return f"""*Codebase Analysis:*

```
{analysis["raw_analysis"]}
```"""
        
        # Format the modules
        modules = analysis.get("modules", [])
        modules_text = ""
        for module in modules:
            name = module.get("name", "")
            purpose = module.get("purpose", "")
            modules_text += f"• *{name}*: {purpose}\n"
        
        # Format the key classes
        key_classes = analysis.get("key_classes", [])
        classes_text = ""
        for cls in key_classes:
            name = cls.get("name", "")
            purpose = cls.get("purpose", "")
            classes_text += f"• *{name}*: {purpose}\n"
        
        # Format the key functions
        key_functions = analysis.get("key_functions", [])
        functions_text = ""
        for func in key_functions:
            name = func.get("name", "")
            purpose = func.get("purpose", "")
            functions_text += f"• *{name}*: {purpose}\n"
        
        # Format the architecture
        architecture = analysis.get("architecture", "")
        
        # Format the message
        message = f"""*Codebase Analysis:*

*Modules:*
{modules_text or "No modules found."}

*Key Classes:*
{classes_text or "No key classes found."}

*Key Functions:*
{functions_text or "No key functions found."}

*Architecture:*
{architecture or "No architecture information available."}"""
        
        return message