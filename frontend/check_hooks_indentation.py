
import os
import re

def check_indentation(directory):
    # Regex: Start of line, 6 or more spaces, then 'use' followed by Capital letter
    pattern = re.compile(r'^ {6,}\buse[A-Z]')
    
    print("Checking for deeply indented hooks (Potential conditional hooks)...")
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tsx'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f):
                        if pattern.match(line):
                            print(f"{file}:{i+1} -> {line.strip()}")

if __name__ == "__main__":
    check_indentation('src/pages')
