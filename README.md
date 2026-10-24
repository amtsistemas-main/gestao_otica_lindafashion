# Ótica Linda Fashion — Gestão

Aplicativo desktop de gestão para ótica, desenvolvido em Python e PySide6 para Windows.

## Estado do projeto

A interface inicial e o módulo Produtos estão em desenvolvimento. A autenticação online usa Supabase Auth; os dados do catálogo são isolados por organização e protegidos por políticas RLS. Nenhuma chave privilegiada do Supabase deve ser distribuída dentro do aplicativo desktop.

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
- Estoque
- Fornecedores
- Financeiro
- Autenticação e sessão
- Integrações de pagamento (provedor a definir)

## Módulo Produtos e Supabase

O módulo separa modelos, regras de negócio, repositório e interface em `modules/products/`. Leitores de código de barras USB que funcionam como teclado são compatíveis; configure o leitor para enviar Enter ao final da leitura. Para habilitar dados online, aplique `database/migrations/202610240001_products.sql` no SQL Editor do Supabase e crie uma organização e um vínculo ativo em `organization_members` para o usuário autenticado. Sem esse vínculo, o catálogo online não será carregado.

## Módulo Estoque e compras

Aplique `supabase/migrations/202610240002_inventory_purchase_requests.sql` no SQL Editor do Supabase após a migration de Produtos. A migration cria fornecedores, histórico de movimentações, solicitações de compra e seus itens, com isolamento por organização via RLS.

O saldo não deve ser alterado diretamente no cadastro do produto para registrar uma entrada ou saída operacional. Use o módulo Estoque: a função transacional `record_stock_movement` bloqueia o registro do produto, calcula o novo saldo, impede saídas abaixo de zero e grava o histórico na mesma transação. Produtos com saldo igual ou abaixo do mínimo podem ser selecionados para abrir uma solicitação vinculada a um fornecedor e quantidade sugerida. A solicitação fica registrada no sistema; o envio externo ao fornecedor por e-mail/WhatsApp e o recebimento de pedidos serão etapas futuras.

## Segurança e integridade

- Nunca configure `service_role` ou qualquer segredo privilegiado do Supabase no cliente desktop.
- Aplique políticas RLS restritivas nas tabelas acessadas pela aplicação.
- Valide entradas no serviço e no banco; não dependa apenas da interface.
- Operações que alterem estoque ou movimentações financeiras deverão ser transacionais no banco.
- Não registre senhas, tokens ou dados de autenticação nos logs.

## Limitações desta fase

O modo de pré-visualização permite testar a interface e o cadastro local do módulo Produtos, mas não representa a integração online com Supabase. A conexão real com Supabase exige URL, chave pública/anon ou publishable key e um esquema de banco configurado. O fluxo de pagamentos será implementado após a definição do provedor.
