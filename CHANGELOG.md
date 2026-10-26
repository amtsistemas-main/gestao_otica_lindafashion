# Histórico de versões

## 1.0.0 — 26/10/2026

Primeira versão de produção.

### Gestão
- Produtos ópticos, estoque com histórico auditável e solicitações de compra, fornecedores, clientes, receitas OD/OE, financeiro e indicadores.
- **Vendas / PDV** e **Pedidos e laboratório** unificados em um único módulo. A venda cria o pedido vinculado com o status atual escolhido no PDV; as mudanças de status avisam o cliente pelo WhatsApp.
- Documento de venda em PDF premium, sempre em uma página A4, com visualizador nativo para imprimir, salvar ou enviar pelo WhatsApp.
- Relacionamento (CRM): segmentos de recompra, tarefas com calendário (atalhos e dias já agendados) e mensagens sugeridas.
- Módulo Análises desativado nesta versão (permanece no código para ser liberado depois).

### Acesso
- Sistema fechado com login por nome de usuário; o administrador cria os logins e libera os módulos de cada usuário (com proteção também no banco).
- Tela de login white label e menu da conta no topo (Configurações e Sair).

### WhatsApp
- WhatsApp da loja conectado por QR Code (gateway Evolution API da AMT), com fila no banco, limites de envio e alternativa manual (wa.me).
- Aviso de status do pedido enviado a cada mudança, inclusive quando o pedido volta a uma etapa já avisada.

### Interface
- Primeira tela de cada módulo dentro da janela principal; nenhuma janela ultrapassa a área útil da tela.
- Fonte Arial, ícone da ótica na barra de tarefas, sidebar azul com logo em fundo branco e versão no rodapé.

### Distribuição
- Instalador para Windows (Inno Setup) com executável PyInstaller, configuração pública embutida, verificação `--smoke-test` e log local.
- Atualizações automáticas pelas GitHub Releases: download em segundo plano, conferência SHA-256 e instalação silenciosa (agora ou ao fechar o sistema).
- Banco: migrations `202610240001` a `202610260016` aplicadas no Supabase.
