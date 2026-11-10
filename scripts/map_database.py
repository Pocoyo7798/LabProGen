"""Read the database folders (protocols, actions, chemical entities) for the schema map.

Used by build_schema_map.py. Only needs PyYAML. Files may be YAML or JSON:

* database/protocols: a LabProcedure (protocol_name + laboratory_actions), or an
  application export with a list of procedures under ``activities`` (and an
  optional ``materials`` registry that ``{entity_id: ...}`` references point to).
  A leading comment block ("# Source text: ...") is shown as the source text.
* database/actions: assembled (complex) actions as the GUI saves them
  (``complex_action_name`` + ``steps``, or a ``complex_actions`` list), or
  LinkML actions (a mapping with ``type``, or a list of them).
* database/chemical_entities: LinkML chemical entities (a mapping with
  ``type``, a list of them, or a ``materials`` registry).

Anything that is not recognised is still listed, with its raw content.
"""
from __future__ import annotations

import json
import os
import re

import yaml

SOURCE_RE = re.compile(r"^\s*source text:\s*$", re.I)
FILE_EXT = (".yaml", ".yml", ".json")


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

def _read(path: str):
    """Return (data, raw text, error)."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    try:
        data = json.loads(raw) if path.lower().endswith(".json") else yaml.safe_load(raw)
        return data, raw, None
    except Exception as exc:  # shown on the page, never fatal
        return None, raw, f"Could not read the file: {exc}"


def _files(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        return []
    return sorted(
        os.path.join(folder, f) for f in os.listdir(folder)
        if f.lower().endswith(FILE_EXT) and not f.startswith(".")
    )


def source_text(raw: str) -> str:
    """The leading comment block of a file, without '#', and without a 'Source text:' title."""
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            if stripped in ("", "---") and not lines:
                continue
            break
        body = stripped[1:].strip()
        if not body:  # an empty comment line ends the source paragraph
            if lines:
                break
            continue
        if SOURCE_RE.match(body):
            continue
        lines.append(body)
    return " ".join(lines)


# --------------------------------------------------------------------------
# Schema helpers
# --------------------------------------------------------------------------

def _chain(schema: dict, name: str) -> list[str]:
    classes = schema.get("classes") or {}
    out, seen = [], set()
    while name and name in classes and name not in seen:
        out.append(name)
        seen.add(name)
        name = (classes[name] or {}).get("is_a")
    return out


def _method_outputs(schema: dict, method_class: str):
    classes, enums = schema.get("classes") or {}, schema.get("enums") or {}
    for name in _chain(schema, method_class):
        raw = ((classes.get(name) or {}).get("annotations") or {}).get("outputs")
        enum_name = raw.get("value") if isinstance(raw, dict) else raw
        if enum_name:
            return [str(v) for v in ((enums.get(enum_name) or {}).get("permissible_values") or {})]
    return None


def _outputs(action: dict, schema: dict):
    """[] = one unnamed output; a list = named outputs; None = unknown."""
    if action.get("type") != "Separate":
        return []
    method = action.get("method")
    if not isinstance(method, dict) or not method.get("type"):
        return None
    return _method_outputs(schema, method["type"])


# --------------------------------------------------------------------------
# Graph checks (same rules as labprogen/linkml/graph.py, schema 3.x)
# --------------------------------------------------------------------------

def graph_issues(actions: list[dict], schema: dict) -> list[str]:
    issues: list[str] = []
    actions = [a for a in actions if isinstance(a, dict)]
    index_of: dict[str, int] = {}
    for i, a in enumerate(actions):
        aid = a.get("id")
        if aid in (None, ""):
            issues.append(f"Step {i + 1} ({a.get('type')}) has no id.")
            continue
        if str(aid) in index_of:
            issues.append(f"Id '{aid}' is used more than once.")
        else:
            index_of[str(aid)] = i
    outs = [_outputs(a, schema) for a in actions]

    loops = []
    loop_of = {}
    for i, a in enumerate(actions):
        if a.get("type") != "Repeat":
            continue
        amount, until = a.get("amount"), a.get("until")
        if amount is None and not until:
            issues.append(f"Repeat '{a.get('id')}' needs an amount or an until condition.")
        elif amount is not None and (isinstance(amount, bool) or not isinstance(amount, int) or amount < 2):
            issues.append(f"Repeat '{a.get('id')}': amount must be an integer of at least 2.")
        start = index_of.get(str(a.get("restart_at")))
        if start is None:
            issues.append(f"Repeat '{a.get('id')}': restart_at '{a.get('restart_at')}' is not an action id.")
        elif start >= i:
            issues.append(f"Repeat '{a.get('id')}': restart_at must point to an earlier action.")
        else:
            loops.append((start, i))
            loop_of[i] = (start, i)
    for x in range(len(loops)):
        for y in range(x + 1, len(loops)):
            (s1, e1), (s2, e2) = loops[x], loops[y]
            if s1 < s2 <= e1 < e2 or s2 < s1 <= e2 < e1:
                issues.append("Two loops partly overlap; loops must be nested or separate.")

    for i, a in enumerate(actions):
        ref = a.get("input")
        if ref in (None, ""):
            if i > 0:
                issues.append(f"'{a.get('id')}' ({a.get('type')}) has no input.")
            continue
        tid, _, out = str(ref).partition(".")
        t = index_of.get(tid)
        if t is None:
            issues.append(f"'{a.get('id')}': input '{ref}' is not an action id.")
            continue
        if out:
            if outs[t] == []:
                issues.append(f"'{a.get('id')}': '{tid}' has a single output; use '{tid}'.")
            elif outs[t] is not None and out not in outs[t]:
                issues.append(f"'{a.get('id')}': '{tid}' has no output '{out}'.")
        elif outs[t] and len(outs[t]) > 1:
            issues.append(f"'{a.get('id')}': '{tid}' has several outputs; name one ({', '.join(outs[t])}).")
        if a.get("type") == "Repeat" and i in loop_of:
            s, e = loop_of[i]
            if not s <= t < e:
                issues.append(f"Repeat '{a.get('id')}': input must come from inside its loop.")
        elif t >= i:
            issues.append(f"'{a.get('id')}': input '{ref}' must point to an earlier action.")
    return issues


# --------------------------------------------------------------------------
# Summaries
# --------------------------------------------------------------------------

def _value_text(value) -> str:
    if isinstance(value, dict):
        if value.get("type") and value.get("name"):
            return f"{value['name']} ({value['type']})" + (f", {value['quantity']}" if value.get("quantity") else "")
        if value.get("type"):
            inner = ", ".join(f"{k} {v}" for k, v in value.items() if k != "type" and not isinstance(v, (dict, list)))
            return value["type"] + (f" ({inner})" if inner else "")
        return ", ".join(f"{k}: {_value_text(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(_value_text(v) for v in value)
    return str(value)


def _params(action: dict) -> list[list[str]]:
    skip = {"type", "id", "input"}
    return [[k, _value_text(v)] for k, v in action.items() if k not in skip]


def _chemical_names(value, out: set[str]) -> None:
    if isinstance(value, dict):
        if value.get("name") and value.get("type") and value.get("type") not in ("MixtureConstituent",):
            out.add(str(value["name"]))
        for v in value.values():
            _chemical_names(v, out)
    elif isinstance(value, list):
        for v in value:
            _chemical_names(v, out)


def _keywords(actions: list[dict]) -> list[str]:
    """Searchable terms: separation methods, containers, processes, until conditions."""
    out: set[str] = set()
    for a in actions:
        for key in ("recipient", "process", "agitation_type", "add_type"):
            if a.get(key):
                out.add(str(a[key]))
        for key in ("method", "until"):
            if isinstance(a.get(key), dict) and a[key].get("type"):
                out.add(str(a[key]["type"]))
    return sorted(out)


def _expand_refs(value, materials: dict):
    if isinstance(value, dict):
        if set(value) == {"entity_id"} and value["entity_id"] in materials:
            return _expand_refs(materials[value["entity_id"]], materials)
        return {k: _expand_refs(v, materials) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_refs(v, materials) for v in value]
    return value


# --------------------------------------------------------------------------
# Mermaid graph of a procedure
# --------------------------------------------------------------------------

def _label(text: str) -> str:
    return str(text).replace('"', "'").replace("\n", " ")


def _node_detail(a: dict) -> str:
    t = a.get("type")
    if t == "Add":
        names = set()
        _chemical_names(a.get("chemical"), names)
        q = [str(c.get("quantity")) for c in (a.get("chemical") or []) if isinstance(c, dict) and c.get("quantity")]
        return ", ".join(sorted(names))[:40] + (f" ({q[0]})" if len(q) == 1 else "")
    if t == "Separate":
        return ((a.get("method") or {}).get("type") or "")
    if t == "ChangeTemperature":
        return str(a.get("temperature", ""))
    if t == "ChangePressure":
        return str(a.get("pressure", ""))
    if t == "ChangeAgitation":
        return str(a.get("agitation_type", ""))
    if t == "ChangeContainer":
        return f"{a.get('recipient', '')}, {a.get('container_state', '')}".strip(", ")
    if t == "NoAction":
        return str(a.get("duration", ""))
    if t == "Repeat":
        until = a.get("until")
        if until:
            return _value_text(until)
        return f"x{a.get('amount')}"
    return str(a.get("duration", ""))


def procedure_mermaid(actions: list[dict]) -> str:
    actions = [a for a in actions if isinstance(a, dict) and a.get("id")]
    key = {str(a["id"]): f"n{i}" for i, a in enumerate(actions)}
    lines = ["flowchart TD"]
    for a in actions:
        detail = _node_detail(a)
        text = f"<b>{_label(a['id'])}</b> {_label(a.get('type', ''))}" + (f"<br/>{_label(detail)}" if detail else "")
        shape = ("{{", "}}") if a.get("type") == "Repeat" else (("[/", "/]") if a.get("type") == "Separate" else ("[", "]"))
        lines.append(f'  {key[str(a["id"])]}{shape[0]}"{text}"{shape[1]}')
    for a in actions:
        ref = a.get("input")
        if not ref:
            continue
        tid, _, out = str(ref).partition(".")
        if tid not in key:
            continue
        arrow = f' -- "{_label(out)}" --> ' if out else " --> "
        lines.append(f"  {key[tid]}{arrow}{key[str(a['id'])]}")
        if a.get("type") == "Repeat" and str(a.get("restart_at")) in key:
            lines.append(f'  {key[str(a["id"])]} -. "repeat" .-> {key[str(a["restart_at"])]}')
    classes = {"ChangeContainer": "container", "Add": "add", "ContinuousAddition": "add", "Separate": "separate",
               "Repeat": "loop", "ChangeTemperature": "persistent", "ChangePressure": "persistent",
               "ChangeAgitation": "persistent"}
    for a in actions:
        if a.get("type") in classes:
            lines.append(f"  class {key[str(a['id'])]} {classes[a['type']]}")
    lines += ["  classDef container stroke-dasharray:4 3", "  classDef separate stroke-width:2px",
              "  classDef loop stroke-width:2px"]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Folders
# --------------------------------------------------------------------------

def _rel(path: str, root: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def read_protocols(folder: str, root: str, schema: dict) -> list[dict]:
    out = []
    for path in _files(folder):
        data, raw, error = _read(path)
        base = {"file": _rel(path, root), "source_text": source_text(raw)}
        procedures = []
        if isinstance(data, dict) and isinstance(data.get("laboratory_actions"), list):
            procedures = [data]
        elif isinstance(data, dict) and isinstance(data.get("activities"), list):
            materials = data.get("materials") if isinstance(data.get("materials"), dict) else {}
            procedures = [_expand_refs(p, materials) for p in data["activities"] if isinstance(p, dict)]
        if not procedures:
            out.append({**base, "id": os.path.splitext(os.path.basename(path))[0], "name": os.path.basename(path),
                        "error": error or "Not recognised as a protocol (no laboratory_actions).",
                        "raw": raw[:20000], "actions": [], "issues": [], "types": [], "keywords": [],
                        "chemicals": []})
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        for n, proc in enumerate(procedures, 1):
            actions = [a for a in proc.get("laboratory_actions") or [] if isinstance(a, dict)]
            names: set[str] = set()
            _chemical_names(actions, names)
            out.append({
                **base,
                "id": stem if len(procedures) == 1 else f"{stem}-{n}",
                "name": proc.get("protocol_name") or stem,
                "actions": [{"id": str(a.get("id", "")), "type": a.get("type", ""), "input": a.get("input", ""),
                             "params": _params(a)} for a in actions],
                "types": sorted({a.get("type", "") for a in actions}),
                "keywords": _keywords(actions),
                "chemicals": sorted(names),
                "issues": graph_issues(actions, schema),
                "mermaid": procedure_mermaid(actions),
                "raw": raw[:20000],
            })
    return out


def read_actions(folder: str, root: str) -> list[dict]:
    out = []
    for path in _files(folder):
        data, raw, error = _read(path)
        stem = os.path.splitext(os.path.basename(path))[0]
        items = []
        if isinstance(data, dict) and isinstance(data.get("complex_actions"), list):
            items = data["complex_actions"]
        elif isinstance(data, dict) and (data.get("complex_action_name") or data.get("steps")):
            items = [data]
        elif isinstance(data, dict) and data.get("type"):
            items = [{"complex_action_name": data.get("id") or stem, "linkml": [data]}]
        elif isinstance(data, list) and all(isinstance(x, dict) for x in data):
            items = [{"complex_action_name": stem, "linkml": data}]
        if not items:
            out.append({"id": stem, "name": os.path.basename(path), "file": _rel(path, root),
                        "error": error or "Not recognised as an action.", "steps": [], "parameters": [], "raw": raw[:20000]})
            continue
        for n, item in enumerate(items, 1):
            if "linkml" in item:
                steps = [[a.get("type", ""), _value_text({k: v for k, v in a.items() if k not in ("type",)})]
                         for a in item["linkml"]]
                params = []
            else:
                steps = [[s.get("action", ""), _value_text(s.get("params") or {})] for s in item.get("steps") or []
                         if isinstance(s, dict)]
                params = [[str(p.get("step_index", "")), p.get("action", ""), p.get("display_name") or p.get("param_key", ""),
                           str(p.get("value", "")), str(p.get("unit", "")), "yes" if p.get("editable") else "no"]
                          for p in item.get("parameters") or [] if isinstance(p, dict)]
            out.append({"id": stem if len(items) == 1 else f"{stem}-{n}",
                        "name": item.get("complex_action_name") or stem, "file": _rel(path, root),
                        "steps": steps, "parameters": params, "raw": raw[:20000]})
    return out


def read_entities(folder: str, root: str) -> list[dict]:
    out = []
    for path in _files(folder):
        data, raw, error = _read(path)
        stem = os.path.splitext(os.path.basename(path))[0]
        if isinstance(data, dict) and isinstance(data.get("materials"), dict):
            items = list(data["materials"].values())
        elif isinstance(data, dict):
            items = [data]
        elif isinstance(data, list):
            items = data
        else:
            items = []
        items = [x for x in items if isinstance(x, dict) and x.get("type")]
        if not items:
            out.append({"id": stem, "name": os.path.basename(path), "file": _rel(path, root), "type": "",
                        "error": error or "Not recognised as a chemical entity (no type).", "fields": [], "raw": raw[:20000]})
            continue
        for n, item in enumerate(items, 1):
            out.append({"id": stem if len(items) == 1 else f"{stem}-{n}",
                        "name": item.get("name") or item.get("species_name") or stem, "type": item.get("type"),
                        "file": _rel(path, root),
                        "fields": [[k, _value_text(v)] for k, v in item.items() if k not in ("type", "name")],
                        "raw": raw[:20000]})
    return out


def read_database(database_dir: str, root: str, schema: dict) -> dict:
    return {
        "protocols": read_protocols(os.path.join(database_dir, "protocols"), root, schema),
        "actions": read_actions(os.path.join(database_dir, "actions"), root),
        "entities": read_entities(os.path.join(database_dir, "chemical_entities"), root),
    }
