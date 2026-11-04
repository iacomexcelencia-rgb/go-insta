# Live: criando o Go Insta! com IA

## A proposta da aula

**Você apresenta o problema e os requisitos; a IA constrói, instala e testa com você.** O aluno aprende a dirigir esse trabalho e conferir a entrega. A aula não depende de uma marca de VPS nem de ter n8n instalado.

Samuel fará ao vivo no ambiente dele. O Codex ou Claude de cada aluno deve examinar seu ambiente e escolher a implantação compatível. Os comandos deste repositório são recursos técnicos para o assistente, não conteúdo que o aluno precisa decorar.

## Requisitos para participar

- Codex ou Claude com as ferramentas de desenvolvimento e acesso ao ambiente que serão utilizadas na aula. O controle do navegador precisa estar disponível e conectado; uma aba aberta por si só não concede esse acesso.
- Uma pasta de projeto e acesso administrativo à VPS que será usada.
- Um endereço HTTPS público estável para o webhook. A IA verifica se o provedor já oferece um hostname utilizável ou se há outro endereço existente. **Domínio comprado separadamente, Hostinger e n8n não são requisitos do Go Insta!.** Se o ambiente não tiver endereço adequado, essa parte precisa ser providenciada.
- Conta profissional do Instagram, acesso ao Meta for Developers e celular para verificações. Cada aluno terá seu próprio app Meta e suas credenciais.

A VPS mantém os serviços funcionando com o PC desligado. O software aberto não cobra licença; infraestrutura e ferramentas de IA podem ter seus próprios custos. Não é necessário Supabase.

## O sistema que vamos pedir à IA

1. Painel privado com login, sem credenciais padrão ou segredos no código público.
2. Conexão da própria conta profissional pela API oficial, usando app Meta próprio.
3. Campanhas editáveis: publicação + palavra-chave → mensagem no Direct + botão de link.
4. Continuação após interação, quando permitida, com botão que abre o perfil.
5. Modo de teste por conta, pausa, ativação explícita e histórico de execução.
6. Métricas disponíveis pela API, comparação de conteúdos/períodos e indicação clara do que estiver indisponível. Não inventar métricas, vendas ou atribuição.
7. Webhook HTTPS com assinatura validada, armazenamento persistente, proteção contra duplicatas, backup e instruções de recuperação.

O escopo detalhado e as limitações da implementação pública estão no [README](../README.md) e em [Métricas](METRICAS.md).

## Sequência simples para conduzir ao vivo

**1. Mostrar o destino.** Abra seu Go Insta! e mostre o painel, uma campanha de teste e os insights. Explique o que quer recriar e o que considera uma entrega funcionando.

**2. Dar a missão.** Abra uma pasta no Codex e use o [prompt de partida](PROMPT-CODEX.md). Diga o nome do projeto, seu perfil e os requisitos. Se usar o repositório como base, explique isso; se construir do zero, use-o como referência de comportamento, sem anunciar que todas as funcionalidades estarão prontas antes dos testes.

**3. Acompanhar a construção.** Peça primeiro uma versão executável. Veja o painel, experimente o fluxo e peça correções concretas. Mostre como você avalia a entrega da IA, não apenas o texto que ela responde.

**4. Instalar no ambiente disponível.** Deixe Hostinger ou outro provedor acessível ao assistente. A IA identifica servidor, serviços existentes e HTTPS, adapta a instalação e verifica que não afetou os serviços anteriores. No seu exemplo pode ser `/go-insta/` junto do n8n; outros alunos podem usar outra configuração.

**5. Conectar a conta.** A IA auxilia na configuração do app Meta, token e webhook; o aluno conclui verificações de identidade e consentimentos. Confira identidade da conta, callback, assinatura dos eventos e chegada de um evento real. Use [META.md](META.md) como referência.

**6. Testar uma campanha real.** Escolha post, conta de teste, palavra COMANDO, mensagem e link. Autorize o teste, faça um comentário novo e confira Direct, botões, continuação e histórico. Mantenha a liberação geral separada desse teste.

**7. Entregar autonomia.** Mostre como o aluno cria/edita/pausa campanhas no painel e acompanha os dados. Peça à IA um `RETOMADA.md`, sem segredos, com acesso, manutenção, testes e pendências.

## Quando a aula encontrar uma pendência

Login, código, CAPTCHA e verificações ficam com o aluno. Chaves e tokens devem ser preenchidos fora da transmissão e guardados somente na configuração privada. Se a Meta exigir análise ou verificação adicional, registre a pendência e continue a demonstração no ambiente já preparado. Não prometa que toda conta será aprovada durante a live.

Faça um ensaio no ambiente escolhido. Testes sintéticos de software não substituem a conexão real nem a validação de entrega. Não é necessário transformar o ensaio em aula de administração de servidores.
