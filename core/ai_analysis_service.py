"""AI-assisted business analysis using tenant-scoped catalog data.

No privileged Supabase key is used. OpenAI credentials are read from the local
environment and are never logged or sent to the UI.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal

from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client


ANALYSIS_LABELS = {
    "sales": "Desempenho de vendas",
    "inventory": "Situação do estoque",
    "products": "Produtos e categorias",
    "finance": "Resumo financeiro",
}


class AIAnalysisService:
    """Collects authorized data and asks the AI to interpret only that evidence."""

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"

    def analyze(self, request: dict[str, str]) -> dict:
        if not self._api_key:
            raise ConfigurationError(
                "A integração de IA não está configurada. Defina OPENAI_API_KEY no arquivo .env."
            )
        analysis = request.get("analysis", "")
        if analysis not in ANALYSIS_LABELS:
            raise ValueError("Selecione um tipo de análise válido.")
        if analysis in {"sales", "finance"}:
            raise ConfigurationError(
                "Esta análise ainda não pode ser executada com dados reais: "
                "o projeto não possui tabelas de vendas ou financeiro integradas. "
                "Nenhum valor será estimado ou inventado."
            )

        evidence = self._load_catalog()
        if not evidence["products"]:
            raise ConfigurationError(
                "Não há produtos ativos cadastrados para analisar. Cadastre produtos e tente novamente."
            )
        if analysis == "inventory":
            metrics = self._inventory_metrics(evidence["products"])
        else:
            metrics = self._product_metrics(evidence["products"])

        payload = {
            "analysis": ANALYSIS_LABELS[analysis],
            "period": request.get("period_label", ""),
            "context": request.get("context", ""),
            "source": "Catálogo de produtos ativo do usuário autenticado; números calculados localmente.",
            "metrics": metrics,
            "catalog": evidence,
        }
        ai = self._request_model(payload)
        return {
            "title": ANALYSIS_LABELS[analysis],
            "summary": ai.get("summary", ""),
            "status": "Concluída",
            "metrics": metrics,
            "columns": ai.get("columns", []),
            "rows": ai.get("rows", []),
            "recommendations": ai.get("recommendations", []),
            "source_note": "Baseado no catálogo ativo da organização autenticada.",
        }

    @staticmethod
    def _load_catalog() -> dict:
        session = session_manager.current
        if session is None:
            raise ConfigurationError("Entre no sistema para gerar análises com dados da ótica.")
        client = get_supabase_client()
        membership = (
            client.table("organization_members")
            .select("organization_id")
            .eq("user_id", session.user_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        memberships = membership.data or []
        if not memberships:
            raise ConfigurationError("Seu usuário não possui vínculo ativo com uma organização.")
        organization_id = str(memberships[0]["organization_id"])
        response = (
            client.table("products")
            .select("name,category,brand,cost_price,sale_price,discount_percent,stock_quantity,minimum_stock,active")
            .eq("organization_id", organization_id)
            .eq("active", True)
            .order("name")
            .limit(1000)
            .execute()
        )
        products = []
        for row in response.data or []:
            cost = Decimal(str(row.get("cost_price") or 0))
            price = Decimal(str(row.get("sale_price") or 0))
            discount = Decimal(str(row.get("discount_percent") or 0))
            final_price = price * (Decimal("1") - discount / Decimal("100"))
            products.append({
                "name": str(row.get("name") or ""),
                "category": str(row.get("category") or "Sem categoria"),
                "brand": str(row.get("brand") or "Sem marca"),
                "cost_price": float(cost),
                "sale_price": float(price),
                "discount_percent": float(discount),
                "final_price": round(float(final_price), 2),
                "stock_quantity": int(row.get("stock_quantity") or 0),
                "minimum_stock": int(row.get("minimum_stock") or 0),
            })
        return {"products": products, "count": len(products)}

    @staticmethod
    def _inventory_metrics(products: list[dict]) -> list[dict[str, str]]:
        low = [p for p in products if p["stock_quantity"] <= p["minimum_stock"]]
        out = [p for p in products if p["stock_quantity"] == 0]
        units = sum(p["stock_quantity"] for p in products)
        stock_cost = sum(p["stock_quantity"] * p["cost_price"] for p in products)
        return [
            {"label": "Produtos ativos", "value": str(len(products))},
            {"label": "Estoque baixo", "value": str(len(low)), "change": "No limite ou abaixo do mínimo"},
            {"label": "Sem estoque", "value": str(len(out))},
            {"label": "Unidades disponíveis", "value": str(units)},
            {"label": "Custo estimado do estoque", "value": f"R$ {stock_cost:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")},
        ]

    @staticmethod
    def _product_metrics(products: list[dict]) -> list[dict[str, str]]:
        categories = Counter(p["category"] for p in products)
        priced = [p for p in products if p["sale_price"] > 0]
        avg_price = sum(p["sale_price"] for p in priced) / len(priced) if priced else 0
        avg_margin = (
            sum((p["final_price"] - p["cost_price"]) / p["sale_price"] * 100 for p in priced) / len(priced)
            if priced else 0
        )
        return [
            {"label": "Produtos ativos", "value": str(len(products))},
            {"label": "Categorias", "value": str(len(categories))},
            {"label": "Preço de venda médio", "value": f"R$ {avg_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")},
            {"label": "Margem bruta média estimada", "value": f"{avg_margin:.1f}%"},
        ]

    def _request_model(self, payload: dict) -> dict:
        system_prompt = (
            "Você é analista de negócios de uma ótica brasileira. Use exclusivamente os dados "
            "fornecidos. Não invente vendas, faturamento, despesas, tendências temporais nem causas "
            "que não possam ser inferidas. Diferencie fatos e recomendações. Responda somente JSON "
            "válido com as chaves summary (string), columns (array de strings), rows (array de objetos "
            "ou arrays compatíveis com columns) e recommendations (array de strings). "
            "Para rows, produza até 10 linhas úteis, usando dados reais do catálogo fornecido."
        )
        body = json.dumps({
            "model": self._model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }).encode("utf-8")
        req = Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=45) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise ConfigurationError("A chave de IA é inválida ou não tem permissão para este modelo.") from exc
            if exc.code == 429:
                raise ConfigurationError("Limite de uso da IA atingido. Aguarde e tente novamente.") from exc
            raise RuntimeError(f"O provedor de IA retornou HTTP {exc.code}.") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Não foi possível conectar ao serviço de IA. Verifique a internet e tente novamente.") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError("O serviço de IA retornou uma resposta inválida.") from exc

        try:
            content = raw["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Não foi possível interpretar a resposta estruturada da IA.") from exc
        if not isinstance(result, dict):
            raise RuntimeError("A resposta da IA não está no formato esperado.")
        return result


class AIAnalysisWorker(QThread):
    """Runs network/database work off the GUI thread."""
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, request: dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self._request = dict(request)

    def run(self) -> None:
        try:
            result = AIAnalysisService().analyze(self._request)
        except Exception as exc:
            self.failed.emit(str(exc) or "Falha inesperada ao gerar a análise.")
            return
        self.succeeded.emit(result)
