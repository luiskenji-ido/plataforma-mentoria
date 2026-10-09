from app import app, db, bcrypt
from models import Usuario
from datetime import datetime

with app.app_context():
    # Recria todas as tabelas no banco novo
    db.create_all()
    
    # Verifica se já existe para não duplicar
    admin = Usuario.query.filter_by(email='admin@mentoria.com').first()
    
    if not admin:
        # Cria a senha criptografada padrão
        senha_hash = bcrypt.generate_password_hash('Admin@2026').decode('utf-8')
        
        novo_admin = Usuario(
            nome='Administrador Principal',
            email='admin@mentoria.com',
            senha=senha_hash,
            tipo_usuario='Administrador',
            status='Ativo',
            forcar_troca_senha=False,  # Desliga a exigência de troca imediata para evitar bloqueio
            data_ultima_troca_senha=datetime.utcnow()
        )
        
        db.session.add(novo_admin)
        db.session.commit()
        print("✅ Administrador recriado com sucesso!")
        print("➡ E-mail: admin@mentoria.com")
        print("➡️ Senha: Admin@2026")
    else:
        print("⚠ O administrador já existe!")