// Página "Por Ano" do módulo /enade-time: indicadores sem agregar nem ordenar edições (saíram "Média NT GER"
// e "Melhor ano") e tabela de estatística descritiva por edição (unidade curso-ano), conferidas contra a API.
// Pré-requisitos: API do ENADE-Time no ar com a rota /analises/descritiva e EnadeX_Frontend em
// `pnpm start -p 3000` (build de produção). Não depende da campanha de benchmark.
import { chromium } from 'playwright-core'

import { API, BASE, CHROME, OUT, RUIDO_CONHECIDO, criarVerificador } from './config.mjs'

const { check, encerrar } = criarVerificador()

const get = async (caminho) => (await fetch(`${API}${caminho}`)).json()
const fmt = (n, d = 2) =>
  n === null || n === undefined ? '—' : n.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })
const NOTAS = { nt_ger: 'NT GER', nt_fg: 'NT FG', nt_ce: 'NT CE' }

/** As células da linha como a tabela deve mostrá-las (n, média, DP, variância, CV, mín, Q1, mediana, Q3, máx). */
const esperadaDaLinha = (e) => [
  fmt(e.n, 0), fmt(e.media), fmt(e.desvio_padrao), fmt(e.variancia), fmt(e.coef_variacao, 1),
  fmt(e.minimo), fmt(e.q1), fmt(e.mediana), fmt(e.q3), fmt(e.maximo),
]

const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage()
const erros = []
page.on('pageerror', (e) => erros.push(e.message))
page.on('response', (r) => r.status() >= 400 && erros.push(`[http ${r.status()}] ${r.url()}`))

const abrir = async (query = '') => {
  await page.goto(`${BASE}/enade-time/enade/anual${query}`)
  await page.getByRole('table').waitFor({ timeout: 20000 })
  await page.waitForLoadState('networkidle')
}
const texto = () => page.locator('body').innerText()
const cartao = (rotulo) => page.getByText(rotulo, { exact: true }).locator('xpath=../..')
const linhasDaTabela = () =>
  page.locator('table tbody tr').evaluateAll((trs) =>
    trs.map((tr) => ({
      ano: tr.querySelector('th')?.textContent,
      celulas: [...tr.querySelectorAll('td')].map((td) => td.textContent),
    })),
  )

// 1) Sem filtros: seis edições
const descritiva = await get('/analises/descritiva')
const resumo = await get('/analises/resumo-anual')
await abrir()
let t = await texto()

check('Indicador "Melhor ano" removido', !t.includes('Melhor ano'))
check('Indicador "Média NT GER" removido (nenhum cartão com esse rótulo)', (await page.locator('main').getByText('Média NT GER', { exact: true }).count()) === 0)
check('Texto "Menor média observada" removido (também ordenava edições)', !t.includes('Menor média observada'))
check('A média simples entre edições (37,14) não aparece', !t.includes('37,14'))

const totalRegistros = resumo.reduce((s, r) => s + r.total_registros, 0)
const totalCursoAno = resumo.reduce((s, r) => s + r.total_cursos, 0)
check('Cartão "Registros (filtro)"', (await cartao('Registros (filtro)').innerText()).includes(fmt(totalRegistros, 0)), fmt(totalRegistros, 0))
check('Cartão "Cursos (curso-ano)"', (await cartao('Cursos (curso-ano)').innerText()).includes(fmt(totalCursoAno, 0)), fmt(totalCursoAno, 0))
check('Cartão "Edições no recorte"', (await cartao('Edições no recorte').innerText()).includes(String(resumo.length)))
const dp = await cartao('Desvio-padrão entre cursos (NT GER)').innerText()
check('Cartão de dispersão: com várias edições diz "Por edição" e remete à tabela', dp.includes('Por edição') && dp.includes('tabela abaixo'), dp.replace(/\n/g, ' | '))

// 2) Tabela descritiva
check(
  'Título "Estatística descritiva por edição (unidade curso-ano)"',
  (await page.getByRole('heading', { name: 'Estatística descritiva por edição (unidade curso-ano)' }).count()) === 1,
)
const cabecalhos = await page.locator('table thead th').evaluateAll((ths) => ths.map((th) => [th.textContent, th.getAttribute('scope')]))
check(
  'Cabeçalhos de coluna (scope=col): Ano, Cursos, Média, DP, Variância, CV (%), Mín, Q1, Mediana, Q3, Máx',
  cabecalhos.map(([c]) => c).join(',') === 'Ano,Cursos,Média,DP,Variância,CV (%),Mín,Q1,Mediana,Q3,Máx' && cabecalhos.every(([, s]) => s === 'col'),
)
const linhas = await linhasDaTabela()
check(`Uma linha por edição (${descritiva.length})`, linhas.length === descritiva.length)
check('Anos são cabeçalhos de linha (th scope=row)', (await page.locator('table tbody th[scope="row"]').count()) === descritiva.length)
for (const nota of Object.keys(NOTAS)) {
  if (nota !== 'nt_ger') await page.getByLabel('Nota').selectOption(nota)
  const obtidas = await linhasDaTabela()
  const iguais = descritiva.every((d, i) => obtidas[i].ano === String(d.nu_ano) && obtidas[i].celulas.join('|') === esperadaDaLinha(d[nota]).join('|'))
  check(`Tabela ${NOTAS[nota]}: valores = API, vírgula decimal, 2 casas e CV com 1`, iguais, obtidas[0]?.celulas.join(' '))
}
await page.getByLabel('Nota').selectOption('nt_ger')
const ger2005 = esperadaDaLinha(descritiva.find((d) => d.nu_ano === 2005).nt_ger).join(' ')
check('Exemplo conferido: NT GER 2005 = 110 33,11 6,93 48,08 20,9 0,99 29,09 33,03 37,87 49,25', ger2005 === '110 33,11 6,93 48,08 20,9 0,99 29,09 33,03 37,87 49,25', ger2005)
t = await texto()
check(
  'Nota de rodapé da tabela',
  t.includes('Medidas calculadas sobre as médias de curso (uma observação por curso-ano). As edições não são diretamente comparáveis; 2005 e 2008 incluem ingressantes.'),
)
await page.screenshot({ path: `${OUT}/anual.png`, fullPage: true })

// 3) Uma única edição: desvio-padrão e média por curso dessa edição
const so2014 = await get('/analises/descritiva?nu_ano=2014')
await abrir('?nu_ano=2014')
const dp1 = await cartao('Desvio-padrão entre cursos (NT GER)').innerText()
check(
  'Edição única: cartão mostra DP e média por curso da edição',
  so2014.length === 1 && dp1.includes(fmt(so2014[0].nt_ger.desvio_padrao)) && dp1.includes(`média por curso ${fmt(so2014[0].nt_ger.media)}`) && dp1.includes('Edição 2014'),
  dp1.replace(/\n/g, ' | '),
)
check('Edição única: a tabela tem 1 linha', (await linhasDaTabela()).length === 1)

// 4) Telas estreitas: a tabela rola dentro da região, focável pelo teclado, sem rolagem na página
await page.setViewportSize({ width: 375, height: 800 })
await abrir()
const medidas = await page.evaluate(() => {
  const regiao = document.querySelector('main [role="region"][aria-label^="Estatística descritiva"]')
  return {
    pagina: document.documentElement.scrollWidth <= window.innerWidth,
    rola: regiao.scrollWidth > regiao.clientWidth,
    focavel: regiao.getAttribute('tabindex') === '0',
  }
})
check('375px: a página não ganha rolagem horizontal', medidas.pagina)
check('375px: a tabela rola na horizontal dentro da região', medidas.rola)
check('Região rolável focável pelo teclado (tabindex=0)', medidas.focavel)
await page.screenshot({ path: `${OUT}/anual-375.png`, fullPage: true })

const relevantes = erros.filter((e) => !RUIDO_CONHECIDO.some((re) => re.test(e)))
check('Sem erros de página nem respostas HTTP >= 400 (descontado o ruído do layout raiz)', relevantes.length === 0, relevantes.slice(0, 5).join(' | '))
await browser.close()
encerrar()
