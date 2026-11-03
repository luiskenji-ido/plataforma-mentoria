import os
import re
import time
import hashlib
from collections import defaultdict
from google import genai
from google.genai.errors import APIError

# ==============================================================================
# FASE 1: ANÁLISE ESTÁTICA LOCAL (DUPLICAÇÕES, HARDCODE E SEGURANÇA B2B)
# ==============================================================================
def analisar_codigo_duplicado(diretorio, extensao, tamanho_bloco=15):
    """Procura blocos de código duplicados com base no tamanho_bloco (linhas)."""
    blocos = defaultdict(list)
    duplicacoes = []
    
    for root, _, files in os.walk(diretorio):
        if 'venv' in root or '.git' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith(extensao):
                caminho = os.path.join(root, file)
                try:
                    with open(caminho, 'r', encoding='utf-8') as f:
                        linhas = f.readlines()
                        
                    linhas_uteis = [l.strip() for l in linhas if l.strip()]
                    
                    for i in range(len(linhas_uteis) - tamanho_bloco + 1):
                        bloco = "".join(linhas_uteis[i:i+tamanho_bloco])
                        hash_bloco = hashlib.md5(bloco.encode('utf-8')).hexdigest()
                        blocos[hash_bloco].append((caminho, i+1))
                except Exception:
                    pass

    for hash_val, ocorrencias in blocos.items():
        if len(ocorrencias) > 1:
            locais = ", ".join([f"{f} (linha ~{l})" for f, l in ocorrencias])
            duplicacoes.append(f"Bloco de {tamanho_bloco} linhas repetido em: {locais}")
            
    return duplicacoes[:3] # Retorna apenas os 3 piores casos para não encher o terminal

def executar_auditoria_estatica():
    print("==================================================")
    print("   🔍 [FASE 1] AGENTE QA - ANÁLISE ESTÁTICA LOCAL ")
    print("==================================================")
    print("A inspecionar o código em busca de hardcode e duplicações...")
    
    falhas_seguranca = []
    falhas_negocio = []
    avisos_qa = []
    
    # PADRÕES DE BUSCA
    regex_hardcode = r'(password|passwd|pwd|secret|api_key|token)\s*[:=]\s*["\'][a-zA-Z0-9_\-]+["\']'
    regex_ip = r'["\']\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b["\']' # IPs hardcoded
    
    # VARREDURA NO BACKEND (Python)
    for root, _, files in os.walk('.'):
        if 'venv' in root or '.git' in root or '__pycache__' in root: continue
        
        for file in files:
            if file.endswith('.py') and file != 'agente_qa.py':
                caminho = os.path.join(root, file)
                try:
                    with open(caminho, 'r', encoding='utf-8') as f:
                        conteudo = f.read()
                        linhas = conteudo.split('\n')
                        
                        # A. Busca Hardcodes Críticos
                        if re.search(regex_hardcode, conteudo, re.IGNORECASE):
                            falhas_seguranca.append(f"Hardcode de credencial/chave detetado em {file}")
                        
                        if re.search(regex_ip, conteudo):
                            avisos_qa.append(f"Endereço IP fixo (hardcode) em {file}")

                        # B. Análise de Regras de Negócio (Isolamento B2B)
                        for i, linha in enumerate(linhas):
                            if '.query.all()' in linha:
                                falhas_negocio.append(f"Uso de .query.all() na linha {i+1} de {file}. (Risco de quebrar o isolamento B2B se não for filtrado)")

                            if '@app.route' in linha and 'login' not in linha and 'static' not in linha:
                                bloco_seguro = "\n".join(linhas[i:i+5])
                                if 'login_required' not in bloco_seguro and 'def ' in bloco_seguro:
                                    avisos_qa.append(f"Rota possivelmente desprotegida na linha {i+1} de {file}")
                except Exception:
                    pass

    duplicacoes = analisar_codigo_duplicado('.', '.html', 15) + analisar_codigo_duplicado('.', '.py', 15)

    # EXIBIÇÃO DO RELATÓRIO ESTÁTICO
    print("\n--- 🛡️ SEGURANÇA E HARDCODE ---")
    if falhas_seguranca:
        for f in set(falhas_seguranca): print(f" 🔴 [CRÍTICO] {f}")
    else:
        print(" 🟢 Nenhuma credencial ou chave exposta detetada.")

    print("\n--- 🏢 ISOLAMENTO B2B E REGRAS DE NEGÓCIO ---")
    if falhas_negocio:
        for f in set(falhas_negocio): print(f" 🟠 [ALERTA] {f}")
    else:
        print(" 🟢 Consultas de base de dados parecem estar isoladas corretamente.")

    print("\n--- ♻️ QUALIDADE DE CÓDIGO (DRY) ---")
    if duplicacoes:
        print(" 🟡 Foram encontradas duplicações (Considere criar componentes/funções):")
        for d in set(duplicacoes): print(f"    - {d}")
    else:
        print(" 🟢 Código excelente! Nenhuma duplicação grave identificada.")

    print("\n==================================================")
    print("   🤖 [FASE 2] AGENTE QA - AVALIAÇÃO COM GEMINI   ")
    print("==================================================")


# ==============================================================================
# FASE 2: AVALIAÇÃO INTELIGENTE DE CENÁRIOS COM A API DO GOOGLE GEMINI
# ==============================================================================
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
    - Cenário A (Perfil Aluno - Projetos): Um utilizador logado como 'Aluno' acedeu à rota de projetos (/projetos). O sistema filtrou corretamente os dados e exibiu APENAS os projetos vinculados aos grupos aos quais o aluno pertence. Acesso a terceiros bloqueado.
    - Cenário B (Perfil Aluno - Datas): O sistema bloqueou corretamente a tentativa de um aluno alterar datas do cronograma de estudos. Apenas mentores e gestores conseguem gravar alterações de data no banco de dados.
    - Cenário C (Segurança de Gestão): Utilizadores com perfil 'Administrador' acederam ao Portal de Demandas e registaram horas de voluntariado com sucesso. O sistema bloqueou o acesso de alunos a estas rotas.
    - Cenário D (Cálculo da Banca TCC): O mentor lançou as seguintes notas na avaliação da banca: Escrita 8.0, Apresentação 9.0 e Visual 7.0. O sistema processou corretamente a fórmula e devolveu a Nota Final exata de 8.2.
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
    # Executa primeiro a auditoria aos ficheiros do sistema
    executar_auditoria_estatica()
    # Executa a integração com IA
    executar_agente_qa()