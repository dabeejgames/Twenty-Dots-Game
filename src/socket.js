import { io } from "socket.io-client";

// Use your backend server URL and port
const URL = process.env.NODE_ENV === "production" ? undefined : "http://localhost:4000";
export const socket = io(URL);
