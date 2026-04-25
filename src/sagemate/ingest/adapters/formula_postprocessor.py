"""
LaTeX Formula Post-Processor for PDF-extracted text.

Converts common Unicode math symbols and malformed LaTeX fragments
into clean Markdown-compatible LaTeX.

Usage:
    from .formula_postprocessor import FormulaPostProcessor
    clean = FormulaPostProcessor.process(raw_text)
"""

from __future__ import annotations

import re


class FormulaPostProcessor:
    """Post-process PDF-extracted text to normalize LaTeX formulas."""

    # Unicode superscripts → ^n
    _SUPERSCRIPTS: dict[str, str] = {
        "⁰": "^0",
        "¹": "^1",
        "²": "^2",
        "³": "^3",
        "⁴": "^4",
        "⁵": "^5",
        "⁶": "^6",
        "⁷": "^7",
        "⁸": "^8",
        "⁹": "^9",
        "⁺": "^+",
        "⁻": "^-",
        "⁼": "^=",
        "⁽": "^(",
        "⁾": "^)",
        "ⁿ": "^n",
        "ⁱ": "^i",
        "ʲ": "^j",
        "ᵏ": "^k",
        "ˣ": "^x",
        "ʸ": "^y",
        "ᶻ": "^z",
    }

    # Unicode subscripts → _n
    _SUBSCRIPTS: dict[str, str] = {
        "₀": "_0",
        "₁": "_1",
        "₂": "_2",
        "₃": "_3",
        "₄": "_4",
        "₅": "_5",
        "₆": "_6",
        "₇": "_7",
        "₈": "_8",
        "₉": "_9",
        "₊": "_+",
        "₋": "_-",
        "₌": "_=",
        "₍": "_(",
        "₎": "_)",
        "ₙ": "_n",
        "ᵢ": "_i",
        "ⱼ": "_j",
        "ₖ": "_k",
    }

    # Greek letters
    _GREEK: dict[str, str] = {
        "α": r"\alpha",
        "β": r"\beta",
        "γ": r"\gamma",
        "δ": r"\delta",
        "ε": r"\epsilon",
        "ζ": r"\zeta",
        "η": r"\eta",
        "θ": r"\theta",
        "ι": r"\iota",
        "κ": r"\kappa",
        "λ": r"\lambda",
        "μ": r"\mu",
        "ν": r"\nu",
        "ξ": r"\xi",
        "ο": r"\omicron",
        "π": r"\pi",
        "ρ": r"\rho",
        "σ": r"\sigma",
        "τ": r"\tau",
        "υ": r"\upsilon",
        "φ": r"\phi",
        "χ": r"\chi",
        "ψ": r"\psi",
        "ω": r"\omega",
        "Α": r"\Alpha",
        "Β": r"\Beta",
        "Γ": r"\Gamma",
        "Δ": r"\Delta",
        "Ε": r"\Epsilon",
        "Ζ": r"\Zeta",
        "Η": r"\Eta",
        "Θ": r"\Theta",
        "Ι": r"\Iota",
        "Κ": r"\Kappa",
        "Λ": r"\Lambda",
        "Μ": r"\Mu",
        "Ν": r"\Nu",
        "Ξ": r"\Xi",
        "Ο": r"\Omicron",
        "Π": r"\Pi",
        "Ρ": r"\Rho",
        "Σ": r"\Sigma",
        "Τ": r"\Tau",
        "Υ": r"\Upsilon",
        "Φ": r"\Phi",
        "Χ": r"\Chi",
        "Ψ": r"\Psi",
        "Ω": r"\Omega",
    }

    # Common math operators
    _OPERATORS: dict[str, str] = {
        "×": r"\times",
        "÷": r"\div",
        "±": r"\pm",
        "∓": r"\mp",
        "∞": r"\infty",
        "∂": r"\partial",
        "∇": r"\nabla",
        "∫": r"\int",
        "∑": r"\sum",
        "∏": r"\prod",
        "√": r"\sqrt",
        "≈": r"\approx",
        "≠": r"\neq",
        "≤": r"\leq",
        "≥": r"\geq",
        "←": r"\leftarrow",
        "→": r"\rightarrow",
        "⇒": r"\Rightarrow",
        "⇔": r"\Leftrightarrow",
        "∈": r"\in",
        "∉": r"\notin",
        "⊂": r"\subset",
        "⊃": r"\supset",
        "∪": r"\cup",
        "∩": r"\cap",
        "∅": r"\emptyset",
        "∀": r"\forall",
        "∃": r"\exists",
        "∧": r"\wedge",
        "∨": r"\vee",
        "¬": r"\neg",
    }

    @classmethod
    def process(cls, text: str) -> str:
        """
        Run full post-processing pipeline on PDF-extracted text.
        """
        text = cls._fix_dollar_spacing(text)
        text = cls._convert_unicode_superscripts(text)
        text = cls._convert_unicode_subscripts(text)
        text = cls._convert_greek_letters(text)
        text = cls._convert_math_operators(text)
        text = cls._fix_fractions(text)
        text = cls._fix_common_patterns(text)
        return text

    @classmethod
    def _fix_dollar_spacing(cls, text: str) -> str:
        """
        Fix spaces inside LaTeX delimiters.
        e.g. '$ ^ { \\x5cS + 1 } $' → '$^{\\x5cS+1}$'
        """
        def _compact_inline(match: re.Match) -> str:
            inner = match.group(1)
            # Compact spaces inside the formula
            inner = re.sub(r"\{\s+", "{", inner)
            inner = re.sub(r"\s+\}", "}", inner)
            inner = " ".join(inner.split())
            return f"${inner}$"

        # Match $ ... $ pairs (non-greedy, allow escaped dollars)
        text = re.sub(r"\$\s*(.+?)\s*\$", _compact_inline, text)

        # Also fix block math $$ ... $$
        def _compact_block(match: re.Match) -> str:
            inner = match.group(1)
            inner = " ".join(inner.split())
            return f"$${inner}$$"

        text = re.sub(r"\$\$\s*(.+?)\s*\$\$", _compact_block, text, flags=re.DOTALL)
        return text

    @classmethod
    def _convert_unicode_superscripts(cls, text: str) -> str:
        for ch, latex in cls._SUPERSCRIPTS.items():
            text = text.replace(ch, latex)
        return text

    @classmethod
    def _convert_unicode_subscripts(cls, text: str) -> str:
        for ch, latex in cls._SUBSCRIPTS.items():
            text = text.replace(ch, latex)
        return text

    @classmethod
    def _convert_greek_letters(cls, text: str) -> str:
        for ch, latex in cls._GREEK.items():
            text = text.replace(ch, latex)
        return text

    @classmethod
    def _convert_math_operators(cls, text: str) -> str:
        for ch, latex in cls._OPERATORS.items():
            text = text.replace(ch, latex)
        return text

    @classmethod
    def _fix_fractions(cls, text: str) -> str:
        """
        Convert patterns like 'a / b' inside math mode to '\frac{a}{b}'.
        This is conservative — only for simple cases.
        """
        # Simple heuristic: $... / ...$ → $...\frac{...}{...}$
        # Not applied by default to avoid false positives
        return text

    @classmethod
    def _fix_common_patterns(cls, text: str) -> str:
        """Fix common malformed LaTeX from PDF extraction."""
        # Fix double dollars with spaces: $$ ... $$ → $$...$$
        text = re.sub(r"\$\$\s+", "$$", text)
        text = re.sub(r"\s+\$\$", "$$", text)

        # Fix spacing in exponents: x^ 2 → x^2
        text = re.sub(r"\^\s+", "^", text)

        # Fix broken symbols that pdftotext often splits
        text = text.replace(r"\ S", r"\S")
        text = text.replace(r"\ circ", r"\circ")
        text = text.replace(r"\ alpha", r"\alpha")
        text = text.replace(r"\ beta", r"\beta")
        text = text.replace(r"\ gamma", r"\gamma")
        text = text.replace(r"\ delta", r"\delta")

        # Section symbol in math context: § → \S
        text = re.sub(r"\$(.*?)§(.*?)\$", lambda m: f"${m.group(1)}\\S{m.group(2)}$", text)

        return text
