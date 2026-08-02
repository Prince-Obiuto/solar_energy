import { create } from "zustand";

import { INITIAL_SETTINGS } from "../services/settings.service";

const useSettingsStore = create((set) => ({
  settings: INITIAL_SETTINGS,
  updateSetting: (sectionId, fieldId, value) => set((state) => ({ settings: { ...state.settings, [sectionId]: { ...state.settings[sectionId], [fieldId]: value } } })),
}));

export default useSettingsStore;
