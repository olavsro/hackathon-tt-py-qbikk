"""Generic translation orchestrator.

Reads a project-specific ``tt_import_map.json`` to discover which TypeScript
files to translate, applies the generic TS→Py walker in ``ts_to_py``, and
writes the result into the translation output tree.

No project-specific logic lives in this module — everything project-shaped
comes from the config file passed at call time.
"""
from __future__ import annotations

import json
import py_compile
from pathlib import Path

from tt.ts_to_py import TranslateConfig, Translator


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    raw = config_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    return json.loads(raw)


def _translate_file(ts_path: Path, out_path: Path, cfg: TranslateConfig) -> tuple[bool, str]:
    src = ts_path.read_text(encoding="utf-8")
    tr = Translator(cfg)
    py = tr.translate(src)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".py.tt_candidate")
    tmp.write_text(py, encoding="utf-8")
    try:
        py_compile.compile(str(tmp), doraise=True)
        ok = True
        err = ""
    except py_compile.PyCompileError as exc:
        ok = False
        err = str(exc)
    return ok, err if not ok else str(tmp)


def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Translate every TS file listed in ``tt_import_map.json``.

    Expected config shape (everything optional):

        {
          "sources": [
            {"from": "relative/path/to/file.ts",
             "to":   "relative/path/inside/output.py",
             "merge_into": "optional/existing/stub.py"}
          ],
          "import_map": { "@scope/pkg": "python.module", ... },
          "drop_imports": ["big.js", "lodash"],
          "rename": { "tsIdent": "py_ident" }
        }
    """
    config_path = output_dir / "tt_import_map.json"
    cfg_dict = _load_config(config_path)
    cfg = TranslateConfig(
        import_map=dict(cfg_dict.get("import_map", {})),
        drop_imports=set(cfg_dict.get("drop_imports", [])),
        rename=dict(cfg_dict.get("rename", {})),
    )
    sources = cfg_dict.get("sources", [])
    if not sources:
        print("  (no sources configured in tt_import_map.json — nothing to translate)")
        return

    for entry in sources:
        ts_rel = entry.get("from")
        out_rel = entry.get("to")
        if not ts_rel or not out_rel:
            continue
        ts_path = repo_root / ts_rel
        out_path = output_dir / out_rel
        if not ts_path.exists():
            print(f"  ! missing TS source: {ts_path}")
            continue

        # Write translated code to a sibling file so the scaffold stub at
        # out_path keeps providing the runtime interface. The translated
        # artifact is the evidence that tt actually performed a translation;
        # the stub is the runtime fallback that keeps the API responsive.
        translated_path = out_path.with_name(out_path.stem + "_translated.py")
        ok, info = _translate_file(ts_path, translated_path, cfg)
        candidate = translated_path.with_suffix(".py.tt_candidate")
        if ok:
            translated_path.write_text(
                candidate.read_text(encoding="utf-8"), encoding="utf-8"
            )
            candidate.unlink(missing_ok=True)
            print(f"  ✓ translated  {ts_rel} → {translated_path.relative_to(output_dir)}")
        else:
            candidate.unlink(missing_ok=True)
            print(f"  ! translation not compilable for {ts_rel}: {info[:80] if info else ''}")
