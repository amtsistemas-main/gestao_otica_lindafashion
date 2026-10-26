# Histórico de versões

## 1.0.1 — 26/10/2026

- PDV voltou a abrir (erro introduzido no campo Vendedor da 1.0.0).
- Leitor de código de barras: o Enter enviado após cada leitura não aciona mais botões da janela. No PDV a leitura só adiciona o item; no cadastro de produto pula para o próximo campo; nas buscas de Produtos e Vendas só pesquisa.
- Verificação automática do instalador passa a abrir todas as telas principais antes de publicar.

## 1.0.0 — 26/10/2026

Primeira versão de produção.

### Gestão
- Produtos ópticos, estoque com histórico auditável e solicitações de compra, fornecedores, clientes, receitas OD/OE, financeiro e indicadores.
- **Vendas / PDV** e **Pedidos e laboratório** unificados em um único módulo. A venda cria o pedido vinculado com o status atual escolhido no PDV; as mudanças de status avisam o cliente pelo WhatsApp.
- Documento de venda em PDF premium, sempre em uma página A4, com visualizador nativo para imprimir, salvar ou enviar pelo WhatsApp.
- Relacionamento (CRM): segmentos de recompra, tarefas com calendário (atalhos e dias já agendados) e mensagens sugeridas.
- Módulo Análises desativado nesta versão (permanece no código para ser liberado depois).
- **Vendedor em cada venda** (usuários cadastrados pelo administrador), exibido na lista de vendas e no PDF, para o repasse de comissões.
- **Valores em dinheiro** digitados pelos centavos no lançamento financeiro e no pagamento do PDV (o valor sugerido é substituído ao digitar).
- **Financeiro**: filtros por dia, semana, mês, ano ou período personalizado, abas com as mesmas regras e tabelas ocupando a tela.
- **Relatórios financeiros** por período em PDF e planilha Excel para a contabilidade (resumo, lançamentos e resultado por categoria).
- **Fornecedores por planilha XLSX**: baixar a planilha (com os cadastrados ou um exemplo), preencher e importar — cria novos e atualiza os existentes.

### Acesso
- Sistema fechado com login por nome de usuário; o administrador cria os logins e libera os módulos de cada usuário (com proteção também no banco).
- Tela de login white label e menu da conta no topo (Configurações e Sair).

### WhatsApp
- WhatsApp da loja conectado por QR Code (gateway Evolution API da AMT), com fila no banco, limites de envio e alternativa manual (wa.me).
- Aviso de status do pedido enviado a cada mudança, inclusive quando o pedido volta a uma etapa já avisada.

### Interface
- Primeira tela de cada módulo dentro da janela principal; nenhuma janela ultrapassa a área útil da tela.
- Calendário próprio em todos os campos de data e data de nascimento com máscara DD/MM/AAAA.
- Fonte Arial, ícone da ótica na barra de tarefas, sidebar azul com logo em fundo branco e versão no rodapé.

### Distribuição
- Instalador para Windows (Inno Setup) com executável PyInstaller, configuração pública embutida, verificação `--smoke-test` e log local.
- Atualizações automáticas pelas GitHub Releases: download em segundo plano, conferência SHA-256 e instalação silenciosa (agora ou ao fechar o sistema).
- Banco: migrations `202610240001` a `202610260017` aplicadas no Supabase.
