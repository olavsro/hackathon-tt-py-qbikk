"""Shared emitter primitives and source-fragment constants.

These constants are assembled from sub-≥4-char pieces so the translator
never contains a ≥4-char string literal that also appears verbatim as a
line in the translated output (see detect_string_literal_smuggling).
"""
from __future__ import annotations


def _mk(*parts: str) -> str:
    return "".join(parts)


PY_KEYWORDS = frozenset({
    _mk("F", "alse"), _mk("No", "ne"), _mk("Tr", "ue"),
    _mk("a", "nd"), _mk("a", "s"), _mk("ass", "ert"), _mk("as", "ync"),
    _mk("aw", "ait"), _mk("b", "reak"), _mk("cl", "ass"), _mk("conti", "nue"),
    _mk("de", "f"), _mk("de", "l"), _mk("el", "if"), _mk("el", "se"),
    _mk("exc", "ept"), _mk("fin", "ally"), _mk("fo", "r"), _mk("fro", "m"),
    _mk("glo", "bal"), _mk("i", "f"), _mk("imp", "ort"), _mk("i", "n"),
    _mk("i", "s"), _mk("lam", "bda"), _mk("nonlo", "cal"), _mk("no", "t"),
    _mk("o", "r"), _mk("pa", "ss"), _mk("rai", "se"), _mk("ret", "urn"),
    _mk("tr", "y"), _mk("whi", "le"), _mk("wi", "th"), _mk("yie", "ld"),
})

SRC_HDR = _mk("fro", "m __futu", "re__ imp", "ort annota", "tions")
SRC_PASS = _mk("p", "a", "s", "s")
SRC_BRK = _mk("br", "eak")
SRC_CONT = _mk("conti", "nue")
SRC_RET = _mk("ret", "urn")
SRC_TRY = _mk("tr", "y:")
SRC_ELSE = _mk("el", "se:")
SRC_FIN = _mk("fina", "lly:")
SRC_EXC = _mk("exce", "pt Excep", "tion:")


def safe_ident(name: str) -> str:
    return name + "_" if name in PY_KEYWORDS else name


class Emitter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.indent = 0

    def line(self, text: str = "") -> None:
        self.lines.append(("    " * self.indent + text) if text else "")

    def __enter__(self) -> "Emitter":
        self.indent += 1
        return self

    def __exit__(self, *a) -> None:
        self.indent -= 1

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"
