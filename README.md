# Go Insta! por ExcelêncIA

**Automações de comentários para Direct e análise do Instagram, no seu próprio servidor.**

Versão **0.1.0-beta** · instalação independente · uma conta profissional por instalação · licença MIT.

Cada instalador usa **seu próprio aplicativo da Meta, suas credenciais e seu servidor**. Nenhuma conta, token ou base de dados do autor acompanha o código. Não depende de Supabase nem de n8n.

**Preciso de uma VPS ou deixar o PC ligado?** Esta distribuição foi preparada para VPS Linux. Com o sistema na VPS, seu computador pode ficar desligado: o servidor recebe os webhooks e executa automações e coletas. Rodar no PC exigiria mantê-lo ligado, com internet e um endpoint HTTPS público; essa não é a instalação de produção oferecida aqui. O GitHub distribui o código, não hospeda os serviços. Se já possui uma VPS compatível, pode usá-la sem contratar outra, cuidando dos recursos disponíveis e dos serviços existentes.

## O que você consegue fazer

- Criar campanhas: comentário com palavra-chave → Direct com botão para um link.
- Continuar com uma segunda mensagem depois da interação explícita no botão do fluxo.
- Testar com uma conta específica, pausar, editar e ativar campanhas pelo painel.
- Acompanhar envios aceitos pela API, interações e situações que exigem revisão.
- Consultar insights de perfil, publicações, Reels, público e Stories, conforme a API disponibilizar.
- Comparar períodos e publicações, classificar conteúdos por série/tema e exportar CSV.
- Registrar vendas manualmente, deixando explícita sua origem e evitando confundi-las com conversões atribuídas automaticamente.

## Como a pessoa conecta o Instagram?

1. Instala o Go Insta! em uma VPS Linux com domínio e HTTPS.
2. Cria seu app no Meta for Developers e configura **Instagram API with Instagram Login**.
3. Adiciona sua conta profissional, aceita os convites e autoriza as permissões exigidas pela Meta.
4. Gera o token no painel da Meta e informa **ID do aplicativo Instagram, chave secreta Instagram e token** na tela **Conexão** do Go Insta!.
5. Cadastra o webhook com os valores exibidos no painel e assina os eventos da conta.
6. Faz um teste real com outra conta autorizada e só então ativa sua campanha.

**Esta versão não oferece login OAuth em um clique.** O painel orienta e valida a configuração inicial; não cria o app da Meta por você. Ter um app próprio não dispensa as permissões, níveis de acesso, análise do app ou verificações que a Meta exigir. Um teste com administrador/testador não comprova funcionamento para o público em geral.

→ [Instalar no servidor](docs/INSTALACAO.md) · [Configurar Meta e Instagram](docs/META.md) · [Entender os insights](docs/METRICAS.md) · [Operação e recuperação](docs/OPERACAO.md)

## Começar em uma VPS nova

Pré-requisitos: Git, Python 3.13, Docker Engine e Docker Compose v2, um subdomínio apontando para a VPS e portas 80/443 disponíveis. Reserve pelo menos 2 GB de RAM para sistema, serviços e construção da imagem; é uma estimativa inicial, não um teste de capacidade.

```bash
git clone https://github.com/iacomexcelencia-rgb/go-insta.git
cd go-insta
sudo python3 setup_install.py
docker compose --profile https up -d --build
docker compose ps
```

O instalador pede domínio, administrador, senha e contato público para privacidade. Não há senha padrão. O Caddy obtém o certificado HTTPS; abra o domínio configurado e siga **Conexão**.

**Já usa n8n, Traefik, Nginx ou outro proxy nas portas 80/443?** Siga a alternativa com proxy existente em [Instalação](docs/INSTALACAO.md). Não suba um segundo proxy nas mesmas portas. Esta versão usa um subdomínio próprio, sem prefixo de caminho.

## Limites importantes desta versão

- O software é gratuito sob MIT; VPS, domínio e outros serviços contratados pelo instalador podem ter custos.
- Funciona com conta profissional (empresa/criador), API oficial e permissões válidas. Não solicita a senha do Instagram.
- Não envia mensagem automaticamente para novo seguidor, não força alguém a seguir, não publica conteúdo e não oferece caixa de entrada completa.
- O botão de perfil abre o Instagram; seguir continua sendo uma decisão da pessoa.
- Não mede automaticamente cliques no site ou vendas. Tempo médio assistido não equivale a uma curva completa de retenção.
- Métricas ausentes são apresentadas como indisponíveis, não como zero. Veja os limites de amostra e histórico na tela de insights.
- O token de longa duração tem tentativa de renovação após 20 dias. A renovação pode falhar; revogação, expiração ou alteração de acesso exigem reconexão. O Go Insta! não troca automaticamente um token curto por longo.
- Um único administrador e uma única conta por instalação. Não é um SaaS com múltiplos clientes.

## Desenvolvimento e verificação

```bash
python -m unittest discover -v
node --check go-public/app.js
node --check go-public/onboarding.js
node --check go-public/analytics.js
```

Os testes usam dados sintéticos e não enviam mensagens à Meta. O fluxo de CI também constrói a imagem e inicia uma instalação vazia em Docker, sem token. Consulte o resultado da execução do GitHub Actions; não confunda esse teste com aprovação do app ou validação real de uma nova conta Meta.

## Dados e segurança

O repositório contém somente código, documentação e fixtures sintéticas. `secrets/`, `data/`, `.env` e backups não são versionados nem enviados no build. Credenciais ficam em arquivos privados no servidor; **não são criptografadas em repouso pelo aplicativo**. Restrinja o acesso à VPS e proteja também os backups.

O painel usa senha com hash scrypt, sessões no servidor, proteção de origem e CSRF. Webhooks exigem HMAC SHA-256. Envios de resultado incerto não são repetidos automaticamente. A instalação começa sem campanhas, e reconectar pausa as existentes.

As páginas `/privacy` e `/data-deletion` são modelos preenchidos com os dados do operador. Revise-as para sua operação antes de cadastrá-las na Meta. Não publique tokens, senhas, payloads privados ou bancos em issues.

Projeto independente, sem afiliação à Meta ou ao Instagram. Mantido por Samuel Hipólito / ExcelêncIA. Contribuições são bem-vindas; reproduza problemas com dados fictícios.
