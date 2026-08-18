"use client";

import { useEffect } from "react";
import { app } from "@microsoft/teams-js";

/** Initialize TeamsJS only when the application is hosted in an iframe. */
export function TeamsInitializer() {
  useEffect(() => {
    if (window.self === window.top) {
      return;
    }

    void app.initialize().catch((error: unknown) => {
      // An iframe outside a supported Microsoft 365 host should not prevent the
      // standalone web application from loading.
      console.warn("Teams SDK initialization was unavailable.", error);
    });
  }, []);

  return null;
}
