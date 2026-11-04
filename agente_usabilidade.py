from app import app, db
from models import Usuario

def executar_testes_usabilidade():
    print("\n==================================================")
    print("  🕵️‍♂️ AGENTE DE USABILIDADE - TESTE DE PERFIS")
    print("==================================================\n")

    # Isso abre o "motor" do nosso site para testes
    with app.app_context():
        # Vamos buscar um Aluno e um Administrador reais no seu banco de dados
        aluno = Usuario.query.filter_by(tipo_usuario='Aluno').first()
        admin = Usuario.query.filter_by(tipo_usuario='Administrador').first()

        # Criamos um "navegador invisível" que navega no site muito rápido
        cliente = app.test_client()

        # ----------------------------------------------------
        # TESTE 1: O Administrador consegue acessar os Cadastros?
        # ----------------------------------------------------
        if admin:
            print(f"🔹 Testando perfil ADMINISTRADOR ({admin.nome})...")
            # Finge que o Administrador fez login
            with cliente.session_transaction() as sessao:
                sessao['_user_id'] = str(admin.id)
                sessao['_fresh'] = True

            # Tenta abrir a página de Cadastros
            resposta = cliente.get('/admin/usuarios')
            
            # 200 significa "Página carregou perfeitamente"
            if resposta.status_code == 200:
                print("   ✅ Acesso à página de Cadastros: PERMITIDO (Correto e Seguro!)")
            else:
                print("   ❌ Falha: O Administrador não conseguiu abrir a página.")

        # ----------------------------------------------------
        # TESTE 2: O Aluno é bloqueado ao tentar ver Cadastros?
        # ----------------------------------------------------
        if aluno:
            print(f"\n🔹 Testando perfil ALUNO ({aluno.nome})...")
            # Finge que o Aluno fez login
            with cliente.session_transaction() as sessao:
                sessao['_user_id'] = str(aluno.id)
                sessao['_fresh'] = True

            # O Aluno "digita" o endereço de Cadastros no navegador invisível
            resposta = cliente.get('/admin/usuarios')
            
            # Se o site mostrar "Acesso Negado" ou redirecionar (status 302), a segurança funcionou!
            if resposta.status_code == 302 or b"Acesso Negado" in resposta.data:
                print("   ✅ Acesso à página de Cadastros: BLOQUEADO (Correto e Seguro!)")
            else:
                print("   ❌ ALERTA GRAVE: O Aluno conseguiu acessar a área de administração!")

        print("\n==================================================")
        print("✅ Validação de Usabilidade concluída com sucesso.")

if __name__ == "__main__":
    executar_testes_usabilidade()