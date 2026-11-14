"""
AGENTE OMNITEST — PERFIL MENTOR
Uso: python agentes_omnitest/agente_mentor.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Mentor. Para rodar todos os perfis use executar_todos.py.
No app.py o Mentor tem as mesmas permissões do Professor, por isso herda o mesmo roteiro.
"""
from nucleo import executar_cli
from agente_professor import AgenteProfessor


class AgenteMentor(AgenteProfessor):
    chave_perfil = "mentor"


if __name__ == "__main__":
    executar_cli(AgenteMentor)
