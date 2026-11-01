import os
import time
from google import genai
from google.genai.errors import APIError

def executar_agente_qa():
    print("🔄 [1/4] A carregar diretrizes de QA e regras do sistema B2B...")
    
    base_conhecimento = """
    REGRAS DE NEGÓCIO DA PLATAFORMA B2B:
    - Regra 1 (Isolamento de Alunos): Alunos só devem visualizar projetos vinculados ao seu próprio grupo. O acesso a projetos de outros alunos/grupos deve ser restrito.
    - Regra 2 (Segurança de Perfil): Alunos não têm permissão de acesso ao Portal de Demandas (Tickets) nem ao Relógio de Voluntariado Corporativo.
    - Regra 3 (Edição de Datas): Alterações de datas e cronogramas nos acompanhamentos de estudo devem proteger contra prazos retroativos inválidos.
    - Regra 4 (Banca de Avaliação): O cálculo da nota final do TCC deve seguir estritamente os pesos definidos (Ex: Escrita 40%, Apresentação 40%, Visual 20%).
    """

    skill_instrucoes = """
    ### Skill: Agente Avançado de QA B2B
    Atue como um Engenheiro de Qualidade Sênior. Analise os cenários de teste simulados abaixo, compare-os com as regras de negócio e aponte falhas de segurança, erros de isolamento de dados ou melhorias necessárias.
    Gere a resposta obrigatoriamente estruturada com:
    - 🟢 **Homologado / Aprovado**: Funcionalidades que passaram nos testes.
    - 🔴 **Falhas Encontradas**: Desvios de regra (ex: aluno vendo projetos de terceiros, erro ao alterar datas).
    - 💡 **Recomendações de Correção**: Como ajustar o código Flask/SQLAlchemy.
    """

    cenarios_teste = """
    CENÁRIOS EXECUTADOS NESTA RODADA:
    - Cenário A (Perfil Aluno - Projetos): Um usuário logado como 'Aluno' acedeu à rota de projetos (/projetos) e conseguiu listar todos os projetos cadastrados no sistema, independentemente de pertencerem ao seu grupo.
    - Cenário B (Perfil Aluno - Datas): Um aluno tentou atualizar a data de término de um curso no acompanhamento e encontrou dificuldades de submissão devido a restrições de validação do formulário.
    - Cenário C (Segurança de Gestão): Usuários com perfil 'Administrador' testaram com sucesso a abertura de tickets no Portal de Demandas e o registro manual de horas de voluntariado.
    """

    prompt_completo = f"""
    {skill_instrucoes}
    
    ---
    {base_conhecimento}
    
    ---
    {cenarios_teste}
    
    Com base nas informações acima, elabore o relatório técnico detalhado de QA.
    """

    client = genai.Client()
    max_tentativas = 3
    
    for tentativa in range(1, max_tentativas + 1):
        try:
            print(f"🤖 [2/4] A contactar a API do Gemini (Tentativa {tentativa}/{max_tentativas})...")
            
            # Utiliza o modelo correto indicado pelo Google
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt_completo,
            )

            print("\n==================================================")
            print("    RELATÓRIO DE HOMOLOGAÇÃO DO AGENTE QA B2B     ")
            print("==================================================\n")
            print(response.text)
            print("\n==================================================")
            print("✅ [4/4] Ciclo de testes concluído com sucesso.")
            break # Sucesso, sai do ciclo de tentativas
            
        except Exception as e:
            print(f"⚠️ Aviso na tentativa {tentativa}: {e}")
            if tentativa < max_tentativas:
                print("⏳ Servidor ocupado (Alta demanda). A aguardar 5 segundos para tentar novamente...")
                time.sleep(5)
            else:
                print("\n❌ Todas as tentativas falharam devido à alta demanda temporária nos servidores. Tente novamente em instantes.")

if __name__ == "__main__":
    executar_agente_qa()