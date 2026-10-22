import { createContext, useContext, useState, type ReactNode } from "react";
import { clearSession, currentUser, saveSession, type User } from "./api";

const Ctx = createContext<{ user: User | null; login: (t: any) => void; logout: () => void }>({
  user: null,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(currentUser());
  const login = (tokens: any) => {
    saveSession(tokens);
    setUser(tokens.user);
  };
  const logout = () => {
    clearSession();
    setUser(null);
  };
  return <Ctx.Provider value={{ user, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

export function canSee(user: User | null, roles: string[]) {
  if (!user) return false;
  return user.is_manager || roles.includes(user.role);
}
