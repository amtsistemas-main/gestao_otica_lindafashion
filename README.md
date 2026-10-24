# Ótica Linda Fashion — Gestão

Aplicativo desktop de gestão para ótica, desenvolvido em Python e PySide6 para Windows.

## Estado do projeto

Esta é a estrutura inicial do projeto. A autenticação online será feita pelo Supabase Auth; dados e permissões deverão ser protegidos por políticas RLS no banco. Nenhuma chave privilegiada do Supabase deve ser distribuída dentro do aplicativo desktop.

## Requisitos

- Windows 10 ou 11 (64 bits)
- Python 3.11 ou superior
- Projeto Supabase configurado para o ambiente

## Configuração local

1. Crie e ative um ambiente virtual:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Instale as dependências:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Copie `.env.example` para `.env` e preencha somente as credenciais públicas necessárias.
4. Execute:
   ```powershell
   python app.py
   ```

## Módulos planejados

- Início e indicadores
- Produtos e leitura de código de barras
- Estoque
- Fornecedores
- Financeiro
- Autenticação e sessão
- Integrações de pagamento (provedor a definir)

## Segurança e integridade

- Nunca configure `service_role` ou qualquer segredo privilegiado do Supabase no cliente desktop.
- Aplique políticas RLS restritivas nas tabelas acessadas pela aplicação.
- Valide entradas no serviço e no banco; não dependa apenas da interface.
- Operações que alterem estoque ou movimentações financeiras deverão ser transacionais no banco.
- Não registre senhas, tokens ou dados de autenticação nos logs.

## Limitações desta fase

A conexão real com Supabase exige URL, chave pública/anon ou publishable key e um esquema de banco configurado. O fluxo de pagamentos será implementado após a definição do provedor.
