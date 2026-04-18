"""Generic TypeScript → Python translator built on tree-sitter.

No project-specific logic — the walker only handles TS AST node types and
emits Python source. Every tree-sitter node type has a small handler method
and dispatch happens through tables built at init time, so each method
stays well within the per-function statement budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import tree_sitter_typescript as _tst
from tree_sitter import Language, Node, Parser

from tt.ts_emit import (
    SRC_BRK, SRC_CONT, SRC_ELSE, SRC_EXC, SRC_FIN, SRC_HDR,
    SRC_PASS, SRC_RET, SRC_TRY, Emitter, safe_ident,
)
from tt.ts_names import camel_to_snake

_LANG = Language(_tst.language_typescript())


def _parser() -> Parser:
    return Parser(_LANG)


_BINARY_OP_MAP = {
    "===": "==", "!==": "!=", "&&": "and", "||": "or",
}
_UNARY_OP_MAP = {"!": "not ", "-": "-", "+": "+"}
_ASSIGN_OP_SET = {"=", "+=", "-=", "*=", "/=", "%=", "??=", "||=", "&&="}


@dataclass
class TranslateConfig:
    import_map: dict[str, str] = field(default_factory=dict)
    drop_imports: set[str] = field(default_factory=set)
    rename: dict[str, str] = field(default_factory=dict)
    snake_case_methods: bool = True
    max_method_statements: int = 0  # 0 disables the cap


class Translator:
    def __init__(self, config: TranslateConfig | None = None) -> None:
        self.cfg = config or TranslateConfig()
        self._source: bytes = b""
        self._call_shortcuts = self._init_call_shortcuts()
        self._stmt_dispatch = {
            "expression_statement": self._s_expr,
            "lexical_declaration": self._emit_lexical,
            "variable_declaration": self._emit_lexical,
            "return_statement": self._s_return,
            "if_statement": self._emit_if,
            "for_in_statement": self._emit_for_in,
            "for_statement": self._emit_for_c,
            "while_statement": self._s_while,
            "break_statement": lambda n, e: e.line(SRC_BRK),
            "continue_statement": lambda n, e: e.line(SRC_CONT),
            "throw_statement": self._s_throw,
            "try_statement": self._emit_try,
            "statement_block": self._emit_block,
            "comment": self._emit_comment,
            "empty_statement": lambda n, e: None,
        }
        self._expr_dispatch = {
            "identifier": self._e_ident,
            "shorthand_property_identifier": self._e_ident,
            "this": lambda n: "self",
            "number": self._e_number,
            "string": self._e_string,
            "template_string": self._template_string,
            "true": lambda n: "True",
            "false": lambda n: "False",
            "null": lambda n: "None",
            "undefined": lambda n: "None",
            "parenthesized_expression": self._e_paren,
            "unary_expression": self._e_unary,
            "binary_expression": self._e_binary,
            "assignment_expression": self._e_assign,
            "augmented_assignment_expression": self._e_aug,
            "update_expression": self._e_update,
            "ternary_expression": self._e_ternary,
            "call_expression": self._call,
            "new_expression": self._e_new,
            "member_expression": self._e_member,
            "subscript_expression": self._e_subscript,
            "object": self._object_literal,
            "array": self._e_array,
            "arrow_function": self._arrow,
            "spread_element": self._e_spread,
            "as_expression": self._e_unwrap,
            "satisfies_expression": self._e_unwrap,
            "non_null_expression": self._e_unwrap,
            "sequence_expression": self._e_sequence,
            "regex": lambda n: "r" + repr(self._text(n)),
        }
        self._top_dispatch = {
            "import_statement": self._emit_import,
            "class_declaration": self._emit_class,
            "export_statement": self._emit_export,
            "lexical_declaration": self._emit_lexical,
            "function_declaration": self._emit_function,
            "expression_statement": self._emit_stmt,
            "comment": self._emit_comment,
        }

    # -------------------------------------------------- driver
    def translate(self, source: bytes | str) -> str:
        src = source.encode("utf-8") if isinstance(source, str) else source
        self._source = src
        tree = _parser().parse(src)
        em = Emitter()
        em.line(SRC_HDR)
        em.line()
        for child in tree.root_node.children:
            handler = self._top_dispatch.get(child.type)
            if handler is not None:
                handler(child, em)
            elif child.type in ("interface_declaration", "type_alias_declaration", "enum_declaration"):
                em.line(f"# [stripped] {child.type}")
        return em.text()

    # -------------------------------------------------- helpers
    def _text(self, node: Node) -> str:
        return self._source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _child(self, node: Node, *types: str) -> Node | None:
        for c in node.children:
            if c.type in types:
                return c
        return None

    def _children(self, node: Node, *types: str) -> list[Node]:
        return [c for c in node.children if c.type in types]

    def _first_named(self, node: Node) -> Node | None:
        for c in node.children:
            if c.is_named:
                return c
        return None

    def _named(self, node: Node) -> list[Node]:
        return [c for c in node.children if c.is_named]

    def _ident(self, name: str, *, is_method: bool = False) -> str:
        if name in self.cfg.rename:
            name = self.cfg.rename[name]
        if is_method and self.cfg.snake_case_methods:
            name = camel_to_snake(name)
        return safe_ident(name)

    # -------------------------------------------------- imports
    def _emit_import(self, node: Node, em: Emitter) -> None:
        mapped, clause = self._resolve_import(node)
        if not mapped:
            return
        default_name, names = self._parse_clause(clause) if clause else (None, [])
        if default_name:
            em.line(f"from {mapped} import {default_name}")
        if names:
            parts = [o if o == a else f"{o} as {a}" for o, a in names]
            em.line(f"from {mapped} import {', '.join(parts)}")

    def _resolve_import(self, node: Node) -> tuple[str, Node | None]:
        src_node = self._child(node, "string")
        if src_node is None:
            return "", None
        src = self._string_value(src_node)
        if src in self.cfg.drop_imports:
            return "", None
        return self.cfg.import_map.get(src, "") or "", self._child(node, "import_clause")

    def _parse_clause(self, clause: Node) -> tuple[str | None, list[tuple[str, str]]]:
        default_name: str | None = None
        names: list[tuple[str, str]] = []
        for c in clause.children:
            if c.type == "identifier":
                default_name = self._text(c)
            elif c.type == "named_imports":
                names.extend(self._parse_named_imports(c))
        return default_name, names

    def _parse_named_imports(self, ni: Node) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for spec in self._children(ni, "import_specifier"):
            ids = self._children(spec, "identifier")
            if len(ids) == 1:
                n = self._text(ids[0])
                out.append((n, n))
            elif len(ids) == 2:
                out.append((self._text(ids[0]), self._text(ids[1])))
        return out

    def _string_value(self, node: Node) -> str:
        frag = self._child(node, "string_fragment")
        if frag is not None:
            return self._text(frag)
        t = self._text(node)
        return t[1:-1] if len(t) >= 2 and t[0] in ("'", '"') else t

    def _emit_export(self, node: Node, em: Emitter) -> None:
        inner = self._child(node, "class_declaration", "lexical_declaration",
                            "function_declaration", "interface_declaration")
        if inner is None:
            return
        handler = self._top_dispatch.get(inner.type)
        if handler is not None:
            handler(inner, em)

    # -------------------------------------------------- classes
    def _emit_class(self, node: Node, em: Emitter) -> None:
        name_node = self._child(node, "type_identifier")
        name = self._text(name_node) if name_node else "Anonymous"
        bases = self._class_bases(node)
        base_str = f"({', '.join(bases)})" if bases else ""
        em.line(f"class {name}{base_str}:")
        body = self._child(node, "class_body")
        members = self._class_members(body) if body else []
        with em:
            self._emit_class_members(members, em)

    def _emit_class_members(self, members: list[Node], em: Emitter) -> None:
        if not members:
            em.line(SRC_PASS)
            return
        for m in members:
            self._emit_class_member(m, em)
            em.line()

    def _class_bases(self, node: Node) -> list[str]:
        bases: list[str] = []
        heritage = self._child(node, "class_heritage")
        if heritage is None:
            return bases
        ext = self._child(heritage, "extends_clause")
        if ext is None:
            return bases
        for c in ext.children:
            if c.is_named and c.type != "extends":
                bases.append(self._expr(c))
        return bases

    def _class_members(self, body: Node) -> list[Node]:
        return [c for c in body.children if c.is_named and c.type != "comment"]

    def _emit_class_member(self, node: Node, em: Emitter) -> None:
        if node.type == "method_definition":
            self._emit_method(node, em)
        elif node.type == "public_field_definition":
            self._emit_field(node, em)

    def _emit_field(self, node: Node, em: Emitter) -> None:
        name_node = self._child(node, "property_identifier")
        if name_node is None:
            return
        name = self._ident(self._text(name_node), is_method=True)
        expr_node = self._after_eq(node)
        if expr_node is not None:
            em.line(f"{name} = {self._expr(expr_node)}")
        else:
            em.line(f"{name}: object = None")

    def _after_eq(self, node: Node) -> Node | None:
        saw_eq = False
        for c in node.children:
            if saw_eq and c.is_named and c.type != "type_annotation":
                return c
            if c.type == "=":
                saw_eq = True
        return None

    def _emit_method(self, node: Node, em: Emitter) -> None:
        name_node = self._child(node, "property_identifier")
        if name_node is None:
            return
        name = self._ident(self._text(name_node), is_method=True)
        params = self._child(node, "formal_parameters")
        param_list = self._param_list(params) if params else []
        args = ", ".join(["self"] + param_list)
        em.line(f"def {name}({args}):")
        body = self._child(node, "statement_block")
        with em:
            self._emit_method_body(body, em)

    def _emit_method_body(self, body: Node | None, em: Emitter) -> None:
        if body is None:
            em.line(SRC_PASS)
            return
        cap = self.cfg.max_method_statements
        if cap and self._count_body_stmts(body) > cap:
            em.line(SRC_PASS)
            em.line(f"# body exceeds translator cap ({cap} stmts) — stubbed")
            return
        self._emit_block(body, em)

    def _count_body_stmts(self, body: Node) -> int:
        return sum(1 for c in body.children if c.is_named and c.type != "comment")

    def _emit_function(self, node: Node, em: Emitter) -> None:
        name_node = self._child(node, "identifier")
        name = self._ident(self._text(name_node)) if name_node else "anon"
        params = self._child(node, "formal_parameters")
        param_list = self._param_list(params) if params else []
        em.line(f"def {name}({', '.join(param_list)}):")
        body = self._child(node, "statement_block")
        with em:
            if body is None:
                em.line(SRC_PASS)
            else:
                self._emit_block(body, em)

    def _param_list(self, params: Node) -> list[str]:
        out: list[str] = []
        for c in params.children:
            if c.type in ("required_parameter", "optional_parameter"):
                out.append(self._param(c))
            elif c.type == "rest_parameter":
                ident = self._child(c, "identifier")
                out.append("*" + (self._text(ident) if ident else "args"))
        return out

    def _param(self, node: Node) -> str:
        for c in node.children:
            if c.type == "identifier":
                return self._ident(self._text(c))
            if c.type == "object_pattern":
                return "_kw"
            if c.type == "array_pattern":
                return "_arr"
        return "_"

    # -------------------------------------------------- statements
    def _emit_block(self, block: Node, em: Emitter) -> None:
        emitted = False
        for c in block.children:
            if not c.is_named:
                continue
            self._emit_stmt(c, em)
            emitted = True
        if not emitted:
            em.line(SRC_PASS)

    def _emit_stmt(self, node: Node, em: Emitter) -> None:
        handler = self._stmt_dispatch.get(node.type)
        if handler is not None:
            handler(node, em)
        else:
            em.line(f"# [unhandled stmt: {node.type}]")

    def _s_expr(self, node: Node, em: Emitter) -> None:
        inner = self._first_named(node)
        if inner is None:
            return
        expr = self._expr(inner)
        em.line(expr if expr else SRC_PASS)

    def _s_return(self, node: Node, em: Emitter) -> None:
        inner = self._first_named(node)
        if inner is None:
            em.line(SRC_RET)
        else:
            em.line(f"{SRC_RET} {self._expr(inner)}")

    def _s_while(self, node: Node, em: Emitter) -> None:
        cond = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        em.line(f"while {self._expr(cond) if cond else 'True'}:")
        with em:
            self._emit_body(body, em)

    def _s_throw(self, node: Node, em: Emitter) -> None:
        inner = self._first_named(node)
        em.line(f"raise Exception({self._expr(inner) if inner else ''})")

    def _emit_body(self, body: Node | None, em: Emitter) -> None:
        if body is None:
            em.line(SRC_PASS)
            return
        if body.type == "statement_block":
            self._emit_block(body, em)
        else:
            self._emit_stmt(body, em)

    def _emit_lexical(self, node: Node, em: Emitter) -> None:
        for decl in self._children(node, "variable_declarator"):
            self._emit_declarator(decl, em)

    def _emit_declarator(self, decl: Node, em: Emitter) -> None:
        name_node = self._declarator_name(decl)
        value_node = self._after_eq(decl)
        if name_node is None:
            return
        if name_node.type == "identifier":
            lhs = self._ident(self._text(name_node))
            rhs = self._expr(value_node) if value_node is not None else "None"
            em.line(f"{lhs} = {rhs}")
            return
        if name_node.type == "object_pattern":
            self._emit_obj_destructure(name_node, value_node, em)
            return
        if name_node.type == "array_pattern":
            self._emit_arr_destructure(name_node, value_node, em)

    def _declarator_name(self, decl: Node) -> Node | None:
        for c in decl.children:
            if c.is_named and c.type in ("identifier", "object_pattern", "array_pattern"):
                return c
        return None

    def _emit_obj_destructure(self, pat: Node, value: Node | None, em: Emitter) -> None:
        names = [self._ident(self._text(c)) for c in pat.children
                 if c.type == "shorthand_property_identifier_pattern"]
        if value is None or not names:
            for n in names:
                em.line(f"{n} = None")
            return
        em.line(f"_src = {self._expr(value)}")
        for n in names:
            em.line(
                f"{n} = _src[{n!r}] if isinstance(_src, dict) "
                f"else getattr(_src, {n!r}, None)"
            )

    def _emit_arr_destructure(self, pat: Node, value: Node | None, em: Emitter) -> None:
        names = [self._ident(self._text(c)) for c in pat.children if c.type == "identifier"]
        if not names:
            return
        rhs = self._expr(value) if value is not None else "[]"
        em.line(f"{', '.join(names)} = ({rhs} + [None]*{len(names)})[:{len(names)}]")

    def _emit_if(self, node: Node, em: Emitter) -> None:
        cond = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt = node.child_by_field_name("alternative")
        em.line(f"if {self._expr(cond) if cond else 'True'}:")
        with em:
            self._emit_body(cons, em)
        self._emit_alt(alt, em)

    def _emit_alt(self, alt: Node | None, em: Emitter) -> None:
        inner = self._unwrap_else(alt)
        if inner is None:
            return
        if inner.type == "if_statement":
            self._emit_elif(inner, em)
            return
        em.line(SRC_ELSE)
        with em:
            self._emit_body(inner, em)

    def _emit_elif(self, inner: Node, em: Emitter) -> None:
        cond = inner.child_by_field_name("condition")
        cons = inner.child_by_field_name("consequence")
        alt = inner.child_by_field_name("alternative")
        em.line(f"elif {self._expr(cond) if cond else 'True'}:")
        with em:
            self._emit_body(cons, em)
        self._emit_alt(alt, em)

    def _unwrap_else(self, alt: Node | None) -> Node | None:
        if alt is None:
            return None
        if alt.type == "else_clause":
            return self._first_named(alt)
        return alt

    def _emit_for_in(self, node: Node, em: Emitter) -> None:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        body = node.child_by_field_name("body")
        op = self._for_operator(node)
        lhs = self._for_left(left) if left else "_x"
        rhs = self._expr(right) if right else "[]"
        if op == "in":
            em.line(
                f"for {lhs} in (list({rhs}.keys()) if isinstance({rhs}, dict) else {rhs}):"
            )
        else:
            em.line(f"for {lhs} in {rhs}:")
        with em:
            self._emit_body(body, em)

    def _for_operator(self, node: Node) -> str:
        for c in node.children:
            if c.type in ("of", "in"):
                return c.type
        return "in"

    def _for_left(self, node: Node) -> str:
        if node.type in ("lexical_declaration", "variable_declaration"):
            decl = self._child(node, "variable_declarator")
            inner = self._first_named(decl) if decl else None
            return self._for_left(inner) if inner else "_x"
        if node.type == "identifier":
            return self._ident(self._text(node))
        if node.type == "object_pattern":
            return self._obj_pat_tuple(node)
        if node.type == "array_pattern":
            return self._arr_pat_tuple(node)
        return "_x"

    def _obj_pat_tuple(self, node: Node) -> str:
        names = [self._ident(self._text(c)) for c in node.children
                 if c.type == "shorthand_property_identifier_pattern"]
        return "(" + ", ".join(names) + ",)" if names else "_obj"

    def _arr_pat_tuple(self, node: Node) -> str:
        names = [self._ident(self._text(c)) for c in node.children if c.type == "identifier"]
        return ", ".join(names) if names else "_arr"

    def _emit_for_c(self, node: Node, em: Emitter) -> None:
        init = node.child_by_field_name("initializer")
        cond = node.child_by_field_name("condition")
        incr = node.child_by_field_name("increment")
        body = node.child_by_field_name("body")
        if init is not None:
            self._for_init(init, em)
        em.line(f"while {self._expr(cond) if cond else 'True'}:")
        with em:
            self._emit_body(body, em)
            if incr is not None:
                em.line(self._expr(incr))

    def _for_init(self, init: Node, em: Emitter) -> None:
        if init.type in ("lexical_declaration", "variable_declaration"):
            self._emit_lexical(init, em)
        else:
            em.line(self._expr(init))

    def _emit_try(self, node: Node, em: Emitter) -> None:
        self._emit_try_section(SRC_TRY, self._child(node, "statement_block"), em)
        handler = self._child(node, "catch_clause")
        if handler is not None:
            self._emit_try_section(SRC_EXC, self._child(handler, "statement_block"), em)
        finalizer = self._child(node, "finally_clause")
        if finalizer is not None:
            self._emit_try_section(SRC_FIN, self._child(finalizer, "statement_block"), em)

    def _emit_try_section(self, header: str, body: Node | None, em: Emitter) -> None:
        em.line(header)
        with em:
            self._emit_body(body, em)

    def _emit_comment(self, node: Node, em: Emitter) -> None:
        txt = self._text(node)
        if txt.startswith("//"):
            em.line("# " + txt[2:].strip())
            return
        if txt.startswith("/*"):
            inner = txt[2:-2] if txt.endswith("*/") else txt[2:]
            for ln in inner.splitlines():
                em.line("# " + ln.strip().lstrip("* "))

    # -------------------------------------------------- expressions
    def _expr(self, node: Node) -> str:
        handler = self._expr_dispatch.get(node.type)
        if handler is not None:
            return handler(node)
        return f"__unhandled_{node.type}__"

    def _e_ident(self, node: Node) -> str:
        n = self._text(node)
        if n in ("undefined", "null"):
            return "None"
        if n == "true":
            return "True"
        if n == "false":
            return "False"
        if n == "this":
            return "self"
        return self._ident(n)

    def _e_number(self, node: Node) -> str:
        return self._text(node)

    def _e_string(self, node: Node) -> str:
        return repr(self._string_value(node))

    def _e_paren(self, node: Node) -> str:
        inner = self._first_named(node)
        return f"({self._expr(inner)})" if inner else "()"

    def _e_unary(self, node: Node) -> str:
        op_node = next(
            (c for c in node.children
             if not c.is_named and c.type in ("!", "-", "+", "typeof", "void", "delete")),
            None,
        )
        arg = self._first_named(node)
        op = op_node.type if op_node else ""
        inner = self._expr(arg) if arg else ""
        return self._unary_emit(op, inner)

    def _unary_emit(self, op: str, inner: str) -> str:
        if op == "typeof":
            return f"type({inner}).__name__"
        prefix = _UNARY_OP_MAP.get(op)
        return f"({prefix}{inner})" if prefix is not None else inner

    def _e_binary(self, node: Node) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op = self._binary_op(node, left, right)
        l = self._expr(left) if left else ""
        r = self._expr(right) if right else ""
        return self._binary_emit(op, l, r)

    def _binary_op(self, node: Node, left: Node | None, right: Node | None) -> str:
        for c in node.children:
            if not c.is_named and c is not left and c is not right:
                return c.type
        return "+"

    def _binary_emit(self, op: str, l: str, r: str) -> str:
        if op == "??":
            return f"({l} if {l} is not None else {r})"
        if op == "instanceof":
            return f"isinstance({l}, {r})"
        return f"({l} {_BINARY_OP_MAP.get(op, op)} {r})"

    def _e_assign(self, node: Node) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op = self._assign_op(node)
        l = self._expr(left) if left else ""
        r = self._expr(right) if right else ""
        return self._assign_emit(op, l, r)

    def _assign_op(self, node: Node) -> str:
        for c in node.children:
            if not c.is_named and c.type in _ASSIGN_OP_SET:
                return c.type
        return "="

    _COMPOUND_ASSIGN = {
        "??=": "{l} = {l} if {l} is not None else {r}",
        "||=": "{l} = {l} or {r}",
        "&&=": "{l} = {l} and {r}",
    }

    def _assign_emit(self, op: str, l: str, r: str) -> str:
        tmpl = self._COMPOUND_ASSIGN.get(op)
        if tmpl is not None:
            return tmpl.format(l=l, r=r)
        return f"{l} {op} {r}"

    def _e_aug(self, node: Node) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op = "+="
        for c in node.children:
            if not c.is_named and "=" in c.type and len(c.type) == 2:
                op = c.type
                break
        return f"{self._expr(left)} {op} {self._expr(right)}"

    def _e_update(self, node: Node) -> str:
        arg = self._first_named(node)
        op = "+="
        for c in node.children:
            if c.type == "--":
                op = "-="
        return f"{self._expr(arg)} {op} 1"

    def _e_ternary(self, node: Node) -> str:
        cond = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt = node.child_by_field_name("alternative")
        return f"({self._expr(cons)} if {self._expr(cond)} else {self._expr(alt)})"

    def _call(self, node: Node) -> str:
        fn = node.child_by_field_name("function")
        args = self._child(node, "arguments")
        arg_str = self._arg_list(args) if args else ""
        short = self._call_shortcut(fn, args, arg_str)
        if short is not None:
            return short
        return f"{self._expr(fn) if fn else ''}({arg_str})"

    def _call_shortcut(self, fn: Node | None, args: Node | None, arg_str: str) -> str | None:
        if fn is None or fn.type != "member_expression":
            return None
        prop = fn.child_by_field_name("property")
        obj = fn.child_by_field_name("object")
        pname = self._text(prop) if prop else ""
        return self._shortcut_for(pname, obj, args, arg_str)

    def _shortcut_for(
        self, pname: str, obj: Node | None, args: Node | None, arg_str: str,
    ) -> str | None:
        handler = self._call_shortcuts.get(pname)
        if handler is None:
            return None
        return handler(obj, args, arg_str)

    def _init_call_shortcuts(self) -> dict:
        return {
            "push": lambda o, a, s: f"{self._expr(o)}.append({s})",
            "includes": self._sc_includes,
            "filter": self._sc_filter,
            "map": self._sc_map,
            "find": self._sc_find,
            "some": self._sc_some,
            "every": self._sc_every,
            "at": self._sc_at,
            "slice": lambda o, a, s: f"{self._expr(o)}[{s}]" if a and self._arg_items(a) else f"{self._expr(o)}[:]",
            "concat": lambda o, a, s: f"([*{self._expr(o)}, *{s}])",
            "toString": lambda o, a, s: f"str({self._expr(o)})",
            "toNumber": lambda o, a, s: f"float({self._expr(o)})",
        }

    def _sc_includes(self, obj: Node | None, args: Node | None, arg_str: str) -> str | None:
        if args and len(self._arg_items(args)) == 1:
            return f"({arg_str} in {self._expr(obj)})"
        return None

    def _predicate_parts(self, args: Node | None) -> tuple[str, str] | None:
        items = self._arg_items(args) if args else []
        if len(items) != 1 or items[0].type != "arrow_function":
            return None
        pvar, body = self._arrow_predicate(items[0])
        return (pvar, body) if body is not None else None

    def _arrow_predicate(self, arrow: Node) -> tuple[str, str | None]:
        params = self._child(arrow, "formal_parameters")
        plist, pvar = self._predicate_param(arrow, params)
        body_node = self._arrow_body(arrow, params)
        if body_node is None:
            return pvar, None
        if body_node.type == "statement_block":
            body = self._arrow_block_return(body_node)
            return pvar, body
        return pvar, self._expr(body_node)

    def _predicate_param(self, arrow: Node, params: Node | None) -> tuple[list[str], str]:
        if params is None:
            single = self._arrow_single_param(arrow)
            return single, single[0] if single else "_x"
        plist = self._param_list(params)
        return plist, plist[0] if plist else "_x"

    def _arrow_block_return(self, body_node: Node) -> str | None:
        stmts = [c for c in body_node.children if c.is_named and c.type != "comment"]
        if len(stmts) == 1 and stmts[0].type == "return_statement":
            inner = self._first_named(stmts[0])
            return self._expr(inner) if inner is not None else None
        return None

    def _sc_filter(self, obj, args, arg_str):
        parts = self._predicate_parts(args)
        if parts is None:
            return None
        pvar, body = parts
        return f"[{pvar} for {pvar} in {self._expr(obj)} if {body}]"

    def _sc_map(self, obj, args, arg_str):
        parts = self._predicate_parts(args)
        if parts is None:
            return None
        pvar, body = parts
        return f"[{body} for {pvar} in {self._expr(obj)}]"

    def _sc_find(self, obj, args, arg_str):
        parts = self._predicate_parts(args)
        if parts is None:
            return None
        pvar, body = parts
        return f"next(({pvar} for {pvar} in {self._expr(obj)} if {body}), None)"

    def _sc_some(self, obj, args, arg_str):
        parts = self._predicate_parts(args)
        if parts is None:
            return None
        pvar, body = parts
        return f"any({body} for {pvar} in {self._expr(obj)})"

    def _sc_every(self, obj, args, arg_str):
        parts = self._predicate_parts(args)
        if parts is None:
            return None
        pvar, body = parts
        return f"all({body} for {pvar} in {self._expr(obj)})"

    def _sc_at(self, obj, args, arg_str):
        return f"({self._expr(obj)}[{arg_str}] if {self._expr(obj)} else None)"

    def _arg_items(self, args: Node) -> list[Node]:
        return [c for c in args.children if c.is_named and c.type != "comment"]

    def _arg_list(self, args: Node) -> str:
        return ", ".join(self._expr(c) for c in self._arg_items(args))

    def _e_new(self, node: Node) -> str:
        ctor = node.child_by_field_name("constructor")
        args = self._child(node, "arguments")
        arg_str = self._arg_list(args) if args else ""
        return f"{self._expr(ctor)}({arg_str})"

    def _e_member(self, node: Node) -> str:
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        pname = self._text(prop) if prop else ""
        if pname == "length":
            return f"len({self._expr(obj) if obj else ''})"
        return f"{self._expr(obj) if obj else ''}.{self._ident(pname, is_method=True)}"

    def _e_subscript(self, node: Node) -> str:
        obj = node.child_by_field_name("object")
        idx = node.child_by_field_name("index")
        return f"{self._expr(obj)}[{self._expr(idx)}]"

    def _e_array(self, node: Node) -> str:
        return "[" + ", ".join(self._expr(c) for c in node.children if c.is_named) + "]"

    def _e_spread(self, node: Node) -> str:
        inner = self._first_named(node)
        return f"*{self._expr(inner)}" if inner else "*[]"

    def _e_unwrap(self, node: Node) -> str:
        inner = self._first_named(node)
        return self._expr(inner) if inner else ""

    def _e_sequence(self, node: Node) -> str:
        parts = [self._expr(c) for c in node.children if c.is_named]
        return "(" + ", ".join(parts) + ")[-1]"

    def _object_literal(self, node: Node) -> str:
        items: list[str] = []
        for c in node.children:
            piece = self._object_item(c)
            if piece:
                items.append(piece)
        return "{" + ", ".join(items) + "}"

    def _object_item(self, c: Node) -> str:
        if c.type == "pair":
            k = c.child_by_field_name("key")
            v = c.child_by_field_name("value")
            if k is None or v is None:
                return ""
            return f"{self._object_key(k)}: {self._expr(v)}"
        if c.type == "shorthand_property_identifier":
            n = self._ident(self._text(c))
            return f"{n!r}: {n}"
        if c.type == "spread_element":
            inner = self._first_named(c)
            return f"**{self._expr(inner)}" if inner else ""
        return ""

    def _object_key(self, node: Node) -> str:
        if node.type == "property_identifier":
            return repr(self._text(node))
        if node.type == "string":
            return repr(self._string_value(node))
        if node.type == "number":
            return self._text(node)
        if node.type == "computed_property_name":
            inner = self._first_named(node)
            return self._expr(inner) if inner else "''"
        return repr(self._text(node))

    def _template_string(self, node: Node) -> str:
        parts: list[str] = []
        for c in node.children:
            if c.type == "string_fragment":
                parts.append(self._text(c).replace("{", "{{").replace("}", "}}"))
            elif c.type == "template_substitution":
                inner = self._first_named(c)
                if inner is not None:
                    parts.append("{" + self._expr(inner) + "}")
        return "f" + repr("".join(parts))

    def _arrow(self, node: Node) -> str:
        params = self._child(node, "formal_parameters")
        plist = self._param_list(params) if params else self._arrow_single_param(node)
        body_node = self._arrow_body(node, params)
        destructured = self._collect_destructured_fields(params) if params else []
        return self._arrow_emit(plist, body_node, destructured)

    def _arrow_single_param(self, node: Node) -> list[str]:
        ident = self._child(node, "identifier")
        return [self._ident(self._text(ident))] if ident is not None else []

    def _arrow_body(self, node: Node, params: Node | None) -> Node | None:
        for c in node.children:
            if c.is_named and c.type != "formal_parameters" and c is not params:
                return c
        return None

    def _arrow_emit(
        self, plist: list[str], body_node: Node | None,
        destructured: list[str],
    ) -> str:
        if body_node is None:
            return "(lambda: None)"
        joined = ", ".join(plist)
        body = self._arrow_body_source(body_node)
        wrapped = self._wrap_destructured(body, destructured) if destructured else body
        return f"(lambda {joined}: {wrapped})"

    def _arrow_body_source(self, body_node: Node) -> str:
        if body_node.type != "statement_block":
            return self._expr(body_node)
        inner = self._arrow_block_return(body_node)
        return inner if inner is not None else "True"

    def _wrap_destructured(self, body: str, fields: list[str]) -> str:
        # fields were destructured from a TS object param — rebind them inside
        # the body by reading from the opaque _kw dict. Using dict.get keeps
        # missing-field references safe (returns None instead of KeyError).
        defaults = ", ".join(f"{f}=(_kw.get({f!r}) if isinstance(_kw, dict) else getattr(_kw, {f!r}, None))"
                             for f in fields)
        return f"(lambda {defaults}: {body})()"

    def _collect_destructured_fields(self, params: Node) -> list[str]:
        for c in params.children:
            if c.type in ("required_parameter", "optional_parameter"):
                pat = self._child(c, "object_pattern")
                if pat is not None:
                    return [self._ident(self._text(x))
                            for x in pat.children
                            if x.type == "shorthand_property_identifier_pattern"]
        return []
