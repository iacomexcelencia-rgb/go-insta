# Instalar o Go Insta!

**Para a live com Codex:** comece pelo [roteiro](LIVE-CODEX.md) e pelo [prompt pronto](PROMPT-CODEX.md). O aluno abre suas contas autenticadas e o Codex executa a parte técnica. Os comandos abaixo são a referência para o assistente e para quem preferir instalar manualmente.

## Hostinger: usar o endereço que você já tem

Não é necessário comprar domínio. Esta opção reaproveita o **hostname HTTPS do n8n e o Traefik existente**. Exemplo ilustrativo:

- n8n: `https://n8n.srv123456.hstgr.cloud/`
- Go Insta!: `https://n8n.srv123456.hstgr.cloud/go-insta/`

Copie o endereço real que abre seu n8n. O nome pode variar, inclusive `n8n-xxxx.srv123456.hstgr.cloud`. O número do exemplo não é seu endereço. O Go Insta! tem processos próprios: o n8n não executa suas automações; aproveitamos a infraestrutura de HTTPS já pronta.

### Preparação

VPS Linux com Docker Engine/Compose v2, Python 3.10 ou posterior e Git. O template **Ubuntu 24.04 com n8n**, documentado pela Hostinger, é a referência para uma VPS nova. Abra o n8n, conclua a criação do administrador e confirme que HTTPS funciona sem alerta de certificado.

**Se a VPS já tem dados, não reinstale o sistema nem aplique outro template.** Verifique a configuração atual. Reserve recursos além dos consumidos pelo n8n; 2 GB livres para instalação/construção é uma referência inicial, não uma medição de capacidade. O PC pode ficar desligado depois da instalação; a VPS precisa continuar ativa.

### Comandos de instalação

No terminal da VPS, fora da pasta do n8n:

```bash
git clone https://github.com/iacomexcelencia-rgb/go-insta.git
cd go-insta
sudo python3 setup_install.py --hostinger
sudo python3 manage.py up -d --build --wait
sudo python3 manage.py ps
```

O assistente pede o endereço HTTPS existente, usuário/senha do novo painel e contato público para privacidade. Pode colar o endereço com ou sem `/go-insta/`. Não há senha padrão. Quando o terminal já estiver como root, `sudo` é dispensável.

Antes de gravar configuração, o assistente consulta o Docker e valida HTTPS. Precisa encontrar uma única rota `Host(...)` com TLS e entrypoint explícitos, rede compartilhada com Traefik e caminho `/go-insta/` livre. Gera uma composição adicional só para o Go Insta!, usando a rede, entrypoint e emissor de certificado encontrados. Não edita os arquivos do n8n, não reinicia Traefik e não abre outro proxy nas portas 80/443.

Se o template usar configuração diferente, a descoberta para com uma explicação. Isso não significa que precisa comprar domínio: o Codex deve inspecionar a configuração e adaptar o encaminhamento. Não invente nomes de redes, não desative validação TLS e não pare o n8n para contornar um erro.

### Conferência

Abra o endereço impresso, terminado em `/go-insta/`. Confira:

1. O n8n continua acessível no endereço original.
2. `/go-insta/health` responde `{"ok":true}`.
3. `/go-insta/api/dashboard` sem login retorna HTTP 401.
4. Login e recursos visuais carregam. **Conexão** começa sem conta vinculada.
5. `/go-insta/privacy` e `/go-insta/data-deletion` exibem o responsável correto.

Em **Conexão**, as URLs completas já incluem `/go-insta/`. Copie-as para a Meta. Siga [META.md](META.md) para conectar sua própria conta e testar eventos reais.

### Arquivos da instalação

Preserve `.env`, `.go-insta-mode`, `compose.hostinger.json`, `secrets/` e `data/`. São locais e ignorados pelo Git. `manage.py` usa sempre a composição correta na instalação, manutenção e atualização; use-o em vez de comandos Compose avulsos.

Os containers executam com UID/GID 10002. O assistente com sudo ajusta a propriedade dos diretórios privados. Docker rootless e Swarm não são cobertos por este assistente. Uma instalação por conta e por VPS neste fluxo automático; uma segunda exige projeto, nomes de rotas, portas e armazenamento separados.

## Alternativa: HTTPS próprio em uma VPS sem proxy

Se preferir um endereço dedicado que já aponta para a VPS, execute `sudo python3 setup_install.py` sem `--hostinger`. Depois use os mesmos comandos `manage.py`. Nesse modo, Caddy é iniciado nas portas 80/443 para obter HTTPS. As portas precisam estar disponíveis, o DNS correto e a entrada TCP 80/443 liberada. Não use esse modo ao lado de um proxy que já ocupa essas portas.

## Alternativa: outro proxy existente

Execute `sudo python3 setup_install.py --proxy` para um hostname dedicado. `manage.py` inicia somente app, worker e analytics. Configure manualmente o proxy com HTTPS válido e destino `127.0.0.1:18766` se ele roda no host. Um proxy em container precisa de rede Docker compartilhada e destino interno `app:8766`; o loopback do container não é o host. Não exponha 18766 publicamente.

Para montagem manual em `/go-insta/`, configure `GO_BASE=/go-insta` e encaminhe o caminho **sem removê-lo**. `GO_ORIGIN` contém somente `https://hostname`, sem caminho. A aplicação valida a origem separadamente do prefixo.

## Erros comuns

| Mensagem/sintoma | Próximo passo |
| --- | --- |
| Docker não pode ser consultado | Conferir `docker compose version` e acesso com sudo na VPS |
| Não encontrou uma única rota compatível | Confirmar URL do n8n; examinar rota TLS e rede do Traefik sem alterar os serviços existentes |
| HTTPS não validado | Conferir DNS, certificado e se o n8n abre pelo hostname informado |
| Já existe rota ou projeto Go Insta! | Localizar a instalação anterior e atualizar; não duplicar |
| Porta 18766 ocupada | Identificar o serviço; ajustar a nova composição com ajuda técnica, sem derrubar o serviço atual |
| HTTP 404/502 pelo proxy | Conferir rede externa, labels e estado do app; não ativar Caddy junto do Traefik |
| Login recusado por origem | `GO_ORIGIN` deve coincidir com HTTPS/hostname do navegador, sem `/go-insta/` |
| Callback Meta não valida | Copiar a URL completa de Conexão e o token de verificação; conferir saúde/HTTPS |

Atualizações e recuperação: [OPERACAO.md](OPERACAO.md). Não rode novamente o assistente em uma instalação existente nem use `down -v` para atualizar.

Referências consultadas em 04/11/2026: [template n8n da Hostinger](https://www.hostinger.com/support/10473267-how-to-use-the-n8n-vps-template-at-hostinger/), [hostname e Traefik da Hostinger](https://www.hostinger.com/support/11927159-changing-the-domain-for-n8n-on-vps-at-hostinger/), [roteamento Docker do Traefik](https://doc.traefik.io/traefik/reference/routing-configuration/other-providers/docker/). O domínio registrado pertence à Hostinger; você usa o hostname fornecido enquanto o serviço correspondente estiver disponível.
