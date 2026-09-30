from app import app, db
from sqlalchemy import text

with app.app_context():
    print("A iniciar a atualização do banco de dados...")
    
    # Desliga temporariamente a verificação de chaves para podermos apagar a tabela
    db.session.execute(text('PRAGMA foreign_keys=OFF;'))
    
    # Apaga APENAS a tabela antiga de turmas que está com a coluna errada
    db.session.execute(text('DROP TABLE IF EXISTS turma;'))
    
    # Volta a ligar as chaves de segurança
    db.session.execute(text('PRAGMA foreign_keys=ON;'))
    
    # Pede ao SQLAlchemy para recriar as tabelas baseando-se no models.py atualizado
    db.create_all()
    
    print("Sucesso! A tabela Turma foi recriada e está pronta para receber as Trilhas.")