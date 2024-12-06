import json
import subprocess
import os
import shutil
import tempfile
from typing import Dict, List, Any, Optional
import re
import sys

class ESLintConfigExpander:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.temp_dir = None
        self.installed_packages = set()

    def setup_temp_environment(self) -> None:
        """Create and setup temporary npm environment."""
        self.temp_dir = tempfile.mkdtemp()
        original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        
        print("Setting up temporary npm environment...")
        
        # Create package.json with all required dependencies
        pkg_json = {
            "name": "eslint-config-temp",
            "version": "1.0.0",
            "private": True,
            "dependencies": {
                "eslint": "^8.0.0",
                "eslint-plugin-vue": "^9.0.0",
                "eslint-plugin-storybook": "^0.6.0",
                "eslint-config-prettier": "^9.0.0",
                "eslint-plugin-jsdoc": "^46.0.0",
                "eslint-plugin-vuejs-accessibility": "^2.0.0",
                "eslint-plugin-html": "^7.0.0",
                "eslint-plugin-prettier": "^5.0.0"
            }
        }
        
        with open('package.json', 'w') as f:
            json.dump(pkg_json, f, indent=2)
        
        print("Installing packages...")
        try:
            # Run npm install with more verbose output
            result = subprocess.run(
                ['npm', 'install', '--verbose'],
                check=True,
                capture_output=True,
                text=True
            )
            self.installed_packages = set(pkg_json['dependencies'].keys())
            print("✓ Packages installed successfully")
            
            # Create a simple test script to verify module loading
            test_script = """
            const eslint = require('eslint');
            console.log('ESLint loaded successfully');
            """
            with open('test.js', 'w') as f:
                f.write(test_script)
            
            # Test if we can load ESLint
            subprocess.run(['node', 'test.js'], check=True)
            print("✓ Module resolution verified")
            
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to set up environment: {e.stderr}")
            os.chdir(original_dir)
            self.cleanup()
            sys.exit(1)
        
        os.chdir(original_dir)

    def parse_config_file(self, file_path: str) -> Dict[str, Any]:
        """Parse the ESLint configuration file."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Remove comments
            content = re.sub(r'//.*?\n|/\*.*?\*/', '', content, flags=re.S)
            
            # Extract configuration object
            match = re.search(r'module\.exports\s*=\s*({[\s\S]*})', content, re.MULTILINE | re.DOTALL)
            if not match:
                print(f"Warning: Could not find module.exports in {file_path}, trying to parse as raw config...")
                match = re.search(r'({[\s\S]*})', content, re.MULTILINE | re.DOTALL)
                if not match:
                    raise ValueError(f"Could not parse configuration in {file_path}")
            
            config_str = match.group(1)
            
            # Convert to valid JSON
            config_str = (config_str
                .replace('process.env.NODE_ENV === \'production\' ? \'error\' : \'warn\'', '"warn"')
                .replace('true', 'true')
                .replace('false', 'false')
                .replace('null', 'null'))
            
            # Use Node to parse the configuration
            js_code = f"""
            try {{
                const config = {config_str};
                console.log(JSON.stringify(config));
            }} catch (error) {{
                console.error(error.message);
                process.exit(1);
            }}
            """
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(js_code)
                temp_file = f.name
            
            try:
                result = subprocess.run(
                    ['node', temp_file], 
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=self.temp_dir
                )
                return json.loads(result.stdout)
            finally:
                os.unlink(temp_file)
                
        except Exception as e:
            print(f"Error parsing config file: {str(e)}")
            sys.exit(1)

    def get_extended_config(self, extend: str) -> Dict[str, Any]:
        """Get configuration from an extend rule."""
        try:
            if extend == 'eslint:recommended':
                js_code = """
                const { Linter } = require('eslint');
                const linter = new Linter();
                const recommended = Array.from(linter.getRules())
                    .filter(([, rule]) => rule.meta?.docs?.recommended)
                    .reduce((rules, [name]) => {
                        rules[name] = 'error';
                        return rules;
                    }, {});
                console.log(JSON.stringify({ rules: recommended }));
                """
            else:
                js_code = f"""
                const path = require('path');
                
                // Explicitly set the NODE_PATH to include our node_modules
                process.env.NODE_PATH = path.join(process.cwd(), 'node_modules');
                require('module').Module._initPaths();

                try {{
                    let config;
                    if ('{extend}'.startsWith('plugin:')) {{
                        const [_, pluginName, configName] = '{extend}'.match(/^plugin:([^/]+)\/(.+)$/);
                        const packageName = pluginName === 'vue' ? 'eslint-plugin-vue' :
                                         pluginName === 'storybook' ? 'eslint-plugin-storybook' :
                                         `eslint-plugin-${{pluginName}}`;
                        
                        const plugin = require(packageName);
                        config = plugin.configs?.[configName] || plugin.configs?.recommended;
                    }} else {{
                        const packageName = '{extend}' === 'prettier' ? 'eslint-config-prettier' :
                                         `eslint-config-{extend}`;
                        config = require(packageName);
                    }}
                    
                    if (config?.configs?.recommended) {{
                        config = config.configs.recommended;
                    }}
                    
                    console.log(JSON.stringify(config));
                }} catch (error) {{
                    console.error(`Error loading configuration: ${{error.message}}`);
                    process.exit(1);
                }}
                """
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(js_code)
                temp_file = f.name
            
            try:
                result = subprocess.run(
                    ['node', temp_file],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=self.temp_dir,
                    env={
                        **os.environ,
                        'NODE_PATH': os.path.join(self.temp_dir, 'node_modules')
                    }
                )
                config = json.loads(result.stdout)
                return config.get('rules', {})
            except subprocess.CalledProcessError as e:
                print(f"Node.js error for {extend}:")
                print(e.stderr)
                return {}
            finally:
                os.unlink(temp_file)
                
        except Exception as e:
            print(f"Warning: Could not load extended configuration '{extend}': {str(e)}")
            return {}

    def expand_config(self) -> Dict[str, Any]:
        """Expand the ESLint configuration."""
        try:
            print(f"Reading configuration from {self.config_path}...")
            config = self.parse_config_file(self.config_path)
            
            print("\nSetting up environment and installing dependencies...")
            self.setup_temp_environment()
            
            print("\nExpanding configuration rules...")
            expanded_rules = {}
            
            # Process extends
            if 'extends' in config:
                extends_list = config['extends']
                if isinstance(extends_list, str):
                    extends_list = [extends_list]
                
                for extend in extends_list:
                    print(f"\nProcessing extended configuration: {extend}")
                    extended_rules = self.get_extended_config(extend)
                    if extended_rules:
                        print(f"✓ Loaded rules from {extend}")
                        expanded_rules.update(extended_rules)
                    else:
                        print(f"✗ Could not load rules from {extend}")
            
            # Add local rules (these take precedence)
            if 'rules' in config:
                expanded_rules.update(config['rules'])
            
            return expanded_rules
            
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            print("\nCleaning up temporary files...")
            shutil.rmtree(self.temp_dir)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 expand_eslint_config.py <eslint-config-file>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    if not os.path.exists(config_path):
        print(f"Error: File not found: {config_path}")
        sys.exit(1)
    
    expander = ESLintConfigExpander(config_path)
    try:
        rules = expander.expand_config()
        print("\nExpanded configuration:")
        print(json.dumps(rules, indent=2))
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()