from app import app, db, bcrypt
from models import Usuario

with app.app_context():
    # Garante que as tabelas estão criadas
    db.create_all()
    
    # Verifica se já existe um admin para não duplicar
    if not Usuario.query.filter_by(email='admin@admin.com').first():
        # Cria uma senha forte que passa na sua regra de segurança
        senha_criptografada = bcrypt.generate_password_hash('Mentoria@2026').decode('utf-8')
        
        admin = Usuario(
            nome='Luis Admin',
            email='admin@admin.com',
            senha=senha_criptografada,
            tipo_usuario='Administrador',
            forcar_troca_senha=False
        )
        
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuário criado com sucesso!")
        print("📧 E-mail: admin@admin.com")
        print("🔑 Senha: Mentoria@2026")
    else:
        print("⚠️ O usuário já existe no banco de dados.")