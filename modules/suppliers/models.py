"""Supplier fields shared by the form and the spreadsheet import."""
from __future__ import annotations

SUPPLIER_FIELDS = (
    "name", "legal_name", "trade_name", "document", "state_registration",
    "municipal_registration", "contact_name", "phone", "whatsapp", "email",
    "website", "postal_code", "street", "address_number", "address_complement",
    "neighborhood", "city", "state", "payment_terms", "pix_key", "bank_name",
    "bank_branch", "bank_account", "notes", "active",
)
FIELD_LABELS = {
    "name": "Nome de exibição *", "legal_name": "Razão social", "trade_name": "Nome fantasia",
    "document": "CPF / CNPJ", "state_registration": "Inscrição estadual",
    "municipal_registration": "Inscrição municipal", "contact_name": "Pessoa de contato",
    "phone": "Telefone", "whatsapp": "WhatsApp", "email": "E-mail",
    "website": "Site", "postal_code": "CEP", "street": "Logradouro",
    "address_number": "Número", "address_complement": "Complemento",
    "neighborhood": "Bairro", "city": "Cidade", "state": "UF",
    "payment_terms": "Condições de pagamento", "pix_key": "Chave PIX",
    "bank_name": "Banco", "bank_branch": "Agência", "bank_account": "Conta bancária",
    "notes": "Observações internas",
}
