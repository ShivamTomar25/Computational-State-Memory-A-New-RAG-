import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import "./index.css";
import { NetworkStatus } from "./components/performance/NetworkStatus";
import { reportWebVitals } from "./performance/reportWebVitals";
import { queryClient } from "./query/queryClient";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <NetworkStatus />
    </QueryClientProvider>
  </React.StrictMode>,
);

reportWebVitals();
