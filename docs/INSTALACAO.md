# Instalação independente

Alvo de implantação: VPS Linux, Docker Engine e Compose v2. Python 3.13 e Git são necessários no host para o assistente inicial. Docker Desktop/Windows não é o alvo de produção desta versão. Não é uma aplicação que pode ser hospedada apenas em GitHub Pages ou Vercel estática: há processos permanentes e armazenamento local.

## VPS nova, sem proxy

1. Instale Docker Engine/Compose pelo [guia oficial](https://docs.docker.com/engine/install/). Instale Git e Python pelo gerenciador da distribuição.
2. Aponte o registro DNS do subdomínio para a VPS. Se houver registro IPv6, ele também deve apontar para um endereço funcional da VPS.
3. Libere entrada TCP 80 e 443 para HTTP/HTTPS. Não exponha 18766 nem o banco.
4. Clone o repositório e execute o assistente:

```bash
git clone https://github.com/iacomexcelencia-rgb/go-insta.git
cd go-insta
sudo python3 setup_install.py
```

Informe, por exemplo, `https://insta.seudominio.com.br`, sem caminho/porta. Crie o usuário e a senha do painel. O nome do responsável e o e-mail serão públicos nas páginas de privacidade/exclusão. O assistente cria `.env`, `secrets/installation.json`, `secrets/auth-seed.json` e `data/`. Não imprime a senha nem recebe credenciais da Meta.

O processo dos containers usa UID/GID 10002. A execução com sudo ajusta a propriedade de `data/` e `secrets/` para esse usuário. Para Docker rootless, ajuste a propriedade conforme o mapeamento de IDs do seu ambiente; esse cenário não é coberto pelo assistente.

```bash
docker compose --profile https up -d --build
docker compose ps
```

O serviço `app` precisa ficar saudável; `worker` e `analytics` devem permanecer em execução. O serviço `https` cuida dos certificados. Abra o domínio, faça login e siga [Configuração Meta](META.md). Não execute mais de um worker para o mesmo banco.

## VPS com proxy existente

Não use o perfil `https`. Suba apenas os três serviços da aplicação:

```bash
docker compose up -d --build
```

O painel fica acessível **somente no loopback do host**, em `127.0.0.1:18766`. Configure seu proxy com domínio dedicado, HTTPS válido e encaminhamento para essa porta. Exemplo para Caddy executando no host:

```caddy
insta.seudominio.com.br {
    reverse_proxy 127.0.0.1:18766
}
```

Se o proxy também estiver em container, o loopback dele não é o host. Conecte-o à rede Docker apropriada e encaminhe para `app:8766` nessa rede, ou use uma configuração de host gateway deliberada. Não publique a porta interna em todas as interfaces para contornar a rede. O `GO_ORIGIN` deve ser exatamente a URL HTTPS visível ao navegador; caso contrário o login será recusado por origem.

Não instale em `/go-insta/` nesta distribuição. A aplicação e os endereços do webhook usam a raiz de um subdomínio.

## Teste da infraestrutura

- `https://seu-dominio/health`: deve responder `{"ok": true}`.
- `/api/dashboard` sem login: deve recusar com HTTP 401.
- `/privacy` e `/data-deletion`: devem mostrar seu contato público correto.
- Depois do login, **Conexão** deve iniciar sem conta ou contatos de outro usuário.

Nunca copie os arquivos `data/` e `secrets/` de outra pessoa. Para um segundo Instagram, crie outra instalação com outro banco, domínio e portas/rede sem conflito.

## Atualizações

Leia as notas da versão, faça backup consistente e mantenha `data/`, `secrets/` e `.env`. Não rode novamente o assistente. Use `git pull --ff-only`, reconstrua e suba os serviços com o mesmo perfil usado na instalação. Veja [Operação](OPERACAO.md). Não use `docker compose down -v` como procedimento de atualização.
