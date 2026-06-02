
import os
import re

def scan_react_hooks(directory):
    hook_pattern = re.compile(r'\buse[A-Z][a-zA-Z0-9]*\(')
    component_pattern = re.compile(r'const\s+([A-Z][a-zA-Z0-9]*)\s*[:=]\s*(?:React\.FC<.*>|.*=>)')
    
    print(f"Scanning {directory} for React Hook violations...")
    print("-" * 50)

    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith('.tsx') and not file.endswith('.ts'):
                continue
            
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            current_component = None
            has_seen_return = False
            conditional_depth = 0
            
            # Very naive parser
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                # effective "start of component"
                comp_match = component_pattern.search(line)
                if comp_match:
                    current_component = comp_match.group(1)
                    has_seen_return = False
                    # simplified: assuming component ends when we see another, or not tracking end
                
                if not current_component:
                    continue

                # Check for return
                if stripped.startswith('return ') or stripped == 'return;' or re.search(r'\bif\s*\(.*\)\s*return\b', stripped):
                    # We found a return.
                    # BUT, returns inside useEffect/callbacks are fine.
                    # This naive check flags returns inside sub-functions too.
                    # However, if we see a return at the top level of the component, that's what matters.
                    # Improving logic: Check indentation.
                    # Only flag "Early Return" if indentation is low?
                    # This is hard.
                    # Let's just track "Possible early return" and flags hooks after it.
                    has_seen_return = True

                # Check for Hook Call
                hook_match = hook_pattern.search(line)
                if hook_match:
                    hook_name = hook_match.group(0)
                    
                    # Violation 1: Hook after return
                    if has_seen_return:
                        # Ignore if inside a deeper scope (like useEffect callback)
                        # Naive check: does the line look like a top-level hook?
                        # e.g. "const [x, setX] = useState" or "useEffect(...)".
                        # If indentation is same as previous lines?
                        print(f"[VIOLATION] Hook Usage After Return in {file}:{i+1} -> {hook_name}")
                        print(f"    Line: {stripped}")

                    # Violation 2: Hook inside conditional (if/else)
                    # Use simple string check for now
                    # (This script is a heuristic, not a parser)
                    # Better manual check: grep for hooks indented more than 4 spaces if standard is 4?
                    pass

    print("-" * 50)
    print("Scan complete. Please verify flagged items manually.")

if __name__ == "__main__":
    scan_react_hooks('src')
