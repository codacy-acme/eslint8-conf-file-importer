# ESLint Configuration Tools

This repository contains two Python tools for managing ESLint configurations and creating Codacy standards:

1. ESLint Config Expander (`expand_eslint_config.py`)
2. Codacy ESLint Standard Creator (`create_eslint_standard.py`)

These tools work together to help you convert your ESLint configuration into a Codacy coding standard.

## Prerequisites

- Python 3.6+
- Node.js and npm (for ESLint)
- ESLint installed in your project
- Codacy API token (for creating standards)

## Installation

```bash
pip install requests tqdm typing
```

Make sure you have ESLint installed in your project:
```bash
npm install eslint
```

## Step 1: Expand ESLint Configuration

The first tool, `expand_eslint_config.py`, takes your existing ESLint configuration and expands it into a fully resolved configuration file. This is necessary because ESLint configs often use extends and plugins that need to be resolved.

### Usage

```bash
python expand_eslint_config.py
```

By default, it looks for `.eslintrc.js` in the current directory. You can specify a different path by modifying the `main()` function call.

### What it does

1. Reads your ESLint configuration file
2. Uses ESLint's `--print-config` option to get the fully resolved configuration
3. Formats the configuration according to ESLint style guidelines
4. Creates a new file named `eslintrc.expanded.js` with the expanded configuration

## Step 2: Create Codacy Standard

The second tool, `create_eslint_standard.py`, takes the expanded ESLint configuration and creates a Codacy coding standard with matching rules.

### Usage

```bash
python create_eslint_standard.py \
  --api-token YOUR_CODACY_API_TOKEN \
  --organization YOUR_ORG_NAME \
  --provider [gh|gl|bb] \
  --name "Your Standard Name" \
  --eslint-config eslintrc.expanded.js
```

### Arguments

- `--api-token`: Your Codacy API token
- `--organization`: Your organization name in Codacy
- `--provider`: Git provider (use 'gh' for GitHub, 'gl' for GitLab, or 'bb' for Bitbucket)
- `--name`: Name for the new coding standard
- `--eslint-config`: Path to your ESLint config file (use the expanded config from Step 1)

### What it does

1. Parses the expanded ESLint configuration
2. Maps ESLint rules to corresponding Codacy patterns
3. Creates a new coding standard in Codacy
4. Disables all tools except ESLint
5. Configures ESLint with your mapped rules
6. Promotes the standard to make it available for use
7. Saves the results to a JSON file

## Output

After running both tools, you'll have:
1. An expanded ESLint configuration file (`eslintrc.expanded.js`)
2. A new Codacy coding standard with your ESLint rules
3. A JSON file containing the results of the standard creation

## Example Workflow

```bash
# Step 1: Expand your ESLint config
python expand_eslint_config.py

# Step 2: Create Codacy standard
python create_eslint_standard.py \
  --api-token "your-api-token" \
  --organization "your-org" \
  --provider gh \
  --name "Team ESLint Standard" \
  --eslint-config eslintrc.expanded.js
```

## Error Handling

Both tools include comprehensive error handling and logging:
- Failed API requests will be retried up to 3 times
- Parsing errors are logged with details
- Network errors show full response content
- Results are saved even if promotion fails

## Limitations

- The tools only handle ESLint rules that have corresponding Codacy patterns
- Some complex ESLint configurations might need manual adjustment
- The tools require direct access to the Codacy API

## Troubleshooting

If you encounter issues:
1. Check that your ESLint config is valid
2. Verify your Codacy API token has sufficient permissions
3. Look for error messages in the console output
4. Check the generated JSON file for details about the process