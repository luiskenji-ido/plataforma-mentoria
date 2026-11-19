# Publicar num servidor Ubuntu 24.04 (servidor próprio ou máquina virtual na AWS, GCP ou Azure)

Tudo funciona neste tipo de hospedagem: telas, arquivos, backups, lembretes, agentes e Orquestrador.
O passo a passo completo está no ReadME, seção "Instalação em servidor Ubuntu 24.04". Resumo:

1. Pacotes, usuário `mentoria`, código em `/srv/mentoria`, ambiente virtual e `pip install -r requirements.txt`.
2. Pasta de backups: `sudo mkdir -p /var/backups/mentoria && sudo chown mentoria: /var/backups/mentoria`.
3. `sudo -u mentoria .venv/bin/python instalar.py` — escolha a hospedagem e o banco; rode o comando que ele mostrar
   para criar o banco e o usuário e rode o instalador de novo.
4. Serviços: copie `mentoria.service` e `mentoria-tarefas.*` para `/etc/systemd/system/` e
   `sudo systemctl daemon-reload && sudo systemctl enable --now mentoria mentoria-tarefas.timer`.
5. nginx e HTTPS: `nginx-mentoria.conf` em `/etc/nginx/sites-available/mentoria` e `sudo certbot --nginx -d <domínio>`.
   As gravações das reuniões ficam em `/srv/mentoria/uploads/reunioes/` (até 100 MB cada, no padrão): a gestão ajusta
   o limite em Parâmetros de regras conforme o disco; ao mudar, ajuste também o `client_max_body_size` da rota da gravação.
   Os vídeos e materiais das aulas dos cursos ficam em `/srv/mentoria/uploads/aulas/` (vídeo até 100 MB, no padrão, em
   Parâmetros de regras › Conteúdo dos cursos); a rota do conteúdo do curso tem o próprio `client_max_body_size` no nginx.
6. Entre como Administrador: preencha **Identidade da instituição** e confira **Ambiente e compatibilidade**.

Arquivos desta pasta: `mentoria.service` (gunicorn), `mentoria-tarefas.service` + `.timer` (de hora em hora),
`nginx-mentoria.conf` e `env.exemplo` (modelo do .env, caso não use o instalador).
