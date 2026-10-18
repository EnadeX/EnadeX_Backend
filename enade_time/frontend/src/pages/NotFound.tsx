import { Link } from "react-router-dom";
import { Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="card text-center p-8">
      <h2 className="text-2xl font-bold text-academia-900">404</h2>
      <p className="text-sm text-academia-600 mt-2">
        A página solicitada não existe.
      </p>
      <Link to="/" className="btn-primary mt-4 inline-flex">
        <Home className="h-4 w-4 mr-2" aria-hidden />
        Voltar à Visão Geral
      </Link>
    </div>
  );
}
