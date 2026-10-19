"""
Teste ponta a ponta do frontend do E-XplainENADE no navegador real (Edge via DevTools Protocol).
NÃO faz parte do `unittest discover`: precisa dos servidores e do Edge. Cobre as correções da F4
(2026-10-19, ver DEVELOPMENT.md):

  * debounce do resumo da capa (3 digitações rápidas = 1 chamada) e descarte de resposta antiga
  * avisos de amostra pequena (regra de Green) na tela e no PDF
  * coluna "p < 0,05?" (e o fim de "Confiável?")
  * o PDF baixado traz a hipótese que está NA TELA, mesmo com o formulário alterado depois
  * aviso "formulário alterado depois desta execução"
  * rede fora do ar: mensagem clara em português e botão destravado

Pré-requisitos (de e_xplainenade/ e do EnadeX_Frontend/):
    python e_xplainenade_rotas.py          # API isolada, porta 8003 (expõe o nome do PDF)
    npx next dev -p 3000                   # frontend (NEXT_PUBLIC_EXPLAIN_API_URL=http://localhost:8003)
    python tests/e2e/e2e_frontend.py       # este teste; sai com código 1 se algo falhar

Variáveis opcionais: EDGE_PATH (caminho do msedge.exe), FRONTEND_URL (padrão http://localhost:3000).
Requer: pip install websockets pypdf
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets
from pypdf import PdfReader

_EDGES = (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
          r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
EDGE = os.environ.get("EDGE_PATH") or next((p for p in _EDGES if os.path.exists(p)), "msedge")
URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/") + "/e-xplainenade"
TMP = tempfile.mkdtemp(prefix="e2e_explainenade_")
DL = os.path.join(TMP, "downloads")
PORTA = 9339

proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORTA}",
                         f"--user-data-dir={os.path.join(TMP, 'perfil')}", "--window-size=1440,1000", "about:blank"])
page = None
for _ in range(60):
    try:
        page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/json")) if t["type"] == "page")
        break
    except Exception:
        time.sleep(0.3)
if page is None:
    proc.terminate()
    sys.exit("Não consegui abrir o Edge (defina EDGE_PATH).")

resultados = []


def ok(nome, cond, detalhe=""):
    resultados.append((nome, bool(cond)))
    print(f"{'OK   ' if cond else 'FALHA'} {nome}" + (f"  — {detalhe}" if detalhe else ""), flush=True)


async def main():
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=100_000_000) as ws:
        n, pend, ev = 0, {}, []

        async def leitor():
            async for raw in ws:
                m = json.loads(raw)
                if m.get("id") in pend:
                    pend.pop(m["id"]).set_result(m)
                elif "method" in m:
                    ev.append(m)

        async def cmd(method, **params):
            nonlocal n
            n += 1
            f = asyncio.get_event_loop().create_future()
            pend[n] = f
            await ws.send(json.dumps({"id": n, "method": method, "params": params}))
            msg = await f
            if "error" in msg:
                raise RuntimeError(f"{method}: {msg['error']}")
            return msg.get("result", {})

        async def js(expr):
            r = await cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
            if "exceptionDetails" in r:
                raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", str(r["exceptionDetails"])))
            return r.get("result", {}).get("value")

        async def esperar(expr, segundos=120):
            for _ in range(segundos * 2):
                if await js(expr):
                    return True
                await asyncio.sleep(0.5)
            return False

        async def baixar_pdf():
            shutil.rmtree(DL, ignore_errors=True)
            os.makedirs(DL)
            await js("__btn('Baixar relatório PDF').click()")
            for _ in range(240):
                await asyncio.sleep(0.5)
                if any(f.endswith(".pdf") for f in os.listdir(DL)):
                    break
            await asyncio.sleep(1)
            arquivos = [f for f in os.listdir(DL) if f.endswith(".pdf")]
            if not arquivos:
                return ""
            leitor_pdf = PdfReader(os.path.join(DL, arquivos[0]))
            return re.sub(r"[ \t]+", " ", " ".join(p.extract_text() for p in leitor_pdf.pages))

        t = asyncio.create_task(leitor())
        for d in ("Page", "Network", "Runtime"):
            await cmd(f"{d}.enable")
        os.makedirs(DL, exist_ok=True)
        await cmd("Page.setDownloadBehavior", behavior="allow", downloadPath=DL)

        await cmd("Page.navigate", url=URL)
        await esperar("!!document.querySelector('aside input[type=number]') && !document.querySelector('aside input[type=number]').disabled "
                      "&& document.querySelectorAll('aside input[type=checkbox]').length > 5")
        await js(r"""window.__set = (el, v) => {
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
          el.dispatchEvent(new Event('input', {bubbles: true}));
        };
        window.__cb = txt => [...document.querySelectorAll('aside input[type=checkbox]')].find(c => c.parentElement.textContent.trim() === txt);
        window.__btn = txt => [...document.querySelectorAll('button')].find(b => b.textContent.includes(txt));
        window.__formula = () => [...document.querySelectorAll('p')].find(p => /NT_GER ~/.test(p.textContent))?.textContent.trim();""")
        # A 1ª chamada ao backend recém-iniciado é a frio (~11 s, 13 consultas ao Supabase); espera terminar.
        await esperar("/\\d+ cursos/.test(document.body.innerText)", 90)

        # ── Debounce do resumo: digitar 1 → 10 → 100 rapidamente ─────────────────────
        ev.clear()
        for v in ("1", "10", "100"):
            await js(f"__set(document.querySelector('aside input[type=number]'), '{v}')")
            await asyncio.sleep(0.12)
        await esperar("/Base:\\s*11 cursos/.test(document.body.innerText)", 30)
        reqs = [e for e in ev if e["method"] == "Network.requestWillBeSent"
                and "/dataset/resumo" in e["params"]["request"]["url"]
                and e["params"]["request"]["method"] == "GET"]  # sem o OPTIONS da pré-verificação do CORS
        ok("debounce: 3 digitações rápidas geram 1 única chamada ao resumo", len(reqs) == 1, f"{len(reqs)} chamada(s)")
        base = await js("(document.body.innerText.match(/Base:[\\s\\S]{0,60}/)||[''])[0].replace(/\\s+/g,' ')")
        ok("capa mostra o recorte do ÚLTIMO valor digitado (100 → 11 cursos)", "11 cursos" in (base or ""), base)

        # ── Amostra pequena: avisos na tela e no PDF ─────────────────────────────────
        await js("__btn('Executar hipótese').click()")
        ok("executa a hipótese (mínimo de 100 presentes)", await esperar("document.body.innerText.includes('Efeito de cada fator')"))
        txt = await js("document.body.innerText")
        ok("tela mostra 'Avisos sobre este modelo' com a regra de Green",
           "Avisos sobre este modelo" in txt and "Green" in txt)
        ok("coluna 'p < 0,05?' no lugar de 'Confiável?'", "p < 0,05?" in txt and "Confiável?" not in txt)
        ok("sem aviso de formulário alterado logo após executar", "foi alterado depois desta execução" not in txt)
        pdf = await baixar_pdf()
        ok("PDF baixado leva a caixa de avisos", "Avisos sobre este modelo" in pdf and "Green" in pdf)
        ok("PDF sem 'Confiavel?' nem 'efeito comprovado'", "Confiavel?" not in pdf and "efeito comprovado" not in pdf)

        # ── PDF = tela: altera o formulário DEPOIS de executar ───────────────────────
        await js("__set(document.querySelector('aside input[type=number]'), '')")
        await asyncio.sleep(0.6)
        await js("__btn('Executar hipótese').click()")
        await esperar("document.body.innerText.includes('Efeito de cada fator') && !document.body.innerText.includes('Avisos sobre este modelo')", 90)
        ok("sem corte de presentes: some o bloco de avisos",
           "Avisos sobre este modelo" not in await js("document.body.innerText"))
        formula_antes = await js("__formula()")
        await js("__cb('Sexo').click()")  # altera o formulário SEM executar
        await asyncio.sleep(0.8)
        ok("aparece 'o formulário foi alterado depois desta execução'",
           "foi alterado depois desta execução" in await js("document.body.innerText"))
        ok("a fórmula exibida continua a da execução (sem TP_SEXO)",
           await js("__formula()") == formula_antes and "TP_SEXO" not in formula_antes, formula_antes)
        pdf = await baixar_pdf()
        ok("PDF baixado traz a hipótese da TELA, e não a do formulário alterado (sem TP_SEXO)",
           "NT_GER ~" in pdf and "TP_SEXO" not in pdf)

        await js("__btn('Executar hipótese').click()")
        await esperar("document.body.innerText.includes('TP_SEXO')", 90)
        await asyncio.sleep(1)
        ok("depois de executar de novo, o aviso de formulário alterado some",
           "foi alterado depois desta execução" not in await js("document.body.innerText"))

        # ── Rede fora do ar (tem de ser o ÚLTIMO passo) ──────────────────────────────
        await cmd("Network.emulateNetworkConditions", offline=True, latency=0, downloadThroughput=-1, uploadThroughput=-1)
        await js("__btn('Executar hipótese').click()")
        achou = await esperar("document.body.innerText.includes('Não foi possível calcular a hipótese')", 30)
        txt = await js("document.body.innerText")
        ok("rede fora do ar: a tela mostra o erro (não fica em 'Calculando...')", achou)
        ok("a mensagem explica, em português, que não conectou à API",
           "Não foi possível conectar à API do E-XplainENADE" in txt)
        ok("o botão volta ao normal", "Calculando..." not in txt)
        t.cancel()


try:
    asyncio.run(main())
finally:
    proc.terminate()
    time.sleep(1)
    shutil.rmtree(TMP, ignore_errors=True)

falhas = [nome for nome, c in resultados if not c]
print(f"\n{len(resultados) - len(falhas)}/{len(resultados)} verificações OK" + (f"  | FALHARAM: {falhas}" if falhas else ""))
sys.exit(1 if falhas else 0)
