from sqlalchemy.orm import Session
from backend.models import LocationNode, GroupChat
from typing import List, Set, Optional

def get_location_ancestors(db: Session, location_id: int) -> List[int]:
    """
    Returns list of ancestor location IDs from nearest parent to root.
    E.g. Building -> Street -> Neighborhood -> City -> Country
    """
    ancestors = []
    current_id = location_id
    while current_id:
        node = db.query(LocationNode).filter(LocationNode.id == current_id).first()
        if not node or not node.parent_id:
            break
        ancestors.append(node.parent_id)
        current_id = node.parent_id
    return ancestors

def get_location_descendants(db: Session, location_id: int) -> Set[int]:
    # ponytail: simplified BFS queue traversal into recursive set union
    descendants = {c.id for c in db.query(LocationNode).filter(LocationNode.parent_id == location_id).all()}
    return descendants.union(*(get_location_descendants(db, d_id) for d_id in list(descendants)))


def is_descendant_of(db: Session, child_id: int, parent_id: int) -> bool:
    """
    Checks if a node is a descendant of another node.
    """
    if not child_id or not parent_id:
        return False
    if child_id == parent_id:
        return True
    ancestors = get_location_ancestors(db, child_id)
    return parent_id in ancestors

def auto_create_node_path(db: Session, path: List[str]) -> Optional[LocationNode]:
    """
    Auto-creates location tree nodes if missing.
    path: List of names in hierarchy order: [Country, City, Neighborhood, Street, Building]
    """
    levels = ["COUNTRY", "CITY", "NEIGHBORHOOD", "STREET", "BUILDING"]
    if not path or len(path) > len(levels):
        return None

    parent_id = None
    last_node = None

    for idx, name in enumerate(path):
        level = levels[idx]
        # Clean up whitespace
        name = name.strip()
        if not name:
            continue
        
        # Check if node already exists at this level with this parent
        node = db.query(LocationNode).filter(
            LocationNode.name == name,
            LocationNode.level == level,
            LocationNode.parent_id == parent_id
        ).first()

        if not node:
            print(f"Auto-creating node: {name} ({level}) under parent_id {parent_id}")
            node = LocationNode(name=name, level=level, parent_id=parent_id)
            db.add(node)
            db.commit()
            db.refresh(node)

            # Auto-create mock groups for the newly created node
            gtype = "PRIVATE" if level == "BUILDING" else "PUBLIC"
            # TG mock
            tg_chat_id = f"tg_chat_{name.lower().replace(' ', '_')}"
            tg_group = GroupChat(
                location_id=node.id,
                platform="TELEGRAM",
                chat_id=tg_chat_id,
                type=gtype,
                invite_link=f"https://t.me/joinchat/{tg_chat_id}"
            )
            db.add(tg_group)

            # WA mock
            wa_chat_id = f"wa_chat_{name.lower().replace(' ', '_')}"
            wa_group = GroupChat(
                location_id=node.id,
                platform="WHATSAPP",
                chat_id=wa_chat_id,
                type=gtype,
                invite_link=f"https://chat.whatsapp.com/{wa_chat_id}"
            )
            db.add(wa_group)
            db.commit()

        parent_id = node.id
        last_node = node

    return last_node
