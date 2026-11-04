# Conectar seu próprio app da Meta

Este guia usa **Instagram API with Instagram Login**, com chamadas para `graph.instagram.com`. Não misture tokens de Página do Facebook, o fluxo Facebook Login ou a antiga Basic Display API. Os nomes dos menus da Meta podem mudar.

## 1. Criar e preparar

Abra [Meta for Developers](https://developers.facebook.com/apps/) e crie seu aplicativo com o caso de uso/produto Instagram compatível com gerenciamento de conta profissional. Complete os requisitos apresentados pela Meta. Cadastre uma conta Instagram profissional (empresa ou criador) nas configurações da API e aceite o convite de testador no Instagram, quando solicitado.

Configure os acessos exigidos para leitura do perfil/mídia, comentários, mensagens e insights. No fluxo Instagram Login, confira as permissões `instagram_business_basic`, `instagram_business_manage_comments`, `instagram_business_manage_messages` e, quando disponível para seu caso de uso/versão, `instagram_business_manage_insights`. O Go Insta! não precisa da permissão de publicar conteúdo nesta versão. A existência de uma opção no código não garante que sua conta receberá a permissão.

## 2. Gerar o token e salvar

Use o gerador de token das configurações da API do Instagram. Conclua pessoalmente login, verificações e consentimento. Confira as permissões e a validade. Use token de longa duração para permitir a renovação periódica; esta versão não realiza a troca de um token curto por longo.

No Go Insta!, abra **Conexão** e informe:

| Campo | Origem |
| --- | --- |
| ID do aplicativo Instagram | Configuração da API/produto Instagram do seu app |
| Chave secreta do aplicativo Instagram | Mesmo produto/app Instagram; pode exigir reautenticação na Meta |
| Token de usuário Instagram | Gerador de token do próprio app, autorizado para sua conta |

Não confunda a chave do app Instagram com a chave de outro app ou com um token de verificação de webhook. A validação inicial consulta a identidade da conta pelo token; a confirmação da chave de assinatura ocorre quando chega um evento com HMAC válido.

Clique em **Verificar e salvar conexão**. O painel mostra o perfil confirmado. Credenciais ficam somente no seu servidor. Ao reconectar, campanhas são pausadas. A instalação não permite trocar para outro perfil e misturar o histórico: use outra instalação.

## 3. Configurar os eventos

Copie da tela Conexão a URL de callback e o token de verificação. Cadastre no produto Instagram da Meta, salve e habilite os campos:

- `comments`
- `messages`
- `messaging_postbacks`

Cadastre também as URLs de privacidade e de instruções para exclusão, após revisar seu conteúdo. Volte ao Go Insta! e clique em **Assinar eventos da conta**.

Há três confirmações diferentes no painel: callback verificado, assinatura confirmada pela API e evento válido recebido. A primeira ou a segunda sozinha não comprovam a entrega real. A assinatura de eventos não liga campanhas.

## 4. Testar a instalação

1. Com outra conta autorizada no contexto de teste do seu app, comente em uma publicação do perfil conectado.
2. Em **Conexão → Verificar status**, confira a chegada do evento e o ID dessa conta. O ID é o identificador recebido pela API, não o @.
3. Atualize as publicações. Crie campanha, selecione o post, a palavra-chave, o link e o ID de teste. Salvar deixa a campanha pausada.
4. Clique em **Testar**. Faça um **novo** comentário com a palavra-chave após iniciar o teste.
5. Confira o Direct, o botão do link e, se habilitada, a segunda mensagem após tocar no botão de continuação. Entre tentativas, aguarde pelo menos 60 segundos.
6. Confira o histórico de envios. “Aceita pela API” não significa leitura, clique, venda ou novo seguidor.

## 5. Liberar para o público

Confira no painel da Meta as exigências para pessoas sem papel no app: publicação do app, acesso avançado, análise de permissões, verificação ou outras etapas podem ser necessárias para seu caso. **Publicar o código no GitHub ou colocar o app em produção não concede permissões automaticamente.**

Só depois das liberações e de testar a entrega para uma conta fora dos papéis do app, use **Ativar** no Go Insta!. A confirmação mostra o público, as mensagens e os destinos. Respeite as janelas e restrições da Meta; o Go Insta! não contorna essas regras.

## Diagnóstico rápido

| Sintoma | Conferir |
| --- | --- |
| Token não valida | Fluxo Instagram Login, conta profissional, validade e permissões |
| Callback não valida | DNS/HTTPS, URL completa e token de verificação |
| Callback valida, mas não chega evento | Campos habilitados, assinatura da conta, papéis/acesso do app |
| Assinatura HTTP 403 | Chave secreta do app Instagram correto; não use chave de outro app |
| Evento chega, mas não envia | Campanha em teste/ativa, conta de teste, post, palavra inteira, comentário novo e limites |
| Algumas métricas indisponíveis | Tipo/idade de mídia, permissão, volume mínimo e limites do endpoint |
| Renovação falhou | Gere outro token no mesmo app e reconecte a mesma conta; refaça assinatura e teste |

Referências oficiais: [coleção Instagram da Meta no Postman](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api), [Instagram Platform](https://developers.facebook.com/docs/instagram-platform/), [App Review](https://developers.facebook.com/docs/app-review/). Use a seção Instagram Login da documentação, não a de Facebook Login.
