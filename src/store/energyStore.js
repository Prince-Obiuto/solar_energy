import { create } from "zustand";

const useEnergyStore = create((set) => ({

    solar: {

        power: 0,
        voltage: 0,
        current: 0

    },

    battery: {

        percentage: 0,
        voltage: 0,
        charging: false

    },

    inverter: {

        status: "Offline",
        outputPower: 0,
        gridConnected: false

    },

    loads: {

        totalPower: 0,

        zones: []

    },

    updateData: (payload) => set(payload)

}));

export default useEnergyStore;