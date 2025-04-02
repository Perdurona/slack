"""
Codebase Analyzer for analyzing repositories and generating changes.

This module provides the CodebaseAnalyzer class that uses Codegen's tools
to analyze repositories and generate code changes based on user requests.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple

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
from codegen.sdk.code_generation.prompts.api_docs import (
    get_docstrings_for_classes,
    get_codebase_docstring,
    get_behavior_docstring,
    get_core_symbol_docstring,
    get_language_specific_docstring,
    get_codegen_sdk_docs
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class CodebaseAnalyzer:
    """
    Analyzer for codebases that generates changes based on user requests.
    
    This class uses Codegen's tools to analyze repositories and generate
    code changes based on user requests.
    """
    
    def __init__(
        self,
        model_provider: str = "anthropic",
        model_name: str = "claude-3-5-sonnet-latest",
        github_token: Optional[str] = None
    ):
        """
        Initialize the CodebaseAnalyzer.
        
        Args:
            model_provider: The model provider to use (anthropic or openai)
            model_name: The name of the model to use
            github_token: GitHub API token (optional)
        """
        self.model_provider = model_provider
        self.model_name = model_name
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        
    def analyze_codebase(self, repo_name: str) -> Dict[str, Any]:
        """
        Analyze a codebase to understand its structure and dependencies.
        
        Args:
            repo_name: The name of the repository
            
        Returns:
            A dictionary containing the analysis results
        """
        logger.info(f"Analyzing codebase: {repo_name}")
        
        try:
            # Initialize the codebase
            codebase = Codebase.from_repo(repo_name, github_token=self.github_token)
            
            # Create an inspector agent
            agent = create_codebase_inspector_agent(
                codebase,
                model_provider=self.model_provider,
                model_name=self.model_name
            )
            
            # Analyze the codebase
            prompt = f"""
            Analyze the codebase and provide a summary of its structure, including:
            
            1. Main modules and their purposes
            2. Key classes and functions
            3. Dependencies between components
            4. Overall architecture
            
            Return the analysis as a JSON object with the following structure:
            {{
                "modules": [
                    {{
                        "name": "module_name",
                        "purpose": "module_purpose",
                        "key_components": ["component1", "component2"]
                    }}
                ],
                "key_classes": [
                    {{
                        "name": "class_name",
                        "purpose": "class_purpose",
                        "methods": ["method1", "method2"]
                    }}
                ],
                "key_functions": [
                    {{
                        "name": "function_name",
                        "purpose": "function_purpose"
                    }}
                ],
                "dependencies": [
                    {{
                        "from": "component1",
                        "to": "component2",
                        "type": "dependency_type"
                    }}
                ],
                "architecture": "description_of_architecture"
            }}
            """
            
            response = agent.invoke(prompt)
            
            try:
                # Parse the JSON response
                analysis = json.loads(response)
                logger.info(f"Codebase analysis completed")
                return analysis
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {response}")
                # Return the raw response
                return {"raw_analysis": response}
                
        except Exception as e:
            logger.error(f"Error analyzing codebase: {str(e)}")
            return {"error": str(e)}
    
    def generate_changes(self, repo_name: str, change_details: str) -> Dict[str, Any]:
        """
        Generate code changes based on the repository and change details.
        
        Args:
            repo_name: The name of the repository
            change_details: Description of the changes to make
            
        Returns:
            A dictionary containing the generated changes
        """
        logger.info(f"Generating changes for repo: {repo_name}")
        logger.info(f"Change details: {change_details}")
        
        try:
            # Initialize the codebase
            codebase = Codebase.from_repo(repo_name, github_token=self.github_token)
            
            # Get codebase documentation to enhance context
            codebase_docs = get_codebase_docstring(codebase, ProgrammingLanguage.PYTHON)
            
            # Create tools for the agent
            tools = [
                CreateFileTool(codebase),
                DeleteFileTool(codebase),
                EditFileTool(codebase),
                ListDirectoryTool(codebase),
                MoveSymbolTool(codebase),
                RenameFileTool(codebase),
                ReplacementEditTool(codebase),
                RevealSymbolTool(codebase),
                SearchTool(codebase),
                ViewFileTool(codebase)
            ]
            
            # Create a codebase agent with the tools
            agent = create_codebase_agent(
                codebase,
                model_provider=self.model_provider,
                model_name=self.model_name,
                additional_tools=tools
            )
            
            # Generate the changes based on the change details
            prompt = f"""
            You are an expert software engineer tasked with implementing the following changes:
            
            {change_details}
            
            Codebase information:
            {codebase_docs}
            
            First, analyze the codebase to understand its structure and identify the files that need to be modified.
            Then, implement the requested changes using the available tools.
            
            Return your changes as a JSON object with the following structure:
            {{
                "files_modified": [
                    {{
                        "path": "path/to/file.py",
                        "action": "create|modify|delete",
                        "content": "new file content or changes"
                    }}
                ],
                "commit_message": "Brief description of the changes",
                "pr_title": "Title for the PR",
                "pr_description": "Detailed description of the changes for the PR"
            }}
            """
            
            response = agent.invoke(prompt)
            
            try:
                # Parse the JSON response
                changes = json.loads(response)
                logger.info(f"Generated changes: {changes}")
                return changes
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {response}")
                # Fallback to simple changes
                return {
                    "files_modified": [],
                    "commit_message": f"Changes based on: {change_details}",
                    "pr_title": f"Automated PR: {change_details[:50]}...",
                    "pr_description": f"This PR implements the following changes:\n\n{change_details}"
                }
                
        except Exception as e:
            logger.error(f"Error generating changes: {str(e)}")
            return {
                "error": str(e),
                "files_modified": [],
                "commit_message": f"Changes based on: {change_details}",
                "pr_title": f"Automated PR: {change_details[:50]}...",
                "pr_description": f"This PR implements the following changes:\n\n{change_details}"
            }
    
    def extract_code_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract code blocks from text.
        
        Args:
            text: The text containing code blocks
            
        Returns:
            A list of dictionaries containing the extracted code blocks
        """
        import re
        
        # Extract code blocks
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