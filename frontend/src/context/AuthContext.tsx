import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { apiJson, ApiError } from "@/lib/api";

export interface User {
  id: number;
  email: string;
  username: string;
  display_name: string | null;
  form_level?: number | null;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (
    email: string,
    username: string,
    password: string
  ) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

function toMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message;
  return err instanceof Error ? err.message : fallback;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      setUser(await apiJson<User>("/api/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const login = async (identifier: string, password: string) => {
    try {
      const data = await apiJson<{ user: User }>("/api/auth/login", {
        method: "POST",
        body: identifier.includes("@")
          ? { email: identifier, password }
          : { username: identifier, password },
      });
      setUser(data.user);
    } catch (err) {
      throw new Error(toMessage(err, "登入失敗，請稍後再試。"));
    }
  };

  const register = async (
    email: string,
    username: string,
    password: string
  ) => {
    try {
      await apiJson("/api/auth/register", {
        method: "POST",
        body: { email, username, password },
      });
      await login(email, password);
    } catch (err) {
      throw new Error(toMessage(err, "註冊失敗，請稍後再試。"));
    }
  };

  const logout = async () => {
    try {
      await apiJson("/api/auth/logout", { method: "POST" });
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
