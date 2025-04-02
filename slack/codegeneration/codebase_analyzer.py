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
        github_token: Optional[str] = None,
        language: ProgrammingLanguage = ProgrammingLanguage.PYTHON
    ):
        """
        Initialize the CodebaseAnalyzer.
        
        Args:
            model_provider: The model provider to use (anthropic or openai)
            model_name: The name of the model to use
            github_token: GitHub API token (optional)
            language: The programming language of the codebase
        """
        self.model_provider = model_provider
        self.model_name = model_name
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.language = language
        self.codebase_cache = {}
        
    def get_codebase(self, repo_name: str) -> Codebase:
        """
        Get a codebase instance for a repository.
        
        This method caches codebase instances to avoid re-initializing them
        for the same repository.
        
        Args:
            repo_name: The name of the repository
            
        Returns:
            A codebase instance
        """
        if repo_name in self.codebase_cache:
            logger.info(f"Using cached codebase for {repo_name}")
            return self.codebase_cache[repo_name]
        
        logger.info(f"Initializing codebase for {repo_name}")
        try:
            # Try to initialize from repo
            codebase = Codebase.from_repo(
                repo_name, 
                language=self.language.value, 
                github_token=self.github_token
            )
            self.codebase_cache[repo_name] = codebase
            return codebase
        except Exception as e:
            logger.error(f"Error initializing codebase from repo: {str(e)}")
            
            # Try to initialize from local path
            try:
                # Check if the repo name is a local path
                if os.path.exists(repo_name):
                    codebase = Codebase(repo_name, language=self.language.value)
                    self.codebase_cache[repo_name] = codebase
                    return codebase
                
                # Try to find the repo in common locations
                common_locations = [
                    os.path.join(os.getcwd(), repo_name),
                    os.path.join(os.path.expanduser("~"), repo_name),
                    os.path.join("/tmp", repo_name)
                ]
                
                for location in common_locations:
                    if os.path.exists(location):
                        codebase = Codebase(location, language=self.language.value)
                        self.codebase_cache[repo_name] = codebase
                        return codebase
                
                # If all else fails, create a new codebase
                codebase = Codebase(repo_name, language=self.language.value)
                self.codebase_cache[repo_name] = codebase
                return codebase
            except Exception as e2:
                logger.error(f"Error initializing codebase from local path: {str(e2)}")
                raise Exception(f"Failed to initialize codebase: {str(e)}, {str(e2)}")
    
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
            codebase = self.get_codebase(repo_name)
            
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
            codebase = self.get_codebase(repo_name)
            
            # Get codebase documentation to enhance context
            codebase_docs = get_codebase_docstring(codebase, self.language)
            
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
                SemanticEditTool(codebase),
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
    
    def detect_programming_language(self, repo_name: str) -> ProgrammingLanguage:
        """
        Detect the programming language of a repository.
        
        Args:
            repo_name: The name of the repository
            
        Returns:
            The detected programming language
        """
        try:
            # Initialize the codebase
            codebase = self.get_codebase(repo_name)
            
            # Count file extensions
            extension_counts = {}
            for file in codebase.files:
                ext = os.path.splitext(file.filepath)[1].lower()
                if ext:
                    extension_counts[ext] = extension_counts.get(ext, 0) + 1
            
            # Map extensions to languages
            extension_to_language = {
                ".py": ProgrammingLanguage.PYTHON,
                ".js": ProgrammingLanguage.JAVASCRIPT,
                ".ts": ProgrammingLanguage.TYPESCRIPT,
                ".jsx": ProgrammingLanguage.JAVASCRIPT,
                ".tsx": ProgrammingLanguage.TYPESCRIPT,
                ".java": ProgrammingLanguage.JAVA,
                ".go": ProgrammingLanguage.GO,
                ".rb": ProgrammingLanguage.RUBY,
                ".php": ProgrammingLanguage.PHP,
                ".c": ProgrammingLanguage.C,
                ".cpp": ProgrammingLanguage.CPP,
                ".cs": ProgrammingLanguage.CSHARP,
                ".swift": ProgrammingLanguage.SWIFT,
                ".kt": ProgrammingLanguage.KOTLIN,
                ".rs": ProgrammingLanguage.RUST
            }
            
            # Find the most common language
            most_common_ext = max(extension_counts.items(), key=lambda x: x[1])[0] if extension_counts else None
            
            if most_common_ext and most_common_ext in extension_to_language:
                return extension_to_language[most_common_ext]
            
            # Default to Python
            return ProgrammingLanguage.PYTHON
        except Exception as e:
            logger.error(f"Error detecting programming language: {str(e)}")
            return ProgrammingLanguage.PYTHON