import sqlite3
import os

# Mira no seu banco de dados atual
caminho = os.path.join('instance', 'mentoria.db')

# Conecta no banco
conexao = sqlite3.connect(caminho)
cursor = conexao.cursor()

try:
    # Injeta a coluna nova na tabela de usuários
    cursor.execute("ALTER TABLE usuario ADD COLUMN exibir_tour BOOLEAN DEFAULT 1")
    conexao.commit()
    print("Sucesso! A coluna do Tour foi adicionada e seus dados foram salvos.")
except Exception as e:
    print(f"Atenção: {e}")

conexao.close()