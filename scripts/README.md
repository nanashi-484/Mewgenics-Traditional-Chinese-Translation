# Simplified to Traditional Chinese Conversion Script

This script `simplified_to_traditional.py` converts Simplified Chinese text to Traditional Chinese text within CSV files. It is designed to process all Chinese characters found in any cell of the specified CSV files.

## Usage

To run the script, execute it from the project root directory.

```bash
python3 scripts/simplified_to_traditional.py [target_directory]
```

-   `[target_directory]` (optional): The path to the directory containing the CSV files you want to convert. If not provided, it defaults to `Mewgenics_CN_patch/data/text`.

**Example:**

To convert the default directory:
```bash
python3 scripts/simplified_to_traditional.py
```

To convert a custom directory (e.g., `my_custom_text_files`):
```bash
python3 scripts/simplified_to_traditional.py my_custom_text_files
```

## How it works

The script uses OpenCC dictionary files (`STPhrases.txt` and `STCharacters.txt`) located in the `scripts/conversion_tools` directory to perform the Simplified to Traditional Chinese conversion. It reads each CSV file, iterates through every cell, and if a cell contains Chinese characters, it applies the conversion. The modified content is then written back to the original file.

## Important Notes

-   The script overwrites the original CSV files with the converted content. It is recommended to back up your files before running the script.
-   The conversion relies on the provided dictionary files. While comprehensive, some specific terms might require manual adjustment after the conversion.
-   The script processes *all* text that contains CJK Unified Ideographs (`\u4e00-\u9fff`) in any column, excluding columns typically associated with non-Chinese languages (e.g., `KEY`, `en`, `sp`, `fr`, `de`, `it`, `pt-br`) by checking against common header names. (Correction: The latest version of the script processes ALL cells that contain Chinese characters, regardless of column headers, as per user's latest request.)

---
_This script and its associated dictionary files were generated to facilitate Simplified to Traditional Chinese conversion for the Mewgenics Traditional Chinese Translation project._
