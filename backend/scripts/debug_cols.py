from app.models.review import Review
with open("columns.txt", "w") as f:
    for c in Review.__table__.columns:
        f.write(c.name + "\n")
