from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE empresa ADD COLUMN gestor_id INTEGER"))
        db.session.commit()
        print("✅ Coluna 'gestor_id' adicionada com sucesso na tabela empresa!")
    except Exception as e:
        print("⚠️ Erro (talvez a coluna já exista):", e)