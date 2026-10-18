export function Footer() {
  return (
    <footer className="border-t border-academia-100 bg-white">
      <div className="max-w-screen-2xl mx-auto px-6 py-4 text-xs text-academia-500 flex flex-col sm:flex-row items-start sm:items-center gap-1 sm:gap-4">
        <span>
          ENADE-Time Distribuído — projeto acadêmico de Sistemas Paralelos e
          Distribuídos
        </span>
        <span className="text-academia-300 hidden sm:inline">·</span>
        <span>Dados: INEP/ENADE 2005–2021 (Norte e Nordeste, Computação)</span>
      </div>
    </footer>
  );
}
