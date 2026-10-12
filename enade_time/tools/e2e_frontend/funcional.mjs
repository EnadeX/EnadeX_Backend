// Verificação funcional do módulo /enade-time no Chrome real: dados na tela, deep link,
// filtros, abas, exportações, alerta de amostra, paginação, benchmark, 404 e responsivo.
// Pré-requisitos: API do ENADE-Time no ar, EnadeX_Frontend em `pnpm start -p 3000`
// (build de produção) e o banco com a campanha oficial 899faa82 (os valores esperados
// de speedup abaixo são os dela).
import fs from 'node:fs'
import { chromium } from 'playwright-core'

import { API, BASE, CHROME, OUT, RUIDO_CONHECIDO, criarVerificador } from './config.mjs'

const { check, encerrar } = criarVerificador()
const logs = []
const alertas = []

const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const ctx = await browser.newContext({ viewport: { width: 1280, height: 640 }, acceptDownloads: true })
const page = await ctx.newPage()
page.on('console', (m) => {
  // "Failed to load resource" não traz a URL: os erros HTTP são conferidos pelo listener de response.
  if (['error', 'warning'].includes(m.type()) && !/Failed to load resource/.test(m.text()))
    logs.push(`[${m.type()}] ${m.text()} @ ${page.url()}`)
})
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message} @ ${page.url()}`))
page.on('response', (r) => {
  if (r.status() >= 400) logs.push(`[http ${r.status()}] ${r.url()}`)
})
page.on('dialog', async (d) => {
  alertas.push(d.message())
  await d.dismiss()
})

const idle = () => page.waitForLoadState('networkidle')
const texto = () => page.locator('body').innerText()
const png = (nome) => `${OUT}/${nome}.png`

// 1) Visão geral
await page.goto(`${BASE}/enade-time`)
await page.getByText('API conectada').waitFor({ timeout: 15000 })
await idle()
let t = await texto()
check('Home: pill "API conectada · v0.2.0"', t.includes('API conectada · v0.2.0'))
check('Home: total de registros 24.967', t.includes('24.967'))
check('Home: melhor speedup exibido (2,70)', /2,70\d\d×/.test(t))
check('Home: exatamente um h1', (await page.locator('h1').count()) === 1)
check(
  'Home: nav principal com aria-current',
  (await page.locator('nav[aria-label="Seções do ENADE-Time"] a[aria-current="page"]').count()) >= 1,
)
await page.screenshot({ path: png('home'), fullPage: true })

// 2) Análises: deep link sobrevive ao reload
await page.goto(`${BASE}/enade-time/enade/anual?nu_ano=2021&co_regiao=2`)
await page.locator('.recharts-surface').first().waitFor({ timeout: 15000 })
await idle()
let ano = await page.locator('label:has-text("Ano") select').inputValue()
let reg = await page.locator('label:has-text("Região") select').inputValue()
check('Deep link: filtros refletidos nos selects', ano === '2021' && reg === '2', `ano=${ano} regiao=${reg}`)
await page.reload()
await page.locator('.recharts-surface').first().waitFor({ timeout: 15000 })
await idle()
ano = await page.locator('label:has-text("Ano") select').inputValue()
check('Deep link sobrevive ao reload', ano === '2021')
check('Anual: gráfico renderizado', (await page.locator('.recharts-surface').count()) >= 1)

// 3) Mudar filtro não rola a página; aplicar atualiza a URL
await page.evaluate(() => window.scrollTo(0, 250))
const y0 = await page.evaluate(() => window.scrollY)
await page.locator('label:has-text("Ano") select').selectOption('2017')
await page.getByRole('button', { name: 'Aplicar' }).click()
await page.waitForURL(/nu_ano=2017/)
await idle()
const y1 = await page.evaluate(() => window.scrollY)
check('Filtro: URL atualizada sem rolar para o topo', y0 > 0 && y1 > 0, `scrollY ${y0} -> ${y1}`)
check('Filtro: URL contém nu_ano=2017 e co_regiao=2', page.url().includes('nu_ano=2017') && page.url().includes('co_regiao=2'))

// 4) Abas preservam a query
await page.getByRole('link', { name: 'Por Região' }).click()
await page.waitForURL(/\/enade\/regional/)
check('Abas preservam filtros ao trocar', page.url().includes('nu_ano=2017'), page.url())
await page.locator('.recharts-bar-rectangle').first().waitFor({ timeout: 15000 })
await page.waitForTimeout(1800) // animação de entrada do Recharts
check(
  'Regional: barras desenhadas + tabela',
  (await page.locator('.recharts-bar-rectangle').count()) >= 1 && (await texto()).includes('Detalhamento por região'),
)
await page.screenshot({ path: png('regional'), fullPage: true })

// 5) UF, IES
await page.goto(`${BASE}/enade-time/enade/uf`)
await page.locator('.recharts-surface').first().waitFor({ timeout: 15000 })
check('UF: gráfico renderizado', true)
await page.goto(`${BASE}/enade-time/enade/ies`)
await page.getByText('Ranking de IES').first().waitFor()
await idle()
check('IES: tabela de ranking', (await page.locator('table tbody tr').count()) > 0)

// 6) Comparar: sem barra de filtros, exportações e alerta de amostra
await page.goto(`${BASE}/enade-time/enade/comparar`)
await page.locator('.recharts-surface').first().waitFor({ timeout: 15000 })
await idle()
check('Comparar: barra de filtros globais oculta', !(await texto()).includes('Cód. IES'))
const svgsNoWrapper = await page.locator('.recharts-wrapper > svg.recharts-surface').count()
check('Comparar: seletor do export casa o <svg> do gráfico', svgsNoWrapper >= 1, `n=${svgsNoWrapper}`)
const baixar = async (rotulo) => {
  const [dl] = await Promise.all([
    page.waitForEvent('download', { timeout: 8000 }),
    page.getByRole('button', { name: rotulo }).click(),
  ])
  return { nome: dl.suggestedFilename(), conteudo: fs.readFileSync(await dl.path(), 'utf8') }
}
const csv = await baixar('Exportar CSV')
check('Export CSV', csv.nome.endsWith('.csv') && csv.conteudo.includes('ano;grupo;media_nt_ger;n_registros'), csv.nome)
const svg = await baixar('Exportar SVG')
check(
  'Export SVG (com eixos e série)',
  svg.nome.endsWith('.svg') && svg.conteudo.includes('<svg') && svg.conteudo.includes('recharts-line'),
  `${svg.nome} ${svg.conteudo.length} bytes`,
)
check('Export SVG sem alerta de falha', alertas.length === 0, alertas.join('|'))
const md = await baixar('Exportar relatório (.md)')
check('Export relatório .md', md.nome.endsWith('.md') && md.conteudo.includes('# Relatório Longitudinal'), md.nome)
await page.screenshot({ path: png('comparar'), fullPage: true })

// 7) AlertaAmostra: achar via API uma UF com n < 30 em algum ano
const ufs = await (await fetch(`${API}/dim/ufs`)).json()
const pequenas = []
for (const u of ufs) {
  const rows = await (await fetch(`${API}/analises/resumo-anual?co_uf=${u.co_uf}`)).json()
  if (rows.some((r) => r.total_registros < 30)) pequenas.push(u)
}
console.log(`  (UFs com algum ano n<30: ${pequenas.map((u) => u.sigla).join(', ') || 'nenhuma'})`)
if (pequenas.length >= 1) {
  await page.locator('label:has-text("Dimensão") select').selectOption('co_uf')
  await page.locator('label:has-text("Grupo A") select').selectOption(String(pequenas[0].co_uf))
  const outro = ufs.find((u) => u.co_uf !== pequenas[0].co_uf)
  await page.locator('label:has-text("Grupo B") select').selectOption(String(outro.co_uf))
  await idle()
  await page.getByText('Amostra reduzida').waitFor({ timeout: 8000 }).catch(() => {})
  check('AlertaAmostra aparece para UF pequena', (await texto()).includes('Amostra reduzida'))
  await page.screenshot({ path: png('alerta-amostra'), fullPage: true })
} else {
  check('AlertaAmostra (nenhuma UF com n<30 nos dados)', true, 'sem caso para exibir')
}

// 8) Registros: paginação e volta para a página 1 ao mudar filtro
await page.goto(`${BASE}/enade-time/enade/registros`)
await page.getByText('Registros (paginados)').waitFor()
await page.getByText('Página 1 /').waitFor({ timeout: 15000 })
await page.getByRole('button', { name: 'Próxima página' }).click()
await page.getByText('Página 2 /').waitFor({ timeout: 15000 })
check('Registros: avança para a página 2', true)
await page.locator('label:has-text("Ano") select').selectOption('2021')
await page.getByRole('button', { name: 'Aplicar' }).click()
await page.waitForURL(/nu_ano=2021/)
await page.getByText('Página 1 /').waitFor({ timeout: 15000 })
check('Registros: volta à página 1 quando o filtro muda', true)

// 9) SPD
await page.goto(`${BASE}/enade-time/spd/comparativo`)
await page.getByText('Interpretação desta').waitFor({ timeout: 15000 })
await idle()
t = await texto()
check('Comparativo: "Melhor configuração: 6 workers · crescente"', t.includes('Melhor configuração: 6 workers · crescente'))
check('Comparativo: mediana de N suítes', /mediana de \d+ suítes/.test(t) || /sobre \d+ suítes/.test(t))
check('Comparativo: fração sequencial estimada (Karp–Flatt)', t.includes('fração sequencial estimada'))
check('Comparativo: condições de medição declaradas', t.includes('Condições de medição') && t.includes('núcleos físicos'))
check('Comparativo: 4 gráficos', (await page.locator('.recharts-surface').count()) >= 4)
await page.waitForTimeout(1800)
await page.screenshot({ path: png('comparativo'), fullPage: true })

await page.goto(`${BASE}/enade-time/spd/execucoes`)
await page.getByText('Execuções de benchmark').waitFor()
await page.locator('table tbody tr').first().waitFor({ timeout: 15000 })
const nExec = await page.locator('table tbody tr').count()
check('Execuções: tabela carregada', nExec > 0, `${nExec} linhas`)
await page.getByRole('link', { name: 'ver etapas' }).first().click()
await page.waitForURL(/\/spd\/etapas\/\d+/)
await page.getByText(/Execução #\d+/).first().waitFor({ timeout: 15000 })
await idle()
check('Etapas: detalhe da execução + gráfico', (await page.locator('.recharts-surface').count()) >= 1)
check('Etapas: abas do SPD ocultas', (await page.locator('nav[aria-label="Benchmark SPD"]').count()) === 0)
await page.goto(`${BASE}/enade-time/spd/metricas`)
await page.locator('table tbody tr').first().waitFor({ timeout: 15000 })
check('Métricas: tabela carregada', (await page.locator('table tbody tr').count()) > 0)

// 10) Sobre e 404 do módulo (o conteúdo do 404 chega por streaming: esperar o texto)
await page.goto(`${BASE}/enade-time/sobre`)
check('Sobre: conteúdo', (await texto()).includes('Metodologia do benchmark'))
const r404 = await page.goto(`${BASE}/enade-time/qualquer-coisa`, { waitUntil: 'commit' })
await page.getByText('A página solicitada não existe no ENADE-Time').waitFor({ timeout: 8000 }).catch(() => {})
check(
  '404 do módulo dentro da casca (status 404)',
  r404.status() === 404 && (await texto()).includes('A página solicitada não existe no ENADE-Time'),
)

// 11) Console limpo (descontado o ruído do layout raiz do grupo e o 404 provocado acima)
const relevantes = logs.filter((l) => ![/qualquer-coisa/i, ...RUIDO_CONHECIDO].some((re) => re.test(l)))
check('Console/rede: sem erros ou avisos relevantes', relevantes.length === 0, relevantes.slice(0, 6).join('\n    '))

// 12) Responsivo: a página não pode ganhar rolagem horizontal
for (const largura of [375, 768, 1280, 1920]) {
  await page.setViewportSize({ width: largura, height: 800 })
  for (const rota of [
    '/enade-time',
    '/enade-time/enade/anual',
    '/enade-time/enade/registros',
    '/enade-time/spd/comparativo',
    '/enade-time/spd/execucoes',
  ]) {
    await page.goto(BASE + rota)
    await page.waitForTimeout(1800)
    const { sw, iw } = await page.evaluate(() => ({
      sw: document.documentElement.scrollWidth,
      iw: window.innerWidth,
    }))
    check(`Responsivo ${largura}px ${rota}: sem rolagem horizontal`, sw <= iw + 1, `scrollWidth=${sw} inner=${iw}`)
  }
}

await browser.close()
encerrar()
