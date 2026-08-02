import { useEffect, useRef } from "react";

export default function useInterval(callback, delay) {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (delay === null) {
      return undefined;
    }

    const intervalId = window.setInterval(() => savedCallback.current(), delay);
    return () => window.clearInterval(intervalId);
  }, [delay]);
}
