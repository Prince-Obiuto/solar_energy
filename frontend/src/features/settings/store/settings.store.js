import { create } from "zustand";
import { persist } from "zustand/middleware";

import { INITIAL_SETTINGS } from "../services/settings.service";

const useSettingsStore = create(
  persist(
    (set) => ({
      settings: INITIAL_SETTINGS,
      updateSetting: (sectionId, fieldId, value) => set((state) => ({ settings: { ...state.settings, [sectionId]: { ...state.settings[sectionId], [fieldId]: value } } })),
    }),
    { name: "ems-settings" },
  ),
);

export default useSettingsStore;
