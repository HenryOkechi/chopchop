import os
import datetime
from google.cloud import firestore

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
_db = None

def db():
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT)
    return _db


def save_prices(records: list, source_type: str, source_note: str) -> dict:
    """Saves extracted price records to Firestore.

    Args:
        records: list of price record dicts from extraction.
        source_type: one of photo, whatsapp, voice, direct_ask.
        source_note: short description of where this came from.

    Returns:
        dict with status, count saved, and any containers needing resolution.
    """
    today = datetime.date.today().isoformat()
    batch = db().batch()
    unresolved = []

    for r in records:
        r["source_type"] = source_type
        r["source_note"] = source_note
        r["observed_date"] = today
        key = f"{today}_{r.get('item')}_{r.get('grade') or 'base'}"
        batch.set(db().collection("prices").document(key), r)

        c = r.get("container")
        if c:
            cid = f"{c}_{r.get('item')}".replace(" ", "_")
            if not db().collection("containers").document(cid).get().exists:
                unresolved.append({"container": c, "commodity": r.get("item")})

    batch.commit()
    return {
        "status": "ok",
        "saved": len(records),
        "observed_date": today,
        "unresolved_containers": unresolved,
    }


def lookup_container(container: str, commodity: str) -> dict:
    """Checks Firestore for a known capacity mapping for a container.

    Args:
        container: container name, e.g. custard bucket.
        commodity: what it holds, e.g. rice.

    Returns:
        dict with status found or not_found, and the mapping if found.
    """
    cid = f"{container}_{commodity}".replace(" ", "_")
    doc = db().collection("containers").document(cid).get()
    if doc.exists:
        return {"status": "found", "mapping": doc.to_dict()}
    return {"status": "not_found", "container": container, "commodity": commodity}


def save_container(
    container: str,
    commodity: str,
    weight_kg: float,
    confidence: float,
    conflicting_values: list,
    resolution_note: str,
) -> dict:
    """Saves a researched container capacity mapping to Firestore.

    Args:
        container: container name.
        commodity: what it holds.
        weight_kg: resolved weight in kilograms.
        confidence: 0.0 to 1.0.
        conflicting_values: the differing values found across sources.
        resolution_note: how the conflict was resolved.

    Returns:
        dict with status and the saved mapping.
    """
    cid = f"{container}_{commodity}".replace(" ", "_")
    mapping = {
        "container": container,
        "commodity": commodity,
        "weight_kg": weight_kg,
        "confidence": confidence,
        "conflicting_values": conflicting_values,
        "resolution_note": resolution_note,
        "resolved_at": datetime.date.today().isoformat(),
    }
    db().collection("containers").document(cid).set(mapping)
    return {"status": "saved", "mapping": mapping}
