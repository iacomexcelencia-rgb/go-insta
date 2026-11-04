# Prompt de partida para Codex ou Claude

Cole na pasta do projeto. Preencha os campos iniciais e deixe as ferramentas/contas necessárias acessíveis ao assistente. Não cole senhas ou tokens.

```text
Projeto: Go Insta! por ExcelêncIA — minha instalação independente
Meu Instagram: @SEU_PERFIL
Responsável: SEU_NOME
E-mail público para privacidade: SEU_EMAIL

Quero construir e colocar em funcionamento meu próprio sistema de automação
e análise do Instagram. Trabalhe comigo até uma entrega executável, não
apenas um plano. Referência pública de requisitos e implementação:
https://github.com/iacomexcelencia-rgb/go-insta

Quero aprender a orientar a IA durante esse processo. Explique de forma
simples as decisões importantes e mostre resultados que eu consiga testar.
Você pode usar o projeto aberto como base e personalizá-lo; deixe claro
o que foi reutilizado e o que foi implementado nesta sessão.

Requisitos:
- Painel com login, configuração de campanhas e histórico.
- Conexão da minha conta profissional pela API oficial do Instagram,
  usando meu próprio app Meta, sem credenciais compartilhadas.
- Comentário com palavra-chave em uma publicação escolhida dispara
  Direct com mensagem e botão para o link configurado.
- Continuação após interação, quando permitida pela Meta, e opção de
  botão que abre meu perfil. Não executar Seguir automaticamente.
- Modo de teste restrito, pausa e ativação explícita das campanhas.
- Insights disponibilizados pela API e comparação de conteúdos/períodos,
  sem confundir dados ausentes com zero nem inferir vendas de visualizações.
- Webhook com assinatura validada, proteção contra envios duplicados,
  dados persistentes, backup, autenticação e proteção de segredos.

Minha VPS e a Meta estão acessíveis no navegador. Use as ferramentas que
você tem para inspecionar o ambiente e executar a configuração. Se o acesso
ao navegador ainda não estiver conectado, me ajude a conectá-lo.

Não presuma Hostinger, n8n ou uma configuração específica. Descubra o que
já existe e adapte a instalação. Prefira aproveitar um endereço HTTPS
público estável já disponível, inclusive hostname fornecido pelo provedor,
sem comprar domínio desnecessariamente. Se não houver endereço adequado,
explique a necessidade e as opções antes de contratar qualquer serviço.
Preserve os serviços existentes. Não reinstale a VPS nem remova dados.

Autorizo preparar o código, os serviços do Go Insta! e sua configuração
na minha VPS identificada. Se houver vários servidores e o destino não
estiver claro, pergunte qual usar. Não contrate nada automaticamente.
Eu farei os logins, códigos, CAPTCHA e consentimentos necessários.
Não publique senhas, tokens ou chaves no chat, código, logs ou capturas.

Mantenha campanhas pausadas. Para o primeiro envio, peça o post, a conta
de teste, o link e a mensagem e me mostre o fluxo antes de executar.
Não libere para todo o público sem meu pedido explícito.

Teste a aplicação e a infraestrutura, confirme a conta correta e depois
valide um evento e um fluxo reais comigo. Diferencie esses testes de
aprovação da Meta. Se depender de análise/verificação, registre a pendência.

Ao terminar, entregue o endereço do painel e um RETOMADA.md local com
o que foi feito, como operar/atualizar, testes concluídos e pendências,
sem segredos. Quero poder continuar de onde paramos em outra sessão.
```

Esse pedido se adapta ao ambiente e às ferramentas disponíveis. Para uma aula de reconstrução integral, substitua a autorização de reutilizar a base por: “Implemente a partir dos requisitos; use o repositório apenas como referência e valide cada etapa.” Isso aumenta o trabalho de implementação e testes; o resultado deve ser demonstrado, não presumido.
