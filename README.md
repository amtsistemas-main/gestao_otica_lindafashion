# Ótica Linda Fashion — Gestão

Aplicativo desktop de gestão para ótica, desenvolvido em Python e PySide6 para Windows.

## Estado do projeto

Versão **1.0.0** (veja `CHANGELOG.md`). A versão é definida em `config/version.py` e usada pelo aplicativo, pelo executável e pelo instalador. A autenticação online usa Supabase Auth; os dados do catálogo são isolados por organização e protegidos por políticas RLS. Nenhuma chave privilegiada do Supabase deve ser distribuída dentro do aplicativo desktop.

## Requisitos

- Windows 10 ou 11 (64 bits)
- Python 3.11 ou superior

## Configuração local no Windows

1. Abra o PowerShell na pasta do projeto.
2. Crie e ative um ambiente virtual:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Instale as dependências:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Abrir a interface sem login (modo de pré-visualização)

Para visualizar o painel principal sem configurar Supabase, credenciais ou autenticação, execute:

```powershell
python app.py --preview
```

Esse modo serve para inspecionar a interface e experimentar o módulo Produtos localmente. Não cria sessão autenticada nem grava dados online. O catálogo usa armazenamento temporário em memória e os produtos são descartados ao fechar o aplicativo. Os outros módulos ainda em construção mostram um aviso informativo.

Para abrir a tela de acesso normal, use:

```powershell
python app.py
```

O fluxo de login requer as configurações públicas do Supabase no arquivo `.env`. Para isso, copie `.env.example` para `.env` e preencha os valores necessários.

## Módulos previstos

- Início e indicadores
- Produtos: cadastro, código de barras, SKU, custo, preço de venda, desconto, estoque mínimo e desativação
- Estoque: saldo, estoque mínimo, histórico auditável de entradas/saídas/ajustes, alertas e solicitações de compra vinculadas a fornecedores
- Fornecedores: cadastro completo fiscal, comercial, contato, endereço e pagamento; ativação/desativação e consulta dos produtos vinculados
- Financeiro
- Autenticação e sessão
- Integrações de pagamento (provedor a definir)

## Módulo Produtos e Supabase

O módulo separa modelos, regras de negócio, repositório e interface em `modules/products/`. Leitores de código de barras USB que funcionam como teclado são compatíveis; configure o leitor para enviar Enter ao final da leitura. Para habilitar dados online, aplique `database/migrations/202610240001_products.sql` no SQL Editor do Supabase e crie uma organização e um vínculo ativo em `organization_members` para o usuário autenticado. Sem esse vínculo, o catálogo online não será carregado.

## Módulo Estoque e compras

As migrations `202610240002_inventory_purchase_requests.sql`, `202610240003_receive_purchase_items.sql`, `202610240004_inventory_indexes_security.sql` e `202610240005_complete_supplier_catalog_and_product_link.sql` criam fornecedores, histórico de movimentações, solicitações de compra, recebimento transacional, cadastro completo de fornecedores e vínculo de fornecedor principal por produto. A migration 005 foi aplicada no projeto Supabase conectado. As tabelas usam RLS para isolamento por organização.

Para registrar a chegada de mercadorias, aplique também `supabase/migrations/202610240003_purchase_receiving.sql`. Na aba Solicitações de compra, selecione o pedido e use **Receber mercadoria**. É possível receber quantidades parciais por item; cada confirmação registra a entrada no estoque, atualiza o histórico e recalcula o status da solicitação atomicamente. A quantidade recebida não pode ultrapassar o saldo pendente.\n\nO saldo não deve ser alterado diretamente no cadastro do produto para registrar uma entrada ou saída operacional. Use o módulo Estoque: a função transacional `record_stock_movement` bloqueia o registro do produto, calcula o novo saldo, impede saídas abaixo de zero e grava o histórico na mesma transação. Produtos com saldo igual ou abaixo do mínimo podem ser selecionados para abrir uma solicitação vinculada a um fornecedor e quantidade sugerida. O recebimento parcial ou total pode ser registrado a partir da solicitação: o banco atualiza o saldo do produto, registra a entrada e recalcula o status na mesma transação. O envio externo ao fornecedor por e-mail/WhatsApp permanece como etapa futura.

## Módulo Fornecedores e vínculo com Produtos

O módulo `modules/suppliers/` permite cadastrar nome de exibição, razão social, nome fantasia, CPF/CNPJ, inscrições estadual e municipal, contato, telefone, WhatsApp, e-mail, site, endereço completo, condições de pagamento, chave PIX, dados bancários e observações internas. Fornecedores podem ser ativados ou desativados sem excluir o histórico. A lista exibe quantos produtos estão vinculados e permite consultar os respectivos produtos.

No cadastro de Produtos, o campo **Fornecedor principal** vincula o produto a um fornecedor da mesma organização. O fornecedor também aparece na tabela do catálogo. O relacionamento usa `products.supplier_id` com chave estrangeira composta por fornecedor e organização, evitando vínculo cruzado entre organizações. A migration `202610240005_complete_supplier_catalog_and_product_link.sql` foi aplicada no Supabase.

## Gestão óptica de alto padrão

Seis frentes integradas. As migrations e a ordem de aplicação estão em `database/migrations/README.md` (arquivos `202610250001` a `202610250015`, já aplicados no projeto Supabase conectado).

1. **Produtos ópticos** (`modules/products/`): tipo de produto com campos próprios (armação, lente oftálmica, lente de contato, solar, acessório, serviço), modelo, cor, tamanho, material, índice e tratamentos de lente, ponto e quantidade de reposição, serviços sem controle de estoque e filtro por tipo.
2. **Receitas** (`modules/prescriptions/`): OD/OE estruturado (esférico, cilíndrico, eixo, adição, DNP longe/perto, altura, prisma), passos de 0,25 D, eixo obrigatório com cilindro, alertas de digitação (anisometropia, DNP de perto maior que a de longe, receita vencida), histórico por cliente e vínculo com a venda e o pedido.
3. **Pedidos e laboratório** (`modules/lab_orders/`): quadro por etapa (aguardando envio, enviado, em produção, recebido, em conferência, pronto para retirada, entregue), laboratório, custo, prazos, alertas de atraso, ocorrências com custo e aviso ao liberar sem conferência.
4. **PDV** (`modules/sales/pos.py`): leitor de código de barras, receita sugerida, medidas da armação, pagamentos múltiplos com troco, sinal e crediário/boleto parcelado, limite único de desconto da loja (administradores podem exceder informando o motivo), orçamentos convertíveis em venda e cancelamento com estorno. A finalização é uma única transação no banco com proteção contra duplicidade.
5. **Indicadores** (`modules/analytics/`): faturamento × lucro efetivo, margem de contribuição, ticket médio, conversão de orçamentos, vendas por vendedor, produtos mais rentáveis, estoque parado e envelhecimento de contas a receber.
6. **Relacionamento** (`modules/crm/`): preferências do cliente, agenda de follow-ups (pós-venda e revisão de receita criados automaticamente pelo banco), segmentos de recompra (receita vencendo, em risco, fiéis, novos, inativos, aniversariantes), WhatsApp com mensagem sugerida somente para quem consentiu e exportação CSV.

A lógica de negócio dessas frentes tem testes em `tests/test_optical_business_rules.py`.

## Navegação, documentos e usuários

- **Telas dentro da janela principal**: a primeira tela de cada módulo abre no lugar da visão geral; cadastros, PDV e demais telas secundárias continuam em janelas próprias. Todas as janelas se ajustam à área útil da tela (inclusive notebooks 1366×768) e, quando o conteúdo é maior, rolam sem cortar campos.
- **Vendas / PDV** (`modules/sales/hub.py`): vendas, orçamentos, PDV e o quadro de pedidos do laboratório no mesmo módulo, em abas.
- **Documento de venda em PDF** (`modules/sales/document_pdf.py`): ordem de serviço, orçamento ou comprovante com identidade da loja (Configurações), itens, pagamentos e parcelas, receita OD/OE, medidas da armação, laboratório, condições, assinaturas e canhoto com código de barras. O documento cabe em uma única página A4: a densidade é reduzida automaticamente quando necessário.
- **Multilogin** (Configurações → Usuários e acessos): sistema fechado com login por **nome de usuário**; o dono ou administrador cria os logins e escolhe os módulos de cada usuário; o menu e os atalhos mostram apenas os módulos liberados. A criação de logins usa a Edge Function `admin-users` (chave privilegiada somente no servidor), e o Financeiro também é protegido por módulo no banco.
- **WhatsApp da loja** (Configurações → WhatsApp da loja): o cliente conecta o WhatsApp da loja por QR Code (gateway Evolution API hospedado pela AMT, uma instância por loja). Mensagens de status de pedido, PDFs de venda e contatos do CRM passam a ser enviados automaticamente pela fila do banco; sem conexão, o envio manual continua. Detalhes e implantação do servidor: `docs/whatsapp-evolution.md`.

## Instalador para Windows

Gerado com PyInstaller (executável em pasta) e Inno Setup (instalador em português, atalhos no menu Iniciar e na área de trabalho, desinstalador). Requisitos na máquina de build: as dependências do `requirements.txt`, `pip install pyinstaller` e `winget install JRSoftware.InnoSetup`.

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

O script lê a versão de `config/version.py`, copia do `.env` **somente** `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` para o pacote, gera `dist\OticaLindaFashion\`, executa `OticaLindaFashion.exe --smoke-test` e cria `dist\installer\OticaLindaFashion-Setup-<versão>.exe`. A instalação é por usuário (sem exigir administrador).

Na máquina do cliente, um arquivo `%APPDATA%\OticaLindaFashion\.env` substitui a configuração embutida, se necessário. O log do aplicativo fica em `%LOCALAPPDATA%\OticaLindaFashion\logs\app.log`.

## Segurança e integridade

- Nunca configure `service_role` ou qualquer segredo privilegiado do Supabase no cliente desktop.
- Aplique políticas RLS restritivas nas tabelas acessadas pela aplicação.
- Valide entradas no serviço e no banco; não dependa apenas da interface.
- Operações que alterem estoque ou movimentações financeiras deverão ser transacionais no banco.
- Não registre senhas, tokens ou dados de autenticação nos logs.

## Limitações desta fase

O modo de pré-visualização permite testar a interface e o cadastro local do módulo Produtos, mas não representa a integração online com Supabase. A conexão real com Supabase exige URL, chave pública/anon ou publishable key e um esquema de banco configurado. O fluxo de pagamentos será implementado após a definição do provedor.
