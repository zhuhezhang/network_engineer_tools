# Text Comparison Tool

## Project Description

This is a text difference comparison tool implemented based on PySide6 and difflib. The tool provides an intuitive interface to compare the differences between two text files, supports importing files in multiple encoding formats, and offers rich editing and viewing features.

## Main Features

- **Line Numbers**: All editing areas display line numbers, and the result area scrollbars scroll synchronously for easy comparison.
- **Encoding Support**: Supports importing comparison text from text files in multiple encoding formats.
- **Font Scaling**: Supports font scaling, and supports Ctrl/Cmd + mouse wheel scaling.
- **Highlight Display**: Comparison results support character-level highlighting (red-deletion, green-addition, yellow-modification).
- **Interface Adjustment**: You can adjust the size of the four text areas by dragging the split bar, and double-clicking the split bar restores the default ratio.
- **Search and Replace**: Supports search and replace functions, including case matching, whole word matching, and regular expressions.
- **Interface Language**: Supports switching between Chinese and English interfaces.


## Dev

1. Ensure Python 3.8+ and pip are installed.
2. Install dependencies:
   ```bash
   pip install PySide6 charset-normalizer
   ```
3. Run the program:
   ```bash
   python main.py
   ```