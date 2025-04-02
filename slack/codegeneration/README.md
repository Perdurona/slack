# Codegen PR Creation Agent

This module provides a Slack bot that can create GitHub Pull Requests based on natural language requests. It uses Codegen's powerful tools to analyze repositories, generate code changes, and create PRs.

## Architecture

The PR Creation Agent consists of four main components:

1. **PR Agent**: The main coordinator that handles Slack events and PR creation workflow
2. **Codebase Analyzer**: Analyzes codebases and generates changes using Codegen's tools
3. **GitHub Handler**: Creates and manages PRs using Codegen's GitHub tools
4. **Response Formatter**: Formats responses for Slack messages

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Slack Events   │────▶│  Codebase       │────▶│  GitHub PR      │
│  API            │     │  Analyzer       │     │  Creator        │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                      Response Formatter                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
                              ▼
                    ┌─────────────────┐
                    │                 │
                    │  Slack Message  │
                    │  Response       │
                    │                 │
                    └─────────────────┘
```

## Components

### PR Agent (`pr_agent.py`)

The PR Agent is the main coordinator that handles Slack events and PR creation workflow. It:

- Detects PR creation requests using pattern matching
- Extracts repository and change details from user messages
- Coordinates the workflow between the Codebase Analyzer and GitHub Handler
- Provides feedback to users at each step of the process
- Integrates with CodegenApp for event handling

### Codebase Analyzer (`codebase_analyzer.py`)

The Codebase Analyzer uses Codegen's tools to analyze repositories and generate code changes. It:

- Initializes codebases from repositories or local paths with multiple fallback methods
- Analyzes codebase structure and dependencies
- Generates code changes based on user requests
- Detects programming languages and adapts accordingly
- Extracts repository and change details from user messages

### GitHub Handler (`github_handler.py`)

The GitHub Handler creates and manages PRs using Codegen's GitHub tools. It:

- Creates branches for changes
- Applies changes to files
- Creates PRs with appropriate titles and descriptions
- Adds comments to PRs and updates existing PRs
- Handles error cases with appropriate fallbacks

### Response Formatter (`response_formatter.py`)

The Response Formatter formats responses for Slack messages. It:

- Formats PR creation responses with emojis and formatting
- Formats error messages with clear explanations
- Formats codebase analysis results with structured information
- Provides help messages and other utility formatting

## Usage

Users can request PR creation by mentioning the bot with a message like:

```
@bot create a PR to add error handling to the login component in the user-service repository
```

The bot will:

1. Acknowledge the request
2. Analyze the repository
3. Generate the requested changes
4. Create a PR with the changes
5. Provide a link to the PR

## Configuration

The module requires the following environment variables:

- `GITHUB_TOKEN`: GitHub API token
- `SLACK_BOT_TOKEN`: Slack bot token
- `SLACK_APP_TOKEN`: Slack app token
- `CODEGEN_MODEL_PROVIDER`: Model provider (anthropic or openai)
- `CODEGEN_MODEL_NAME`: Model name to use
- `DEFAULT_REPO`: Default repository name (optional)
- `DEFAULT_ORG`: Default organization name (optional)

## Integration with Codegen

This module integrates with Codegen's powerful tools:

- **Codebase**: Represents a codebase and provides methods for analyzing and modifying it
- **CodeAgent**: Agent for interacting with a codebase
- **Langchain Tools**: Tools for manipulating files and code
- **GitHub Tools**: Tools for creating PRs, viewing PRs, and adding comments
- **CodegenApp**: Application for handling events from Slack, GitHub, and Linear

## Advanced Features

- **Dynamic Repository Initialization**: Automatically detects and initializes repositories with multiple fallback methods
- **Programming Language Detection**: Detects the programming language of a repository from name or content
- **Codebase Caching**: Caches codebase instances to avoid re-initializing them
- **Error Handling**: Robust error handling for all operations with appropriate fallbacks
- **PR Update Support**: Supports updating existing PRs with new changes
- **PR Merging**: Supports merging PRs directly from Slack
- **Event Handling**: Handles events from Slack, GitHub, and Linear

## Implementation Details

### Dynamic Codebase Initialization

The Codebase Analyzer uses a multi-step approach to initialize codebases:

1. Try to initialize from GitHub repo using Codegen's `Codebase.from_repo`
2. Try to initialize from local path if the repo name is a valid path
3. Try to find the repo in common locations (current directory, home directory, temp directory)
4. Create a new temporary codebase as a last resort

This ensures that the agent can work with repositories even if they're not directly accessible via GitHub.

### Programming Language Detection

The agent can detect the programming language of a repository in two ways:

1. From the repository name (e.g., "python-project" is likely a Python project)
2. By analyzing the file extensions in the repository

This allows the agent to adapt its analysis and code generation to the specific language of the repository.

### Event Handling

The agent integrates with Codegen's event handling system to process events from different sources:

1. **Slack Events**: App mentions and messages
2. **GitHub Events**: PR creation, labeling, and comments
3. **Linear Events**: Issue creation and updates

This allows the agent to respond to events from different platforms and provide a seamless experience for users.

## Future Enhancements

1. **Repository Selection**: Support for multiple repositories with interactive selection
2. **Branch Management**: Custom base and head branches with conflict resolution
3. **PR Template Customization**: Organization-specific templates and custom PR formats
4. **PR Review and Updates**: Request reviews and update existing PRs based on feedback
5. **Linear Integration**: Link PRs to Linear tickets and update ticket status
6. **Code Quality Checks**: Run linters and tests before creating PRs
7. **Interactive PR Creation**: Multi-step PR creation with user feedback at each step