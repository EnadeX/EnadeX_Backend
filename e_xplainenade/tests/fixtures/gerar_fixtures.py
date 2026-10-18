"""
Gera os dois arquivos que permitem testar o pipeline inteiro SEM o Supabase:

  base_705_cursos.csv   a base agregada por curso (saída de loader.get_dataset_from_supabase());
                        uma linha = um curso, sem nenhum dado individual de estudante
  golden_v2.json        os números de referência dos 12 cenários da rodada v2
                        (resultados/2026-10-14_v2/*/resposta.json) + o pedido de cada um

Rodar a partir de e_xplainenade/ só quando o ETL ou a metodologia mudarem DE PROPÓSITO
(e depois de uma nova rodada de resultados):

    python tests/fixtures/gerar_fixtures.py

Se um teste do golden quebrar sem que ninguém tenha mexido no ETL/modelo de propósito,
o problema é uma regressão — não regenere os arquivos para "consertar" o teste.
"""
import json
import sys
from pathlib import Path

import pandas as pd

# Escrever com repr() e ler com float_precision="round_trip" é o que preserva os doubles
# bit a bit: o to_csv padrão arredonda a 16 dígitos (44.849999999999994 -> 44.85) e o
# read_csv padrão usa um parser rápido que erra no último bit. Qualquer diferença muda o
# hash da base e as últimas casas dos coeficientes.
FLOAT_FORMAT = lambda v: repr(float(v))  # noqa: E731
LEITURA = {"float_precision": "round_trip"}


def carregar_base(caminho: Path = None) -> pd.DataFrame:
    """Lê base_705_cursos.csv exatamente como foi gravada (valores e dtypes)."""
    return pd.read_csv(caminho or Path(__file__).resolve().parent / "base_705_cursos.csv", **LEITURA)

AQUI = Path(__file__).resolve().parent
PROJETO = AQUI.parents[1]
sys.path.insert(0, str(PROJETO))

from config.variable_map import CURSO_OPTS, IES_OPTS  # noqa: E402
from modules import loader  # noqa: E402

RODADA = PROJETO / "resultados" / "2026-10-14_v2"

# Trechos de resposta.json usados como referência (textos ficam de fora: mudam de propósito).
CAMPOS_NUMERICOS = ["model_metrics", "coef_table", "comparison_table", "vif_table", "residuals_diag",
                    "diagnostics_ols", "shap_summary", "medias_centragem"]


def _pedido(resposta: dict, cenario: dict) -> dict:
    """Reconstrói o corpo do POST /hipotese a partir da fórmula e do formulário gravados."""
    y, direita = resposta["formula"].split(" ~ ")
    termos = direita.split(" + ")
    f = cenario["formulario"]
    return {
        "y": y,
        "x_vars": [t for t in termos if ":" not in t],
        "interactions": [t.split(":") for t in termos if ":" in t],
        "grupos": CURSO_OPTS[f["curso"]],
        "ies_filter": IES_OPTS[f["ies"]],
        "min_alunos": f["min_alunos"],
    }


def main():
    df = loader.get_dataset_from_supabase()
    destino = AQUI / "base_705_cursos.csv"
    df.to_csv(destino, index=False, float_format=FLOAT_FORMAT)
    releitura = carregar_base(destino)
    pd.testing.assert_frame_equal(df.reset_index(drop=True), releitura, check_exact=True)
    print(f"{destino.name}: {len(df)} cursos x {df.shape[1]} colunas (releitura idêntica)")

    golden = {}
    for pasta in sorted(p for p in RODADA.iterdir() if p.is_dir() and p.name[:2].isdigit()):
        resposta = json.loads((pasta / "resposta.json").read_text(encoding="utf-8"))
        cenario = json.loads((pasta / "cenario.json").read_text(encoding="utf-8"))
        rep = resposta["reprodutibilidade"]
        golden[pasta.name] = {
            "pedido": _pedido(resposta, cenario),
            "formula": resposta["formula"],
            "esperado": {k: resposta[k] for k in CAMPOS_NUMERICOS},
            "hash_base_sha256": rep["hash_base_sha256"],
            "n_cursos_base": rep["n_cursos_base"],
            "versoes": {k: rep["versoes"][k] for k in ("pandas", "numpy", "statsmodels", "scipy", "patsy")},
        }
    saida = AQUI / "golden_v2.json"
    saida.write_text(json.dumps(golden, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{saida.name}: {len(golden)} cenários, {saida.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
