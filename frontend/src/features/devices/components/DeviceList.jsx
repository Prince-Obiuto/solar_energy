import DeviceCard from "./DeviceCard";

export default function DeviceList({ devices }) {
  return <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{devices.map((device) => <DeviceCard device={device} key={device.id} />)}</div>;
}
