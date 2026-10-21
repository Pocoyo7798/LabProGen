#!/usr/bin/env python3
"""Build the interactive schema map (a single HTML page) from the LinkML schema.

Usage (from the repository root):
    python scripts/build_schema_map.py
    python scripts/build_schema_map.py --schema schema/action_data_model.yaml --out site/index.html

Only needs PyYAML (pip install pyyaml).
"""
import argparse
import datetime as dt
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_schema(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_data(schema, source_name):
    classes_in = schema.get("classes") or {}
    slots_in = schema.get("slots") or {}
    enums_in = schema.get("enums") or {}

    def chain(name):
        """Class followed by its is_a ancestors (nearest first)."""
        out, seen = [], set()
        while name and name in classes_in and name not in seen:
            out.append(name)
            seen.add(name)
            name = (classes_in[name] or {}).get("is_a")
        return out

    def owners(name, _seen=None):
        """Classes that contribute slots (ancestors, their mixins and the mixins'
        own ancestors), oldest first."""
        seen = set() if _seen is None else _seen
        order = []
        for c in reversed(chain(name)):
            for m in (classes_in[c] or {}).get("mixins") or []:
                if m in classes_in and m not in seen:
                    for o in owners(m, seen):
                        if o not in order:
                            order.append(o)
            if c not in seen:
                seen.add(c)
                order.append(c)
        return order

    def contributors(name):
        """Every class whose slot_usage applies to this class, nearest first."""
        return list(reversed(owners(name)))

    def group(name):
        ch = chain(name)
        if (classes_in[name] or {}).get("mixin"):
            return "mixin"
        if "Action" in ch:
            return "action"
        if "ChemicalEntity" in ch:
            return "chemical"
        if (classes_in[name] or {}).get("tree_root"):
            return "procedure"
        return "helper"

    classes = {}
    for name, c in classes_in.items():
        c = c or {}
        ch = chain(name)
        rows, seen = [], set()
        for owner in owners(name):
            for s in (classes_in[owner] or {}).get("slots") or []:
                if s in seen:
                    continue
                seen.add(s)
                base = slots_in.get(s) or {}
                eff = {
                    "name": s,
                    "owner": owner,
                    "range": base.get("range") or schema.get("default_range") or "string",
                    "required": bool(base.get("required", False)),
                    "multivalued": bool(base.get("multivalued", False)),
                    "description": (base.get("description") or "").strip(),
                    "slot_uri": base.get("slot_uri"),
                    "mappings": base.get("exact_mappings") or [],
                }
                # slot_usage overrides, applied from the oldest ancestor to the class itself
                for k in reversed(contributors(name)):
                    su = ((classes_in[k] or {}).get("slot_usage") or {}).get(s) or {}
                    for key in ("range", "required", "multivalued", "description"):
                        if key in su:
                            eff[key] = su[key].strip() if isinstance(su[key], str) else su[key]
                r = eff["range"]
                eff["kind"] = "class" if r in classes_in else "enum" if r in enums_in else "type"
                rows.append(eff)
        classes[name] = {
            "name": name,
            "is_a": c.get("is_a") if c.get("is_a") in classes_in else None,
            "mixins": [m for m in c.get("mixins") or [] if m in classes_in],
            "abstract": bool(c.get("abstract")),
            "mixin": bool(c.get("mixin")),
            "description": (c.get("description") or "").strip(),
            "class_uri": c.get("class_uri"),
            "exact": c.get("exact_mappings") or [],
            "related": c.get("related_mappings") or [],
            "aliases": c.get("aliases") or [],
            "comments": [str(x).strip() for x in c.get("comments") or []],
            "tree_root": bool(c.get("tree_root")),
            "group": group(name),
            "slots": rows,
        }

    enums = {}
    for name, e in enums_in.items():
        values = []
        for k, v in ((e or {}).get("permissible_values") or {}).items():
            v = v or {}
            values.append({"v": str(k), "description": v.get("description"), "meaning": v.get("meaning")})
        enums[name] = {"name": name, "values": values}

    rels = []
    for name, c in classes.items():
        for r in c["slots"]:
            if r["kind"] == "class" and r["owner"] == name:
                rels.append([name, r["range"], r["name"], r["multivalued"]])

    meta = {
        "name": schema.get("title") or schema.get("name") or "LinkML schema",
        "version": str(schema.get("version") or "unversioned"),
        "id": schema.get("id") or "",
        "source": source_name,
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "nclasses": len(classes_in),
        "nslots": len(slots_in),
        "nenums": len(enums_in),
    }
    return {"meta": meta, "order": list(classes_in), "classes": classes, "enums": enums, "rels": rels}


def build_mermaid(data):
    C, R, order = data["classes"], data["rels"], data["order"]

    def diagram(names, rels, direction):
        names = [n for n in order if n in names]
        lines = ["classDiagram", f"  direction {direction}"]
        for n in names:
            if C[n]["is_a"] in names:
                lines.append(f"  {C[n]['is_a']} <|-- {n}")
        for n in names:
            for m in C[n].get("mixins") or []:
                if m in names:
                    lines.append(f"  {m} <|.. {n}")
        for a, b, s, mv in rels:
            lines.append(f'  {a} --> "{"*" if mv else "1"}" {b} : {s}')
        for n in names:
            lines.append(f"  class {n}")
            if C[n]["abstract"]:
                lines.append(f"  <<abstract>> {n}")
            if C[n]["mixin"]:
                lines.append(f"  <<mixin>> {n}")
        return "\n".join(lines)

    def ancestors(n):
        out = []
        while n:
            out.append(n)
            n = C[n]["is_a"]
        return out

    # Helper classes held by an action (e.g. separation methods), with their
    # subclasses, are drawn in the action diagram rather than the chemical one.
    action_targets = {b for a, b, s, mv in R if C[a]["group"] == "action" and C[b]["group"] == "helper"}
    action_helpers = {n for n in C if C[n]["group"] == "helper" and set(ancestors(n)) & action_targets}
    action_names = {n for n in C if C[n]["group"] == "action"} | action_helpers
    action_rels = [r for r in R if r[0] in action_names and r[1] in action_names]
    chem_names = {n for n in C if C[n]["group"] in ("chemical", "helper", "mixin")} - action_helpers
    chem_rels = [r for r in R if r[0] in chem_names]
    link_rels = [r for r in R if C[r[0]]["group"] in ("procedure", "action")]
    link_names = {r[0] for r in link_rels} | {r[1] for r in link_rels}
    links = ["classDiagram", "  direction LR"]
    links += [f'  {a} --> "{"*" if mv else "1"}" {b} : {s}' for a, b, s, mv in link_rels]
    links += [f"  class {n}" for n in order if n in link_names]
    return {
        "links": "\n".join(links),
        "actions": diagram(action_names, action_rels, "TB"),
        "chemical": diagram(chem_names, chem_rels, "TB"),
    }


def as_script_json(obj):
    # Keep "</script>" sequences from ending the <script> block early.
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schema", default=os.path.join(ROOT, "schema", "action_data_model.yaml"))
    ap.add_argument("--template", default=os.path.join(HERE, "schema_map_template.html"))
    ap.add_argument("--out", default=os.path.join(ROOT, "site", "index.html"))
    args = ap.parse_args()

    schema = load_schema(args.schema)
    data = build_data(schema, os.path.relpath(args.schema, ROOT).replace(os.sep, "/"))
    mermaid = build_mermaid(data)

    with open(args.template, encoding="utf-8") as fh:
        html = fh.read()
    for token in ("__SCHEMA_JSON__", "__MERMAID_JSON__"):
        if token not in html:
            sys.exit(f"Template is missing the {token} placeholder")
    html = html.replace("__SCHEMA_JSON__", as_script_json(data)).replace("__MERMAID_JSON__", as_script_json(mermaid))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    m = data["meta"]
    print(f"Wrote {args.out}: {m['nclasses']} classes, {m['nslots']} slots, {m['nenums']} enums (version {m['version']})")


if __name__ == "__main__":
    main()
