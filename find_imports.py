import os
import re

project_root = "."  # Current folder
imports = set()

for root, _, files in os.walk(project_root):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    # Match "import x" or "from x import y"
                    match = re.match(r'^\s*(?:from|import)\s+([\w\.]+)', line)
                    if match:
                        module = match.group(1).split('.')[0]
                        # Skip Python built-ins
                        if module not in ('os', 'sys', 're', 'json', 'datetime', 'time', 'typing', 'pathlib', 'logging'):
                            imports.add(module)

print("\n=== Third-party imports detected ===")
for module in sorted(imports):
    print(module)
