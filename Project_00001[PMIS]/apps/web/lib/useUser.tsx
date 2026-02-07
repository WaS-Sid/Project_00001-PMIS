import React, { createContext, useContext, ReactNode } from "react";
import { getApiClient, UserHeaders } from "./api";

export interface User {
  userId: string;
  name: string;
  roles: string[];
}

interface UserContextType {
  user: User | null;
  setUser: (user: User | null) => void;
  hasRole: (role: string) => boolean;
  headers: UserHeaders | null;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export interface UserProviderProps {
  children: ReactNode;
  defaultUser?: User;
}

export function UserProvider({ children, defaultUser }: UserProviderProps) {
  const [user, setUserState] = React.useState<User | null>(defaultUser || null);

  const setUser = (newUser: User | null) => {
    setUserState(newUser);
    if (newUser) {
      const apiClient = getApiClient();
      apiClient.setUserHeaders({
        "X-User-Id": newUser.userId,
        "X-User-Role": newUser.roles.join(","),
        "X-User-Name": newUser.name,
      });
    }
  };

  const hasRole = (role: string): boolean => {
    return user?.roles.includes(role) || false;
  };

  const headers = user
    ? {
        "X-User-Id": user.userId,
        "X-User-Role": user.roles.join(","),
        "X-User-Name": user.name,
      }
    : null;

  return (
    <UserContext.Provider value={{ user, setUser, hasRole, headers }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser(): UserContextType {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error("useUser must be used within a UserProvider");
  }
  return context;
}
