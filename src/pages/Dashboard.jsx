import { useEffect } from "react";

import Layout from "../components/layout/Layout";
import StatCard from "../components/dashboard/StatCard";

import useEnergyStore from "../store/energyStore";
import { generateEnergyData } from "../services/mockData";

export default function Dashboard() {

    const {
        solar,
        battery,
        inverter,
        loads,
        updateData
    } = useEnergyStore();

    useEffect(() => {

        updateData(generateEnergyData());

        const timer = setInterval(() => {
            updateData(generateEnergyData());
        }, 3000);

        return () => clearInterval(timer);

    }, [updateData]);

    return (

        <Layout>

            <div className="grid grid-cols-3 gap-6">

                <StatCard
                    title="Solar Output"
                    value={`${solar.power} kW`}
                />

                <StatCard
                    title="Battery"
                    value={`${battery.percentage}%`}
                />

                <StatCard
                    title="Load"
                    value={`${loads.totalPower} kW`}
                />

                <StatCard
                    title="Inverter"
                    value={inverter.status}
                />

                <StatCard
                    title="Grid"
                    value={inverter.gridConnected ? "Connected" : "Disconnected"}
                />

            </div>

        </Layout>

    );

}