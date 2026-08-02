import Card from "../../../components/ui/Card";
import SettingField from "./SettingField";

export default function SettingsPanel({ onChange, section, values }) {
  return <Card className="border border-gray-100 shadow-sm"><h3 className="text-lg font-semibold text-gray-900">{section.label}</h3><p className="mt-1 text-sm text-gray-500">Changes are stored in the local Zustand settings state.</p><div className="mt-6 space-y-4">{section.fields.map((field) => <SettingField field={field} key={field.id} onChange={(value) => onChange(section.id, field.id, value)} value={values[field.id]} />)}</div></Card>;
}
