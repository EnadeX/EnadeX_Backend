import AppRoutes from "./routes";
import AppLayout from "./components/layout/AppLayout";

export default function App() {
  return (
    <AppLayout>
      <AppRoutes />
    </AppLayout>
  );
}
