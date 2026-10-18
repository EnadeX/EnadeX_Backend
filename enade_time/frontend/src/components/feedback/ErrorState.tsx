import { AlertCircle, RefreshCw } from "lucide-react";

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="card border-red-200 bg-red-50 p-4">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" aria-hidden />
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-red-800">
            Erro ao carregar dados
          </h4>
          <p className="text-sm text-red-700 mt-1 break-words">{message}</p>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="btn btn-secondary text-red-800 bg-white border border-red-200 hover:bg-red-100"
          >
            <RefreshCw className="h-4 w-4 mr-1" aria-hidden />
            Tentar novamente
          </button>
        )}
      </div>
    </div>
  );
}
