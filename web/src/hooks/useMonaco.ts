import { useMonaco } from "@monaco-editor/react";
import { useEffect } from "react";
import { registerDelugeLanguage } from "../lib/deluge-language";

/**
 * Registers the Deluge language definition and dark theme
 * the first time Monaco becomes available.
 */
export function useDelugeLanguage() {
  const monaco = useMonaco();

  useEffect(() => {
    if (monaco) {
      registerDelugeLanguage(monaco);
    }
  }, [monaco]);
}
