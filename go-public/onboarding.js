'use strict';
const Onboarding={
  render(){
    const c=state.connection;
    const address=(label,value)=>`<div class="field"><label>${label}</label><code class="copy-value">${escape(value)}</code></div>`;
    return title('CONEXÃO','Seu Instagram. Seu aplicativo.','Siga estas etapas uma vez. Depois, gerencie suas campanhas por aqui.','<button id="connection-refresh">Verificar status</button>')+`
    <div class="notice ${c.refresh_error?'warn':''}">${c.connected?`Conta verificada: <b>@${escape(c.username)}</b>. Última validação: ${when(c.last_verified)}.`:'Comece criando seu próprio app na Meta. Esta instalação conecta uma conta profissional.'} ${escape(c.refresh_error||'')}</div>
    <div class="connection-grid">
    <section class="panel pad"><span class="eyebrow">ETAPA 01 · APP E CONTA</span><h2>Prepare o acesso na Meta</h2>
    <p>Crie um aplicativo no Meta for Developers e adicione a API do Instagram com login do Instagram. Sua conta deve ser profissional: empresa ou criador.</p>
    <ol class="onboarding-list"><li>Adicione sua conta nas configurações da API. Aceite o convite de testador no Instagram, se solicitado.</li><li>Habilite as permissões disponíveis para perfil, comentários, mensagens e insights. O Go Insta! não publica posts.</li><li>Gere um token de usuário Instagram no painel da Meta e confira sua validade. Para renovação automática, use um token de longa duração.</li></ol>
    <p class="footnote">O acesso de outras pessoas às automações depende das permissões e do nível de acesso aprovados pela Meta. Um teste com testador não comprova acesso público.</p>
    <div class="actions"><a class="button-anchor" target="_blank" rel="noopener noreferrer" href="https://developers.facebook.com/apps/">Abrir Meta for Developers ↗</a><a class="button-anchor" target="_blank" rel="noopener noreferrer" href="https://github.com/iacomexcelencia-rgb/go-insta/blob/main/docs/META.md">Guia completo ↗</a></div></section>
    <section class="panel pad"><span class="eyebrow">ETAPA 02 · CONEXÃO PRIVADA</span><h2>${c.connected?'Reconectar a mesma conta':'Conecte seu Instagram'}</h2>
    <p>Use o ID e a chave do aplicativo <b>Instagram</b>, exibidos na configuração da API do seu app Meta.</p>
    <form id="connect-instagram" autocomplete="off"><div class="field"><label for="meta-app-id">ID do aplicativo Instagram</label><input id="meta-app-id" inputmode="numeric" pattern="[0-9]{5,35}" value="${escape(c.app_id)}" required></div>
    <div class="field"><label for="meta-secret">Chave secreta do aplicativo Instagram</label><input id="meta-secret" type="password" autocomplete="new-password" minlength="32" maxlength="128" required></div>
    <div class="field"><label for="meta-token">Token de usuário Instagram</label><input id="meta-token" type="password" autocomplete="new-password" minlength="40" maxlength="4096" required></div>
    <button class="primary" type="submit">Verificar e salvar conexão</button><p class="error-text" id="connect-error" role="alert"></p></form>
    <p class="footnote">As credenciais são enviadas somente ao servidor desta instalação. Reconectar pausa todas as campanhas. Para outro perfil, use outra instalação.</p></section>
    <section class="panel pad"><span class="eyebrow">ETAPA 03 · EVENTOS</span><h2>Configure o webhook</h2><p>No produto Instagram da Meta, copie os valores abaixo e habilite os campos <b>comments</b>, <b>messages</b> e <b>messaging_postbacks</b>.</p>
    ${address('URL de callback',c.webhook_url)}${address('Token de verificação',c.verify_token)}${address('URL de política de privacidade',c.privacy_url)}${address('URL de instruções de exclusão',c.deletion_url)}
    <p>Depois de salvar o webhook na Meta, conecte a conta aos eventos:</p><button id="subscribe-instagram" ${!c.connected?'disabled':''}>Assinar eventos da conta</button>
    <dl class="details"><div><dt>Callback verificado pela Meta</dt><dd>${when(c.webhook_verified_at)}</dd></div><div><dt>Assinatura da conta</dt><dd>${c.subscribed?'Confirmada pela API':'Pendente'}</dd></div><div><dt>Último evento válido recebido</dt><dd>${when(c.webhook_event_at)}</dd></div></dl><p class="error-text">${escape(c.subscription_error)}</p>
    <p class="footnote">Confira os textos de privacidade e exclusão antes de cadastrar as URLs. Você é o responsável pelos dados desta instalação. Assinar eventos não ativa campanhas.</p></section>
    <section class="panel pad"><span class="eyebrow">ETAPA 04 · TESTE REAL</span><h2>Confira antes de ativar</h2><p>Com outra conta autorizada para teste no seu app, faça um novo comentário em uma publicação sua. Depois, clique em “Verificar status”.</p>
    <p>Escolha o ID recebido abaixo ao criar sua campanha. Atualize as publicações, salve o fluxo e selecione <b>Testar</b>. Faça outro comentário com a palavra-chave para testar a entrega.</p>
    ${(c.test_contacts||[]).length?`<div class="table-wrap"><table><thead><tr><th>Conta observada</th><th>ID para teste</th></tr></thead><tbody>${c.test_contacts.map(t=>`<tr><td>${escape(t.username?'@'+t.username:'Sem nome disponível')}</td><td><code>${escape(t.id)}</code></td></tr>`).join('')}</tbody></table></div>`:'<div class="notice">Nenhum contato recebido por comentário ainda.</div>'}
    <button data-refresh ${!c.connected?'disabled':''}>Atualizar publicações</button><p class="footnote">${escape(c.token_policy)} A disponibilidade das métricas depende da conta, do tipo de mídia e da API. Não há medição automática de vendas ou de todos os dados do aplicativo Instagram.</p></section>
    <section class="panel pad"><span class="eyebrow">SEGURANÇA</span><h2>Seu acesso ao painel</h2><form id="change-password"><p>Usuário: <b>${escape(state.user)}</b>. Alterar a senha encerra todas as sessões.</p><div class="field"><label for="current-password">Senha atual</label><input id="current-password" type="password" autocomplete="current-password" maxlength="256" required></div><div class="field"><label for="new-password">Nova senha</label><input id="new-password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></div><div class="field"><label for="repeat-password">Repita a nova senha</label><input id="repeat-password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></div><button type="submit">Alterar senha</button></form></section></div>`;
  },
  bind(){
    $('#connection-refresh').onclick=async e=>{e.target.disabled=true;try{await load();render();toast('Status atualizado.');}catch(err){toast(err.message);e.target.disabled=false;}};
    $('#connect-instagram').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;$('#connect-error').textContent='';try{await api('connection',{app_id:$('#meta-app-id').value.trim(),app_secret:$('#meta-secret').value.trim(),token:$('#meta-token').value.trim()});$('#meta-secret').value='';$('#meta-token').value='';await load();render();toast('Conta verificada. Agora configure o webhook.');}catch(err){$('#connect-error').textContent=err.message;}finally{button.disabled=false;}};
    $('#subscribe-instagram').onclick=async e=>{e.target.disabled=true;try{await api('connection/subscribe',{});await load();render();toast('Assinatura confirmada. Envie um comentário de teste.');}catch(err){toast(err.message);e.target.disabled=false;}};
  }
};
