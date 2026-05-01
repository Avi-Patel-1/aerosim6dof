import { useState } from "react";
import { LandingPage } from "./components/LandingPage";
import { Workbench } from "./components/Workbench";

type AppView = "home" | "sim" | "returning";

export default function App() {
  const [view, setView] = useState<AppView>("home");

  if (view === "sim") {
    return <Workbench onHome={() => setView("returning")} />;
  }

  return (
    <LandingPage
      mode={view === "returning" ? "returning" : "idle"}
      onEnter={() => setView("sim")}
      onReturnComplete={() => setView("home")}
    />
  );
}
