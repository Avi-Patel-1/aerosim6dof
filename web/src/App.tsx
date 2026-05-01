import { useState } from "react";
import { LandingPage } from "./components/LandingPage";
import { Workbench } from "./components/Workbench";
import type { ReplayHandoff } from "./types";

type AppView = "home" | "sim" | "returning";

export default function App() {
  const [view, setView] = useState<AppView>("home");
  const [handoff, setHandoff] = useState<ReplayHandoff | null>(null);

  if (view === "sim") {
    return <Workbench initialHandoff={handoff} onHome={() => setView("returning")} />;
  }

  return (
    <LandingPage
      mode={view === "returning" ? "returning" : "idle"}
      onEnter={(nextHandoff) => {
        setHandoff(nextHandoff ?? null);
        setView("sim");
      }}
      onReturnComplete={() => setView("home")}
    />
  );
}
