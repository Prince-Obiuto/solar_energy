import Loader from "../ui/Loader";
export default function LoadingState({ message = "Loading dashboard…" }) { return <div className="flex min-h-48 items-center justify-center"><Loader label={message} /></div>; }
