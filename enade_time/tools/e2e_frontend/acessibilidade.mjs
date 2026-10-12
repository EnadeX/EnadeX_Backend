// Acessibilidade do módulo /enade-time: axe-core (WCAG 2.0/2.1 A e AA + boas práticas) em
// todas as páginas e percurso por teclado com checagem de indicador de foco visível.
import fs from 'node:fs'
import { createRequire } from 'node:module'
import { chromium } from 'playwright-core'

import { BASE, CHROME } from './config.mjs'

const require = createRequire(import.meta.url)
const axeSrc = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8')

const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage()

const rotas = [
  '/enade-time',
  '/enade-time/sobre',
  '/enade-time/enade/anual',
  '/enade-time/enade/regional',
  '/enade-time/enade/uf',
  '/enade-time/enade/ies',
  '/enade-time/enade/comparar',
  '/enade-time/enade/registros',
  '/enade-time/spd/comparativo',
  '/enade-time/spd/execucoes',
  '/enade-time/spd/metricas',
  '/enade-time/spd/etapas/1',
]

let violacoes = 0
for (const rota of rotas) {
  await page.goto(BASE + rota)
  await page.waitForTimeout(3500) // dados + animação
  await page.evaluate(axeSrc)
  const res = await page.evaluate(() =>
    window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice'] } }),
  )
  const h1 = await page.locator('h1').count()
  violacoes += res.violations.length + (h1 === 1 ? 0 : 1)
  console.log(`${res.violations.length === 0 && h1 === 1 ? 'OK  ' : 'ATENÇÃO'} ${rota}  (h1=${h1}, violações=${res.violations.length})`)
  for (const v of res.violations) {
    console.log(`     - [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} nós) ex.: ${v.nodes[0].target.join(' ')}`)
  }
}

// Teclado: cada parada de foco precisa ter indicador visível (sombra de anel ou outline).
await page.goto(`${BASE}/enade-time/enade/anual`)
await page.waitForTimeout(3000)
const paradas = []
for (let i = 0; i < 24; i++) {
  await page.keyboard.press('Tab')
  paradas.push(
    await page.evaluate(() => {
      const el = document.activeElement
      if (!el || el === document.body) return null
      const cs = getComputedStyle(el)
      const visivel =
        (cs.boxShadow && cs.boxShadow !== 'none') || (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0)
      const nome = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('placeholder') || '').trim()
      return { tag: el.tagName.toLowerCase(), nome: nome.split('\n')[0].slice(0, 28), visivel }
    }),
  )
}
const reais = paradas.filter(Boolean)
const semFoco = reais.filter((p) => !p.visivel)
console.log(`\nTeclado: ${reais.length} paradas de foco; sem indicador visível: ${semFoco.length}`)
console.log(reais.map((p) => `${p.visivel ? '✓' : '✗'} ${p.tag}:${p.nome}`).join(' | '))

await browser.close()
process.exit(violacoes === 0 && semFoco.length === 0 ? 0 : 1)
