import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from educluster.educluster_config import DIR_CACHE, MODELO_GEMINI, RAIZ_PROJETO

load_dotenv(RAIZ_PROJETO / ".env")

DIR_DESCRICOES = DIR_CACHE / "descricoes"

CONTEXTO_BASE = (
    "Voce e um pesquisador em avaliacao da educacao superior brasileira, escrevendo para "
    "gestores de curso e para uma banca de TCC. Analise os resultados abaixo, obtidos por "
    "clusterizacao nao supervisionada sobre os microdados do ENADE 2021.\n\n"
    "Regras de escrita obrigatorias:\n"
    "- Portugues do Brasil, tom academico e direto\n"
    "- Nunca use o caractere travessao\n"
    "- Nunca afirme causalidade, os dados sao observacionais\n"
    "- Nao invente numeros que nao estejam nos dados fornecidos\n"
    "- Se as metricas indicarem separacao fraca, diga isso explicitamente\n\n"
)

INSTRUCOES = {
    "cursos": (
        "Cada cluster reune cursos de graduacao. As notas vao de 0 a 100. As dimensoes ODP "
        "(Organizacao Didatico Pedagogica), OPORT (Oportunidades de Ampliacao da Formacao) e "
        "INFRA (Infraestrutura) vao de 1 a 6 e medem a percepcao dos proprios estudantes.\n\n"
        "Para cada cluster, escreva um paragrafo de ate 3 linhas com: um nome curto e descritivo "
        "para o perfil, o que caracteriza esses cursos, e o que o resultado sugere para um gestor. "
        "Ao final, escreva um paragrafo sobre a relacao entre desempenho medido e qualidade percebida."
    ),
    "estudantes": (
        "Cada cluster reune estudantes concluintes de todo o Brasil, sem recorte de curso ou regiao. "
        "As notas vao de 0 a 100.\n\n"
        "Para cada cluster, escreva um paragrafo de ate 3 linhas com um nome curto para o perfil e o "
        "que o diferencia. Compare desempenho objetivo e discursivo quando disponivel."
    ),
}


def _chave_cache(contexto: dict, tipo: str) -> str:
    conteudo = json.dumps({"tipo": tipo, "contexto": contexto}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:16]


def montar_prompt(contexto: dict, tipo: str) -> str:
    instrucao = INSTRUCOES.get(tipo, INSTRUCOES["cursos"])
    return (
        CONTEXTO_BASE
        + instrucao
        + "\n\nDADOS:\n"
        + json.dumps(contexto, indent=2, ensure_ascii=False)
    )


def _ler_cache(chave: str):
    arquivo = DIR_DESCRICOES / f"{chave}.json"
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    return None


def _gravar_cache(chave: str, payload: dict):
    DIR_DESCRICOES.mkdir(parents=True, exist_ok=True)
    (DIR_DESCRICOES / f"{chave}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def descrever(contexto: dict, tipo: str = "cursos", forcar: bool = False) -> dict:
    chave = _chave_cache(contexto, tipo)

    if not forcar:
        guardado = _ler_cache(chave)
        if guardado:
            guardado["origem"] = "cache"
            return guardado

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "disponivel": False,
            "motivo": "GEMINI_API_KEY nao configurada no ambiente do backend",
            "chave_cache": chave,
            "prompt_seria": montar_prompt(contexto, tipo)[:400] + "...",
        }

    try:
        import google.generativeai as genai
    except ImportError:
        return {
            "disponivel": False,
            "motivo": "pacote google-generativeai nao instalado no backend",
            "chave_cache": chave,
        }

    try:
        genai.configure(api_key=api_key)
        modelo = genai.GenerativeModel(MODELO_GEMINI)
        texto = modelo.generate_content(montar_prompt(contexto, tipo)).text
    except Exception as erro:
        return {"disponivel": False, "motivo": f"falha na chamada ao modelo: {erro}", "chave_cache": chave}

    payload = {
        "disponivel": True,
        "tipo": tipo,
        "modelo": MODELO_GEMINI,
        "descricao": texto,
        "chave_cache": chave,
        "origem": "geracao",
    }
    _gravar_cache(chave, payload)
    return payload
