import argparse
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import DefaultDict, Dict, List, Optional, Set, Tuple


BANK_RE = re.compile(r"^\s*bank\s+v\d+\s+([0-9a-fA-F]+)\.bnk\s*$")
OBJECT_RE = re.compile(r"^\s*obj\s+(CAk[A-Za-z0-9_]+)\[\d+\]\s*$")
ID_RE = re.compile(r"\bsid\s+ulID\s*=\s*(\d+)(?:\s+\(([^)]*)\))?")
SOURCE_RE = re.compile(r"\bsourceID\s*=\s*(\d+)")
CHILD_RE = re.compile(r"\bulChildID\s*=\s*(\d+)")
ACTION_ID_RE = re.compile(r"\bulActionID\s*=\s*(\d+)")
TARGET_RE = re.compile(r"\bulTargetID\s*=\s*(\d+)")
ACTION_TYPE_RE = re.compile(r"\bulActionType\s*=.*?\[([^]]+)\]")
GROUP_TYPE_RE = re.compile(r"\beGroupType\s*=.*?\[([^]]+)\]")
GROUP_ID_RE = re.compile(r"\bulGroupID\s*=\s*(\d+)")
SWITCH_PACKAGE_RE = re.compile(r"\bobj\s+CAkSwitchPackage\[\d+\]")
SWITCH_ID_RE = re.compile(r"\bulSwitchID\s*=\s*(\d+)(?:\s+\(([^)]*)\))?")
SWITCH_NODE_RE = re.compile(r"\bNodeID\s*=\s*(\d+)")
RANDOM_MODE_RE = re.compile(r"\beRandomMode\s*=.*?\[([^]]+)\]")
MODE_RE = re.compile(r"\beMode\s*=.*?\[([^]]+)\]")
BANK_NAME_RE = re.compile(r"\bdwSoundBankID\s*=\s*\d+\s+\(([^)]*)\)")


GRAPH_CLASSES = {
    "CAkSound",
    "CAkLayerCntr",
    "CAkRanSeqCntr",
    "CAkSwitchCntr",
    "CAkActorMixer",
    "CAkMusicTrack",
    "CAkMusicSegment",
    "CAkMusicRanSeqCntr",
    "CAkMusicSwitchCntr",
    "CAkDialogueEvent",
    "CAkEvent",
}


def is_graph_class(class_name: str) -> bool:
    return class_name in GRAPH_CLASSES or class_name.startswith("CAkAction")


@dataclass
class Node:
    serial: int
    class_name: str
    bank_hex: str
    object_id: Optional[int] = None
    name: Optional[str] = None
    source_ids: List[int] = field(default_factory=list)
    children: List[int] = field(default_factory=list)
    action_ids: List[int] = field(default_factory=list)
    target_id: Optional[int] = None
    action_type: Optional[str] = None
    group_type: Optional[str] = None
    group_id: Optional[int] = None
    switch_values: DefaultDict[int, List[Tuple[int, Optional[str]]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    random_mode: Optional[str] = None
    mode: Optional[str] = None

    @property
    def is_action(self) -> bool:
        return self.class_name.startswith("CAkAction")

    @property
    def is_event(self) -> bool:
        return self.class_name == "CAkEvent"


def parse_banks(mapping_file: Path) -> Tuple[List[Node], Dict[str, str]]:
    nodes: List[Node] = []
    bank_names: Dict[str, str] = {}
    current_bank = "unknown"
    current: Optional[Node] = None
    current_switch_value: Optional[Tuple[int, Optional[str]]] = None
    serial = 0

    def finish_current() -> None:
        nonlocal current
        if current is not None and current.object_id is not None:
            nodes.append(current)
        current = None

    with mapping_file.open("r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            bank_match = BANK_RE.match(line)
            if bank_match:
                finish_current()
                current_bank = bank_match.group(1).lower()
                current_switch_value = None
                continue

            bank_name_match = BANK_NAME_RE.search(line)
            if bank_name_match and current_bank != "unknown":
                bank_names[current_bank] = bank_name_match.group(1)

            object_match = OBJECT_RE.match(line)
            if object_match and is_graph_class(object_match.group(1)):
                finish_current()
                serial += 1
                current = Node(serial, object_match.group(1), current_bank)
                current_switch_value = None
                continue

            if current is None:
                continue

            if current.object_id is None:
                id_match = ID_RE.search(line)
                if id_match:
                    current.object_id = int(id_match.group(1))
                    current.name = id_match.group(2)
                    continue

            source_match = SOURCE_RE.search(line)
            if source_match:
                current.source_ids.append(int(source_match.group(1)))
                continue

            child_match = CHILD_RE.search(line)
            if child_match:
                current.children.append(int(child_match.group(1)))
                continue

            action_id_match = ACTION_ID_RE.search(line)
            if action_id_match:
                current.action_ids.append(int(action_id_match.group(1)))
                continue

            target_match = TARGET_RE.search(line)
            if target_match:
                current.target_id = int(target_match.group(1))
                continue

            action_type_match = ACTION_TYPE_RE.search(line)
            if action_type_match:
                current.action_type = action_type_match.group(1)
                continue

            group_type_match = GROUP_TYPE_RE.search(line)
            if group_type_match:
                current.group_type = group_type_match.group(1)
                continue

            group_id_match = GROUP_ID_RE.search(line)
            if group_id_match:
                current.group_id = int(group_id_match.group(1))
                continue

            if SWITCH_PACKAGE_RE.search(line):
                current_switch_value = None
                continue

            switch_id_match = SWITCH_ID_RE.search(line)
            if switch_id_match:
                current_switch_value = (
                    int(switch_id_match.group(1)),
                    switch_id_match.group(2),
                )
                continue

            switch_node_match = SWITCH_NODE_RE.search(line)
            if switch_node_match and current_switch_value is not None:
                current.switch_values[int(switch_node_match.group(1))].append(
                    current_switch_value
                )
                continue

            random_mode_match = RANDOM_MODE_RE.search(line)
            if random_mode_match:
                current.random_mode = random_mode_match.group(1)
                continue

            mode_match = MODE_RE.search(line)
            if mode_match:
                current.mode = mode_match.group(1)

    finish_current()
    return nodes, bank_names


def preferred(nodes: List[Node], bank_hex: str) -> List[Node]:
    return sorted(nodes, key=lambda node: node.bank_hex != bank_hex)


def find_chains(nodes: List[Node], media_id: int, bank_filter: Optional[str]):
    by_id: DefaultDict[int, List[Node]] = defaultdict(list)
    parents: DefaultDict[int, List[Node]] = defaultdict(list)
    actions_by_target: DefaultDict[int, List[Node]] = defaultdict(list)
    events_by_action: DefaultDict[int, List[Node]] = defaultdict(list)

    for node in nodes:
        if node.object_id is None:
            continue
        by_id[node.object_id].append(node)
        for child_id in node.children:
            parents[child_id].append(node)
        if node.is_action and node.target_id is not None:
            actions_by_target[node.target_id].append(node)
        if node.is_event:
            for action_id in node.action_ids:
                events_by_action[action_id].append(node)

    sounds = [
        node
        for node in nodes
        if media_id in node.source_ids
        and (bank_filter is None or node.bank_hex == bank_filter)
    ]
    results = []
    seen_results: Set[Tuple[int, int, Tuple[int, ...]]] = set()

    for sound in sounds:
        queue = deque([(sound, [sound], {sound.serial})])
        while queue:
            node, upward_path, visited = queue.popleft()
            if node.object_id is None:
                continue

            for action in preferred(actions_by_target[node.object_id], sound.bank_hex):
                if action.object_id is None:
                    continue
                for event in preferred(events_by_action[action.object_id], sound.bank_hex):
                    if event.object_id is None:
                        continue
                    downward_path = list(reversed(upward_path))
                    key = (
                        event.object_id,
                        action.object_id,
                        tuple(item.serial for item in downward_path),
                    )
                    if key not in seen_results:
                        seen_results.add(key)
                        results.append((event, action, downward_path, by_id))

            for parent in preferred(parents[node.object_id], sound.bank_hex):
                if parent.serial in visited:
                    continue
                queue.append((parent, upward_path + [parent], visited | {parent.serial}))

    return sounds, results


def count_text(count: int) -> str:
    chinese = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}
    return chinese.get(count, str(count))


def display_id(node: Node) -> str:
    if node.name:
        return f"{node.name} ({node.object_id})"
    return str(node.object_id)


def node_label(node: Node) -> str:
    if node.class_name == "CAkSwitchCntr":
        return f"Switch {display_id(node)}"
    if node.class_name in ("CAkRanSeqCntr", "CAkMusicRanSeqCntr"):
        mode = node.mode or "Random/Sequence"
        random_mode = node.random_mode
        if mode == "Random" and random_mode:
            mode = f"{mode}/{random_mode}"
        suffix = ""
        if mode.startswith("Random") and node.children:
            suffix = f"（{count_text(len(node.children))}选一）"
        return f"{mode} {display_id(node)}{suffix}"
    if node.class_name == "CAkLayerCntr":
        return f"Layer {display_id(node)}"
    if node.class_name == "CAkActorMixer":
        return f"ActorMixer {display_id(node)}"
    if node.class_name == "CAkSound":
        return f"Sound {display_id(node)}"
    short_name = node.class_name[3:] if node.class_name.startswith("CAk") else node.class_name
    return f"{short_name} {display_id(node)}"


def collect_direct_wems(
    node: Node, by_id: Dict[int, List[Node]], preferred_bank: str
) -> List[int]:
    media_ids = []
    for child_id in node.children:
        for child in preferred(by_id.get(child_id, []), preferred_bank):
            if child.class_name == "CAkSound":
                media_ids.extend(child.source_ids)
                break
    return media_ids


def print_chain(event: Node, action: Node, path: List[Node], by_id, selected_id: int):
    print(f"Event {display_id(event)}")
    action_type = action.action_type
    if not action_type:
        prefix_text = "CAkAction"
        action_type = (
            action.class_name[len(prefix_text) :]
            if action.class_name.startswith(prefix_text)
            else action.class_name
        )
    print(f"└── Action {display_id(action)} [{action_type}]")
    prefix = "    "

    for index, node in enumerate(path):
        if node.class_name == "CAkSound":
            for media_id in node.source_ids:
                marker = "  ← selected" if media_id == selected_id else ""
                print(f"{prefix}└── WEM {media_id}{marker}")
            continue

        print(f"{prefix}└── {node_label(node)}")
        prefix += "    "

        if node.class_name == "CAkSwitchCntr" and index + 1 < len(path):
            next_node = path[index + 1]
            values = node.switch_values.get(next_node.object_id or -1, [])
            for value_id, value_name in values:
                group_type = node.group_type or "Switch/State"
                value = f"{value_name} ({value_id})" if value_name else str(value_id)
                print(f"{prefix}└── {group_type} {value}")
                prefix += "    "

        if node.class_name == "CAkLayerCntr":
            wems = collect_direct_wems(node, by_id, node.bank_hex)
            if wems:
                for wem_index, media_id in enumerate(wems):
                    branch = "└──" if wem_index == len(wems) - 1 else "├──"
                    marker = "  ← selected" if media_id == selected_id else ""
                    print(f"{prefix}{branch} WEM {media_id}{marker}")
                return


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trace a WEM/media ID back to Wwise Event trigger chains."
    )
    parser.add_argument("banks_txt", type=Path, help="Wwiser banks.txt dump")
    parser.add_argument("media_id", type=int, help="WEM/media ID to trace")
    parser.add_argument(
        "--bank",
        help="optional source BNK hexadecimal ID, for duplicate media IDs",
    )
    args = parser.parse_args()
    bank_filter = args.bank.lower() if args.bank else None
    if bank_filter and bank_filter.endswith(".bnk"):
        bank_filter = bank_filter[:-4]

    if not args.banks_txt.exists():
        print(f"[Error] Cannot find banks dump: {args.banks_txt}")
        return 1

    print(f"Parsing {args.banks_txt} ...")
    nodes, bank_names = parse_banks(args.banks_txt)
    sounds, chains = find_chains(nodes, args.media_id, bank_filter)
    print(f"Parsed {len(nodes)} HIRC graph objects across {len(bank_names)} banks.")

    if not sounds:
        suffix = f" in bank {bank_filter}" if bank_filter else ""
        print(f"[Not found] WEM {args.media_id}{suffix}")
        return 2

    source_banks = sorted({sound.bank_hex for sound in sounds})
    print("Source bank(s): " + ", ".join(
        f"{bank} ({bank_names.get(bank, 'unknown')})" for bank in source_banks
    ))

    if not chains:
        print(
            "[No Event path] The WEM exists, but no Event→Action path was found. "
            "It may be triggered from another unloaded bank or game code."
        )
        return 3

    print(f"Found {len(chains)} trigger chain(s).\n")
    for index, (event, action, path, by_id) in enumerate(chains, 1):
        if len(chains) > 1:
            print(f"=== Chain {index}/{len(chains)} ===")
        print_chain(event, action, path, by_id, args.media_id)
        if index != len(chains):
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
