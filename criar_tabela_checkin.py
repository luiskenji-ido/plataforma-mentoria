from app import app, db

with app.app_context():
    try:
        # O SQLAlchemy identifica as tabelas novas no models.py e cria apenas elas
        db.create_all()
        print("✅ Tabela 'checkin_aula' criada com sucesso no banco de dados!")
    except Exception as e:
        print("⚠️ Erro ao tentar criar a tabela:", e)