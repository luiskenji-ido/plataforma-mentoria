from app import app
from models import db, Tarefa

with app.app_context():
    # Apaga apenas a tabela de tarefas para receber a nova estrutura
    Tarefa.__table__.drop(db.engine, checkfirst=True)
    db.create_all()
    print("Sucesso! Tabela de Tarefas recriada com suporte a Subtarefas e Equipe!")