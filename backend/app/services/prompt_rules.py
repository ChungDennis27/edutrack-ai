"""Shared prompt fragments used across LLM services."""

# Student-facing mathematics must be readable without a formula renderer.
PLAIN_MATH_RULE = """
【數學式寫法（必須嚴格遵守）】
1. 所有數學式用學生平時書寫、一眼能讀的普通文字，不要用 LaTeX。
2. 禁止輸出 $、$$、\\frac、\\sqrt、\\pm，或其他反斜線公式指令。
3. 次方寫成 x²，或在一行文字裡寫 x^2。分數寫成 a/b。開方寫成 √。正負寫成 ±。
4. 正確示範：判別式 Δ = b² − 4ac；求根公式 x = (−b ± √(b² − 4ac)) / (2a)
5. 錯誤示範：$\\Delta = b^2 - 4ac$；x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}
6. 中文解釋用普通文字。公式只在需要時以上面的寫法插入，不要把整句中文放進公式裡。
"""
