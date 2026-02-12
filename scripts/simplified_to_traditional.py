import csv
import os
import glob
import re
import sys # Import sys for command-line arguments

# Paths
# Dictionaries are now in 'scripts/conversion_tools' relative to the project root
DICTIONARY_DIR = os.path.join(os.path.dirname(__file__), 'conversion_tools')

# Default target directory
# This can be overridden by a command-line argument
DEFAULT_TARGET_DIR = 'Mewgenics_CN_patch/data/text' 
TARGET_DIR = DEFAULT_TARGET_DIR

# Check for command-line arguments for TARGET_DIR
if len(sys.argv) > 1:
    TARGET_DIR = sys.argv[1]
    print(f"Using target directory from argument: {TARGET_DIR}")
else:
    print(f"Using default target directory: {DEFAULT_TARGET_DIR}")


# Load Dictionaries
char_map = {}
phrase_map = {}

# Helper to load dictionary correctly
def load_dict(filename, target_map):
    path = os.path.join(DICTIONARY_DIR, filename)
    if not os.path.exists(path):
        print(f"Warning: {filename} not found at {path}.")
        return
    
    count = 0
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            
            parts = line.split('\t') # Assume tab-separated
            parts = [p for p in parts if p] # Filter out empty strings from split
            
            if len(parts) >= 2:
                source = parts[0]
                # Take only the first Traditional Chinese option, if there are multiple separated by space
                target = parts[1].split(' ')[0]
                target_map[source] = target
                count += 1
    print(f"Loaded {count} entries from {filename}")

print("Loading dictionaries...")
load_dict('STPhrases.txt', phrase_map)
load_dict('STCharacters.txt', char_map)

# Optimization: Max length of a phrase
max_phrase_len = 0
if phrase_map:
    max_phrase_len = max(len(k) for k in phrase_map.keys())

print(f"Max phrase length: {max_phrase_len}")

# Function to check if a string contains any Chinese characters
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def convert_text(text):
    if not text:
        return text
    
    result = []
    i = 0
    n = len(text)
    
    while i < n:
        matched = False
        limit = min(max_phrase_len, n - i)
        for length in range(limit, 0, -1): # Iterate from longest possible match down to 1 character
            sub = text[i : i + length]
            if sub in phrase_map:
                result.append(phrase_map[sub])
                i += length
                matched = True
                break
        
        if not matched:
            char = text[i]
            if char in char_map:
                result.append(char_map[char])
            else:
                result.append(char)
            i += 1
            
    return "".join(result)

# Process files
# Ensure TARGET_DIR exists before globbing
if not os.path.isdir(TARGET_DIR):
    print(f"Error: Target directory '{TARGET_DIR}' not found. Please provide a valid directory.")
    sys.exit(1)

csv_files = glob.glob(os.path.join(TARGET_DIR, '*.csv'))
print(f"Found {len(csv_files)} CSV files in {TARGET_DIR}.")

for file_path in csv_files:
    print(f"Processing {file_path}...")
    temp_file_path = file_path + '.tmp'
    
    with open(file_path, 'r', encoding='utf-8', newline='') as infile, \
         open(temp_file_path, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        try:
            headers = next(reader)
        except StopIteration:
            writer.writerow([])
            continue
            
        writer.writerow(headers)
        
        for row in reader:
            new_row = list(row)
            for col_index, cell_value in enumerate(row):
                if contains_chinese(cell_value):
                    new_row[col_index] = convert_text(cell_value)
            writer.writerow(new_row)
            
    os.replace(temp_file_path, file_path)

print("Conversion complete.")
