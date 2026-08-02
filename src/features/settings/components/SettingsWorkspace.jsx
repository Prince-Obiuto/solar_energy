import { useState } from "react";

import SectionHeading from "../../../components/ui/SectionHeading";
import { SETTINGS_SECTIONS } from "../services/settings.service";
import useSettingsStore from "../store/settings.store";
import SettingsNav from "./SettingsNav";
import SettingsPanel from "./SettingsPanel";

export default function SettingsWorkspace() {
  const [activeSection, setActiveSection] = useState(SETTINGS_SECTIONS[0].id);
  const { settings, updateSetting } = useSettingsStore();
  const section = SETTINGS_SECTIONS.find((item) => item.id === activeSection);
  return <div className="mx-auto max-w-7xl space-y-6"><SectionHeading eyebrow="Local preferences" title="Settings" /><div className="grid gap-6 lg:grid-cols-[15rem_1fr]"><SettingsNav activeSection={activeSection} onSelect={setActiveSection} sections={SETTINGS_SECTIONS} /><SettingsPanel onChange={updateSetting} section={section} values={settings[section.id]} /></div></div>;
}
