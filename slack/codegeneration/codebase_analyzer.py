"""
Codebase Analyzer for analyzing repositories and generating changes.

This module provides the CodebaseAnalyzer class that uses Codegen's tools
to analyze repositories and generate code changes based on user requests.
"""

import json
import logging
import os
import re
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Union

from codegen import CodeAgent, Codebase
from codegen.sdk.core.codebase import Codebase
from codegen.shared.enums.programming_language import ProgrammingLanguage
from codegen.configs.models.codebase import CodebaseConfig
from codegen.configs.models.secrets import SecretsConfig
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
    code changes based on user requests. It handles dynamic repository
    initialization and caching for better performance.
    """
    
    def __init__(
        self,
        model_provider: str = "anthropic",
        model_name: str = "claude-3-5-sonnet-latest",
        github_token: Optional[str] = None,
        default_language: ProgrammingLanguage = ProgrammingLanguage.PYTHON,
        tmp_dir: str = "/tmp/codegen"
    ):
        """
        Initialize the CodebaseAnalyzer.
        
        Args:
            model_provider: The model provider to use (anthropic or openai)
            model_name: The name of the model to use
            github_token: GitHub API token (optional)
            default_language: The default programming language to use
            tmp_dir: Temporary directory for cloning repositories
        """
        self.model_provider = model_provider
        self.model_name = model_name
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.default_language = default_language
        self.tmp_dir = tmp_dir
        self.codebase_cache = {}
        
        # Create the temporary directory if it doesn't exist
        os.makedirs(self.tmp_dir, exist_ok=True)
    
    def get_codebase(self, repo_name: str, language: Optional[ProgrammingLanguage] = None, commit: str = "latest") -> Codebase:
        """
        Get a codebase instance for a repository.
        
        This method tries multiple initialization methods and caches codebase
        instances to avoid re-initializing them for the same repository.
        
        Args:
            repo_name: The name of the repository (org/repo or local path)
            language: The programming language of the codebase (optional)
            commit: The commit to checkout (default: "latest")
            
        Returns:
            A codebase instance
            
        Raises:
            Exception: If all initialization methods fail
        """
        cache_key = f"{repo_name}:{commit}"
        if cache_key in self.codebase_cache:
            logger.info(f"Using cached codebase for {repo_name}")
            return self.codebase_cache[cache_key]
        
        # Detect language if not provided
        detected_language = language or self.detect_programming_language_from_name(repo_name)
        
        logger.info(f"Initializing codebase for {repo_name} with language {detected_language}")
        
        # Try different initialization methods
        errors = []
        
        # Method 1: Try to initialize from GitHub repo
        if "/" in repo_name and not os.path.exists(repo_name):
            try:
                logger.info(f"Trying to initialize from GitHub repo: {repo_name}")
                config = CodebaseConfig(sync_enabled=True)
                secrets = SecretsConfig(github_token=self.github_token)
                
                codebase = Codebase.from_repo(
                    repo_full_name=repo_name, 
                    language=detected_language, 
                    tmp_dir=self.tmp_dir,
                    commit=commit,
                    config=config,
                    secrets=secrets
                )
                
                self.codebase_cache[cache_key] = codebase
                logger.info(f"Successfully initialized codebase from GitHub repo: {repo_name}")
                return codebase
            except Exception as e:
                error_msg = f"Error initializing codebase from GitHub repo: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
        
        # Method 2: Try to initialize from local path
        try:
            # Check if the repo name is a local path
            if os.path.exists(repo_name):
                logger.info(f"Trying to initialize from local path: {repo_name}")
                codebase = Codebase(repo_name, language=detected_language)
                self.codebase_cache[cache_key] = codebase
                logger.info(f"Successfully initialized codebase from local path: {repo_name}")
                return codebase
        except Exception as e:
            error_msg = f"Error initializing codebase from local path: {str(e)}"
            logger.warning(error_msg)
            errors.append(error_msg)
        
        # Method 3: Try to find the repo in common locations
        common_locations = [
            os.path.join(os.getcwd(), repo_name),
            os.path.join(os.path.expanduser("~"), repo_name),
            os.path.join(self.tmp_dir, repo_name)
        ]
        
        for location in common_locations:
            try:
                if os.path.exists(location):
                    logger.info(f"Trying to initialize from common location: {location}")
                    codebase = Codebase(location, language=detected_language)
                    self.codebase_cache[cache_key] = codebase
                    logger.info(f"Successfully initialized codebase from common location: {location}")
                    return codebase
            except Exception as e:
                error_msg = f"Error initializing codebase from common location {location}: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
        
        # Method 4: Create a new temporary codebase
        try:
            logger.info(f"Creating a new temporary codebase for: {repo_name}")
            temp_dir = tempfile.mkdtemp(dir=self.tmp_dir)
            codebase = Codebase(temp_dir, language=detected_language)
            self.codebase_cache[cache_key] = codebase
            logger.info(f"Successfully created a new temporary codebase for: {repo_name}")
            return codebase
        except Exception as e:
            error_msg = f"Error creating a new temporary codebase: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        # If all methods fail, raise an exception with all errors
        raise Exception(f"Failed to initialize codebase for {repo_name}. Errors: {'; '.join(errors)}")
    
    def detect_programming_language_from_name(self, repo_name: str) -> ProgrammingLanguage:
        """
        Detect the programming language from the repository name.
        
        Args:
            repo_name: The name of the repository
            
        Returns:
            The detected programming language
        """
        # Extract the repo part from org/repo format
        if "/" in repo_name and not os.path.exists(repo_name):
            repo_part = repo_name.split("/")[-1]
        else:
            repo_part = os.path.basename(repo_name)
        
        # Check for language indicators in the name
        language_indicators = {
            "python": ProgrammingLanguage.PYTHON,
            "py": ProgrammingLanguage.PYTHON,
            "django": ProgrammingLanguage.PYTHON,
            "flask": ProgrammingLanguage.PYTHON,
            "js": ProgrammingLanguage.JAVASCRIPT,
            "javascript": ProgrammingLanguage.JAVASCRIPT,
            "node": ProgrammingLanguage.JAVASCRIPT,
            "ts": ProgrammingLanguage.TYPESCRIPT,
            "typescript": ProgrammingLanguage.TYPESCRIPT,
            "react": ProgrammingLanguage.JAVASCRIPT,
            "vue": ProgrammingLanguage.JAVASCRIPT,
            "angular": ProgrammingLanguage.TYPESCRIPT,
            "java": ProgrammingLanguage.JAVA,
            "go": ProgrammingLanguage.GO,
            "golang": ProgrammingLanguage.GO,
            "ruby": ProgrammingLanguage.RUBY,
            "rails": ProgrammingLanguage.RUBY,
            "php": ProgrammingLanguage.PHP,
            "laravel": ProgrammingLanguage.PHP,
            "cpp": ProgrammingLanguage.CPP,
            "c++": ProgrammingLanguage.CPP,
            "csharp": ProgrammingLanguage.CSHARP,
            "cs": ProgrammingLanguage.CSHARP,
            "dotnet": ProgrammingLanguage.CSHARP,
            "swift": ProgrammingLanguage.SWIFT,
            "kotlin": ProgrammingLanguage.KOTLIN,
            "rust": ProgrammingLanguage.RUST,
        }
        
        repo_part_lower = repo_part.lower()
        for indicator, language in language_indicators.items():
            if indicator in repo_part_lower:
                return language
        
        # Default to the default language
        return self.default_language
    
    def detect_programming_language(self, repo_name: str) -> ProgrammingLanguage:
        """
        Detect the programming language of a repository by analyzing its files.
        
        Args:
            repo_name: The name of the repository
            
        Returns:
            The detected programming language
        """
        try:
            # Try to initialize the codebase
            try:
                codebase = self.get_codebase(repo_name)
            except Exception:
                # If initialization fails, return the default language
                return self.default_language
            
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
            if extension_counts:
                most_common_ext = max(extension_counts.items(), key=lambda x: x[1])[0]
                if most_common_ext in extension_to_language:
                    return extension_to_language[most_common_ext]
            
            # Default to Python
            return self.default_language
        except Exception as e:
            logger.error(f"Error detecting programming language: {str(e)}")
            return self.default_language
    
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
            language = self.detect_programming_language(repo_name)
            codebase_docs = get_codebase_docstring(codebase, language)
            
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
    
    def extract_repo_and_changes(self, text: str) -> Tuple[str, str]:
        """
        Extract repository name and change details from the user's text.
        
        Args:
            text: The user's message text
            
        Returns:
            A tuple containing the repository name and change details
        """
        logger.info(f"Extracting repo and changes from: {text}")
        
        # Create a chat agent to analyze the text
        agent = create_chat_agent(
            model_provider=self.model_provider,
            model_name=self.model_name
        )
        
        # Prompt the agent to extract repository and change details
        prompt = f"""
        Extract the repository name and change details from the following text:
        
        {text}
        
        Return the result as a JSON object with the following structure:
        {{
            "repository": "repository_name",
            "changes": "detailed description of the changes to make"
        }}
        
        If the repository name is not explicitly mentioned, use "default_repo" as the repository name.
        """
        
        response = agent.invoke(prompt)
        
        try:
            # Parse the JSON response
            result = json.loads(response)
            repository = result.get("repository", "default_repo")
            changes = result.get("changes", "")
            
            logger.info(f"Extracted repository: {repository}")
            logger.info(f"Extracted changes: {changes}")
            
            return repository, changes
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response}")
            # Fallback to simple extraction
            if "repository" in text.lower():
                parts = text.lower().split("repository")
                repository = parts[1].strip().split()[0]
            else:
                repository = "default_repo"
                
            changes = text
                
            return repository, changes