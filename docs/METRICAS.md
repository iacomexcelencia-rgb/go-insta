# O que os números significam

O coletor consulta a API oficial, registra o momento da leitura e informa a cobertura. Ele tenta métricas por grupos e, quando um grupo falha, tenta individualmente. Métrica recusada, ausente ou sem valor fica indisponível; zero retornado é zero real.

| Área | O que é solicitado, quando disponível |
| --- | --- |
| Perfil | Alcance, visualizações, contas engajadas, interações, curtidas, comentários, salvamentos, compartilhamentos, respostas, republicações, visitas e toques no perfil |
| Comparações | Janelas de 7, 28 e 90 dias; período anterior para 7/28; evolução diária de 28 dias |
| Publicações | Inventário, curtidas/comentários do objeto, métricas individuais acumuladas e taxas por alcance |
| Reels | Tempo médio e total assistido, taxa de pulo e visualizações entre plataformas, quando retornados |
| Público | Demografia agregada por idade, gênero, cidade/país e seguidores online, se liberados |
| Stories | Alcance, views, respostas, compartilhamentos, navegação e outras métricas disponíveis; arquivo das leituras realizadas |
| Campanhas | Novas conversas, mensagens aceitas e botão de continuação; inclui testes identificados no histórico |
| Vendas | Lançamentos manuais do operador; sem pixel/checkout ou atribuição automática |

Coleta completa diária; Stories a cada hora. Atualização manual tem intervalo mínimo de cinco minutos. A API pode impor limites adicionais; nenhuma rotina garante atualização em tempo real.

O inventário pode paginar até 10.000 itens. Insights individuais têm seleção limitada às 500 publicações mais recentes elegíveis dos últimos 730 dias e orçamento de consultas. A API pode reduzir ainda mais a cobertura. O painel mostra quantas publicações tiveram consulta; não trate os itens fora da amostra como se tivessem desempenho zero.

Períodos de perfil usam UTC, fim exclusivo e excluem o dia atual. Valores individuais de posts são acumulados, não apenas do período do filtro. Somar alcance de vários dias ou posts conta pessoas repetidas. A Meta pode corrigir valores posteriormente.

Tempos da API são convertidos de milissegundos para segundos/horas. Não há curva completa de retenção, taxa de conclusão inferida nem histórico retroativo garantido de seguidores/Stories. O arquivo de Stories preserva o que foi observado enquanto estava disponível, não recupera Stories nunca coletados.

As comparações entre série, tema, formato ou horário são observacionais. Conteúdos de idades diferentes tiveram tempos diferentes de exposição. Sem experimento controlado, o painel não prova que o formato causou o resultado. Associação manual de uma venda a um post é informação do operador, não prova de causalidade.
