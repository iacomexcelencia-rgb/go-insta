# Operação, atualização e recuperação

## Comandos de manutenção

Execute na pasta do Go Insta!. `manage.py` conserva o modo escolhido, inclusive a rede e as rotas da Hostinger. Em instalações anteriores à versão 0.2 sem `.go-insta-mode`, continue usando a composição/perfil originais; não rode novamente o instalador e não migre o proxy sem conferir sua configuração.

## Serviços e dados

`app` serve o painel e valida webhooks. `worker` consome eventos em série e envia apenas campanhas habilitadas. `analytics` coleta métricas e tenta renovar tokens elegíveis. `https`, opcional, termina TLS com Caddy.

`data/go.sqlite` guarda configurações, sessões, campanhas, histórico, insights e vendas manuais. `data/events.sqlite` guarda metadados mínimos de eventos: IDs, tipo, ação e datas. Não guarda o texto integral de comentários ou Directs. `secrets/` contém credenciais privadas em arquivos com permissão restrita; não há criptografia em repouso no aplicativo.

Nunca coloque os diretórios privados em uma pasta servida estaticamente nem publique seu conteúdo em um repositório. Não use dumps reais para abrir uma issue. O administrador local do servidor consegue ler as credenciais.

## Backups

Com a conta conectada e o worker em execução, há backup consistente diário de `go.sqlite` em `data/backups/`. São cópias no mesmo servidor: não protegem contra perda da VPS. Não há expurgo automático dessas cópias; acompanhe uso de disco e retenção.

Antes de atualizar, execute:

```bash
sudo python3 manage.py exec app python backup.py
```

Isso cria cópias consistentes dos dois bancos em uma pasta datada de `data/backups/`. Guarde também `secrets/` e `.env`, `.go-insta-mode` e `compose.hostinger.json` (quando existente) em backup privado, preferencialmente criptografado e fora da VPS. Pause as campanhas para uma migração e pare os serviços antes da restauração. Restaurar histórico antigo pode reintroduzir eventos e estados anteriores; não retome envios sem conferir campanhas e entregas.

## Atualizar

1. Leia as notas da nova versão e faça backup.
2. Execute `git pull --ff-only` na pasta da instalação.
3. Execute `sudo python3 manage.py up -d --build --wait` usando a configuração salva pelo instalador.
4. Confira `sudo python3 manage.py ps`, o caminho `health` dentro do endereço do painel, Conexão e a primeira coleta. Não recrie o banco para resolver erro de senha.

Preserve `data/`, `secrets/` e `.env`, `.go-insta-mode` e `compose.hostinger.json` (quando existente). O arquivo `auth-seed.json` só inicializa senha em banco novo; editá-lo não troca a senha existente. Para troca normal, use Conexão dentro do painel. Recuperação administrativa por CLI: `sudo python3 manage.py exec app python reset_password.py`; exige acesso ao servidor, pede a senha sem exibi-la e encerra sessões existentes. Não muda o usuário configurado.

## Pausar e diagnosticar

Pausar uma campanha bloqueia novos envios; uma requisição já em andamento pode terminar. Para interromper todos os envios, pare `worker`: `sudo python3 manage.py stop worker`. Coletor e painel podem continuar. Para retomar: `sudo python3 manage.py start worker`.

Consulte `sudo python3 manage.py logs --tail 100 app worker analytics`. Não publique os logs sem revisão. O app não habilita access log; ao configurar seu próprio proxy, evite registrar query strings da verificação do webhook. Segredos não devem aparecer em URLs públicas.

Um envio com retorno incerto fica para revisão e não é repetido automaticamente. Consulte o Direct antes de testar novamente. Falhas de leitura de um comentário também não são reenfileiradas automaticamente nesta versão. Uma nova coleta preserva o snapshot anterior quando falha; métricas individuais indisponíveis não se tornam zero.

## Privacidade e exclusão

O contato de privacidade é definido no assistente. Revise os modelos públicos em `application.py` conforme a operação. Eventos têm retenção de até 30 dias, aplicada quando chegam novos eventos. Outros dados e backups ficam até exclusão pelo operador. Esta versão não possui um botão de exclusão individual de participante; pedidos exigem tratamento administrativo dos bancos e backups. Revogar o app na Meta não apaga cópias locais automaticamente.

## Limites de suporte

Uma conta e um administrador por instância. SQLite em disco local, sem réplicas nem vários workers. Não monte banco em NFS. O projeto não inclui serviço gerenciado, garantia de aprovação na Meta, SLA ou migração automática da instalação privada do autor.
