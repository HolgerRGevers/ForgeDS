// WebSocket bridge client — barrel export
export { BridgeClient, bridge } from "./bridge";

// GitHub services
export {
  requestDeviceCode,
  pollForAccessToken,
  fetchCurrentUser,
} from "./github-auth";

export * as githubApi from "./github-api";
