#!/usr/bin/env python3
import argparse
import requests
import json
import os
import re
import time
from typing import Dict, List, Optional, Union, Any
from tqdm import tqdm

ESLINT_TOOL_UUID = "f8b29663-2cb2-498d-b923-a10c6a8c05cd"
CODACY_API_BASE_URL = "https://app.codacy.com/api/v3"

def get_codacy_headers(api_token: str) -> Dict[str, str]:
    return {
        "api-token": api_token,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def map_eslint_to_codacy_patterns(eslint_patterns: List[Dict], all_codacy_patterns: List[Dict]) -> Dict:
    """Map ESLint rules to Codacy pattern IDs"""
    # Create a lookup dictionary for Codacy patterns
    codacy_pattern_map = {}
    
    print("\nAvailable Codacy patterns that match your rules:")
    pattern_ids = []
    for pattern in all_codacy_patterns:
        if 'patternDefinition' in pattern and 'id' in pattern['patternDefinition']:
            pattern_id = pattern['patternDefinition']['id']
            codacy_pattern_map[pattern_id] = pattern['patternDefinition']
            # Strip ESLint8_ prefix for matching
            if pattern_id.startswith('ESLint8_'):
                pattern_ids.append(pattern_id[8:])  # Store without prefix
                codacy_pattern_map[pattern_id[8:]] = pattern['patternDefinition']  # Store mapping without prefix
            print(f"Found Codacy pattern: {pattern_id}")

    def find_matching_pattern(rule_name: str) -> Optional[str]:
        # Try direct match
        if rule_name in pattern_ids:
            return f"ESLint8_{rule_name}"
            
        # Try without plugin prefix
        if '/' in rule_name:
            base_rule = rule_name.split('/')[-1]
            if base_rule in pattern_ids:
                return f"ESLint8_{base_rule}"
                
        # Try with normalized name (replace / with _)
        normalized_name = rule_name.replace('/', '_')
        if normalized_name in pattern_ids:
            return f"ESLint8_{normalized_name}"
                
        return None

    print("\nMapping ESLint rules to Codacy patterns:")
    mapping_results = {}
    for eslint_pattern in eslint_patterns:
        rule_name = eslint_pattern['id']
        codacy_id = find_matching_pattern(rule_name)
        
        if codacy_id:
            print(f"Found match: {rule_name} -> {codacy_id}")
            mapping_results[rule_name] = codacy_pattern_map[codacy_id[8:]]  # Remove prefix for lookup
        else:
            print(f"No match found for: {rule_name}")

    return mapping_results

def list_coding_standard_tools(organization: str, coding_standard_id: str, api_token: str, provider: str) -> List[Dict]:
    """Get all tools for a coding standard"""
    url = f"{CODACY_API_BASE_URL}/organizations/{provider}/{organization}/coding-standards/{coding_standard_id}/tools"
    response = requests.get(url, headers=get_codacy_headers(api_token))
    response.raise_for_status()
    return response.json()['data']

def list_tool_patterns(organization: str, coding_standard_id: str, tool_uuid: str, api_token: str, provider: str) -> List[Dict]:
    """Get all patterns for a specific tool, handling pagination"""
    url = f"{CODACY_API_BASE_URL}/organizations/{provider}/{organization}/coding-standards/{coding_standard_id}/tools/{tool_uuid}/patterns"
    all_patterns = []
    cursor = None
    
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
            
        response = requests.get(url, headers=get_codacy_headers(api_token), params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data:
            all_patterns.extend(data['data'])
            
        # Check if there's more data to fetch
        pagination = data.get('pagination', {})
        cursor = pagination.get('cursor')
        if not cursor:
            break
            
        print(f"Fetched {len(all_patterns)} patterns so far...")
    
    print(f"Total patterns fetched: {len(all_patterns)}")
    return all_patterns


def batch_update_patterns(organization: str, coding_standard_id: str, tool_uuid: str, patterns: List[Dict], api_token: str, provider: str, batch_size: int = 1000) -> None:
    """Update patterns in batches to stay within API limits"""
    for i in range(0, len(patterns), batch_size):
        batch = patterns[i:i + batch_size]
        print(f"Updating patterns batch {i//batch_size + 1} ({len(batch)} patterns)")
        
        data = {
            "enabled": True,
            "patterns": batch
        }
        
        url = f"{CODACY_API_BASE_URL}/organizations/{provider}/{organization}/coding-standards/{coding_standard_id}/tools/{tool_uuid}"
        
        retries = 3
        while retries > 0:
            try:
                response = requests.patch(url, headers=get_codacy_headers(api_token), json=data)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                retries -= 1
                if retries == 0:
                    raise
                print(f"Request failed, retrying... ({e})")
                time.sleep(2)  # Wait before retry

def disable_all_tools(organization: str, coding_standard_id: str, api_token: str, provider: str):
    """Disable all tools in the coding standard"""
    print("Getting list of tools...")
    tools = list_coding_standard_tools(organization, coding_standard_id, api_token, provider)
    
    print(f"Found {len(tools)} tools. Disabling all...")
    for tool in tqdm(tools, desc="Disabling tools"):
        retries = 3
        while retries > 0:
            try:
                update_coding_standard_tool(organization, coding_standard_id, tool['uuid'], False, [], api_token, provider)
                print(f"Disabled tool: {tool['uuid']}")
                break
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error disabling tool {tool['uuid']} after 3 attempts: {str(e)}")
                    break
                print(f"Error disabling tool {tool['uuid']}, retrying... ({str(e)})")
                time.sleep(2)  # Wait before retry

def update_coding_standard_tool(organization: str, coding_standard_id: str, tool_uuid: str, enabled: bool, patterns: List[Dict], api_token: str, provider: str) -> Dict:
    """Update tool configuration and patterns"""
    if not enabled:
        data = {
            "enabled": False,
            "patterns": []
        }
        url = f"{CODACY_API_BASE_URL}/organizations/{provider}/{organization}/coding-standards/{coding_standard_id}/tools/{tool_uuid}"
        response = requests.patch(url, headers=get_codacy_headers(api_token), json=data)
        response.raise_for_status()
        return response.json() if response.text else {}
        
    if tool_uuid == ESLINT_TOOL_UUID:
        # Get all available patterns for ESLint
        print("Fetching all ESLint patterns (this may take a moment)...")
        all_patterns = list_tool_patterns(organization, coding_standard_id, tool_uuid, api_token, provider)
        
        # Create mapping of all available patterns
        pattern_mapping = {}
        for pattern in all_patterns:
            if 'patternDefinition' in pattern and 'id' in pattern['patternDefinition']:
                pattern_id = pattern['patternDefinition']['id']
                base_id = pattern_id[8:] if pattern_id.startswith('ESLint8_') else pattern_id
                pattern_mapping[base_id] = pattern_id
                # Also map normalized version
                normalized_id = base_id.replace('/', '_')
                pattern_mapping[normalized_id] = pattern_id
        
        enabled_patterns = []
        disabled_patterns = []
        
        # Process patterns from config
        for pattern in patterns:
            rule_name = pattern['id']
            normalized_rule = rule_name.replace('/', '_')
            
            # Try to find matching pattern ID
            codacy_id = None
            if rule_name in pattern_mapping:
                codacy_id = pattern_mapping[rule_name]
            elif normalized_rule in pattern_mapping:
                codacy_id = pattern_mapping[normalized_rule]
            
            if codacy_id:
                enabled_patterns.append({
                    "id": codacy_id,
                    "enabled": True,
                    "parameters": pattern.get("parameters", [])
                })
                print(f"Enabling pattern: {codacy_id}")
            else:
                print(f"Warning: No matching Codacy pattern found for {rule_name}")
        
        # Disable all other patterns
        for pattern in all_patterns:
            if 'patternDefinition' in pattern and 'id' in pattern['patternDefinition']:
                pattern_id = pattern['patternDefinition']['id']
                if not any(ep['id'] == pattern_id for ep in enabled_patterns):
                    disabled_patterns.append({
                        "id": pattern_id,
                        "enabled": False,
                        "parameters": []
                    })
        
        print(f"\nConfiguration summary:")
        print(f"- Enabling {len(enabled_patterns)} patterns from config")
        print(f"- Disabling {len(disabled_patterns)} other patterns")
        
        if enabled_patterns:
            print("\nEnabled patterns:")
            for pattern in enabled_patterns:
                print(f"- {pattern['id']}")
            
            print("\nUpdating enabled patterns...")
            batch_update_patterns(organization, coding_standard_id, tool_uuid, enabled_patterns, api_token, provider)
            
        if disabled_patterns:
            print("\nUpdating disabled patterns...")
            batch_update_patterns(organization, coding_standard_id, tool_uuid, disabled_patterns, api_token, provider)
        
        return {}
    else:
        data = {
            "enabled": enabled,
            "patterns": []
        }
        url = f"{CODACY_API_BASE_URL}/organizations/{provider}/{organization}/coding-standards/{coding_standard_id}/tools/{tool_uuid}"
        response = requests.patch(url, headers=get_codacy_headers(api_token), json=data)
        response.raise_for_status()
        return response.json() if response.text else {}
    
def preprocess_extends(content: str) -> str:
    extends_pattern = r'"extends"\s*:\s*\[(.*?)\]'
    
    def process_extends_content(match):
        extends_content = match.group(1)
        lines = [line.strip().strip(',').strip('"') for line in extends_content.split('\n')]
        processed_lines = []
        
        for line in lines:
            if not line:
                continue
                
            if line.startswith('eslint:'):
                processed_lines.append(f'"{line}"')
            elif line.startswith('plugin:'):
                processed_lines.append(f'"{line}"')
            elif ':' in line:
                line = line.replace('"', '')
                processed_lines.append(f'"{line}"')
            elif line == 'prettier':
                processed_lines.append('"prettier"')
            else:
                processed_lines.append(f'"{line}"')
        
        return '"extends": [\n        ' + ',\n        '.join(processed_lines) + '\n    ]'
    
    return re.sub(extends_pattern, process_extends_content, content, flags=re.DOTALL)

def clean_js_object(content: str) -> str:
    try:
        content = re.sub(r'//.*?\n|/\*.*?\*/', '', content, flags=re.S)
        
        content = re.sub(
            r'process\.env\.NODE_ENV\s*===\s*[\'"]production[\'"]\s*\?\s*[\'"]error[\'"]\s*:\s*[\'"]warn[\'"]',
            '"warn"',
            content
        )
        
        content = content.replace("'", '"')
        content = re.sub(r'([a-zA-Z0-9_-]+)(?=\s*:)', r'"\1"', content)
        content = preprocess_extends(content)
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        content = re.sub(r',(\s*\n\s*[}\]])', r'\1', content)
        
        return content.strip()
    except Exception as e:
        print(f"Error in clean_js_object: {str(e)}")
        print("Content that caused the error:")
        print(content)
        return None

def parse_eslint_config(config_file: str) -> Optional[Dict[str, Any]]:
    try:
        print(f"Reading file: {config_file}")
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print("File read successfully")

        if not content.strip():
            print("Error: Empty configuration file")
            return None

        print("Removing module.exports")
        content = content.replace('module.exports =', '')
        
        print("Cleaning JavaScript object")
        cleaned_content = clean_js_object(content)
        if cleaned_content is None:
            return None
        
        print("Attempting to parse JSON")
        try:
            config = json.loads(cleaned_content)
            rules = config.get('rules', {})
            
            if not rules:
                print("Warning: No rules found in the configuration")
                print("Parsed configuration:")
                print(json.dumps(config, indent=2))
            else:
                print(f"Successfully parsed {len(rules)} rules")
            
            return rules
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print("Cleaned content that failed to parse:")
            print(cleaned_content)
            return None
            
    except Exception as e:
        print(f"Error reading or processing config file: {str(e)}")
        print("Full traceback:")
        import traceback
        traceback.print_exc()
        return None

def map_eslint_rule_to_codacy(rule_name: str, rule_config: Union[str, int, list, dict]) -> Optional[Dict[str, Any]]:
    try:
        if isinstance(rule_config, (int, float)):
            if rule_config == 0:
                return None
            severity = "error" if rule_config == 2 else "warn"
            rule_config = [severity]
        
        if isinstance(rule_config, list):
            severity = rule_config[0]
            parameters = rule_config[1] if len(rule_config) > 1 else None
        elif isinstance(rule_config, str):
            severity = rule_config
            parameters = None
        elif isinstance(rule_config, dict):
            severity = "error"
            parameters = rule_config
        else:
            print(f"Unexpected rule config type for {rule_name}: {type(rule_config)}")
            return None

        if isinstance(severity, (int, float)):
            severity = "error" if severity == 2 else "warn"
        enabled = severity in ['error', 'warn', 2, 1]

        if not enabled:
            return None

        pattern = {
            "id": rule_name,
            "enabled": True,
            "patternId": rule_name
        }

        if parameters and isinstance(parameters, dict):
            mapped_parameters = []
            for param_name, param_value in parameters.items():
                if isinstance(param_value, (list, dict)):
                    param_value = json.dumps(param_value)
                mapped_param = {
                    "name": param_name,
                    "value": str(param_value)
                }
                mapped_parameters.append(mapped_param)
            
            if mapped_parameters:
                pattern["parameters"] = mapped_parameters

        return pattern
    except Exception as e:
        print(f"Error mapping rule {rule_name}: {str(e)}")
        return None

def batch_update_patterns(organization: str, coding_standard_id: str, tool_uuid: str, patterns: List[Dict], api_token: str, provider: str, batch_size: int = 1000) -> None:
    """Update patterns in batches to stay within API limits"""
    for i in range(0, len(patterns), batch_size):
        batch = patterns[i:i + batch_size]
        print(f"Updating patterns batch {i//batch_size + 1} ({len(batch)} patterns)")
        
        data = {
            "enabled": True,
            "patterns": batch
        }
        
        url = f"{CODACY_API_BASE_URL}/organizations/{provider}/{organization}/coding-standards/{coding_standard_id}/tools/{tool_uuid}"
        
        retries = 3
        while retries > 0:
            try:
                response = requests.patch(url, headers=get_codacy_headers(api_token), json=data)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                retries -= 1
                if retries == 0:
                    raise
                print(f"Request failed, retrying... ({e})")
                time.sleep(2)

def create_coding_standard(organization: str, name: str, api_token: str, provider: str) -> Dict:
    url = f"{CODACY_API_BASE_URL}/organizations/{provider}/{organization}/coding-standards"
    data = {
        "name": name,
        "languages": ["Javascript", "TypeScript"]
    }
    
    print(f"Creating coding standard with payload: {json.dumps(data, indent=2)}")
    response = requests.post(url, headers=get_codacy_headers(api_token), json=data)
    response.raise_for_status()
    return response.json()

def promote_coding_standard(organization: str, coding_standard_id: str, api_token: str, provider: str):
    url = f"{CODACY_API_BASE_URL}/organizations/{provider}/{organization}/coding-standards/{coding_standard_id}/promote"
    print("Promoting coding standard")
    response = requests.post(url, headers=get_codacy_headers(api_token))
    response.raise_for_status()
    return response.json() if response.text else {}

def main():
    parser = argparse.ArgumentParser(description='Create Codacy ESLint Standard')
    parser.add_argument('--api-token', required=True,
                        help='Codacy API token')
    parser.add_argument('--organization', required=True,
                        help='Codacy organization name')
    parser.add_argument('--provider', required=True,
                        help='Git provider (gh, gl, or bb)')
    parser.add_argument('--name', required=True,
                        help='Name for the coding standard')
    parser.add_argument('--eslint-config', required=True,
                        help='Path to eslint config file')
    
    args = parser.parse_args()

    if args.provider not in ['gh', 'gl', 'bb']:
        print(f"Error: Provider must be one of: gh, gl, bb")
        return

    if not os.path.isfile(args.eslint_config):
        print(f"Error: ESLint config file not found at {args.eslint_config}")
        return

    try:
        # Parse ESLint config
        print("Parsing ESLint configuration...")
        eslint_rules = parse_eslint_config(args.eslint_config)
        if eslint_rules is None:
            print("Error: Failed to parse ESLint configuration.")
            return

        # Map rules to patterns
        print("Mapping ESLint rules to Codacy patterns...")
        new_patterns = []
        for rule_name, rule_config in eslint_rules.items():
            pattern = map_eslint_rule_to_codacy(rule_name, rule_config)
            if pattern:
                new_patterns.append(pattern)

        if not new_patterns:
            print("Error: No valid patterns found after mapping rules.")
            return

        print(f"Found {len(new_patterns)} valid rules to configure...")

        # Create coding standard
        print(f"Creating coding standard '{args.name}'...")
        standard = create_coding_standard(args.organization, args.name, args.api_token, args.provider)
        coding_standard_id = standard['data']['id']
        print(f"Coding standard created with ID: {coding_standard_id}")

        # First disable all tools
        print("Disabling all tools...")
        disable_all_tools(args.organization, coding_standard_id, args.api_token, args.provider)

        # Enable ESLint with our patterns
        print("Enabling ESLint with configured patterns...")
        update_coding_standard_tool(args.organization, coding_standard_id, ESLINT_TOOL_UUID, True, new_patterns, args.api_token, args.provider)

        # Promote the standard
        print("Promoting coding standard...")
        promote_coding_standard(args.organization, coding_standard_id, args.api_token, args.provider)

        print("\nProcess completed successfully!")
        print(f"Standard ID: {coding_standard_id}")
        
        # Save results
        result = {
            "standard_id": coding_standard_id,
            "name": args.name,
            "organization": args.organization,
            "provider": args.provider,
            "patterns_count": len(new_patterns),
            "patterns": new_patterns
        }
        
        output_filename = f"{args.name.replace(' ', '_').lower()}_result.json"
        with open(output_filename, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Results saved to {output_filename}")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Full traceback:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()