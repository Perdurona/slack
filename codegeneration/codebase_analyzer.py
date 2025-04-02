"""
Codebase Analyzer for analyzing GitHub repositories.

This module provides the CodebaseAnalyzer class that analyzes GitHub repositories
and generates changes based on user requests.
"""

import logging
import os
import re
import json
import tempfile
from typing import Dict, Any, List, Optional, Tuple

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
    Analyzer for GitHub repositories.
    
    This class analyzes GitHub repositories and generates changes based on user requests.
    It uses Codegen's tools to understand the repository structure and generate code changes.
    """
    
    def __init__(
        self,
        model_provider: str = "anthropic",
        model_name: str = "claude-3-5-sonnet-latest",
        github_token: Optional[str] = None
    ):
        """
        Initialize the Codebase Analyzer.
        
        Args:
            model_provider: Model provider (anthropic or openai)
            model_name: Model name to use
            github_token: GitHub API token (optional)
        """
        self.model_provider = model_provider
        self.model_name = model_name
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.codebase_cache = {}
    
    def get_codebase(self, repo_name: str) -> Codebase:
        """
        Get a cached codebase or create a new one.
        
        Args:
            repo_name: The repository name (org/repo)
            
        Returns:
            A Codebase instance
        """
        if repo_name in self.codebase_cache:
            return self.codebase_cache[repo_name]
        
        logger.info(f"Creating new codebase for {repo_name}")
        
        # Determine the programming language based on the repository
        # This is a simple heuristic and could be improved
        if repo_name.endswith(".py") or "python" in repo_name.lower():
            language = ProgrammingLanguage.PYTHON
        elif repo_name.endswith(".js") or "javascript" in repo_name.lower() or "node" in repo_name.lower():
            language = ProgrammingLanguage.JAVASCRIPT
        elif repo_name.endswith(".ts") or "typescript" in repo_name.lower():
            language = ProgrammingLanguage.TYPESCRIPT
        elif repo_name.endswith(".go") or "go" in repo_name.lower():
            language = ProgrammingLanguage.GO
        elif repo_name.endswith(".java") or "java" in repo_name.lower():
            language = ProgrammingLanguage.JAVA
        else:
            # Default to Python
            language = ProgrammingLanguage.PYTHON
        
        # Create a temporary directory for the codebase
        tmp_dir = tempfile.mkdtemp()
        
        # Create the codebase
        codebase = Codebase.from_repo(
            repo_full_name=repo_name,
            language=language,
            tmp_dir=tmp_dir,
            github_token=self.github_token
        )
        
        # Cache the codebase
        self.codebase_cache[repo_name] = codebase
        
        return codebase
    
    def analyze_repository(self, repo_name: str, request_text: str) -> Dict[str, Any]:
        """
        Analyze a GitHub repository.
        
        Args:
            repo_name: The repository name (org/repo)
            request_text: The user's request text
            
        Returns:
            A dictionary containing the analysis results
        """
        try:
            logger.info(f"Analyzing repository: {repo_name}")
            
            # Initialize the codebase
            codebase = self.get_codebase(repo_name)
            
            # Create an agent with tools for analyzing the codebase
            tools = [
                ListDirectoryTool(codebase),
                ViewFileTool(codebase),
                RipGrepTool(codebase),
                RevealSymbolTool(codebase)
            ]
            
            agent = CodeAgent(
                codebase=codebase,
                model_provider=self.model_provider,
                model_name=self.model_name,
                tools=tools
            )
            
            # Create a prompt for analyzing the repository
            prompt = f"""
            Analyze this repository: {repo_name}
            
            The user has requested: "{request_text}"
            
            Please analyze the repository structure and identify the key components that would need to be modified to fulfill this request.
            
            Provide a detailed analysis including:
            1. Key files and directories
            2. Important classes and functions
            3. Dependencies and relationships
            4. Potential areas that need modification
            
            Format your response as a JSON object with the following structure:
            {{
                "repository_structure": {{
                    "key_files": ["file1", "file2", ...],
                    "key_directories": ["dir1", "dir2", ...],
                    "key_components": ["component1", "component2", ...]
                }},
                "analysis": {{
                    "summary": "Brief summary of the repository",
                    "key_findings": ["finding1", "finding2", ...],
                    "dependencies": ["dependency1", "dependency2", ...]
                }},
                "modification_plan": {{
                    "files_to_modify": [
                        {{
                            "path": "path/to/file1",
                            "reason": "Reason for modification",
                            "suggested_changes": "Description of changes"
                        }},
                        ...
                    ],
                    "files_to_create": [
                        {{
                            "path": "path/to/new_file",
                            "purpose": "Purpose of the new file",
                            "content_description": "Description of the content"
                        }},
                        ...
                    ],
                    "files_to_delete": ["path/to/file_to_delete", ...],
                    "implementation_steps": ["step1", "step2", ...]
                }}
            }}
            """
            
            # Run the agent
            response = agent.run(prompt)
            
            # Parse the JSON response
            try:
                # Extract JSON from the response
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response
                
                # Clean up the JSON string
                json_str = re.sub(r'```.*?```', '', json_str, flags=re.DOTALL)
                
                # Parse the JSON
                analysis_result = json.loads(json_str)
                
                return {
                    "status": "success",
                    "repository": repo_name,
                    "analysis": analysis_result
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to parse analysis result: {e}",
                    "repository": repo_name,
                    "raw_response": response
                }
            
        except Exception as e:
            logger.error(f"Error analyzing repository: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "repository": repo_name
            }
    
    def generate_changes(self, repo_name: str, request_text: str, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate changes for a GitHub repository based on the analysis.
        
        Args:
            repo_name: The repository name (org/repo)
            request_text: The user's request text
            analysis_result: The analysis result from analyze_repository
            
        Returns:
            A dictionary containing the generated changes
        """
        try:
            logger.info(f"Generating changes for repository: {repo_name}")
            
            # Initialize the codebase
            codebase = self.get_codebase(repo_name)
            
            # Create an agent with tools for modifying the codebase
            tools = [
                ListDirectoryTool(codebase),
                ViewFileTool(codebase),
                RipGrepTool(codebase),
                RevealSymbolTool(codebase),
                CreateFileTool(codebase),
                DeleteFileTool(codebase),
                EditFileTool(codebase),
                MoveSymbolTool(codebase),
                RenameFileTool(codebase),
                ReplacementEditTool(codebase),
                SemanticEditTool(codebase)
            ]
            
            agent = CodeAgent(
                codebase=codebase,
                model_provider=self.model_provider,
                model_name=self.model_name,
                tools=tools
            )
            
            # Extract the modification plan from the analysis
            modification_plan = analysis_result.get("analysis", {}).get("modification_plan", {})
            
            # Create a prompt for generating changes
            prompt = f"""
            Generate changes for repository: {repo_name}
            
            The user has requested: "{request_text}"
            
            Based on the analysis, the following modifications are needed:
            {json.dumps(modification_plan, indent=2)}
            
            Please generate the necessary changes to fulfill the user's request.
            
            For each file that needs to be modified, provide:
            1. The file path
            2. The content before modification
            3. The content after modification
            
            For each new file that needs to be created, provide:
            1. The file path
            2. The complete content of the file
            
            Format your response as a JSON object with the following structure:
            {{
                "pr_title": "Title for the PR",
                "pr_description": "Description for the PR",
                "commit_message": "Commit message",
                "files_modified": [
                    {{
                        "path": "path/to/file",
                        "action": "modify|create|delete",
                        "content": "New content of the file"
                    }},
                    ...
                ]
            }}
            """
            
            # Run the agent
            response = agent.run(prompt)
            
            # Parse the JSON response
            try:
                # Extract JSON from the response
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response
                
                # Clean up the JSON string
                json_str = re.sub(r'```.*?```', '', json_str, flags=re.DOTALL)
                
                # Parse the JSON
                changes = json.loads(json_str)
                
                return {
                    "status": "success",
                    "repository": repo_name,
                    "pr_title": changes.get("pr_title", f"Automated PR: {request_text[:50]}..."),
                    "pr_description": changes.get("pr_description", f"This PR was automatically created based on the request: {request_text}"),
                    "commit_message": changes.get("commit_message", f"Automated commit: {request_text[:50]}..."),
                    "files_modified": changes.get("files_modified", [])
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to parse changes: {e}",
                    "repository": repo_name,
                    "raw_response": response
                }
            
        except Exception as e:
            logger.error(f"Error generating changes: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "repository": repo_name
            }