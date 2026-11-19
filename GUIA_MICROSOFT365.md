# Conectar a plataforma ao Microsoft 365 (Outlook e Agenda)

Guia para a equipe de TI da empresa. Leva uns 10 minutos.

## O que a plataforma faz com a conta Microsoft

- Cada pessoa conecta a **própria conta corporativa** pelo login oficial da Microsoft. A senha fica só com a Microsoft. A plataforma guarda apenas os tokens de acesso, cifrados.
- **Reuniões da instituição × B2B:** o convite vira um **evento na agenda do Outlook** de quem organiza.
  - O Outlook envia o convite aos participantes, com aceitar e recusar.
  - Remarcações atualizam o mesmo evento.
  - Reunião on-line sem link ganha uma sala do **Teams**.
- **Acompanhamento e sessões de mentoria:** prazos e sessões vão para a agenda do Outlook.
- Permissões pedidas, todas **delegadas** (em nome da própria pessoa, nunca da empresa inteira):

| Permissão | Para quê |
|---|---|
| `User.Read` | nome e e-mail da conta conectada |
| `Calendars.ReadWrite` | criar e atualizar eventos na agenda da pessoa |
| `offline_access` | renovar o acesso sem pedir login de novo |
| `openid`, `profile`, `email` | login |

A plataforma **não lê e-mails** e **não envia e-mail** pela conta da pessoa.

## 1. Registrar o aplicativo no Microsoft Entra ID

1. Acesse **https://entra.microsoft.com** com uma conta de administrador.
2. Vá em **Identidade › Aplicativos › Registros de aplicativo › Novo registro**.
3. Preencha:
   - **Nome:** o nome da plataforma cadastrado em Identidade da instituição (é o nome que as pessoas verão no login).
   - **Tipos de conta com suporte:** *Contas em qualquer diretório organizacional (qualquer locatário do Microsoft Entra ID, multilocatário)*. Assim, cada empresa parceira B2B pode entrar com o próprio Microsoft 365.
     - Se a plataforma for usada por uma só empresa, escolha *Somente contas deste diretório organizacional*.
   - **URI de redirecionamento:** plataforma **Web**, com o endereço `https://luiskenjiido.pythonanywhere.com/oauth-microsoft/callback`.
     - Para testes no computador, acrescente depois (em **Autenticação**) `http://localhost:5000/oauth-microsoft/callback`.
4. Clique em **Registrar** e copie o **ID do aplicativo (cliente)**.

## 2. Criar o segredo do aplicativo

1. No aplicativo, abra **Certificados e segredos › Segredos do cliente › Novo segredo do cliente**.
2. Descrição: `Plataforma Mentoria`. Validade: 24 meses. Anote a data de vencimento para renovar antes.
3. Copie o **Valor** na hora: ele só aparece uma vez. O "ID do segredo" não serve.

## 3. Permissões

1. Abra **Permissões de API › Adicionar uma permissão › Microsoft Graph › Permissões delegadas**.
2. Marque `User.Read`, `Calendars.ReadWrite`, `offline_access`, `openid`, `profile` e `email`.
3. Clique em **Conceder consentimento do administrador para <sua empresa>**. Sem isso, as pessoas veem *"Precisa da aprovação do administrador"*.

### Empresas parceiras com outro Microsoft 365

O administrador do Microsoft 365 de cada parceiro aprova uma única vez:

1. Entra na plataforma e abre **Conectar Microsoft 365**.
2. Na tela da Microsoft, marca **Consentir em nome da sua organização** e aceita.

Depois disso, todas as pessoas daquela empresa conectam sem pedir aprovação.

## 4. Cadastrar na plataforma

1. Entre como **Administrador** e abra **Administração › Provedores de IA e custos**.
2. Abra o quadro **Credenciais dos agentes e integrações** e preencha:
   - **ID do aplicativo Microsoft 365:** o ID copiado no passo 1.
   - **Segredo do aplicativo Microsoft 365:** o valor copiado no passo 2.
   - **Locatário Microsoft 365:** deixe `organizations` para aceitar qualquer empresa, ou informe o ID do locatário (Entra › Visão geral) para aceitar só a sua.
3. Clique em **Salvar credenciais**. Os valores ficam cifrados e não voltam a aparecer na tela.

Também funciona pelo `.env` do servidor, com as variáveis `MS365_CLIENT_ID`, `MS365_CLIENT_SECRET` e `MS365_TENANT`.

## 5. Como as pessoas usam

- **Acompanhamento:** na lista **Agenda**, escolher **Microsoft 365 (Outlook)** e fazer o login.
- **Reuniões da instituição × B2B:** na lista **Contas conectadas**, escolher **Microsoft 365 (Outlook)**. Depois, no convite, escolher **Enviar por: Microsoft 365 / Outlook**.
- Para desconectar, use a mesma lista.

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| "A conexão com o Microsoft 365 ainda não foi configurada" | Cadastrar o ID e o segredo (passo 4). |
| "Precisa da aprovação do administrador" ou "A empresa precisa aprovar o aplicativo" | Consentimento do administrador (passo 3). |
| AADSTS50011 (endereço de retorno não corresponde) | A URI do passo 1 precisa ser exatamente `https://…/oauth-microsoft/callback`. |
| AADSTS7000215 (segredo inválido) | O segredo venceu ou foi copiado o "ID do segredo": criar outro (passo 2). |
| Erro de conexão no PythonAnywhere | Contas gratuitas só acessam sites liberados: confirme que `login.microsoftonline.com` e `graph.microsoft.com` estão na lista de sites permitidos ou peça a liberação ao suporte do PythonAnywhere. |
