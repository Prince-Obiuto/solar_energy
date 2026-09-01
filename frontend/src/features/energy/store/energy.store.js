import { create } from "zustand";

const initialState = {
  data: null,
  error: null,
  status: "idle",
  connectionStatus: "connecting",
};

const useEnergyStore = create((set) => ({
  ...initialState,
  setLoading: () => set({ status: "loading", error: null }),
  setData: (data) => set({ data, error: null, status: "success" }),
  setError: (error) => set({ error, status: "error" }),
}));

export default useEnergyStore;
