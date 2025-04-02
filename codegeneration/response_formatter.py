"""
Response Formatter for formatting Slack messages.

This module provides the ResponseFormatter class that formats responses
for Slack messages.
"""

import logging
import re
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
        repo = pr_result.get("repo", "")
        files_modified = pr_result.get("files_modified", [])
        
        # Format the file modifications
        file_modifications = self._format_file_modifications(files_modified)
        
        # Format the message
        message = f""":rocket: *PR Created Successfully!* :rocket:

<@{user}>, I've created a new Pull Request for you:

*<{pr_url}|#{pr_number}: {pr_title}>* in `{repo}`

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
        repo = pr_result.get("repo", "")
        files_modified = pr_result.get("files_modified", [])
        
        # Format the file modifications
        file_modifications = self._format_file_modifications(files_modified)
        
        # Format the message
        message = f""":white_check_mark: *PR Updated Successfully!* :white_check_mark:

<@{user}>, I've updated the Pull Request for you:

*<{pr_url}|#{pr_number}: {pr_title}>* in `{repo}`

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
    
    def format_pr_details_response(self, pr_details: Dict[str, Any]) -> str:
        """
        Format a PR details response.
        
        Args:
            pr_details: The PR details
            
        Returns:
            A formatted response string
        """
        if "error" in pr_details:
            return self.format_error_response(pr_details["error"])
        
        # Extract PR details
        pr_number = pr_details.get("pr_number")
        pr_url = pr_details.get("pr_url")
        pr_title = pr_details.get("pr_title")
        pr_body = pr_details.get("pr_body", "")
        head_branch = pr_details.get("head_branch")
        base_branch = pr_details.get("base_branch")
        state = pr_details.get("state")
        user = pr_details.get("user")
        repo = pr_details.get("repo", "")
        created_at = pr_details.get("created_at")
        updated_at = pr_details.get("updated_at")
        mergeable = pr_details.get("mergeable")
        
        # Format the message
        message = f"""*PR Details:*

*<{pr_url}|#{pr_number}: {pr_title}>* in `{repo}`

*State:* {state.capitalize() if state else "Unknown"}
*Created by:* {user}
*Created at:* {created_at}
*Updated at:* {updated_at}
*Head branch:* `{head_branch}`
*Base branch:* `{base_branch}`
*Mergeable:* {":white_check_mark:" if mergeable else ":x:"}

*Description:*
```
{pr_body}
```"""
        
        return message
    
    def format_merge_result_response(self, merge_result: Dict[str, Any]) -> str:
        """
        Format a merge result response.
        
        Args:
            merge_result: The merge result
            
        Returns:
            A formatted response string
        """
        if "error" in merge_result:
            return self.format_error_response(merge_result["error"])
        
        # Extract merge details
        pr_number = merge_result.get("pr_number")
        repo = merge_result.get("repo", "")
        merged = merge_result.get("merged", False)
        message = merge_result.get("message", "")
        sha = merge_result.get("sha", "")
        
        # Format the message
        if merged:
            response = f""":tada: *PR Merged Successfully!* :tada:

PR #{pr_number} in `{repo}` has been merged.

*Commit SHA:* `{sha}`
*Message:* {message}"""
        else:
            response = f""":warning: *PR Merge Failed* :warning:

PR #{pr_number} in `{repo}` could not be merged.

*Message:* {message}"""
        
        return response
    
    def format_help_message(self) -> str:
        """
        Format a help message.
        
        Returns:
            A formatted help message string
        """
        message = """*PR Creation Bot Help*

I can help you create and manage Pull Requests directly from Slack. Here are some examples of what you can ask me:

• `@bot create a PR to add error handling to the login component in the user-service repository`
• `@bot make a pull request to fix the bug in the authentication service`
• `@bot submit a PR to update the documentation in the api repository`

You can also specify the repository explicitly:
• `@bot create a PR in org/repo to add a new feature`

For more complex changes, you can provide more details:
• `@bot create a PR to implement the following changes: 1. Add error handling to the login component, 2. Update the error messages, 3. Add tests for the error cases`

If you have any questions or need help, feel free to ask!"""
        
        return message
    
    def extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """
        Extract code blocks from text.
        
        Args:
            text: The text containing code blocks
            
        Returns:
            A list of dictionaries containing the extracted code blocks
        """
        code_blocks = []
        code_block_pattern = r"```(?:(\w+)\n)?(.*?)```"
        matches = re.finditer(code_block_pattern, text, re.DOTALL)
        
        for match in matches:
            language = match.group(1) or "text"
            code = match.group(2).strip()
            code_blocks.append({
                "language": language,
                "code": code
            })
        
        return code_blocks