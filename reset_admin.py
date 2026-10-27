from app import app, db, bcrypt
from models import Usuario

with app.app_context():
    # Procura o seu usuário Administrador
    admin = Usuario.query.filter_by(tipo_usuario='Administrador').first()
    
    if admin:
        # Define uma senha temporária
        senha_temporaria = "Admin@123456"
        admin.senha = bcrypt.generate_password_hash(senha_temporaria).decode('utf-8')
        
        # Desbloqueia a conta e zera as falhas (caso o sistema o tenha bloqueado)
        admin.status = 'Ativo'
        admin.tentativas_login = 0
        admin.forcar_troca_senha = True # Vai forçar você a escolher uma nova logo ao entrar
        
        db.session.commit()
        print(f"✅ SUCESSO! Conta desbloqueada.")
        print(f"📧 E-mail do Admin: {admin.email}")
        print(f"🔑 Senha temporária: {senha_temporaria}")
    else:
        print("❌ Nenhum Administrador encontrado no banco de dados.")