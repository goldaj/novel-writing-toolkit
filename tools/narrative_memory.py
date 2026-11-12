#!/usr/bin/env python3
"""Evidence-backed, offline narrative memory and causal graph (Python 3.10+).

This module NEVER infers fictional truth from prose. Facts, ordering, causality
and knowledge are author-annotated; source quotes are verified against the
manifest. Missing annotations are uncertainty, not proof of inconsistency.
"""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import json
import re

from manuscript_pipeline import ProjectError, load_project, read_utf8

IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
STATES = {"knows", "believes", "suspects"}
TRUST = {"confirmed", "tentative"}
MAX_RECORDS = 5000


def read_memory(path: Path) -> dict:
    try:
        memory = json.loads(read_utf8(path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ProjectError("Cannot read narrative memory: " + str(exc)) from exc
    if not isinstance(memory, dict):
        raise ProjectError("Narrative memory must be an object")
    return memory


def indexed(data: dict, key: str) -> dict:
    records = data.get(key, [])
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ProjectError(key + " must be an array with at most 5000 records")
    indexed_records = {}
    for record in records:
        if not isinstance(record, dict):
            raise ProjectError(key + " entries must be objects")
        ident = record.get("id")
        if not isinstance(ident, str) or not IDENTIFIER.fullmatch(ident):
            raise ProjectError(key + " has invalid record ID")
        if ident in indexed_records:
            raise ProjectError("Duplicate " + key + " ID: " + ident)
        indexed_records[ident] = record
    return indexed_records


def required_string(record: dict, name: str, context: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ProjectError(context + " requires nonempty " + name)
    return value


def optional_id(record: dict, key: str, targets: dict, context: str) -> str | None:
    value = record.get(key)
    if value is not None and (not isinstance(value, str) or value not in targets):
        raise ProjectError(context + " references unknown " + key)
    return value


def text_index(project: Path) -> tuple[dict, dict]:
    info, sections = load_project(project.resolve())
    texts = {}
    for path, _heading in sections:
        name = path.relative_to(project.resolve()).as_posix()
        try:
            texts[name] = read_utf8(path)
        except (OSError, UnicodeError) as exc:
            raise ProjectError("Cannot read section " + name + ": " + str(exc)) from exc
    return info, texts


def source_issues(record: dict, context: str, texts: dict) -> list[dict]:
    source = record.get("source")
    if not isinstance(source, dict):
        raise ProjectError(context + " requires source {chapter, quote}")
    chapter = required_string(source, "chapter", context + " source")
    quote = required_string(source, "quote", context + " source")
    if chapter not in texts:
        raise ProjectError(context + " source chapter not in project manifest: " + chapter)
    if len(quote) > 1600:
        raise ProjectError(context + " source quote exceeds 1600 characters")
    normal = lambda s: " ".join(s.split())
    if normal(quote) not in normal(texts[chapter]):
        return [{"code": "stale_source", "severity": "review", "item": context,
                 "chapter": chapter, "detail": "Exact source quote no longer found"}]
    return []


def validate(project: Path, memory: dict) -> dict:
    """Validate schema, references, source provenance, chronology, and causality.

    Returns a validated view. Only stale quotes and incomplete times are review
    warnings; malformed data and dependency cycles are rejected.
    """
    if memory.get("schema_version") != 1:
        raise ProjectError("memory.schema_version must equal 1")
    _project_info, texts = text_index(project)
    characters = indexed(memory, "characters")
    events = indexed(memory, "events")
    facts = indexed(memory, "facts")
    knowledge = indexed(memory, "knowledge")
    dependencies = indexed(memory, "dependencies")
    issues = []
    for ident, char in characters.items():
        required_string(char, "name", "character " + ident)
        aliases = char.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
            raise ProjectError("character aliases must be nonempty strings")

    for ident, event in events.items():
        required_string(event, "label", "event " + ident)
        ordinal = event.get("time_index")
        if ordinal is not None and (type(ordinal) is not int or ordinal < 0):
            raise ProjectError("event time_index must be a nonnegative integer or null: " + ident)
        issues += source_issues(event, "event:" + ident, texts)
        precedes = event.get("precedes", [])
        if not isinstance(precedes, list) or any(x not in events or x == ident for x in precedes):
            raise ProjectError("Invalid precedes for event " + ident)
        requirements = event.get("requires_knowledge", [])
        if not isinstance(requirements, list):
            raise ProjectError("requires_knowledge must be an array")
        for req in requirements:
            if not isinstance(req, dict) or req.get("character") not in characters or req.get("fact") not in facts:
                raise ProjectError("Invalid knowledge requirement for event " + ident)

    for ident, fact in facts.items():
        subject = required_string(fact, "subject", "fact " + ident)
        if subject != "world" and subject not in characters:
            raise ProjectError("Unknown fact subject: " + subject)
        required_string(fact, "attribute", "fact " + ident)
        required_string(fact, "value", "fact " + ident)
        if fact.get("confidence", "confirmed") not in TRUST:
            raise ProjectError("Unknown fact confidence: " + ident)
        optional_id(fact, "from_event", events, "fact " + ident)
        optional_id(fact, "until_event", events, "fact " + ident)
        issues += source_issues(fact, "fact:" + ident, texts)

    for ident, item in knowledge.items():
        if item.get("character") not in characters or item.get("fact") not in facts:
            raise ProjectError("Unknown character or fact in knowledge " + ident)
        if item.get("state") not in STATES:
            raise ProjectError("Unknown knowledge state in " + ident)
        optional_id(item, "since_event", events, "knowledge " + ident)
        optional_id(item, "until_event", events, "knowledge " + ident)
        if item["state"] == "knows" and "believed_value" in item and (
                item["believed_value"] != facts[item["fact"]]["value"]):
            raise ProjectError("Known value contradicts fact; use believes or suspects: " + ident)
        if "believed_value" in item and not isinstance(item["believed_value"], str):
            raise ProjectError("believed_value must be a string")
        issues += source_issues(item, "knowledge:" + ident, texts)

    for ident, dep in dependencies.items():
        if dep.get("effect_event") not in events:
            raise ProjectError("Unknown effect_event for dependency " + ident)
        groups = dep.get("because_any")
        if not isinstance(groups, list) or not groups or any(
                not isinstance(g, list) or not g for g in groups):
            raise ProjectError("Dependency " + ident + " requires nonempty OR of AND groups")
        for group in groups:
            for token in group:
                if not isinstance(token, str) or ":" not in token:
                    raise ProjectError("Invalid dependency token in " + ident)
                kind, raw_target = token.split(":", 1)
                target, delimiter, expected = raw_target.partition("=")
                if (delimiter and (kind != "fact" or not expected.strip())):
                    raise ProjectError("Only facts may have a nonempty expected value")
                catalog = {"event": events, "fact": facts, "knowledge": knowledge}.get(kind)
                if catalog is None or target not in catalog:
                    raise ProjectError("Unknown dependency token: " + token)
                if kind == "event" and target == dep["effect_event"]:
                    raise ProjectError("Self-dependent event: " + target)
        issues += source_issues(dep, "dependency:" + ident, texts)

    # A causal graph and chronological partial order must each be acyclic.
    chronology_edges = {eid: set(e.get("precedes", [])) for eid, e in events.items()}
    order = _toposort(events, chronology_edges, "chronological")
    for src, children in chronology_edges.items():
        for dst in children:
            a, b = events[src].get("time_index"), events[dst].get("time_index")
            if a is not None and b is not None and a >= b:
                raise ProjectError("precedes contradicts time_index: " + src + " -> " + dst)
    causal_edges = {eid: set() for eid in events}
    for dep in dependencies.values():
        for group in dep["because_any"]:
            for token in group:
                if token.startswith("event:"):
                    causal_edges[token.split(":", 1)[1]].add(dep["effect_event"])
    _toposort(events, causal_edges, "causal")
    for catalog_name, records in (("facts", facts), ("knowledge", knowledge)):
        for ident, item in records.items():
            first = item.get("from_event" if catalog_name == "facts" else "since_event")
            last = item.get("until_event")
            if first and last and events[first].get("time_index") is not None and (
                    events[last].get("time_index") is not None) and (
                    events[first]["time_index"] >= events[last]["time_index"]):
                raise ProjectError("Invalid validity interval: " + ident)
    if any(e.get("time_index") is None for e in events.values()):
        issues.append({"code": "partial_chronology", "severity": "info",
                       "detail": "Events without explicit time_index cannot be strictly ordered"})
    return {"characters": characters, "events": events, "facts": facts,
            "knowledge": knowledge, "dependencies": dependencies,
            "chronological_topology": order, "issues": issues, "texts": texts}


def _toposort(nodes: dict, edges: dict, label: str) -> list[str]:
    indegree = {name: 0 for name in nodes}
    for children in edges.values():
        for dst in children:
            indegree[dst] += 1
    queue = deque(sorted(k for k, v in indegree.items() if v == 0))
    ordered = []
    while queue:
        item = queue.popleft()
        ordered.append(item)
        for dest in sorted(edges[item]):
            indegree[dest] -= 1
            if indegree[dest] == 0:
                queue.append(dest)
    if len(ordered) != len(nodes):
        raise ProjectError("Cycle in " + label + " graph")
    return ordered


def event_time(view: dict, ident: str | None) -> int | None:
    return view["events"][ident].get("time_index") if ident else None


def interval(view: dict, item: dict, start_key: str) -> tuple[int | None, int | None]:
    return event_time(view, item.get(start_key)), event_time(view, item.get("until_event"))


def active_at(view: dict, item: dict, start_key: str, moment: int | None) -> bool | None:
    first, last = interval(view, item, start_key)
    if moment is None or (item.get(start_key) and first is None) or (
            item.get("until_event") and last is None):
        return None
    return (first is None or moment >= first) and (last is None or moment < last)


def fact_conflicts(view: dict) -> list[dict]:
    by_attribute = defaultdict(list)
    for ident, item in view["facts"].items():
        if item.get("confidence", "confirmed") == "confirmed":
            by_attribute[(item["subject"], item["attribute"])].append((ident, item))
    findings = []
    for (subject, attribute), values in by_attribute.items():
        for i, (left_id, left) in enumerate(values):
            for right_id, right in values[i + 1:]:
                if left["value"] == right["value"]:
                    continue
                a_start, a_end = interval(view, left, "from_event")
                b_start, b_end = interval(view, right, "from_event")
                unknown = (
                    (left.get("from_event") and a_start is None) or
                    (left.get("until_event") and a_end is None) or
                    (right.get("from_event") and b_start is None) or
                    (right.get("until_event") and b_end is None)
                )
                if unknown:
                    findings.append({"code": "possible_fact_conflict", "severity": "review",
                                     "subject": subject, "attribute": attribute,
                                     "facts": [left_id, right_id],
                                     "detail": "Intervals are not fully dated"})
                elif max(a_start if a_start is not None else float("-inf"),
                         b_start if b_start is not None else float("-inf")) < min(
                         a_end if a_end is not None else float("inf"),
                         b_end if b_end is not None else float("inf")):
                    findings.append({"code": "overlapping_world_facts", "severity": "review",
                                     "subject": subject, "attribute": attribute,
                                     "facts": [left_id, right_id],
                                     "values": [left["value"], right["value"]]})
    return findings


def knowledge_findings(view: dict) -> list[dict]:
    output = []
    for event_id, event in view["events"].items():
        for requirement in event.get("requires_knowledge", []):
            char, fact = requirement["character"], requirement["fact"]
            options = [k for k in view["knowledge"].values() if k["character"] == char
                       and k["fact"] == fact and k["state"] == "knows"]
            moment = event.get("time_index")
            states = [active_at(view, k, "since_event", moment) for k in options]
            if True in states:
                continue
            if None in states or moment is None:
                status = "knowledge_order_unknown"
            elif options:
                status = "knowledge_not_yet_acquired"
            else:
                status = "knowledge_not_documented"
            output.append({"code": status, "severity": "review", "event": event_id,
                           "character": char, "fact": fact,
                           "detail": "Required knowledge not established at this event"})
    return output


def support_for(view: dict) -> dict[str, dict]:
    """Three-valued evaluation of DECLARED OR/AND prerequisites.

    Unknown chronology is never silently treated as satisfied. Absent records
    in a compared version are false. Textual presence alone is not causality.
    """
    deps = defaultdict(list)
    for ident, dep in view["dependencies"].items():
        deps[dep["effect_event"]].append((ident, dep))
    memo = {}
    visiting = set()

    def token_state(token: str, moment: int | None) -> bool | None:
        kind, raw_target = token.split(":", 1)
        target, _delimiter, expected = raw_target.partition("=")
        if kind == "event":
            if target not in view["events"]:
                return False
            ancestor = view["events"][target].get("time_index")
            if ancestor is None or moment is None:
                return None
            if ancestor > moment:
                return False
            upstream = check(target)["state"]
            return {"supported": True, "unsupported": False, "uncertain": None}[upstream]
        if kind == "fact":
            if expected and view["facts"][target]["value"].casefold() != expected.casefold():
                return False
            return active_at(view, view["facts"][target], "from_event", moment)
        return active_at(view, view["knowledge"][target], "since_event", moment)

    def check(event_id: str) -> dict:
        if event_id in memo:
            return memo[event_id]
        if event_id in visiting:
            raise ProjectError("Causal cycle at " + event_id)
        visiting.add(event_id)
        own = deps.get(event_id, [])
        statuses = []
        for ident, dep in own:
            alternatives = []
            for group in dep["because_any"]:
                states = [token_state(token, view["events"][event_id].get("time_index"))
                          for token in group]
                alternatives.append("supported" if all(x is True for x in states)
                                    else "unsupported" if any(x is False for x in states)
                                    else "uncertain")
            statuses.append({"dependency": ident, "alternatives": alternatives,
                             "state": "supported" if "supported" in alternatives
                             else "uncertain" if "uncertain" in alternatives
                             else "unsupported"})
        visiting.remove(event_id)
        state = "unsupported" if any(s["state"] == "unsupported" for s in statuses) else (
            "uncertain" if any(s["state"] == "uncertain" for s in statuses) else "supported")
        memo[event_id] = {"state": state, "dependencies": statuses,
                          "declared": bool(statuses)}
        return memo[event_id]

    for event_id in view["events"]:
        check(event_id)
    return memo


def audit(project: Path, memory: dict) -> dict:
    view = validate(project, memory)
    events = sorted(view["events"].values(), key=lambda e: (
        e.get("time_index") is None,
        e.get("time_index") if e.get("time_index") is not None else 0,
        e["id"]))
    timeline = [{"id": e["id"], "label": e["label"],
                 "time_index": e.get("time_index"), "source": e["source"],
                 "participants": e.get("participants", [])} for e in events]
    for e in events:
        participants = e.get("participants", [])
        if not isinstance(participants, list) or any(c not in view["characters"] for c in participants):
            raise ProjectError("Unknown event participant: " + e["id"])
    issues = [*view["issues"], *fact_conflicts(view), *knowledge_findings(view)]
    causal = support_for(view)
    for eid, state in causal.items():
        if state["declared"] and state["state"] != "supported":
            issues.append({"code": "causal_" + state["state"], "severity": "review",
                           "event": eid, "detail": "Review declared prerequisites"})
    return {"schema_version": 1, "kind": "narrative_audit",
            "project": memory.get("project", ""),
            "notice": "Only explicitly annotated narrative facts are checked. "
                      "An absence of findings is not evidence of literary consistency.",
            "counts": {"characters": len(view["characters"]), "events": len(events),
                       "facts": len(view["facts"]), "knowledge": len(view["knowledge"]),
                       "dependencies": len(view["dependencies"])},
            "timeline": timeline, "characters": list(view["characters"].values()),
            "facts": list(view["facts"].values()), "knowledge": list(view["knowledge"].values()),
            "causal_support": causal, "issues": issues}


def compare(old_project: Path, new_project: Path, old_memory: dict, new_memory: dict) -> dict:
    """Compare annotated worlds with stable IDs and manuscript changes.

    Changed IDs remain candidates for human review. A surviving alternative
    justification does not certify the narrative, it only weakens one flag.
    """
    old = validate(old_project, old_memory)
    new = validate(new_project, new_memory)
    previous = support_for(old)
    current = support_for(new)
    changed = []
    for kind in ("events", "facts", "knowledge", "dependencies"):
        for ident in sorted(set(old[kind]) | set(new[kind])):
            before, after = old[kind].get(ident), new[kind].get(ident)
            if before != after:
                changed.append({"kind": kind, "id": ident,
                                "change": "added" if before is None else
                                "removed" if after is None else "modified"})
    # Trace dependencies from both versions: removed causal links are relevant.
    consumers = defaultdict(set)
    for view in (old, new):
        for dep in view["dependencies"].values():
            for group in dep["because_any"]:
                for token in group:
                    kind, raw = token.split(":", 1)
                    normalized = kind + ":" + raw.split("=", 1)[0]
                    consumers[normalized].add(dep["effect_event"])
    frontier = deque()
    for item in changed:
        prefix = {"events": "event", "facts": "fact",
                  "knowledge": "knowledge", "dependencies": "event"}[item["kind"]]
        if item["kind"] == "dependencies":
            for view in (old, new):
                dep = view["dependencies"].get(item["id"])
                if dep:
                    frontier.append("event:" + dep["effect_event"])
        else:
            frontier.append(prefix + ":" + item["id"])
    visited = set(frontier)
    impacted = set()
    while frontier:
        token = frontier.popleft()
        for effect in consumers.get(token, ()):
            impacted.add(effect)
            successor = "event:" + effect
            if successor not in visited:
                visited.add(successor)
                frontier.append(successor)
    effects = []
    for eid in sorted(impacted):
        a, b = previous.get(eid, {}).get("state"), current.get(eid, {}).get("state")
        if b is None:
            status = "event_removed"
        elif a == "supported" and b == "unsupported":
            status = "declared_support_lost"
        elif b == "uncertain":
            status = "chronology_or_causality_uncertain"
        elif a == "unsupported" and b == "supported":
            status = "support_restored"
        elif a == b == "supported" and (
                [d["alternatives"] for d in previous[eid]["dependencies"]] !=
                [d["alternatives"] for d in current[eid]["dependencies"]]):
            status = "alternative_support_preserved"
        else:
            status = "review_transitive_consequence"
        effects.append({"event": eid, "before": a, "after": b, "status": status,
                        "source": new["events"].get(eid, old["events"].get(eid))["source"]})
    # Reuse the existing lexical diff as an explicitly non-semantic evidence layer.
    from narrative_impact import analyze
    textual = analyze(old_project, new_project, max_hits=8)
    return {"schema_version": 1, "kind": "narrative_comparison",
            "notice": "Dependency effects are author-declared leads, not automated "
                      "proof of invalid prose. Lexical matches are not causal inference.",
            "before": audit(old_project, old_memory),
            "after": audit(new_project, new_memory),
            "memory_changes": changed, "consequences": effects,
            "changed_blocks": textual["changed_blocks"],
            "text_changes": textual["changes"]}
