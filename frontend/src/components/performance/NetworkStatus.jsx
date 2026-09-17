import { useEffect, useState } from "react";

export function NetworkStatus() {
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);

  useEffect(() => {
    function updateOnline() {
      setOnline(true);
    }

    function updateOffline() {
      setOnline(false);
    }

    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOffline);

    return () => {
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOffline);
    };
  }, []);

  if (online) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 shadow-clinical">
      Network connection lost. Cached data remains visible where available.
    </div>
  );
}
