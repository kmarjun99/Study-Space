
import os
import re

def check_indentation(directory):
    # Regex: Start of line, 6 or more spaces, then 'use' followed by Capital letter
    pattern = re.compile(r'^ {6,}\buse[A-Z]')
    
    with open('indented_hooks_utf8.txt', 'w', encoding='utf-8') as outfile:
        outfile.write("Checking for deeply indented hooks...\n")
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.tsx') or file.endswith('.ts'):
                    filepath = os.path.join(root, file)
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f):
                            if pattern.match(line):
                                outfile.write(f"{file}:{i+1} -> {line.strip()}\n")

if __name__ == "__main__":
    check_indentation('src/pages')
