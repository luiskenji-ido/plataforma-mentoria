# -*- coding: utf-8 -*-
"""
Traduções das telas antigas (Projetos, Diário, Hub, Grupos, Cadastros, Demandas, Painel, Acompanhamento...).

A chave é o próprio texto em português que aparece no template, usado com {{ tt('Texto') }}.
Assim o template continua legível em português e o texto some do dicionário só quando some da tela.
Formato: 'texto em pt': ('english', 'español')
"""

LITERAIS = {
    # ---------------- Comuns
    'Ações': ('Actions', 'Acciones'), 'Ação': ('Action', 'Acción'), 'Editar': ('Edit', 'Editar'), 'Excluir': ('Delete', 'Eliminar'),
    'Cancelar': ('Cancel', 'Cancelar'), 'Salvar Alterações': ('Save changes', 'Guardar cambios'), 'Filtrar': ('Filter', 'Filtrar'),
    'Limpar': ('Clear', 'Limpiar'), 'Todos': ('All', 'Todos'), 'Sim': ('Yes', 'Sí'), 'Não': ('No', 'No'), 'Data': ('Date', 'Fecha'),
    'Tipo': ('Type', 'Tipo'), 'Status': ('Status', 'Estado'), 'Categoria': ('Category', 'Categoría'), 'Descrição': ('Description', 'Descripción'),
    'Empresa': ('Company', 'Empresa'), 'Período': ('Period', 'Período'), 'Tempo': ('Time', 'Tiempo'), 'Outros': ('Other', 'Otros'),
    'Selecione...': ('Select...', 'Seleccione...'), 'Ativo': ('Active', 'Activo'), 'Inativo': ('Inactive', 'Inactivo'),
    'Pendente': ('Pending', 'Pendiente'), 'Em Andamento': ('In progress', 'En curso'), 'Andamento': ('Progress', 'Avance'),
    'Concluído': ('Completed', 'Concluido'), 'Concluídos': ('Completed', 'Concluidos'), 'Aberta': ('Open', 'Abierta'),
    'Cancelada': ('Cancelled', 'Cancelada'), 'Em Análise': ('Under review', 'En análisis'), 'Concluída (Resolvido)': ('Closed (resolved)', 'Concluida (resuelta)'),
    'Online': ('Online', 'En línea'), 'Presencial': ('In person', 'Presencial'), 'Modalidade': ('Mode', 'Modalidad'),
    'Aluno': ('Student', 'Alumno'), 'Alunos': ('Students', 'Alumnos'), 'Mentor': ('Mentor', 'Mentor'), 'Professor': ('Teacher', 'Profesor'),
    'Administrador': ('Administrator', 'Administrador'), 'Mentor Administrador': ('Mentor Administrator', 'Mentor Administrador'),
    'Autor': ('Author', 'Autor'), 'Início': ('Start', 'Inicio'), 'Término': ('End', 'Fin'), 'E-mail': ('Email', 'Correo electrónico'),
    'Hub Educacional': ('Learning Hub', 'Hub Educativo'), 'Sala da Banca': ('Panel Room', 'Sala del Tribunal'),
    'Certificado': ('Certificate', 'Certificado'), 'Plataforma': ('Platform', 'Plataforma'), 'Desativado': ('Disabled', 'Desactivado'),
    'Bloqueado': ('Blocked', 'Bloqueado'), 'Validado': ('Validated', 'Validado'), 'Falta': ('Absence', 'Falta'),
    'Falta Justificada': ('Excused absence', 'Falta justificada'), 'Relatórios': ('Reports', 'Informes'), 'Turma:': ('Class:', 'Grupo:'),
    'Postura': ('Attitude', 'Actitud'), 'Prioridade': ('Priority', 'Prioridad'), 'Alta': ('High', 'Alta'), 'Urgente': ('Urgent', 'Urgente'),
    'Nome Completo': ('Full name', 'Nombre completo'), 'Selecione um grupo...': ('Select a group...', 'Seleccione un grupo...'),
    'Feedback individual...': ('Individual feedback...', 'Comentario individual...'),
    'Nenhum arquivo selecionado': ('No file selected', 'Ningún archivo seleccionado'),
    'Ex: 8.5': ('E.g. 8.5', 'Ej.: 8.5'), 'Ex: 9.0': ('E.g. 9.0', 'Ej.: 9.0'), '0 a 10': ('0 to 10', '0 a 10'),

    # ---------------- Fragmentos de textos com variáveis
    'Apoio:': ('Support:', 'Apoyo:'), 'Atualizar:': ('Update:', 'Actualizar:'), 'Avaliação do Projeto:': ('Project evaluation:', 'Evaluación del proyecto:'),
    'Concluído:': ('Completed:', 'Concluido:'), 'Grupo:': ('Group:', 'Grupo:'), '| Criado em:': ('| Created on:', '| Creado el:'),
    'Nova Tarefa -': ('New task -', 'Nueva tarea -'), 'Projeto:': ('Project:', 'Proyecto:'), 'às': ('at', 'a las'),
    '(Data:': ('(Date:', '(Fecha:'), 'Manter estado atual (': ('Keep current status (', 'Mantener estado actual ('),
    'registo(s) encontrado(s)': ('record(s) found', 'registro(s) encontrado(s)'), 'Alunos matriculados em:': ('Students enrolled in:', 'Alumnos matriculados en:'),
    'Editar Grupo:': ('Edit group:', 'Editar grupo:'), '% de afinidade': ('% match', '% de afinidad'), 'Áreas em comum:': ('Shared areas:', 'Áreas en común:'),
    'Última troca:': ('Last change:', 'Último cambio:'), 'Atualizado em:': ('Updated on:', 'Actualizado el:'), 'Criado em:': ('Created on:', 'Creado el:'),
    'Prioridade:': ('Priority:', 'Prioridad:'), 'Olá,': ('Hello,', 'Hola,'), 'dias': ('days', 'días'), 'horas': ('hours', 'horas'),
    'Atualizado:': ('Updated:', 'Actualizado:'), 'Validação do Mentor (': ('Mentor validation (', 'Validación del mentor ('), '(Aluno)': ('(Student)', '(Alumno)'),
    '📄 Acessar Materiais (': ('📄 Open materials (', '📄 Abrir materiales ('),

    # ---------------- Projetos
    'Gestão de Projetos': ('Project Management', 'Gestión de Proyectos'), 'PROJETOS (TCC)': ('PROJECTS (FINAL PAPER)', 'PROYECTOS (TCC)'),
    'Projetos em Andamento': ('Projects in progress', 'Proyectos en curso'), 'Mostrar Todos os Projetos': ('Show all projects', 'Mostrar todos los proyectos'),
    'Cadastrar Novo Projeto': ('Register new project', 'Registrar nuevo proyecto'), 'Nome do Projeto': ('Project name', 'Nombre del proyecto'),
    'Descreva brevemente o objetivo deste projeto...': ('Briefly describe the goal of this project...', 'Describa brevemente el objetivo de este proyecto...'),
    'Descrição / Objetivo': ('Description / Goal', 'Descripción / Objetivo'), 'Grupo Responsável (Alunos e Mentores)': ('Responsible group (students and mentors)', 'Grupo responsable (alumnos y mentores)'),
    'Selecione um grupo para este projeto...': ('Select a group for this project...', 'Seleccione un grupo para este proyecto...'),
    'Este projeto não tem um grupo vinculado.': ('This project has no linked group.', 'Este proyecto no tiene un grupo vinculado.'),
    'Excluir Projeto': ('Delete project', 'Eliminar proyecto'), 'Excluir Projeto Inteiro': ('Delete entire project', 'Eliminar todo el proyecto'),
    '+ Criar Nova Tarefa': ('+ Create new task', '+ Crear nueva tarea'), 'Nenhuma tarefa cadastrada para este projeto.': ('No tasks registered for this project.', 'No hay tareas registradas para este proyecto.'),
    'Descrição / Atividade': ('Description / Activity', 'Descripción / Actividad'), 'Descrição da Atividade': ('Activity description', 'Descripción de la actividad'),
    'Responsáveis': ('Owners', 'Responsables'), 'Data Início': ('Start date', 'Fecha de inicio'), 'Data Fim': ('End date', 'Fecha de fin'),
    'Data Conclusão': ('Completion date', 'Fecha de conclusión'), '% Conclusão': ('% Complete', '% Conclusión'),
    'Calculado automaticamente pela média das subtarefas': ('Calculated automatically from the subtasks average', 'Calculado automáticamente por el promedio de las subtareas'),
    'Status da Tarefa': ('Task status', 'Estado de la tarea'), 'Status Inicial': ('Initial status', 'Estado inicial'),
    'É uma subtarefa de?': ('Is it a subtask of?', '¿Es una subtarea de?'), 'Não (É Tarefa Principal)': ('No (main task)', 'No (tarea principal)'),
    'Líder (Responsável)': ('Lead (owner)', 'Líder (responsable)'), 'Equipe de Apoio (Opcional)': ('Support team (optional)', 'Equipo de apoyo (opcional)'),
    'Marque as caixas para adicionar colegas ao apoio.': ('Tick the boxes to add teammates as support.', 'Marque las casillas para añadir compañeros como apoyo.'),
    'Ex: Pesquisar materiais e requisitos': ('E.g. Research materials and requirements', 'Ej.: Investigar materiales y requisitos'),
    'Salvar Tarefa': ('Save task', 'Guardar tarea'), 'Salvar e Voltar': ('Save and go back', 'Guardar y volver'), '+ Criar': ('+ Create', '+ Crear'),
    'Materiais de Apoio (Anexos da Tarefa)': ('Support materials (task attachments)', 'Materiales de apoyo (anexos de la tarea)'),
    'Anexos': ('Attachments', 'Anexos'), 'Gerenciar Anexos': ('Manage attachments', 'Gestionar anexos'),
    'Anexar Novos Arquivos (Upload Múltiplo)': ('Attach new files (multiple upload)', 'Adjuntar nuevos archivos (carga múltiple)'),
    '+ Escolher Arquivos': ('+ Choose files', '+ Elegir archivos'), 'Para enviar, selecione os arquivos e clique no botão': ('To upload, select the files and click the button', 'Para enviar, seleccione los archivos y haga clic en el botón'),
    '"Anexar"': ('"Attach"', '"Adjuntar"'), 'azul ao lado.': ('in blue next to it.', 'azul al lado.'),
    'Nenhum arquivo anexado a esta tarefa no momento.': ('No files attached to this task yet.', 'No hay archivos adjuntos a esta tarea por ahora.'),
    'Clique em "Abrir" para visualizar ou selecione as caixas laterais para excluir (conforme sua permissão de perfil).': (
        'Click "Open" to view, or tick the side boxes to delete (according to your profile permissions).',
        'Haga clic en "Abrir" para ver o marque las casillas laterales para eliminar (según los permisos de su perfil).'),
    'Marcar p/ Excluir': ('Mark to delete', 'Marcar para eliminar'), 'Apenas mentores podem apagar este arquivo': ('Only mentors can delete this file', 'Solo los mentores pueden eliminar este archivo'),
    'Sem permissão para excluir material do Mentor': ("You can't delete the mentor's material", 'Sin permiso para eliminar material del mentor'),
    'Apenas professores podem mudar': ('Only teachers can change this', 'Solo los profesores pueden cambiarlo'),
    'Avaliar TCC': ('Evaluate final paper', 'Evaluar TCC'), 'Acessar a Sala da Banca': ('Open the Panel Room', 'Entrar a la Sala del Tribunal'),
    'Salvar Avaliação do TCC': ('Save final paper evaluation', 'Guardar evaluación del TCC'),
    'Nota de Conteúdo (0 a 10)': ('Content grade (0 to 10)', 'Nota de contenido (0 a 10)'), 'Nota de Apresentação (0 a 10)': ('Presentation grade (0 to 10)', 'Nota de presentación (0 a 10)'),
    'Nota de Postura (0 a 10)': ('Attitude grade (0 to 10)', 'Nota de actitud (0 a 10)'), 'Nota Técnica (0 a 10)': ('Technical grade (0 to 10)', 'Nota técnica (0 a 10)'),
    'Qualidade técnica e pesquisa': ('Technical quality and research', 'Calidad técnica e investigación'),
    'Organização, clareza e design': ('Organisation, clarity and design', 'Organización, claridad y diseño'),
    'Observações (Feedback)': ('Notes (feedback)', 'Observaciones (comentarios)'), 'Salvar Parecer': ('Save assessment', 'Guardar dictamen'),
    'Sincronizar na Agenda': ('Sync to calendar', 'Sincronizar en la agenda'), 'Sincronização Automática Ativa': ('Automatic sync on', 'Sincronización automática activa'),
    'Os prazos que você salvar serão enviados automaticamente para o Google Agenda.': ('The deadlines you save are sent automatically to Google Calendar.', 'Los plazos que guarde se enviarán automáticamente a Google Calendar.'),
    'Forçar o envio destes horários para o Google': ('Force sending these times to Google', 'Forzar el envío de estos horarios a Google'),
    'Tela Cheia / Restaurar': ('Full screen / Restore', 'Pantalla completa / Restaurar'), 'Tarefas concluídas:': ('Tasks completed:', 'Tareas concluidas:'),
    'Tempo total investido pela equipa:': ('Total time invested by the team:', 'Tiempo total invertido por el equipo:'),
    'Horários Guardados:': ('Saved times:', 'Horarios guardados:'), 'Nenhum horário registado na plataforma.': ('No times recorded on the platform.', 'No hay horarios registrados en la plataforma.'),
    'O sistema criou um slot para cada dia. Preencha a hora inicial e final': ('The system created a slot for each day. Fill in the start and end time', 'El sistema creó un espacio para cada día. Complete la hora de inicio y de fin'),
    'apenas': ('only', 'solo'), 'os dias que for trabalhar. Apenas a agenda do Líder Responsável será sincronizada.': (
        'for the days you will work. Only the lead owner\'s calendar is synced.', 'en los días que vaya a trabajar. Solo se sincronizará la agenda del líder responsable.'),
    'apenas nos dias que for estudar': ('only on the days you will study', 'solo en los días que vaya a estudiar'),
    'Gravar Planeamento': ('Save plan', 'Guardar planificación'), 'Hora de Início': ('Start time', 'Hora de inicio'), 'Hora de Fim': ('End time', 'Hora de fin'),

    # ---------------- Painel Geral (dashboard)
    'Relógio de Voluntariado Corporativo': ('Corporate Volunteering Clock', 'Reloj de Voluntariado Corporativo'),
    'Iniciar Contagem': ('Start timer', 'Iniciar conteo'), 'Encerrar Voluntariado': ('Stop volunteering', 'Finalizar voluntariado'),
    'Clique para parar o relógio': ('Click to stop the clock', 'Haga clic para detener el reloj'), 'Tempo a contar...': ('Timer running...', 'Contando tiempo...'),
    'Qual foi a atividade?': ('What was the activity?', '¿Cuál fue la actividad?'), 'Inserir Manual': ('Manual entry', 'Registro manual'),
    'Inserir horas de uma atividade que já passou': ('Enter hours for a past activity', 'Registrar horas de una actividad pasada'),
    'Lançamento Manual de Horas': ('Manual hours entry', 'Registro manual de horas'), 'Gravar Horas Manuais': ('Save manual hours', 'Guardar horas manuales'),
    'Data da Atividade': ('Activity date', 'Fecha de la actividad'), 'Use esta opção': ('Use this option', 'Use esta opción'),
    'se realizou uma ajuda extra fora da plataforma e esqueceu de ligar o cronômetro oficial.': (
        'if you helped outside the platform and forgot to start the official timer.', 'si brindó una ayuda extra fuera de la plataforma y olvidó encender el cronómetro oficial.'),
    'Alerta de Segurança:': ('Security alert:', 'Alerta de seguridad:'), 'Sua senha expira em': ('Your password expires in', 'Su contraseña vence en'),
    'Presença Registrada Hoje!': ('Attendance recorded today!', '¡Asistencia registrada hoy!'), 'Marcar Presença e Iniciar': ('Mark attendance and start', 'Marcar asistencia y empezar'),
    'Preencha': ('Fill in', 'Complete'), 'Acessar o curso': ('Open the course', 'Acceder al curso'), 'Ver Certificado': ('View certificate', 'Ver certificado'),
    'Notamos que este é o seu primeiro acesso. Que tal um tour rápido para conhecer as principais ferramentas do seu perfil de': (
        'This is your first visit. How about a quick tour of the main tools for your profile as', 'Notamos que es su primer acceso. ¿Qué tal un recorrido rápido por las principales herramientas de su perfil de'),
    'Sessões Realizadas:': ('Sessions held:', 'Sesiones realizadas:'), 'Tempo de Estudo (Agenda):': ('Study time (calendar):', 'Tiempo de estudio (agenda):'),
    'Projetos': ('Projects', 'Proyectos'),
    'Ainda não há dados para este gráfico. Ele aparece quando houver cursos matriculados.': (
        'No data for this chart yet. It shows up once there are enrolled courses.',
        'Aún no hay datos para este gráfico. Aparece cuando haya cursos matriculados.'),

    # ---------------- Acompanhamento
    'Validação (Mentor)': ('Validation (mentor)', 'Validación (mentor)'), 'Status de Validação': ('Validation status', 'Estado de validación'),
    'Escreva suas anotações...': ('Write your notes...', 'Escriba sus notas...'), 'Anotações do Utilizador': ('User notes', 'Notas del usuario'),
    'Desconectar': ('Disconnect', 'Desconectar'), 'Desconectar do Google': ('Disconnect from Google', 'Desconectar de Google'),
    'Travado (Automático)': ('Locked (automatic)', 'Bloqueado (automático)'), 'Curso Desativado (Apenas Leitura)': ('Course disabled (read only)', 'Curso desactivado (solo lectura)'),
    'Este curso exige Certificado para 100%': ('This course requires a certificate for 100%', 'Este curso exige certificado para el 100%'),
    'Avaliação do Mentor (Boletim Final)': ('Mentor evaluation (final report)', 'Evaluación del mentor (boletín final)'),
    'Hard Skill': ('Hard skill', 'Habilidad técnica'), 'Soft Skill': ('Soft skill', 'Habilidad blanda'),

    # ---------------- Diário › Frequência
    'Gestão de Frequência': ('Attendance Management', 'Gestión de Asistencia'), 'Relatório de Acessos e Frequência': ('Access and attendance report', 'Informe de accesos y asistencia'),
    'Gestão de Presença': ('Attendance', 'Gestión de asistencia'), 'Data Inicial': ('Start date', 'Fecha inicial'), 'Data Final': ('End date', 'Fecha final'),
    'Filtrar por Aluno': ('Filter by student', 'Filtrar por alumno'), 'Todos os Alunos': ('All students', 'Todos los alumnos'),
    'Data e Hora': ('Date and time', 'Fecha y hora'), 'Utilizador (Nome e E-mail)': ('User (name and email)', 'Usuario (nombre y correo)'),
    'Status de Presença': ('Attendance status', 'Estado de asistencia'), 'Gerir Falta/Presença': ('Manage absence/attendance', 'Gestionar falta/asistencia'),
    'Anotações da Equipa (Visível no Diário):': ('Team notes (visible in the class log):', 'Notas del equipo (visibles en el diario):'),
    'Ação de Correção (Opcional):': ('Correction (optional):', 'Corrección (opcional):'), 'Converter para Online': ('Change to online', 'Cambiar a en línea'),
    'Converter para Presencial': ('Change to in person', 'Cambiar a presencial'),
    'Abonar (Converter em Falta Justificada)': ('Excuse (change to excused absence)', 'Justificar (convertir en falta justificada)'),
    'Reprovar (Converter em Falta Injustificada)': ('Reject (change to unexcused absence)', 'Rechazar (convertir en falta injustificada)'),
    'Ex: Atestado médico entregue...': ('E.g. Medical certificate delivered...', 'Ej.: Certificado médico entregado...'),
    'Nenhum registo encontrado com estes filtros.': ('No records found with these filters.', 'No se encontraron registros con estos filtros.'),
    'Imprimir Relatório': ('Print report', 'Imprimir informe'), 'Baixar em Excel': ('Download as Excel', 'Descargar en Excel'),
    'Média de Presença': ('Average attendance', 'Asistencia media'), 'Ausências': ('Absences', 'Ausencias'), 'Faltas Abonadas': ('Excused absences', 'Faltas justificadas'),
    'Justificadas pelos Mentores': ('Excused by mentors', 'Justificadas por los mentores'), 'Registo de faltas diretas': ('Direct absences recorded', 'Registro de faltas directas'),
    'Em Risco': ('At risk', 'En riesgo'), 'Alerta (Em Risco)': ('Warning (at risk)', 'Alerta (en riesgo)'), 'Próximos de 25% de faltas': ('Close to 25% absences', 'Cerca del 25% de faltas'),
    'Infrequência Crítica': ('Critical absence', 'Inasistencia crítica'), 'Ultrapassaram limite de faltas': ('Exceeded the absence limit', 'Superaron el límite de faltas'),
    'Detalhamento de Ausências Pendentes': ('Pending absences in detail', 'Detalle de ausencias pendientes'),
    'Excelente indicador! Não existem alunos com registo de faltas no sistema.': ('Great result! No students have absences recorded.', '¡Excelente indicador! No hay alumnos con faltas registradas.'),
    'Nenhum curso em andamento para análise de risco.': ('No courses in progress for risk analysis.', 'No hay cursos en curso para el análisis de riesgo.'),
    'Nome do Aluno': ('Student name', 'Nombre del alumno'), 'Disciplina / Curso': ('Subject / Course', 'Asignatura / Curso'),
    'Visão global da turma': ('Class overview', 'Visión general del grupo'), 'A analisar o registo de': ('Reviewing the record of', 'Analizando el registro de'),

    # ---------------- Diário › Gestão de Notas
    'Diário de Classe (Notas)': ('Class Log (Grades)', 'Diario de Clase (Notas)'),
    'Selecione a Turma Ativa para Lançar Notas:': ('Select the active class to enter grades:', 'Seleccione el grupo activo para registrar notas:'),
    '-- Escolha uma Turma --': ('-- Choose a class --', '-- Elija un grupo --'),
    'Selecione uma turma no menu acima para começar a gerir as notas.': ('Select a class in the menu above to start managing grades.', 'Seleccione un grupo en el menú de arriba para empezar a gestionar las notas.'),
    'Nota Técnica (0-10)': ('Technical grade (0-10)', 'Nota técnica (0-10)'), 'Nota Postura (0-10)': ('Attitude grade (0-10)', 'Nota de actitud (0-10)'),
    'Salvar Notas da Turma': ('Save class grades', 'Guardar notas del grupo'),
    'Ainda não possui matrículas geradas nas disciplinas.': ('No enrolments generated in the subjects yet.', 'Aún no hay matrículas generadas en las asignaturas.'),
    '1. Avaliação Coletiva (Nota do Grupo)': ('1. Group assessment (group grade)', '1. Evaluación colectiva (nota del grupo)'),
    '2. Avaliação Individual (Por Aluno)': ('2. Individual assessment (per student)', '2. Evaluación individual (por alumno)'),

    # ---------------- Hub Educacional
    'Gestão de Conteúdo, Parceiros e Trilhas': ('Content, Partners and Learning Paths', 'Gestión de Contenido, Socios y Rutas'),
    '01. Catálogo de Cursos': ('01. Course catalogue', '01. Catálogo de cursos'), '02. Parceiros B2B': ('02. B2B partners', '02. Socios B2B'),
    '03. Turmas & Trilhas': ('03. Classes & paths', '03. Grupos y rutas'), '+ Adicionar Novo Curso': ('+ Add new course', '+ Añadir nuevo curso'),
    'Cursos Disponíveis na Plataforma': ('Courses available on the platform', 'Cursos disponibles en la plataforma'),
    'Nome do Curso': ('Course name', 'Nombre del curso'), 'Nome do Curso / Material': ('Course / material name', 'Nombre del curso / material'),
    'Carga': ('Workload', 'Duración'), 'Carga Horária (h)': ('Workload (h)', 'Duración (h)'), 'Exige Cert.?': ('Cert. required?', '¿Exige cert.?'),
    'Cadastrado Por': ('Added by', 'Registrado por'), 'Link (URL)': ('Link (URL)', 'Enlace (URL)'), 'Domínio': ('Domain', 'Dominio'),
    'Nenhum curso cadastrado.': ('No courses registered.', 'No hay cursos registrados.'), 'Salvar Novo Curso': ('Save new course', 'Guardar nuevo curso'),
    'Editar Curso': ('Edit course', 'Editar curso'), 'Excluir Curso': ('Delete course', 'Eliminar curso'),
    'Tem certeza que deseja excluir permanentemente o curso:': ('Are you sure you want to permanently delete the course:', '¿Seguro que desea eliminar definitivamente el curso:'),
    'Esta ação não pode ser desfeita. Considere desativar o curso em vez de o excluir.': ('This cannot be undone. Consider disabling the course instead of deleting it.', 'Esta acción no se puede deshacer. Considere desactivar el curso en lugar de eliminarlo.'),
    'Confirmar Exclusão': ('Confirm deletion', 'Confirmar eliminación'), 'Sim, Excluir!': ('Yes, delete!', '¡Sí, eliminar!'),
    'Ex: Laboratório Azure Cloud': ('E.g. Azure Cloud Lab', 'Ej.: Laboratorio Azure Cloud'), 'Ex: Microsoft Learn': ('E.g. Microsoft Learn', 'Ej.: Microsoft Learn'),
    '+ Cadastrar Empresa': ('+ Register company', '+ Registrar empresa'), 'Empresas Cadastradas': ('Registered companies', 'Empresas registradas'),
    'Nova Empresa Parceira': ('New partner company', 'Nueva empresa socia'), 'Editar Parceiro': ('Edit partner', 'Editar socio'),
    'Nome da Empresa': ('Company name', 'Nombre de la empresa'), 'Empresa Parceira': ('Partner company', 'Empresa socia'),
    'Contato Principal': ('Main contact', 'Contacto principal'), 'Contato 2 (Opcional)': ('Contact 2 (optional)', 'Contacto 2 (opcional)'),
    'E-mail Principal': ('Main email', 'Correo principal'), 'E-mail do Contato 2': ('Contact 2 email', 'Correo del contacto 2'),
    'Gestor Parceiro Responsável': ('Responsible partner manager', 'Gestor socio responsable'), 'Selecione um gestor...': ('Select a manager...', 'Seleccione un gestor...'),
    'Nenhum gestor...': ('No manager...', 'Ningún gestor...'), 'Mentores Disponíveis': ('Available mentors', 'Mentores disponibles'),
    'Mentores (Atuais + Disponíveis)': ('Mentors (current + available)', 'Mentores (actuales + disponibles)'),
    'Todos os mentores já estão alocados a empresas.': ('All mentors are already assigned to companies.', 'Todos los mentores ya están asignados a empresas.'),
    'Segure CTRL para selecionar múltiplos ou remover seleções.': ('Hold CTRL to select several or remove selections.', 'Mantenga CTRL para seleccionar varios o quitar selecciones.'),
    'Ex: Tech Corp SA': ('E.g. Tech Corp Ltd', 'Ej.: Tech Corp SA'), 'Ex: João Silva': ('E.g. John Smith', 'Ej.: Juan Pérez'), 'Ex: Maria Souza': ('E.g. Mary Jones', 'Ej.: María López'),
    'Nova Turma / Trilha': ('New class / path', 'Nuevo grupo / ruta'), 'Turmas Cadastradas': ('Registered classes', 'Grupos registrados'),
    'Turmas Ativas': ('Active classes', 'Grupos activos'), 'Nome da Turma': ('Class name', 'Nombre del grupo'), 'Criar Turma': ('Create class', 'Crear grupo'),
    'Editar Turma': ('Edit class', 'Editar grupo'), 'Excluir Turma': ('Delete class', 'Eliminar grupo'),
    'Tem a certeza que deseja excluir a turma:': ('Are you sure you want to delete the class:', '¿Seguro que desea eliminar el grupo:'),
    'Esta ação irá apagar a turma do sistema.': ('This will remove the class from the system.', 'Esta acción eliminará el grupo del sistema.'),
    'Nenhuma turma encontrada.': ('No classes found.', 'No se encontraron grupos.'), 'Nenhuma (Turma Aberta)': ('None (open class)', 'Ninguna (grupo abierto)'),
    'Qual o objetivo desta turma?': ('What is the goal of this class?', '¿Cuál es el objetivo de este grupo?'),
    'Ex: Turma 2026 - UX Design': ('E.g. Class 2026 - UX Design', 'Ej.: Grupo 2026 - UX Design'), 'Ex: Turma Azure 2026 - Noturno': ('E.g. Azure Class 2026 - Evening', 'Ej.: Grupo Azure 2026 - Nocturno'),
    'Ex: Jovens Talentos 2026': ('E.g. Young Talents 2026', 'Ej.: Jóvenes Talentos 2026'), 'Cursos / Disciplinas': ('Courses / subjects', 'Cursos / asignaturas'),
    'Matricular': ('Enrol', 'Matricular'), 'Matricular Alunos': ('Enrol students', 'Matricular alumnos'), 'Processar Matrículas': ('Process enrolments', 'Procesar matrículas'),
    'Importar Alunos': ('Import students', 'Importar alumnos'), 'Importar Grupo (Opcional)': ('Import group (optional)', 'Importar grupo (opcional)'),
    'Buscar e Selecionar Alunos:': ('Search and select students:', 'Buscar y seleccionar alumnos:'), 'Buscar e Selecionar Alunos (Opcional)': ('Search and select students (optional)', 'Buscar y seleccionar alumnos (opcional)'),
    'Nenhum aluno vinculado a esta turma ainda.': ('No students linked to this class yet.', 'Aún no hay alumnos vinculados a este grupo.'),
    'Não encontra o aluno? Importar Planilha': ("Can't find the student? Import spreadsheet", '¿No encuentra al alumno? Importar planilla'),
    'Selecione o arquivo (.csv)': ('Select the file (.csv)', 'Seleccione el archivo (.csv)'), 'Processar Planilha': ('Process spreadsheet', 'Procesar planilla'),
    'Cadastro Rápido': ('Quick registration', 'Registro rápido'), 'Senha Provisória': ('Temporary password', 'Contraseña provisoria'),

    # ---------------- Grupos
    'Gerenciamento de Grupos': ('Group Management', 'Gestión de Grupos'), 'Criar Novo Grupo': ('Create new group', 'Crear nuevo grupo'),
    '+ Cadastrar Novo Grupo': ('+ Register new group', '+ Registrar nuevo grupo'), 'Grupos Existentes': ('Existing groups', 'Grupos existentes'),
    'Nome do Grupo': ('Group name', 'Nombre del grupo'), 'Data de Criação': ('Creation date', 'Fecha de creación'), 'Criação': ('Created', 'Creación'),
    'Membros Associados': ('Members', 'Miembros asociados'), 'Gerenciar Membros': ('Manage members', 'Gestionar miembros'),
    'Atribuir Membros ao Grupo': ('Assign members to the group', 'Asignar miembros al grupo'),
    'Marque ou desmarque as caixas para adicionar/remover utilizadores deste grupo.': ('Tick or untick the boxes to add/remove users from this group.', 'Marque o desmarque las casillas para añadir/quitar usuarios de este grupo.'),
    'Nenhum grupo cadastrado ainda.': ('No groups registered yet.', 'Aún no hay grupos registrados.'), 'Nenhum membro cadastrado.': ('No members registered.', 'No hay miembros registrados.'),
    'Salvar Grupo': ('Save group', 'Guardar grupo'), 'Salvar': ('Save', 'Guardar'), 'Usuário': ('User', 'Usuario'), 'Voltar': ('Back', 'Volver'),
    'Voltar para Usuários': ('Back to users', 'Volver a usuarios'),

    # ---------------- Cadastros & Usuários
    '01. Equipe Interna': ('01. Internal team', '01. Equipo interno'), '03. Corpo Discente': ('03. Students', '03. Alumnado'),
    '+ Novo': ('+ New', '+ Nuevo'), '+ Adicionar Mentor Novo': ('+ Add new mentor', '+ Añadir nuevo mentor'),
    'Buscar qualquer usuário, e-mail ou mentor...': ('Search any user, email or mentor...', 'Buscar cualquier usuario, correo o mentor...'),
    'Nível de Acesso': ('Access level', 'Nivel de acceso'), 'Parceiro (B2B)': ('Partner (B2B)', 'Socio (B2B)'),
    'Gestor Parceiro (Admin B2B)': ('Partner manager (B2B Admin)', 'Gestor socio (Admin B2B)'),
    'Avaliador da Banca (executivo convidado)': ('Panel evaluator (guest executive)', 'Evaluador del tribunal (ejecutivo invitado)'),
    'Bloqueado (Senha 5x)': ('Blocked (password 5x)', 'Bloqueado (contraseña 5x)'), '(Atual)': ('(Current)', '(Actual)'),
    'Reiniciar Perguntas de Segurança (O aluno recadastrará no próximo login)': ('Reset security questions (the student sets them again at next login)', 'Reiniciar preguntas de seguridad (el alumno las registrará en el próximo inicio de sesión)'),
    'Inteligência Artificial: Match Disponível!': ('AI: match available!', 'Inteligencia artificial: ¡coincidencia disponible!'),
    'O sistema identificou alunos sem mentor cujos objetivos combinam com as especialidades da nossa equipe. Abra a edição do aluno para ver a sugestão da IA.': (
        'The system found students without a mentor whose goals match our team\'s expertise. Open the student to see the AI suggestion.',
        'El sistema identificó alumnos sin mentor cuyos objetivos coinciden con las especialidades de nuestro equipo. Abra la edición del alumno para ver la sugerencia de la IA.'),
    'Mentores Sugeridos pela IA:': ('Mentors suggested by AI:', 'Mentores sugeridos por la IA:'), 'Aprovar e Cadastrar': ('Approve and register', 'Aprobar y registrar'),
    'Negar Pedido': ('Deny request', 'Rechazar solicitud'),

    # ---------------- Portal de Demandas
    'Portal de Demandas (Tickets)': ('Requests Portal (Tickets)', 'Portal de Solicitudes (Tickets)'),
    'Canal Oficial de Alinhamento, Melhorias e Suporte entre ITM e Parceiros B2B.': ('Official channel for alignment, improvements and support between ITM and B2B partners.', 'Canal oficial de alineación, mejoras y soporte entre ITM y los socios B2B.'),
    'Abrir Novo Ticket': ('Open new ticket', 'Abrir nuevo ticket'), 'Enviar Ticket': ('Send ticket', 'Enviar ticket'), '# Ticket': ('# Ticket', '# Ticket'),
    'Assunto / Título': ('Subject / title', 'Asunto / título'), 'Descrição Detalhada': ('Detailed description', 'Descripción detallada'),
    'Explique detalhadamente o contexto da sua solicitação para a equipe de gestão...': ('Explain the context of your request to the management team in detail...', 'Explique en detalle el contexto de su solicitud al equipo de gestión...'),
    'Ex: Alteração da Data da Banca do Grupo 4': ("E.g. Change of Group 4's panel date", 'Ej.: Cambio de la fecha del tribunal del Grupo 4'),
    'Alinhamento Pedagógico': ('Teaching alignment', 'Alineación pedagógica'), 'Mudança de Data / Prazo': ('Date / deadline change', 'Cambio de fecha / plazo'),
    'Sugestão de Melhoria': ('Improvement suggestion', 'Sugerencia de mejora'), 'Dúvida Técnica (Plataforma)': ('Technical question (platform)', 'Duda técnica (plataforma)'),
    'Normal (Análise Padrão)': ('Normal (standard review)', 'Normal (análisis estándar)'), 'Alta (Requer atenção breve)': ('High (needs attention soon)', 'Alta (requiere atención pronto)'),
    'Urgente (Trava o andamento do projeto)': ('Urgent (blocks the project)', 'Urgente (bloquea el avance del proyecto)'),
    'Ver / Responder': ('View / reply', 'Ver / responder'), 'Alterar Status': ('Change status', 'Cambiar estado'), 'Gravar Resposta': ('Save reply', 'Guardar respuesta'),
    'Resposta Oficial (ITM / Parceiro B2B)': ('Official reply (ITM / B2B partner)', 'Respuesta oficial (ITM / socio B2B)'),
    'Escreva a resposta oficial para este ticket...': ('Write the official reply for this ticket...', 'Escriba la respuesta oficial para este ticket...'),
    'A equipe de gestão ainda não respondeu a este ticket.': ('The management team has not replied to this ticket yet.', 'El equipo de gestión aún no respondió este ticket.'),
    'Nenhum ticket registrado no momento. Todos alinhados!': ('No tickets at the moment. All aligned!', 'No hay tickets por ahora. ¡Todo alineado!'),

    # ---------------- Valores do banco exibidos na tela (status, perfis, prioridades)
    'Concluída': ('Completed', 'Concluida'), 'Iniciado': ('Started', 'Iniciado'), 'Ativa': ('Active', 'Activa'), 'Inativa': ('Inactive', 'Inactiva'),
    'Normal': ('Normal', 'Normal'), 'Admin B2B': ('B2B Admin', 'Admin B2B'), 'Avaliador Banca': ('Panel evaluator', 'Evaluador del tribunal'),
    'Agendada': ('Scheduled', 'Programada'), 'Realizada': ('Held', 'Realizada'), 'Remarcada': ('Rescheduled', 'Reprogramada'),
    'Aprovado': ('Approved', 'Aprobado'), 'Negado': ('Denied', 'Rechazado'), 'Em andamento': ('In progress', 'En curso'),
    'Hibrido': ('Hybrid', 'Híbrido'), 'Híbrido': ('Hybrid', 'Híbrido'),

    # ---------------- Textos com ícone
    'Data de Início': ('Start date', 'Fecha de inicio'), 'Filtrar por Grupo:': ('Filter by group:', 'Filtrar por grupo:'),
    '⏳ Lembrar Depois': ('⏳ Remind me later', '⏳ Recordar después'), '✔️ Gravar e Validar': ('✔️ Save and validate', '✔️ Guardar y validar'),
    '❌ Não mostrar novamente': ("❌ Don't show again", '❌ No mostrar de nuevo'), '🚀 Fazer o Tour Agora': ('🚀 Take the tour now', '🚀 Hacer el recorrido ahora'),
    '🎓 Alunos': ('🎓 Students', '🎓 Alumnos'), '🧠 Mentores': ('🧠 Mentors', '🧠 Mentores'), '🧠 Mentores e Equipe': ('🧠 Mentors and team', '🧠 Mentores y equipo'),
    '🏢 Presencial': ('🏢 In person', '🏢 Presencial'), '💻 Online': ('💻 Online', '💻 En línea'),
    '📅 Horários Guardados para o Líder:': ('📅 Times saved for the lead:', '📅 Horarios guardados para el líder:'), '📤 Anexar': ('📤 Attach', '📤 Adjuntar'),
    '🔍 Buscar por nome do aluno ou mentor...': ('🔍 Search by student or mentor name...', '🔍 Buscar por nombre del alumno o mentor...'),
    '🔍 Clique aqui e digite o nome do aluno...': ("🔍 Click here and type the student's name...", '🔍 Haga clic aquí y escriba el nombre del alumno...'),
    '🔍 Clique e digite o nome...': ('🔍 Click and type the name...', '🔍 Haga clic y escriba el nombre...'),
    '🔒 Aula Trancada': ('🔒 Lesson locked', '🔒 Clase bloqueada'), '🔒 Protegido': ('🔒 Protected', '🔒 Protegido'),
    '🔴 Apenas Faltas': ('🔴 Absences only', '🔴 Solo faltas'), '🟢 Apenas Presenças': ('🟢 Attendance only', '🟢 Solo asistencias'),
    '🛡️ Faltas Justificadas': ('🛡️ Excused absences', '🛡️ Faltas justificadas'),
    # O script de admin_banco.html procura o botão por "Histórico", "History" ou "Historial"
    '🗑️ Apagar Todo o Histórico': ('🗑️ Delete All History', '🗑️ Borrar Todo el Historial'),
    '🗑️ Confirmar Exclusão': ('🗑️ Confirm deletion', '🗑️ Confirmar eliminación'), '🗑️ Excluir Selecionados': ('🗑️ Delete selected', '🗑️ Eliminar seleccionados'),
    '🗓️ Definir Horários de Trabalho': ('🗓️ Set work times', '🗓️ Definir horarios de trabajo'),
    '🗓️ Planeamento de Horários (Google Agenda)': ('🗓️ Time planning (Google Calendar)', '🗓️ Planificación de horarios (Google Calendar)'),

    # ---------------- Tours das páginas (templates/_tours.html)
    'O tour interativo para esta página está sendo construído!': ('The interactive tour for this page is being built!', '¡El recorrido interactivo de esta página está en construcción!'),
    'Projetos (TCC): aqui ficam os projetos de conclusão de cada grupo, com tarefas, prazos, entregas e a banca.': (
        'Projects (final paper): each group\'s final projects, with tasks, deadlines, submissions and the panel.',
        'Proyectos (TCC): aquí están los proyectos finales de cada grupo, con tareas, plazos, entregas y el tribunal.'),
    'Cadastre um novo projeto e vincule o grupo responsável (jovens e mentores).': (
        'Register a new project and link the responsible group (young people and mentors).', 'Registre un nuevo proyecto y vincule el grupo responsable (jóvenes y mentores).'),
    'Filtre para ver só os projetos de um grupo.': ("Filter to see only one group's projects.", 'Filtre para ver solo los proyectos de un grupo.'),
    'Cada cartão mostra as tarefas, o progresso, a banca agendada e a entrega final do TCC.': (
        'Each card shows the tasks, progress, scheduled panel and the final paper submission.', 'Cada tarjeta muestra las tareas, el avance, el tribunal programado y la entrega final del TCC.'),
    'Diário de frequência: presenças, faltas e justificativas de todos os jovens.': (
        'Attendance log: attendance, absences and excuses for all young people.', 'Diario de asistencia: asistencias, faltas y justificaciones de todos los jóvenes.'),
    'Use os filtros de período, aluno e tipo de presença para montar o relatório.': (
        'Use the period, student and attendance type filters to build the report.', 'Use los filtros de período, alumno y tipo de asistencia para armar el informe.'),
    'Os indicadores mostram a média de presença e quem está em risco por excesso de faltas.': (
        'The indicators show average attendance and who is at risk from too many absences.', 'Los indicadores muestran la asistencia media y quién está en riesgo por exceso de faltas.'),
    'Na tabela, abra cada registro para abonar, reprovar ou corrigir a modalidade da presença.': (
        'In the table, open each record to excuse, reject or correct the attendance mode.', 'En la tabla, abra cada registro para justificar, rechazar o corregir la modalidad de la asistencia.'),
    'Diário de classe: lance as notas técnica e de postura dos jovens em cada curso da turma.': (
        "Class log: enter the young people's technical and attitude grades for each course in the class.", 'Diario de clase: registre las notas técnica y de actitud de los jóvenes en cada curso del grupo.'),
    'Escolha a turma para carregar os alunos matriculados.': ('Choose the class to load the enrolled students.', 'Elija el grupo para cargar los alumnos matriculados.'),
    'Preencha as notas de 0 a 10 e salve a turma inteira de uma vez.': ('Fill in the grades from 0 to 10 and save the whole class at once.', 'Complete las notas de 0 a 10 y guarde todo el grupo de una vez.'),
    'Grupos: cada grupo reúne os jovens e os mentores que orientam um mesmo TCC.': (
        'Groups: each group brings together the young people and the mentors guiding the same final paper.', 'Grupos: cada grupo reúne a los jóvenes y a los mentores que orientan un mismo TCC.'),
    'Busque e marque os membros para criar um novo grupo.': ('Search and tick the members to create a new group.', 'Busque y marque los miembros para crear un nuevo grupo.'),
    'Aqui estão os grupos existentes; edite os membros sempre que a equipe mudar.': (
        'Here are the existing groups; edit the members whenever the team changes.', 'Aquí están los grupos existentes; edite los miembros cuando cambie el equipo.'),
    'Agenda de bancas: datas, avaliadores, prazos de entrega e resultado de cada TCC.': (
        'Panel schedule: dates, evaluators, submission deadlines and the result of each final paper.', 'Agenda de tribunales: fechas, evaluadores, plazos de entrega y resultado de cada TCC.'),
    'Agende uma banca escolhendo o projeto, a data, os avaliadores e os prazos.': (
        'Schedule a panel by choosing the project, date, evaluators and deadlines.', 'Programe un tribunal eligiendo el proyecto, la fecha, los evaluadores y los plazos.'),
    'Cada cartão mostra a situação da banca, as notas recebidas e os botões para remarcar, cancelar ou publicar o resultado.': (
        "Each card shows the panel's status, the grades received and the buttons to reschedule, cancel or publish the result.",
        'Cada tarjeta muestra la situación del tribunal, las notas recibidas y los botones para reprogramar, cancelar o publicar el resultado.'),
    'Atividades extras: encontros fora do cronograma oficial, com presença e horas de cada participante.': (
        "Extra activities: meetings outside the official schedule, with each participant's attendance and hours.", 'Actividades extra: encuentros fuera del cronograma oficial, con asistencia y horas de cada participante.'),
    'Registre uma nova atividade extra informando o motivo, o grupo e a duração.': (
        'Register a new extra activity with the reason, group and duration.', 'Registre una nueva actividad extra indicando el motivo, el grupo y la duración.'),
    'Acompanhe as atividades, marque presença e exporte o relatório de cada uma.': (
        'Follow the activities, mark attendance and export the report for each one.', 'Siga las actividades, marque asistencia y exporte el informe de cada una.'),
    'Avaliadores da banca: executivos convidados com currículo, área de atuação e empresa.': (
        'Panel evaluators: guest executives with résumé, field and company.', 'Evaluadores del tribunal: ejecutivos invitados con currículum, área de actuación y empresa.'),
    'Cadastre um novo avaliador; ele recebe um acesso restrito às bancas em que for escalado.': (
        'Register a new evaluator; they get access limited to the panels they are assigned to.', 'Registre un nuevo evaluador; recibe un acceso restringido a los tribunales en los que sea designado.'),
    'Cada cartão mostra o perfil do avaliador e o currículo para download.': (
        "Each card shows the evaluator's profile and the résumé to download.", 'Cada tarjeta muestra el perfil del evaluador y el currículum para descargar.'),
    'Sala da Banca: notas, perguntas e cronômetro da apresentação deste TCC.': (
        'Panel Room: grades, questions and the presentation timer for this final paper.', 'Sala del Tribunal: notas, preguntas y cronómetro de la presentación de este TCC.'),
    'Etapa 1: nota do trabalho escrito. Notas abaixo de 7 exigem justificativa.': (
        'Step 1: grade for the written paper. Grades below 7 need a justification.', 'Etapa 1: nota del trabajo escrito. Las notas menores a 7 exigen justificación.'),
    'Etapa 2: notas da apresentação e do material visual, com o feedback para os jovens.': (
        'Step 2: grades for the presentation and visual material, with feedback for the young people.', 'Etapa 2: notas de la presentación y del material visual, con comentarios para los jóvenes.'),
    'Registre as perguntas feitas pela banca e as respostas do grupo.': (
        "Record the panel's questions and the group's answers.", 'Registre las preguntas del tribunal y las respuestas del grupo.'),
    'Biblioteca: TCCs aprovados de todas as edições e materiais de apoio para pesquisa.': (
        'Library: approved final papers from every edition and support materials for research.', 'Biblioteca: TCC aprobados de todas las ediciones y materiales de apoyo para investigar.'),
    'Busque por título, tema, palavra-chave ou autores e filtre por ano.': (
        'Search by title, theme, keyword or authors and filter by year.', 'Busque por título, tema, palabra clave o autores y filtre por año.'),
    'Cada TCC mostra o resumo, as palavras-chave e o PDF para download.': (
        'Each paper shows the abstract, keywords and the PDF to download.', 'Cada TCC muestra el resumen, las palabras clave y el PDF para descargar.'),
    'Os materiais de apoio reúnem guias de metodologia, formatação e apresentação.': (
        'Support materials bring together methodology, formatting and presentation guides.', 'Los materiales de apoyo reúnen guías de metodología, formato y presentación.'),
    'Portal de Demandas: o canal oficial para pedidos, dúvidas e alinhamentos (nada por WhatsApp ou e-mail).': (
        'Requests Portal: the official channel for requests, questions and alignment (nothing via WhatsApp or email).',
        'Portal de Solicitudes: el canal oficial para pedidos, dudas y alineaciones (nada por WhatsApp ni correo).'),
    'Abra um ticket escolhendo a categoria e a prioridade.': ('Open a ticket by choosing the category and priority.', 'Abra un ticket eligiendo la categoría y la prioridad.'),
    'Acompanhe o status de cada ticket e a resposta oficial da equipe.': (
        "Follow each ticket's status and the team's official reply.", 'Siga el estado de cada ticket y la respuesta oficial del equipo.'),
    'Indicadores de voluntariado: o impacto do programa em horas, voluntários e jovens.': (
        "Volunteering indicators: the programme's impact in hours, volunteers and young people.", 'Indicadores de voluntariado: el impacto del programa en horas, voluntarios y jóvenes.'),
    'Filtre por período, empresa, tipo de atividade ou grupo.': ('Filter by period, company, activity type or group.', 'Filtre por período, empresa, tipo de actividad o grupo.'),
    'Os gráficos mostram as horas por tipo de atividade e por mês.': ('The charts show hours by activity type and by month.', 'Los gráficos muestran las horas por tipo de actividad y por mes.'),
    'Este texto já sai pronto para a newsletter de fim de ciclo.': ('This text is ready for the end-of-cycle newsletter.', 'Este texto ya sale listo para el boletín de fin de ciclo.'),
    'Certificados: um para cada projeto aprovado em banca de que você participou.': (
        'Certificates: one for each panel-approved project you took part in.', 'Certificados: uno por cada proyecto aprobado por el tribunal en el que participó.'),
    'Abra o certificado para imprimir ou salvar em PDF; o código permite conferir a autenticidade.': (
        'Open the certificate to print or save as PDF; the code lets anyone check that it is authentic.', 'Abra el certificado para imprimir o guardar en PDF; el código permite verificar su autenticidad.'),
    'Minhas bancas: os TCCs que você vai avaliar, com datas, prazos e arquivos.': (
        'My panels: the final papers you will evaluate, with dates, deadlines and files.', 'Mis tribunales: los TCC que va a evaluar, con fechas, plazos y archivos.'),
    'Baixe o trabalho escrito e os slides entregues pelo grupo.': ('Download the written paper and slides submitted by the group.', 'Descargue el trabajo escrito y las diapositivas entregadas por el grupo.'),
    'Ligue o relógio ao ler o TCC: as horas vão para o seu certificado de voluntariado.': (
        'Start the clock while reading the paper: the hours go to your volunteering certificate.', 'Encienda el reloj al leer el TCC: las horas van a su certificado de voluntariado.'),
    'Abra o formulário para lançar as notas da banca.': ('Open the form to enter the panel grades.', 'Abra el formulario para registrar las notas del tribunal.'),
    'Notificações: avisos de bancas, entregas, tickets e reuniões.': ('Notifications: alerts about panels, submissions, tickets and meetings.', 'Notificaciones: avisos de tribunales, entregas, tickets y reuniones.'),
    'Escolha se também quer receber os avisos por e-mail.': ('Choose whether you also want the alerts by email.', 'Elija si también quiere recibir los avisos por correo.'),
    'Reuniões ITM × Aon: pautas, atas, decisões e encaminhamentos com responsáveis e prazos.': (
        'ITM × Aon meetings: agendas, minutes, decisions and action items with owners and deadlines.', 'Reuniones ITM × Aon: agendas, actas, decisiones y acciones con responsables y plazos.'),
    'Filtre as reuniões por período.': ('Filter meetings by period.', 'Filtre las reuniones por período.'),
    'Abra uma reunião para ver a ata e acompanhar os encaminhamentos.': (
        'Open a meeting to see the minutes and follow the action items.', 'Abra una reunión para ver el acta y seguir las acciones.'),
    'Trilha do TCC: os módulos de orientação que mentores e professores concluem antes de orientar.': (
        'Final paper track: the guidance modules mentors and teachers complete before supervising.', 'Ruta del TCC: los módulos de orientación que mentores y profesores completan antes de orientar.'),
    'Veja quem já concluiu a trilha e quem ainda está pendente.': ('See who has completed the track and who is still pending.', 'Vea quién ya completó la ruta y quién sigue pendiente.'),
    'Cadastre ou edite os módulos da trilha.': ('Add or edit the track modules.', 'Registre o edite los módulos de la ruta.'),

    # ---------------- Perfis de acesso (perfis personalizados)
    'Perfis de acesso': ('Access profiles', 'Perfiles de acceso'), 'Perfis personalizados': ('Custom profiles', 'Perfiles personalizados'),
    'Perfis do sistema': ('System profiles', 'Perfiles del sistema'), 'Novo perfil': ('New profile', 'Nuevo perfil'),
    'Crie perfis sob medida: cada perfil novo herda as permissões de um perfil do sistema e você escolhe quais módulos ele usa.': (
        'Create tailored profiles: each new profile inherits the permissions of a system profile and you choose which modules it uses.',
        'Cree perfiles a medida: cada perfil nuevo hereda los permisos de un perfil del sistema y usted elige qué módulos usa.'),
    'Por segurança, um perfil personalizado nunca tem mais acesso que o perfil-base: os módulos desligados somem do menu e são bloqueados na rota. Cada alteração é aprendida pelo Agente Gerente Técnico e registrada na Governança de aprendizados.': (
        'For security, a custom profile never has more access than its base profile: disabled modules disappear from the menu and are blocked on the route. Every change is learned by the Technical Manager Agent and logged in Learning governance.',
        'Por seguridad, un perfil personalizado nunca tiene más acceso que el perfil base: los módulos desactivados desaparecen del menú y se bloquean en la ruta. Cada cambio lo aprende el Agente Gerente Técnico y queda registrado en la Gobernanza de aprendizajes.'),
    'Herda de': ('Inherits from', 'Hereda de'), 'Herda as permissões de': ('Inherits the permissions of', 'Hereda los permisos de'),
    'usuário(s)': ('user(s)', 'usuario(s)'), 'Usuários': ('Users', 'Usuarios'), 'Módulos disponíveis': ('Available modules', 'Módulos disponibles'),
    'Nenhum perfil personalizado ainda. Clique em Novo perfil para criar o primeiro.': ('No custom profiles yet. Click New profile to create the first one.', 'Aún no hay perfiles personalizados. Haga clic en Nuevo perfil para crear el primero.'),
    'Excluir este perfil? Os usuários dele voltam ao perfil-base.': ('Delete this profile? Its users go back to the base profile.', '¿Eliminar este perfil? Sus usuarios vuelven al perfil base.'),
    'Histórico de alterações dos perfis': ('Profile change history', 'Historial de cambios de los perfiles'),
    'Nome do perfil': ('Profile name', 'Nombre del perfil'), 'Ex.: Coordenador ITM': ('E.g. ITM Coordinator', 'Ej.: Coordinador ITM'),
    'Módulos que este perfil pode usar': ('Modules this profile can use', 'Módulos que este perfil puede usar'),
    'Marcar todos': ('Select all', 'Marcar todos'), 'Desmarcar': ('Clear', 'Desmarcar'), 'sempre': ('always', 'siempre'),
    'Só aparecem os módulos que o perfil-base tem.': ('Only the modules the base profile has are shown.', 'Solo aparecen los módulos que tiene el perfil base.'),
    'Perfil ativo (inativo: os usuários só veem o Painel Geral)': ('Active profile (inactive: users only see the Dashboard)', 'Perfil activo (inactivo: los usuarios solo ven el Panel general)'),
    'Salvar perfil': ('Save profile', 'Guardar perfil'), 'Perfil salvo.': ('Profile saved.', 'Perfil guardado.'),
    'Perfil excluído. Os usuários dele voltaram ao perfil-base.': ('Profile deleted. Its users went back to the base profile.', 'Perfil eliminado. Sus usuarios volvieron al perfil base.'),
    'Informe o nome do perfil e escolha um perfil-base.': ('Enter the profile name and choose a base profile.', 'Indique el nombre del perfil y elija un perfil base.'),
    'Este nome já é de um perfil do sistema. Escolha outro nome.': ('This name belongs to a system profile. Choose another name.', 'Este nombre pertenece a un perfil del sistema. Elija otro nombre.'),
    'Já existe um perfil com este nome.': ('A profile with this name already exists.', 'Ya existe un perfil con este nombre.'),
    'O Agente Gerente Técnico aprendeu a mudança: {codigos}': ('The Technical Manager Agent learned the change: {codigos}', 'El Agente Gerente Técnico aprendió el cambio: {codigos}'),
    'Acesso negado: o seu perfil não inclui este módulo.': ('Access denied: your profile does not include this module.', 'Acceso denegado: su perfil no incluye este módulo.'),
    'Escolha um nível de acesso válido.': ('Choose a valid access level.', 'Elija un nivel de acceso válido.'),
    'Painel Geral': ('Dashboard', 'Panel general'), 'Sessões': ('Sessions', 'Sesiones'), 'Acompanhamento': ('Tracking', 'Seguimiento'),
    'Atividades extras': ('Extra activities', 'Actividades extra'), 'Diário de Classe (frequência e notas)': ('Class log (attendance and grades)', 'Diario de clase (asistencia y notas)'),
    'Projetos (TCC)': ('Projects (final paper)', 'Proyectos (TCC)'), 'Bancas (Minhas bancas e Sala da Banca)': ('Panels (My panels and Panel Room)', 'Tribunales (Mis tribunales y Sala del Tribunal)'),
    'Biblioteca de TCCs': ('Final paper library', 'Biblioteca de TCC'), 'Certificados': ('Certificates', 'Certificados'),
    'Portal de Demandas': ('Requests Portal', 'Portal de Solicitudes'), 'Relógio de voluntariado e relatórios ESG': ('Volunteering clock and ESG reports', 'Reloj de voluntariado e informes ESG'),
    'Cadastros e grupos': ('Users and groups', 'Registros y grupos'), 'Solicitações de mentoria': ('Mentoring requests', 'Solicitudes de mentoría'),
    'Gestão da trilha do TCC': ('Final paper track management', 'Gestión de la ruta del TCC'), 'Reuniões ITM × Aon': ('ITM × Aon meetings', 'Reuniones ITM × Aon'),
    'Agenda de bancas e avaliadores': ('Panel schedule and evaluators', 'Agenda de tribunales y evaluadores'), 'Indicadores de voluntariado': ('Volunteering indicators', 'Indicadores de voluntariado'),
    'Agentes IA e governança de aprendizados': ('AI agents and learning governance', 'Agentes IA y gobernanza de aprendizajes'),
    'Manutenção do banco de dados': ('Database maintenance', 'Mantenimiento de la base de datos'),

    # ---------------- Governança de aprendizados
    'Governança de aprendizados': ('Learning governance', 'Gobernanza de aprendizajes'),
    'O Agente Gerente Técnico percebe as mudanças da plataforma e ensina os agentes de teste. Aqui você audita, revoga e limpa esses aprendizados.': (
        'The Technical Manager Agent notices platform changes and teaches the test agents. Here you audit, revoke and clean up these learnings.',
        'El Agente Gerente Técnico percibe los cambios de la plataforma y enseña a los agentes de prueba. Aquí usted audita, revoca y limpia esos aprendizajes.'),
    'Aprender agora': ('Learn now', 'Aprender ahora'), 'Aplicados': ('Applied', 'Aplicados'), 'Pendentes de aprovação': ('Pending approval', 'Pendientes de aprobación'),
    'Revogados': ('Revoked', 'Revocados'), 'Rejeitados': ('Rejected', 'Rechazados'), 'Última detecção': ('Last detection', 'Última detección'), 'novo(s)': ('new', 'nuevo(s)'),
    'Aprendizados de detecção interna são aplicados automaticamente (e podem ser revogados). Os que vêm de fontes oficiais da internet ficam pendentes até um administrador aprovar.': (
        'Internally detected learnings are applied automatically (and can be revoked). Those from official internet sources stay pending until an administrator approves them.',
        'Los aprendizajes de detección interna se aplican automáticamente (y pueden revocarse). Los que vienen de fuentes oficiales de internet quedan pendientes hasta que un administrador los apruebe.'),
    'Aprendizados': ('Learnings', 'Aprendizajes'), 'Aprendizado': ('Learning', 'Aprendizaje'), 'Agentes': ('Agents', 'Agentes'), 'Origem': ('Source', 'Origen'),
    'Código': ('Code', 'Código'), 'Criado em': ('Created on', 'Creado el'), 'Usos': ('Uses', 'Usos'), 'Todos os agentes': ('All agents', 'Todos los agentes'),
    'Exportar CSV': ('Export CSV', 'Exportar CSV'), 'Exportar JSON': ('Export JSON', 'Exportar JSON'), 'Exportar trilha (CSV)': ('Export trail (CSV)', 'Exportar registro (CSV)'),
    'Nenhum aprendizado com estes filtros.': ('No learnings with these filters.', 'Ningún aprendizaje con estos filtros.'),
    'Assinatura SHA-256': ('SHA-256 signature', 'Firma SHA-256'), 'Revisado por': ('Reviewed by', 'Revisado por'),
    'Perfil novo': ('New profile', 'Perfil nuevo'), 'Perfil alterado': ('Profile changed', 'Perfil modificado'), 'Perfil removido': ('Profile removed', 'Perfil eliminado'),
    'Rota nova': ('New route', 'Ruta nueva'), 'Rota removida': ('Route removed', 'Ruta eliminada'), 'Linha de base': ('Baseline', 'Línea de base'),
    'Referência oficial': ('Official reference', 'Referencia oficial'),
    'Aplicado': ('Applied', 'Aplicado'), 'Aprovar': ('Approve', 'Aprobar'), 'Rejeitar': ('Reject', 'Rechazar'), 'Revogar': ('Revoke', 'Revocar'), 'Reaplicar': ('Reapply', 'Reaplicar'),
    'Aprovado': ('Approved', 'Aprobado'), 'Rejeitado': ('Rejected', 'Rechazado'), 'Revogado': ('Revoked', 'Revocado'), 'Reaplicado': ('Reapplied', 'Reaplicado'),
    'Criado e aplicado': ('Created and applied', 'Creado y aplicado'), 'Consumido pelo agente': ('Used by agent', 'Usado por el agente'),
    'Limpeza para compliance': ('Compliance clean-up', 'Limpieza por cumplimiento'), 'Busca recusada': ('Search refused', 'Búsqueda rechazada'),
    'Fonte incluída': ('Source added', 'Fuente incluida'), 'Fonte ativada': ('Source enabled', 'Fuente activada'),
    'Fonte desativada': ('Source disabled', 'Fuente desactivada'), 'Fonte removida': ('Source removed', 'Fuente eliminada'),
    'Aprender com fonte oficial': ('Learn from an official source', 'Aprender de una fuente oficial'),
    'O Gerente Técnico só lê páginas HTTPS dos domínios da lista de fontes confiáveis. O resultado fica pendente até a aprovação.': (
        'The Technical Manager only reads HTTPS pages from the trusted-source domains. The result stays pending until approved.',
        'El Gerente Técnico solo lee páginas HTTPS de los dominios de la lista de fuentes confiables. El resultado queda pendiente hasta la aprobación.'),
    'Endereço da página (HTTPS)': ('Page address (HTTPS)', 'Dirección de la página (HTTPS)'), 'Tema': ('Topic', 'Tema'),
    'Ex.: Controle de acesso': ('E.g. Access control', 'Ej.: Control de acceso'), 'Ler e propor': ('Read and propose', 'Leer y proponer'),
    'Fontes confiáveis': ('Trusted sources', 'Fuentes confiables'), 'Incluir': ('Add', 'Incluir'), 'Ativar': ('Enable', 'Activar'), 'Desativar': ('Disable', 'Desactivar'),
    'Remover esta fonte da lista?': ('Remove this source from the list?', '¿Quitar esta fuente de la lista?'),
    'Limpeza de aprendizados (compliance)': ('Learning clean-up (compliance)', 'Limpieza de aprendizajes (cumplimiento)'),
    'Antes de apagar, uma cópia em JSON e CSV é guardada no servidor (instance/agentes_conhecimento/auditoria) e a limpeza fica registrada na trilha de eventos, que não é apagada.': (
        'Before deleting, a JSON and CSV copy is saved on the server (instance/agentes_conhecimento/auditoria) and the clean-up is logged in the event trail, which is never deleted.',
        'Antes de borrar, se guarda una copia en JSON y CSV en el servidor (instance/agentes_conhecimento/auditoria) y la limpieza queda registrada en el registro de eventos, que no se borra.'),
    'O que limpar': ('What to clean up', 'Qué limpiar'), 'Revogados e rejeitados': ('Revoked and rejected', 'Revocados y rechazados'),
    'Criados até uma data': ('Created up to a date', 'Creados hasta una fecha'), 'Do agente': ('From agent', 'Del agente'),
    'Todos os aprendizados (recomeça a linha de base)': ('All learnings (restarts the baseline)', 'Todos los aprendizajes (reinicia la línea de base)'),
    'Até': ('Until', 'Hasta'), 'Para liberar, digite LIMPAR': ('To unlock, type LIMPAR', 'Para habilitar, escriba LIMPAR'),
    'Limpar aprendizados': ('Clean up learnings', 'Limpiar aprendizajes'), 'Trilha de eventos': ('Event trail', 'Registro de eventos'), 'últimos 200': ('last 200', 'últimos 200'),
    'Nenhum evento ainda.': ('No events yet.', 'Aún no hay eventos.'),
    'Aprendizado atualizado: {codigo}': ('Learning updated: {codigo}', 'Aprendizaje actualizado: {codigo}'),
    'Detecção concluída: {n} aprendizado(s) novo(s).': ('Detection finished: {n} new learning(s).', 'Detección concluida: {n} aprendizaje(s) nuevo(s).'),
    'Referência lida e enviada para aprovação: {codigo}': ('Reference read and sent for approval: {codigo}', 'Referencia leída y enviada para aprobación: {codigo}'),
    'Busca recusada: {erro}': ('Search refused: {erro}', 'Búsqueda rechazada: {erro}'),
    'Fonte confiável incluída.': ('Trusted source added.', 'Fuente confiable incluida.'),
    'Informe um domínio válido que ainda não esteja na lista (ex.: docs.python.org).': ('Enter a valid domain not yet on the list (e.g. docs.python.org).', 'Indique un dominio válido que aún no esté en la lista (ej.: docs.python.org).'),
    'Para limpar, digite LIMPAR no campo de confirmação.': ('To clean up, type LIMPAR in the confirmation field.', 'Para limpiar, escriba LIMPAR en el campo de confirmación.'),
    'Informe a data limite da limpeza.': ('Enter the clean-up cut-off date.', 'Indique la fecha límite de la limpieza.'),
    '{n} aprendizado(s) removido(s). Cópia de auditoria: {arquivo}': ('{n} learning(s) removed. Audit copy: {arquivo}', '{n} aprendizaje(s) eliminado(s). Copia de auditoría: {arquivo}'),

    # ---------------- Projetos: regra do Aluno
    'Acesso negado: o Aluno não pode cadastrar projetos.': ('Access denied: students cannot create projects.', 'Acceso denegado: el alumno no puede registrar proyectos.'),
    'Informe o nome do projeto e escolha um grupo válido.': ('Enter the project name and choose a valid group.', 'Indique el nombre del proyecto y elija un grupo válido.'),

    # ---------------- Menu do topo e Painel Geral (gráficos personalizáveis)
    'Aprendizagem': ('Learning', 'Aprendizaje'), 'Projetos e TCC': ('Projects & final papers', 'Proyectos y TCC'),
    'Pessoas': ('People', 'Personas'), 'Programa': ('Programme', 'Programa'), 'Sistema': ('System', 'Sistema'),
    'Personalizar gráficos': ('Customise charts', 'Personalizar gráficos'), 'Meus gráficos': ('My charts', 'Mis gráficos'),
    'Troque o tipo de cada gráfico no seletor ou escolha outros dados em Personalizar gráficos.': (
        'Change each chart type in its selector or pick other data in Customise charts.',
        'Cambie el tipo de cada gráfico en su selector o elija otros datos en Personalizar gráficos.'),
    'Escolha até 4 gráficos: o dado, o tipo de gráfico e a cor. A escolha fica salva no seu perfil.': (
        'Pick up to 4 charts: the data, the chart type and the colour. Your choice is saved to your profile.',
        'Elija hasta 4 gráficos: el dato, el tipo de gráfico y el color. La elección queda guardada en su perfil.'),
    'Adicionar gráfico': ('Add chart', 'Añadir gráfico'), 'Restaurar padrão': ('Restore default', 'Restaurar predeterminado'),
    'Salvar gráficos': ('Save charts', 'Guardar gráficos'), 'Dado': ('Data', 'Dato'), 'Tipo de gráfico': ('Chart type', 'Tipo de gráfico'),
    'Cor': ('Colour', 'Color'), 'Remover': ('Remove', 'Quitar'),
    'Gráficos salvos.': ('Charts saved.', 'Gráficos guardados.'), 'Não foi possível salvar os gráficos.': ('The charts could not be saved.', 'No se pudieron guardar los gráficos.'),
    'Escolha pelo menos um gráfico válido.': ('Pick at least one valid chart.', 'Elija al menos un gráfico válido.'),
    'Personalize os gráficos: escolha os dados, o tipo (barras, linhas, pizza, rosca, radar...) e as cores. A escolha fica salva no seu perfil.': (
        'Customise the charts: pick the data, the type (bars, lines, pie, doughnut, radar...) and the colours. Your choice is saved to your profile.',
        'Personalice los gráficos: elija los datos, el tipo (barras, líneas, torta, dona, radar...) y los colores. La elección queda guardada en su perfil.'),
    'Misto (barras + linha)': ('Mixed (bars + line)', 'Mixto (barras + línea)'), 'Barras': ('Bars', 'Barras'),
    'Barras horizontais': ('Horizontal bars', 'Barras horizontales'), 'Barras empilhadas': ('Stacked bars', 'Barras apiladas'),
    'Linhas': ('Lines', 'Líneas'), 'Área': ('Area', 'Área'), 'Pizza': ('Pie', 'Torta'), 'Rosca': ('Doughnut', 'Dona'),
    'Polar': ('Polar', 'Polar'), 'Radar': ('Radar', 'Radar'),
    'Cursos': ('Courses', 'Cursos'), 'Horas': ('Hours', 'Horas'), 'Cursos por status': ('Courses by status', 'Cursos por estado'),
    'Saúde dos cursos': ('Course health', 'Salud de los cursos'), 'Saudáveis': ('Healthy', 'Saludables'),
    'Em atenção': ('Needs attention', 'En atención'), 'Em risco': ('At risk', 'En riesgo'),
    'Certificação dos cursos finalizados': ('Certification of completed courses', 'Certificación de los cursos finalizados'),
    'Carga horária por tipo de curso': ('Workload by course type', 'Carga horaria por tipo de curso'),
    'Projetos (TCC) por status': ('Projects (final paper) by status', 'Proyectos (TCC) por estado'),
    'Progresso por curso': ('Progress by course', 'Progreso por curso'), 'Progresso médio por aluno': ('Average progress by student', 'Progreso medio por alumno'),
    'Minhas horas de voluntariado por mês': ('My volunteering hours by month', 'Mis horas de voluntariado por mes'),
    'Finalizado': ('Completed', 'Finalizado'), 'Parado': ('Stalled', 'Detenido'),

    # ---------------- Administração › Agentes IA
    'Agentes IA': ('AI Agents', 'Agentes IA'), 'Agentes de IA': ('AI agents', 'Agentes de IA'), 'Agente': ('Agent', 'Agente'),
    'Agente Gestor': ('Manager Agent', 'Agente Gestor'), 'Gerente Técnico': ('Technical Manager', 'Gerente Técnico'),
    'O Agente Gerente Técnico coordena os agentes de teste, aprende as mudanças da plataforma e distribui os aprendizados: cada perfil é testado de ponta a ponta, ao vivo, com relatório em PDF na pasta do perfil.': (
        "The Technical Manager Agent coordinates the test agents, learns platform changes and distributes the learnings: each profile is tested end to end, live, with a PDF report in the profile's folder.",
        'El Agente Gerente Técnico coordina los agentes de prueba, aprende los cambios de la plataforma y distribuye los aprendizajes: cada perfil se prueba de punta a punta, en vivo, con informe en PDF en la carpeta del perfil.'), 'Gestor B2B': ('B2B Manager', 'Gestor B2B'),
    'Agentes Teste Fim a Fim': ('End-to-end test agents', 'Agentes de prueba de punta a punta'),
    'Agentes Teste de Segurança': ('Security test agents', 'Agentes de prueba de seguridad'),
    'Relatórios de Testes Fim a Fim e Evidencias': ('End-to-end test reports and evidence', 'Informes de pruebas de punta a punta y evidencias'),
    'Relatórios de Testes de Segurança': ('Security test reports', 'Informes de pruebas de seguridad'),
    'Prompt de correção LLM': ('LLM fix prompt', 'Prompt de corrección LLM'),
    'O Agente Gestor coordena os agentes de teste: cada perfil é testado de ponta a ponta, ao vivo, e o relatório em PDF com as evidências vai para a pasta do perfil.': (
        "The Manager Agent coordinates the test agents: each profile is tested end to end, live, and the PDF report with the evidence goes to the profile's folder.",
        'El Agente Gestor coordina los agentes de prueba: cada perfil se prueba de punta a punta, en vivo, y el informe en PDF con las evidencias va a la carpeta del perfil.'),
    'Este servidor não tem o Playwright instalado: rode os agentes num computador com o Playwright.': (
        'This server does not have Playwright installed: run the agents on a computer with Playwright.',
        'Este servidor no tiene Playwright instalado: ejecute los agentes en una computadora con Playwright.'),
    'Estrutura': ('Structure', 'Estructura'), 'em breve': ('coming soon', 'próximamente'), 'vazia': ('empty', 'vacía'),
    'Modo escrita (cria e apaga dados de teste)': ('Write mode (creates and deletes test data)', 'Modo escritura (crea y borra datos de prueba)'),
    'Iniciar testes fim a fim': ('Start end-to-end tests', 'Iniciar pruebas de punta a punta'), 'Parar': ('Stop', 'Detener'),
    'Painel ao vivo dos agentes': ('Live agent panel', 'Panel en vivo de los agentes'),
    'Aguardando o início dos testes.': ('Waiting for the tests to start.', 'Esperando el inicio de las pruebas.'),
    'Navegador do agente em execução': ("Running agent's browser", 'Navegador del agente en ejecución'),
    'Nenhum teste em execução. O navegador do agente aparece aqui ao vivo.': (
        "No test running. The agent's browser shows up here live.", 'Ninguna prueba en ejecución. El navegador del agente aparece aquí en vivo.'),
    'Etapa atual': ('Current step', 'Etapa actual'), 'Relatórios desta execução': ('Reports from this run', 'Informes de esta ejecución'),
    'Perfil': ('Profile', 'Perfil'), 'Nenhuma execução ainda.': ('No runs yet.', 'Ninguna ejecución todavía.'),
    'aguardando': ('waiting', 'esperando'), 'testando…': ('testing…', 'probando…'), 'concluído': ('done', 'concluido'),
    'com falhas': ('with failures', 'con fallas'), 'erro': ('error', 'error'), 'Teste Fim a Fim': ('End-to-end test', 'Prueba de punta a punta'),
    'Executando': ('Running', 'Ejecutando'), 'Testes concluídos.': ('Tests finished.', 'Pruebas concluidas.'),
    'Execução interrompida.': ('Run stopped.', 'Ejecución interrumpida.'), 'aprovados': ('passed', 'aprobados'),
    'falhas': ('failures', 'fallas'), 'alertas': ('warnings', 'alertas'),
    'Agente Gestor iniciado: os testes começam pelo Administrador.': ('Manager Agent started: tests begin with the Administrator.', 'Agente Gestor iniciado: las pruebas empiezan por el Administrador.'),
    'Já existe uma execução em andamento.': ('A run is already in progress.', 'Ya hay una ejecución en curso.'),
    'Arquivo não encontrado.': ('File not found.', 'Archivo no encontrado.'),
    'Preparando o navegador do agente…': ("Preparing the agent's browser…", 'Preparando el navegador del agente…'),
    'Progresso por agente': ('Progress by agent', 'Progreso por agente'), 'Execução total': ('Whole run', 'Ejecución total'),
    'Tempo estimado pelas execuções anteriores de cada agente.': ("Time estimated from each agent's previous runs.", 'Tiempo estimado por las ejecuciones anteriores de cada agente.'),
    'restantes': ('left', 'restantes'), 'estimado': ('estimated', 'estimado'), 'concluído em': ('done in', 'concluido en'),
    'fora desta execução': ('not in this run', 'fuera de esta ejecución'),
    'Agentes IA: o Agente Gestor coordena os agentes de teste de cada perfil e mostra os testes ao vivo.': (
        "AI Agents: the Manager Agent coordinates each profile's test agent and shows the tests live.", 'Agentes IA: el Agente Gestor coordina los agentes de prueba de cada perfil y muestra las pruebas en vivo.'),
    'Escolha os perfis e inicie: os testes começam sempre pelo Administrador e seguem a ordem.': (
        'Pick the profiles and start: tests always begin with the Administrator and follow the order.', 'Elija los perfiles e inicie: las pruebas siempre empiezan por el Administrador y siguen el orden.'),
    'No centro aparece o navegador do agente em execução, ao vivo.': ("The running agent's browser shows up live in the center.", 'En el centro aparece el navegador del agente en ejecución, en vivo.'),
    'Cada robô é o agente de um perfil: brilha enquanto testa e recebe ✓ ou ✗ ao terminar.': (
        "Each robot is a profile's agent: it glows while testing and gets ✓ or ✗ when done.", 'Cada robot es el agente de un perfil: brilla mientras prueba y recibe ✓ o ✗ al terminar.'),
    'Os relatórios em PDF com as evidências e os prompts de correção ficam nestas pastas, separados por perfil.': (
        'The PDF reports with evidence and the fix prompts are in these folders, by profile.', 'Los informes en PDF con las evidencias y los prompts de corrección están en estas carpetas, por perfil.'),

    # ---------------- Manutenção (DB): backups, agendamentos e auditoria
    'Acompanhe a saúde dos backups, mantenha vários agendamentos em paralelo e restaure o banco quando precisar.': (
        'Track backup health, keep several schedules running in parallel and restore the database when needed.',
        'Siga la salud de los respaldos, mantenga varias programaciones en paralelo y restaure la base cuando lo necesite.'),
    'Saúde dos Backups': ('Backup Health', 'Salud de los Respaldos'), 'Atualizar': ('Refresh', 'Actualizar'),
    'Agendamentos ativos': ('Active schedules', 'Programaciones activas'), 'Pausados': ('Paused', 'Pausadas'),
    'Último backup': ('Last backup', 'Último respaldo'), 'Próximo backup': ('Next backup', 'Siguiente respaldo'),
    'Falhas registradas': ('Failures logged', 'Fallas registradas'), 'Situação': ('Status', 'Situación'),
    'Saudável': ('Healthy', 'Saludable'), 'Atenção': ('Warning', 'Atención'), 'Crítica': ('Critical', 'Crítica'),
    'O último backup falhou.': ('The last backup failed.', 'El último respaldo falló.'),
    'Nenhum agendamento ativo.': ('No active schedule.', 'Ninguna programación activa.'),
    'Nenhum backup bem-sucedido nos últimos 8 dias.': ('No successful backup in the last 8 days.', 'Ningún respaldo exitoso en los últimos 8 días.'),
    'Agendamentos': ('Schedules', 'Programaciones'), 'Agendamento': ('Schedule', 'Programación'),
    'Clique em uma linha para editar, executar, pausar ou excluir.': ('Click a row to edit, run, pause or delete.', 'Haga clic en una fila para editar, ejecutar, pausar o eliminar.'),
    '+ Novo agendamento': ('+ New schedule', '+ Nueva programación'), 'Novo agendamento': ('New schedule', 'Nueva programación'),
    'Criar agendamento': ('Create schedule', 'Crear programación'), 'Frequência': ('Frequency', 'Frecuencia'),
    'Diário': ('Daily', 'Diario'), 'Semanal': ('Weekly', 'Semanal'), 'Mensal': ('Monthly', 'Mensual'),
    'Última execução': ('Last run', 'Última ejecución'), 'Próxima execução': ('Next run', 'Próxima ejecución'),
    'Ainda não executado': ('Not run yet', 'Aún no ejecutado'), 'Retenção': ('Retention', 'Retención'), 'Últimos': ('Last', 'Últimos'),
    'Retenção (arquivos)': ('Retention (files)', 'Retención (archivos)'), 'Pasta': ('Folder', 'Carpeta'),
    'Os mais antigos deste agendamento são apagados.': ("This schedule's oldest files are deleted.", 'Se borran los más antiguos de esta programación.'),
    'Data de início': ('Start date', 'Fecha de inicio'), 'Horário': ('Time', 'Horario'),
    'Nenhum agendamento. Crie um para os backups rodarem sozinhos.': ('No schedules. Create one so backups run on their own.', 'Ninguna programación. Cree una para que los respaldos se ejecuten solos.'),
    'No PythonAnywhere os agendamentos rodam pela tarefa de hora em hora (tarefas_agendadas.py); com o app aberto no computador, rodam no horário.': (
        'On PythonAnywhere, schedules run through the hourly task (tarefas_agendadas.py); with the app open on a computer, they run on time.',
        'En PythonAnywhere las programaciones se ejecutan con la tarea de cada hora (tarefas_agendadas.py); con la app abierta en la computadora, a la hora indicada.'),
    'Ver registro de alterações dos agendamentos': ('See the schedule change log', 'Ver el registro de cambios de las programaciones'),
    'Relatório de alterações (CSV)': ('Change report (CSV)', 'Informe de cambios (CSV)'), 'Nenhuma alteração registrada.': ('No changes logged.', 'Ningún cambio registrado.'),
    'Data/Hora': ('Date/Time', 'Fecha/Hora'), 'Detalhes': ('Details', 'Detalles'), 'sistema': ('system', 'sistema'),
    'Criado por': ('Created by', 'Creado por'), 'Executar agora': ('Run now', 'Ejecutar ahora'), 'Pausar': ('Pause', 'Pausar'), 'Retomar': ('Resume', 'Reanudar'),
    'Criado': ('Created', 'Creado'), 'Editado': ('Edited', 'Editado'), 'Pausado': ('Paused', 'Pausado'), 'Retomado': ('Resumed', 'Reanudado'),
    'Excluído': ('Deleted', 'Eliminado'), 'Executado manualmente': ('Run manually', 'Ejecutado manualmente'), 'Migrado': ('Migrated', 'Migrado'),
    'Excluir este agendamento? Os arquivos já gerados continuam na pasta.': ('Delete this schedule? Files already created stay in the folder.', '¿Eliminar esta programación? Los archivos ya generados siguen en la carpeta.'),
    'Backup imediato': ('Immediate backup', 'Respaldo inmediato'), 'Fazer backup': ('Back up now', 'Hacer respaldo'),
    'Gera uma cópia agora e verifica a integridade do arquivo.': ("Creates a copy now and checks the file's integrity.", 'Genera una copia ahora y verifica la integridad del archivo.'),
    'Restaurar backup': ('Restore backup', 'Restaurar respaldo'), 'Restaurar': ('Restore', 'Restaurar'),
    'Escolha um arquivo da lista ou envie um. Uma cópia do banco atual é guardada antes da restauração; agendamentos e histórico de backups são preservados.': (
        'Pick a file from the list or upload one. A copy of the current database is saved before restoring; schedules and backup history are kept.',
        'Elija un archivo de la lista o suba uno. Se guarda una copia de la base actual antes de restaurar; las programaciones y el historial se conservan.'),
    'Restaurar o banco? Os dados atuais serão substituídos pelos do backup (uma cópia de segurança é feita antes).': (
        'Restore the database? Current data will be replaced by the backup (a safety copy is made first).',
        '¿Restaurar la base? Los datos actuales se reemplazarán por los del respaldo (antes se hace una copia de seguridad).'),
    'Backups encontrados': ('Backups found', 'Respaldos encontrados'), 'Ou envie um arquivo .db': ('Or upload a .db file', 'O suba un archivo .db'),
    'Arquivos de backup no servidor': ('Backup files on the server', 'Archivos de respaldo en el servidor'), 'Arquivo': ('File', 'Archivo'),
    'Tamanho': ('Size', 'Tamaño'), 'Duração': ('Duration', 'Duración'), 'Baixar': ('Download', 'Descargar'),
    'Histórico de execuções': ('Run history', 'Historial de ejecuciones'),
    'Backups manuais e automáticos, restaurações, downloads e limpezas. As alterações de configuração ficam no cartão Agendamentos.': (
        'Manual and automatic backups, restores, downloads and clean-ups. Configuration changes are in the Schedules card.',
        'Respaldos manuales y automáticos, restauraciones, descargas y limpiezas. Los cambios de configuración están en la tarjeta Programaciones.'),
    'Limpar filtro': ('Clear filter', 'Limpiar filtro'), 'Relatório para auditoria (CSV)': ('Audit report (CSV)', 'Informe para auditoría (CSV)'),
    'Apagar o histórico? Uma cópia em CSV é guardada no servidor e a limpeza fica registrada.': (
        'Delete the history? A CSV copy is saved on the server and the clean-up is logged.', '¿Borrar el historial? Se guarda una copia en CSV en el servidor y la limpieza queda registrada.'),
    'Nenhum registro no período.': ('No records in this period.', 'Ningún registro en el período.'),
    'Imediato': ('Immediate', 'Inmediato'), 'Agendado': ('Scheduled', 'Programado'), 'Agendado (manual)': ('Scheduled (manual)', 'Programado (manual)'),
    'Restauração': ('Restore', 'Restauración'), 'Segurança (pré-restauração)': ('Safety (before restore)', 'Seguridad (antes de restaurar)'),
    'Segurança (pré-limpeza)': ('Safety (before wipe)', 'Seguridad (antes de borrar)'), 'Limpeza de dados': ('Data wipe', 'Borrado de datos'),
    'Limpeza do histórico': ('History clean-up', 'Limpieza del historial'), 'Download': ('Download', 'Descarga'),
    'Falha': ('Failed', 'Falla'), 'Sucesso': ('Success', 'Éxito'),
    'Atenção: apaga sessões, acompanhamentos, cursos, solicitações e todos os usuários (menos a sua conta). Um backup de segurança é feito antes, e a auditoria é preservada.': (
        'Warning: deletes sessions, tracking, courses, requests and all users (except your account). A safety backup is made first, and the audit trail is kept.',
        'Atención: borra sesiones, seguimientos, cursos, solicitudes y todos los usuarios (menos su cuenta). Antes se hace un respaldo de seguridad y la auditoría se conserva.'),
    'Para liberar, digite APAGAR': ('To unlock, type APAGAR', 'Para habilitar, escriba APAGAR'),
    'Apagar todos os dados': ('Delete all data', 'Borrar todos los datos'), 'Autenticado como:': ('Signed in as:', 'Autenticado como:'),
    'Clique para ordenar': ('Click to sort', 'Haga clic para ordenar'),
    'Saúde dos backups: agendamentos ativos, último e próximo backup, falhas e a situação geral.': (
        'Backup health: active schedules, last and next backup, failures and the overall status.', 'Salud de los respaldos: programaciones activas, último y próximo respaldo, fallas y la situación general.'),
    'Agendamentos: crie vários backups automáticos; clique numa linha para editar, executar, pausar ou excluir. Toda alteração fica registrada.': (
        'Schedules: create several automatic backups; click a row to edit, run, pause or delete. Every change is logged.',
        'Programaciones: cree varios respaldos automáticos; haga clic en una fila para editar, ejecutar, pausar o eliminar. Todo cambio queda registrado.'),
    'Backup imediato: gera uma cópia agora e confere a integridade do arquivo.': ("Immediate backup: creates a copy now and checks the file's integrity.", 'Respaldo inmediato: genera una copia ahora y verifica la integridad del archivo.'),
    'Restaurar: volta o banco a um backup, guardando antes uma cópia do banco atual.': (
        'Restore: returns the database to a backup, saving a copy of the current one first.', 'Restaurar: vuelve la base a un respaldo, guardando antes una copia de la actual.'),
    'Histórico: tudo o que foi executado, com filtro por data e relatório em CSV para auditoria.': (
        'History: everything that ran, with a date filter and a CSV audit report.', 'Historial: todo lo ejecutado, con filtro por fecha e informe en CSV para auditoría.'),
    'Zona de perigo: apagar os dados exige digitar APAGAR e sempre faz um backup de segurança antes.': (
        'Danger zone: deleting data requires typing APAGAR and always makes a safety backup first.', 'Zona de peligro: borrar los datos exige escribir APAGAR y siempre hace un respaldo de seguridad antes.'),
    # Mensagens (flash)
    'Backup concluído e validado: {arquivo}': ('Backup completed and validated: {arquivo}', 'Respaldo concluido y validado: {arquivo}'),
    'O backup falhou: {erro}': ('The backup failed: {erro}', 'El respaldo falló: {erro}'),
    'Confira a frequência, o horário (HH:MM), a data de início e a retenção (1 a 365).': (
        'Check the frequency, time (HH:MM), start date and retention (1 to 365).', 'Revise la frecuencia, el horario (HH:MM), la fecha de inicio y la retención (1 a 365).'),
    'Agendamento criado. Próxima execução: {data}': ('Schedule created. Next run: {data}', 'Programación creada. Próxima ejecución: {data}'),
    'Agendamento atualizado.': ('Schedule updated.', 'Programación actualizada.'), 'Agendamento pausado.': ('Schedule paused.', 'Programación pausada.'),
    'Agendamento retomado.': ('Schedule resumed.', 'Programación reanudada.'),
    'Agendamento excluído. Os arquivos já gerados continuam na pasta.': ('Schedule deleted. Files already created stay in the folder.', 'Programación eliminada. Los archivos ya generados siguen en la carpeta.'),
    'Envie um arquivo .db gerado pelo backup da plataforma.': ("Upload a .db file created by the platform's backup.", 'Suba un archivo .db generado por el respaldo de la plataforma.'),
    'Escolha um backup da lista ou envie um arquivo.': ('Pick a backup from the list or upload a file.', 'Elija un respaldo de la lista o suba un archivo.'),
    'Banco restaurado. A cópia do banco anterior foi guardada em: {arquivo}': ('Database restored. The previous database was saved as: {arquivo}', 'Base restaurada. La copia de la base anterior se guardó en: {arquivo}'),
    'Sua conta não existe no backup restaurado: entre com uma conta desse backup.': (
        'Your account does not exist in the restored backup: sign in with an account from that backup.', 'Su cuenta no existe en el respaldo restaurado: ingrese con una cuenta de ese respaldo.'),
    'Restauração cancelada: {erro}': ('Restore cancelled: {erro}', 'Restauración cancelada: {erro}'),
    'Para apagar os dados, digite APAGAR no campo de confirmação.': ('To delete the data, type APAGAR in the confirmation field.', 'Para borrar los datos, escriba APAGAR en el campo de confirmación.'),
    'Limpeza cancelada: não foi possível fazer o backup de segurança.': ('Wipe cancelled: the safety backup could not be made.', 'Borrado cancelado: no se pudo hacer el respaldo de seguridad.'),
    'Dados apagados. Backup de segurança guardado em: {arquivo}': ('Data deleted. Safety backup saved as: {arquivo}', 'Datos borrados. Respaldo de seguridad guardado en: {arquivo}'),
    'Erro ao apagar os dados: {erro}': ('Error deleting the data: {erro}', 'Error al borrar los datos: {erro}'),
    '{total} registro(s) apagado(s). Cópia em CSV guardada em: auditoria/{arquivo}': ('{total} record(s) deleted. CSV copy saved in: auditoria/{arquivo}', '{total} registro(s) borrado(s). Copia en CSV guardada en: auditoria/{arquivo}'),
    'Arquivo de backup não encontrado.': ('Backup file not found.', 'Archivo de respaldo no encontrado.'),

    # ---------------- Manutenção (DB)
    'Padrão: Backup_repository': ('Default: Backup_repository', 'Predeterminado: Backup_repository'),
    # ---------------- Administração › Agentes de Segurança
    'Agentes de Segurança': ('Security Agents', 'Agentes de Seguridad'),
    'Agentes de testes fim a fim': ('End-to-end test agents', 'Agentes de pruebas de punta a punta'),
    'Abrir': ('Open', 'Abrir'),
    'Gerente de Segurança': ('Security Manager', 'Gerente de Seguridad'),
    'Especialistas': ('Specialists', 'Especialistas'),
    'Consolidado': ('Consolidated', 'Consolidado'),
    'Relatórios de Testes de Segurança': ('Security Test Reports', 'Informes de Pruebas de Seguridad'),
    'Agente Configuração e Segredos': ('Configuration and Secrets Agent', 'Agente Configuración y Secretos'),
    'Agente Inconsistências de Dados': ('Data Inconsistencies Agent', 'Agente Inconsistencias de Datos'),
    'Agente Análise de Código': ('Code Analysis Agent', 'Agente Análisis de Código'),
    'Agente Dependências e Tecnologias': ('Dependencies and Technologies Agent', 'Agente Dependencias y Tecnologías'),
    'Agente Pentest': ('Pentest Agent', 'Agente Pentest'),
    'Configuração e Segredos': ('Configuration and Secrets', 'Configuración y Secretos'),
    'Inconsistências de Dados': ('Data Inconsistencies', 'Inconsistencias de Datos'),
    'Análise de Código (SAST)': ('Code Analysis (SAST)', 'Análisis de Código (SAST)'),
    'Dependências e Tecnologias (SCA)': ('Dependencies and Technologies (SCA)', 'Dependencias y Tecnologías (SCA)'),
    'Pentest (DAST)': ('Pentest (DAST)', 'Pentest (DAST)'),
    'Chaves secretas, modo debug, cookies, CSRF, cabeçalhos de segurança e segredos esquecidos no código.': (
        'Secret keys, debug mode, cookies, CSRF, security headers and secrets left in the code.',
        'Claves secretas, modo debug, cookies, CSRF, cabeceras de seguridad y secretos olvidados en el código.'),
    'Senhas e respostas de segurança mal guardadas, contas de teste, perfis e vínculos inconsistentes, integridade do banco.': (
        'Poorly stored passwords and security answers, test accounts, inconsistent profiles and links, database integrity.',
        'Contraseñas y respuestas de seguridad mal guardadas, cuentas de prueba, perfiles y vínculos inconsistentes, integridad de la base.'),
    'Funções perigosas, SQL montado com texto, rotas sem login, XSS nos templates e código mal escrito.': (
        'Dangerous functions, SQL built from text, routes without login, XSS in templates and poorly written code.',
        'Funciones peligrosas, SQL armado con texto, rutas sin login, XSS en las plantillas y código mal escrito.'),
    'Vulnerabilidades conhecidas (OSV.dev) do Python, Flask, bibliotecas e CDNs; pacotes descontinuados e SRI.': (
        'Known vulnerabilities (OSV.dev) in Python, Flask, libraries and CDNs; discontinued packages and SRI.',
        'Vulnerabilidades conocidas (OSV.dev) de Python, Flask, bibliotecas y CDN; paquetes descontinuados y SRI.'),
    'Ataques controlados na plataforma em execução: XSS, SQL injection, IDOR, CSRF, força bruta, sessão e redirecionamento.': (
        'Controlled attacks on the running platform: XSS, SQL injection, IDOR, CSRF, brute force, session and redirects.',
        'Ataques controlados a la plataforma en ejecución: XSS, inyección SQL, IDOR, CSRF, fuerza bruta, sesión y redirecciones.'),
    'O Gerente de Segurança coordena 5 especialistas em cibersegurança: procuram dados inconsistentes, analisam o código, verificam as vulnerabilidades das tecnologias e fazem testes de invasão controlados. No fim, gera relatórios em PDF e prompts de correção para qualquer LLM.': (
        'The Security Manager coordinates 5 cybersecurity specialists: they look for inconsistent data, analyze the code, check the vulnerabilities of the technologies and run controlled penetration tests. At the end, it generates PDF reports and fix prompts for any LLM.',
        'El Gerente de Seguridad coordina 5 especialistas en ciberseguridad: buscan datos inconsistentes, analizan el código, verifican las vulnerabilidades de las tecnologías y hacen pruebas de intrusión controladas. Al final, genera informes en PDF y prompts de corrección para cualquier LLM.'),
    'O Agente Pentest só ataca a plataforma em ambiente local ou de teste (localhost, *.test). Neste endereço ele registra a verificação como não realizada; os outros agentes rodam normalmente.': (
        'The Pentest Agent only attacks the platform in a local or test environment (localhost, *.test). At this address it records the check as not performed; the other agents run normally.',
        'El Agente Pentest solo ataca la plataforma en un entorno local o de prueba (localhost, *.test). En esta dirección registra la verificación como no realizada; los demás agentes se ejecutan normalmente.'),
    'Sem o Playwright neste servidor, os relatórios saem só como prompt (.md), sem o PDF.': (
        'Without Playwright on this server, reports are produced only as a prompt (.md), without the PDF.',
        'Sin Playwright en este servidor, los informes salen solo como prompt (.md), sin el PDF.'),
    'Referências: OWASP Top 10 (2021), CWE/MITRE e a base de vulnerabilidades OSV.dev, consultada só se estiver nas Fontes confiáveis.': (
        'References: OWASP Top 10 (2021), CWE/MITRE and the OSV.dev vulnerability database, queried only if it is in the Trusted sources.',
        'Referencias: OWASP Top 10 (2021), CWE/MITRE y la base de vulnerabilidades OSV.dev, consultada solo si está en las Fuentes confiables.'),
    'Iniciar auditoria de segurança': ('Start security audit', 'Iniciar auditoría de seguridad'),
    'Painel ao vivo dos agentes de segurança': ('Live panel of the security agents', 'Panel en vivo de los agentes de seguridad'),
    'Aguardando o início da auditoria.': ('Waiting for the audit to start.', 'Esperando el inicio de la auditoría.'),
    'Nota de risco: soma ponderada das vulnerabilidades (Crítica 25, Alta 10, Média 4, Baixa 1), limitada a 100.': (
        'Risk score: weighted sum of the vulnerabilities (Critical 25, High 10, Medium 4, Low 1), capped at 100.',
        'Nota de riesgo: suma ponderada de las vulnerabilidades (Crítica 25, Alta 10, Media 4, Baja 1), limitada a 100.'),
    'Risco': ('Risk', 'Riesgo'),
    'Média': ('Medium', 'Media'),
    'Baixa': ('Low', 'Baja'),
    'Nenhuma auditoria em execução. As verificações e as vulnerabilidades aparecem aqui ao vivo.': (
        'No audit running. Checks and vulnerabilities appear here live.', 'Ninguna auditoría en ejecución. Las verificaciones y las vulnerabilidades aparecen aquí en vivo.'),
    'Resultado consolidado': ('Consolidated result', 'Resultado consolidado'),
    'O resultado aparece ao final da auditoria.': ('The result appears at the end of the audit.', 'El resultado aparece al final de la auditoría.'),
    'Registro do Gerente de Segurança': ('Security Manager log', 'Registro del Gerente de Seguridad'),
    'varrendo…': ('scanning…', 'escaneando…'),
    'sem falhas graves': ('no serious flaws', 'sin fallas graves'),
    'vulnerável': ('vulnerable', 'vulnerable'),
    'Auditando': ('Auditing', 'Auditando'),
    'Auditoria concluída.': ('Audit completed.', 'Auditoría concluida.'),
    'verificações': ('checks', 'verificaciones'),
    'Preparando o agente…': ('Preparing the agent…', 'Preparando el agente…'),
    'Corrigir primeiro': ('Fix first', 'Corregir primero'),
    'Nenhuma vulnerabilidade crítica ou alta.': ('No critical or high vulnerabilities.', 'Ninguna vulnerabilidad crítica o alta.'),
    'Gerente de Segurança iniciado: a auditoria começa pela configuração.': (
        'Security Manager started: the audit begins with the configuration.', 'Gerente de Seguridad iniciado: la auditoría empieza por la configuración.'),
    'Agentes de Segurança: o Gerente de Segurança coordena 5 especialistas em cibersegurança e mostra a auditoria ao vivo.': (
        'Security Agents: the Security Manager coordinates 5 cybersecurity specialists and shows the audit live.',
        'Agentes de Seguridad: el Gerente de Seguridad coordina 5 especialistas en ciberseguridad y muestra la auditoría en vivo.'),
    'Escolha os agentes e inicie a auditoria: o pentest só ataca a própria plataforma em ambiente local ou de teste.': (
        'Choose the agents and start the audit: the pentest only attacks the platform itself in a local or test environment.',
        'Elija los agentes e inicie la auditoría: el pentest solo ataca la propia plataforma en un entorno local o de prueba.'),
    'No centro, o console mostra ao vivo cada verificação e cada vulnerabilidade encontrada.': (
        'In the center, the console shows every check and every vulnerability found, live.',
        'En el centro, la consola muestra en vivo cada verificación y cada vulnerabilidad encontrada.'),
    'Cada escudo é um agente especialista: fica verde se não achou nada grave e vermelho se encontrou vulnerabilidade crítica ou alta.': (
        'Each shield is a specialist agent: it turns green if nothing serious was found and red if it found a critical or high vulnerability.',
        'Cada escudo es un agente especialista: queda verde si no encontró nada grave y rojo si encontró una vulnerabilidad crítica o alta.'),
    'O resultado consolidado traz a nota de risco, as prioridades e o PDF e o prompt de correção para qualquer LLM.': (
        'The consolidated result shows the risk score, the priorities and the PDF and fix prompt for any LLM.',
        'El resultado consolidado trae la nota de riesgo, las prioridades y el PDF y el prompt de corrección para cualquier LLM.'),
    'Os relatórios em PDF e os prompts de correção ficam nestas pastas, uma por agente de segurança.': (
        'The PDF reports and the fix prompts are kept in these folders, one per security agent.',
        'Los informes en PDF y los prompts de corrección quedan en estas carpetas, una por agente de seguridad.'),
    # ---------------- Proteções web (seguranca_web.py)
    'Muitas tentativas seguidas. Aguarde um minuto e tente de novo.': (
        'Too many attempts in a row. Wait a minute and try again.', 'Demasiados intentos seguidos. Espere un minuto e inténtelo de nuevo.'),
    'A página expirou ou o pedido não veio da plataforma. Recarregue a página e tente de novo.': (
        'The page expired or the request did not come from the platform. Reload the page and try again.',
        'La página expiró o la solicitud no vino de la plataforma. Recargue la página e inténtelo de nuevo.'),
    'Desculpe, o assistente está indisponível agora. Tente de novo em alguns minutos.': (
        'Sorry, the assistant is unavailable right now. Try again in a few minutes.',
        'Lo sentimos, el asistente no está disponible ahora. Inténtelo de nuevo en unos minutos.'),
}

# Montados uma vez: {'en': {pt: en}, 'es': {pt: es}}
_POR_IDIOMA = {'en': {pt: v[0] for pt, v in LITERAIS.items()}, 'es': {pt: v[1] for pt, v in LITERAIS.items()}}


def tt(texto, idioma='pt'):
    """Traduz um texto das telas antigas pelo próprio texto em português (sem tradução, devolve o original)."""
    if not isinstance(texto, str) or idioma not in _POR_IDIOMA:
        return texto
    return _POR_IDIOMA[idioma].get(texto, _POR_IDIOMA[idioma].get(texto.strip(), texto))
