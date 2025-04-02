# Codegen PR Creation Agent

This module integrates the Slack bot with Codegen's powerful code analysis and PR creation capabilities. It allows users to request PR creation directly from Slack, with the bot analyzing repositories, generating code changes, and submitting PRs automatically.

## Architecture

The integration consists of four main components:

1. **PR Agent**: Coordinates the workflow between Slack, Codegen, and GitHub
2. **Codebase Analyzer**: Analyzes repositories and generates code changes
3. **GitHub Handler**: Creates and manages PRs
4. **Response Formatter**: Formats responses for Slack

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

## Key Components

### 1. PR Agent (`pr_agent.py`)

The main entry point for PR creation requests. It:
- Detects PR creation requests from Slack messages
- Extracts repository and change details
- Coordinates the workflow between components
- Handles error cases and provides feedback

### 2. Codebase Analyzer (`codebase_analyzer.py`)

Analyzes codebases and generates changes. It:
- Uses Codegen's tools to analyze repositories
- Extracts code structure and dependencies
- Generates appropriate code changes
- Provides context for PR descriptions

### 3. GitHub Handler (`github_handler.py`)

Creates and manages PRs. It:
- Creates branches for changes
- Applies changes to files
- Creates PRs with appropriate titles and descriptions
- Handles PR comments and updates

### 4. Response Formatter (`response_formatter.py`)

Formats responses for Slack. It:
- Creates well-formatted messages with links and code blocks
- Provides status updates during the PR creation process
- Formats error messages when things go wrong

## Usage

Users can request PR creation by mentioning the bot with a message like:

```
@bot create a PR to add error handling to the login component in the user-service repository
```

The bot will:
1. Acknowledge the request
2. Analyze the repository
3. Generate appropriate changes
4. Create a PR
5. Provide a link to the PR

## Implementation Details

The implementation uses:
- Codegen's `CodeAgent` for code analysis and generation
- Codegen's GitHub tools for PR creation and management
- Slack Bolt for Slack integration
- FastAPI for webhook handling

## Configuration

The module requires the following environment variables:
- `GITHUB_TOKEN`: GitHub API token
- `SLACK_BOT_TOKEN`: Slack bot token
- `SLACK_APP_TOKEN`: Slack app token
- `CODEGEN_MODEL_PROVIDER`: Model provider (anthropic or openai)
- `CODEGEN_MODEL_NAME`: Model name to use