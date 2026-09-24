"""Shared prompt fragments used across LLM services."""

# Injected into every maths-related system prompt. The frontend renders KaTeX,
# which only typesets math that is wrapped in delimiters.
LATEX_FORMAT_RULE = """
【數學公式格式（必須嚴格遵守）】
1. 所有數學符號與公式一律用 LaTeX，並以 $...$（行內）或 $$...$$（獨立成行）包住。
2. 嚴禁輸出未被 delimiter 包住嘅 LaTeX，例如直接寫 \\sqrt{x} 或 sqrt{x}。
3. 正確示範：判別式 $\\Delta = b^2 - 4ac$；求根公式 $$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$$
4. 錯誤示範：判別式 \\Delta = b^2 - 4ac ；x = (-b ± sqrt(b^2-4ac)) / 2a
5. 中文解釋用普通文字，唔要放入 $...$ 之內。
"""
