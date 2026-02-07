"""
Attach a demo artifact (e.g., screenshot text) to the latest incident.
"""
from app.database import SessionLocal
from app.tools.models import Object, ObjectArtifact, Incident

if __name__ == '__main__':
    db = SessionLocal()
    inc = db.query(Incident).order_by(Incident.created_at.desc()).first()
    if not inc:
        print("No incident found. Run supervision/seed first.")
    else:
        obj = Object(tenant_id='internal', uploaded_by='demo', filename='screenshot.png', storage_path='docs/sample.png')
        db.add(obj)
        db.commit()
        db.refresh(obj)
        art = ObjectArtifact(object_id=obj.id, artifact_type='ocr', text='Detected error: connection refused', created_by='demo')
        db.add(art)
        db.commit()
        db.refresh(art)
        # attach to incident evidence
        ev = inc.evidence or []
        ev = ev if isinstance(ev, list) else [ev]
        ev.append({"object_id": obj.id, "artifact_id": art.id, "snippet": art.text})
        inc.evidence = ev
        db.commit()
        print(f"Attached object {obj.id} and artifact {art.id} to incident {inc.id}")
    db.close()
